import datetime
import logging
from pathlib import Path

from superlesson.storage import LessonFile, Slides

from .step import Step


logger = logging.getLogger("superlesson")


class Transitions:
    def __init__(self, slides: Slides, transcription_source: LessonFile):
        self._transcription_source = transcription_source
        self.slides = slides

    @Step.step(Step.insert_tmarks, Step.transcribe)
    def insert_tmarks(self):
        # TODO: use audio as source for transcription
        video_path = self._transcription_source.full_path
        audio_path = video_path.with_suffix(".wav")

        png_paths = self._get_png_paths()
        relative_times = self._get_relative_times([path.name for path in png_paths])
        total_seconds = [_time.total_seconds() for _time in relative_times]

        if audio_path.exists():
            logging.warning("Audio file already exists")
        else:
            logging.info(f"Extracting audio to {audio_path}")
            self._extract_audio(video_path, audio_path)

        silences = self._detect_silence(audio_path)

        if len(silences) == 0:
            improved_transition_times = total_seconds
        else:
            improved_transition_times = self._improve_tt(total_seconds, silences, 2.0)

        for i in range(len(improved_transition_times)):
            end = improved_transition_times[i]
            self.slides.merge(end)

        # use this to merge the last slides
        self.slides.merge()

        for i, path in enumerate(png_paths):
            self.slides[i].png_path = path

    def _get_png_paths(self) -> list[Path]:
        tt_directory = self._transcription_source.path / "tframes"
        png_paths = []
        for file in tt_directory.iterdir():
            if file.suffix == ".png":
                png_paths.append(file)

        return png_paths

    def _get_relative_times(self, png_names: list[str]) -> list[datetime.timedelta]:
        import re

        def to_timedelta(h, m, s):
            return datetime.timedelta(hours=int(h), minutes=int(m), seconds=int(s))

        # we have png files in the format XXXXXX.mp4_HH-MM-SS.png
        timestamps = []
        for name in png_names:
            match = re.search(r"_(\d{2}-\d{2}-\d{2})\.png", name)
            assert match is not None
            timestamp = to_timedelta(*match.group(1).split("-"))
            timestamps.append(timestamp)

        return sorted(timestamps)

    # DETECT SILENCE (by far, the slowest step, t= 80 seconds for each hour, rough average)
    # possible alternative: silero-vad, which is already in use by whisper

    # look for differente ways to find silence_thresh programatically.
    # with the code bellow I have to make guesses of threshold_factor
    @staticmethod
    def _detect_silence(audio_file, silence_threshold_factor=10):
        from pydub import AudioSegment, silence

        audio = AudioSegment.from_wav(audio_file)
        silence_thresh = audio.dBFS - silence_threshold_factor
        silences = silence.detect_silence(
            audio, min_silence_len=800, silence_thresh=silence_thresh, seek_step=1
        )
        silences = [
            ((start / 1000), (stop / 1000)) for start, stop in silences
        ]  # convert to seconds
        return silences

    @Step.step(Step.verify_tbreaks_with_mpv, Step.insert_tmarks)
    def verify_tbreaks_with_mpv(self):
        # TODO: parameterize time translation
        time_translation = 6
        relative_times = list(
            filter(
                lambda x: x < 0,
                [
                    slide.timeframe.start.total_seconds() - time_translation
                    for slide in self.slides
                ],
            )
        )

        play_duration = 12
        self._play_video_at_times(relative_times, play_duration)

    def _play_video_at_times(self, times, duration):
        import mpv
        from time import sleep

        player = mpv.MPV()
        player.play(str(self._transcription_source.full_path))
        player.wait_until_playing()
        for _time in times:
            logger.debug(f"Playing video at time {_time}")
            player.seek(_time, reference="absolute", precision="exact")
            sleep(duration)

    # EXTRACT AUDIO (t= 7 sec for each hour, rough average)
    @staticmethod
    def _extract_audio(
        input_file, output_file, audio_codec="pcm_s16le", channels=1, sample_rate=16000
    ):
        import subprocess

        command = f"ffmpeg -loglevel quiet -i {input_file} -vn -acodec {audio_codec} -ac {channels} -ar {sample_rate} {output_file}"
        subprocess.call(command, shell=True, stdout=subprocess.DEVNULL)

    # TRY TO FIND NEAREST SILENCE. IF IT CAN`T FIND, GO BACK TO THE ORIGINAL TT
    @staticmethod
    def _nearest(l, K):
        return sorted(l, key=lambda i: abs(i - K))[0]

    @staticmethod
    def _convert_seconds(seconds):
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        # Split seconds into whole seconds and milliseconds
        seconds, milliseconds = divmod(seconds, 1)
        return "%02d:%02d:%02d.%03d" % (hours, minutes, seconds, milliseconds * 1000)

    @classmethod
    def _improve_tt(cls, times, silences, threshold):
        logger.info("Improving transition times")
        improved_transition_times = []
        for _time in times:
            silence_begin = cls._nearest([silence[0] for silence in silences], _time)
            silence_end = cls._nearest([silence[1] for silence in silences], _time)

            if silence_begin < silence_end:
                if not silence_begin < _time < silence_end:
                    improved_transition_times.append(silence_begin)
                else:
                    improved_transition_times.append(_time)
            # teacher speaks before the slide changes
            elif silence_end < _time and _time - silence_end < threshold:
                improved_transition_times.append(silence_end)
            # teacher silent after the slide changes
            elif silence_begin > _time and silence_begin - _time < threshold:
                improved_transition_times.append(silence_begin)
            else:
                improved_transition_times.append(_time)

        return improved_transition_times
