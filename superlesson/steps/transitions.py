import datetime
import logging
from pathlib import Path

from superlesson.storage import LessonFile, Slides
from superlesson.storage.slide import TimeFrame
from superlesson.storage.utils import seconds_to_timestamp

from .step import Step


logger = logging.getLogger("superlesson")


class Transitions:
    def __init__(self, slides: Slides, transcription_source: LessonFile):
        self._transcription_source = transcription_source
        self.slides = slides

    @Step.step(Step.merge_segments, Step.transcribe)
    def merge_segments(self):
        # TODO: use audio as source for transcription
        video_path = self._transcription_source.full_path
        audio_path = video_path.with_suffix(".wav")

        png_paths = self._get_png_paths()
        timestamps = self._get_ttimes_from_tframes([path.name for path in png_paths])

        if audio_path.exists():
            logger.warning("Audio file already exists")
        else:
            logger.info(f"Extracting audio to {audio_path}")
            self._extract_audio(video_path, audio_path)

        silences = []
        for threshold_offset in range(-6, -10, -2):
            silences = self._detect_silence(audio_path, threshold_offset)
            if len(silences) > 0:
                logger.debug("Found silences: %s", silences)
                break
            logger.debug("Found no silences with threshold offset %s", threshold_offset)

        if len(silences) != 0:
            improved = self._improve_tts_with_silences(timestamps, silences, 2.0)
        else:
            logger.debug("Found no silences")
            improved = timestamps

        for time in improved:
            self.slides.merge(time)

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

    def _get_ttimes_from_tframes(self, png_names: list[str]) -> list[float]:
        import re

        def to_timedelta(h, m, s):
            return datetime.timedelta(hours=int(h), minutes=int(m), seconds=int(s))

        # we have png files in the format XXXXXX.mp4_HH-MM-SS.png
        timestamps = []
        for name in png_names:
            match = re.search(r"_(\d{2}-\d{2}-\d{2})\.png", name)
            assert match is not None
            timestamp = to_timedelta(*match.group(1).split("-")).total_seconds()
            timestamps.append(timestamp)

        timestamps.sort()

        logger.debug(
            "Transition times: %s", [seconds_to_timestamp(time) for time in timestamps]
        )

        return timestamps

    # DETECT SILENCE (by far, the slowest step, t= 80 seconds for each hour, rough average)
    # possible alternative: silero-vad, which is already in use by whisper

    # look for differente ways to find silence_thresh programatically.
    # with the code bellow I have to make guesses of threshold_factor
    @staticmethod
    def _detect_silence(audio_file: Path, threshold_offset: int) -> list[TimeFrame]:
        logger.info("Detecting silence")

        import pydub

        audio = pydub.AudioSegment.from_wav(audio_file)
        logger.debug("Audio duration: %s", seconds_to_timestamp(audio.duration_seconds))

        silence_thresh = audio.dBFS + threshold_offset
        logger.info("Looking for silences using threshold %s", silence_thresh)

        silences = pydub.silence.detect_silence(
            audio,
            min_silence_len=800,
            silence_thresh=silence_thresh,
            seek_step=1,
        )
        silences = [
            TimeFrame((start / 1000), (stop / 1000)) for start, stop in silences
        ]  # convert to seconds
        return silences

    @Step.step(Step.verify_tbreaks_with_mpv, Step.merge_segments)
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

    @classmethod
    def _improve_tts_with_silences(
        cls,
        timestamps: list[float],
        silences: list[TimeFrame],
        threshold: float,
    ) -> list[float]:
        logger.info("Improving transition times")

        improved = timestamps.copy()

        def format_diff(start, end):
            diff = end - start
            sign = "+" if diff > 0 else "-"
            return f"{sign}{abs(diff):.3f}"

        si = 0
        ti = 0
        while ti < len(timestamps) and si < len(silences):
            silence = silences[si]
            time = timestamps[ti]
            if silence.start < time < silence.end:
                ti += 1
            elif silence.end < time:
                # teacher speaks before the slide changes
                if time - silence.end < threshold:
                    improved[ti] = silence.end
                    logger.debug(
                        "Replaced transition time %s with %s (%s)",
                        seconds_to_timestamp(time),
                        seconds_to_timestamp(silence.end),
                        format_diff(time, silence.end),
                    )
                    # there probably isn't another timestamp that fits here
                    ti += 1
                si += 1
            elif time < silence.start:
                # teacher silent after the slide changes
                if silence.start - time < threshold:
                    improved[ti] = silence.start
                    logger.debug(
                        "Replaced transition time %s with %s (%s)",
                        seconds_to_timestamp(time),
                        seconds_to_timestamp(silence.start),
                        format_diff(time, silence.start),
                    )
                ti += 1

        if improved != timestamps:
            logger.info("Improved transition times")
            logger.debug(
                "%s",
                [seconds_to_timestamp(time) for time in improved],
            )

        return improved
