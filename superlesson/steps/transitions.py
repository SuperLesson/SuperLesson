import datetime
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from superlesson.storage import LessonFile, Slides
from superlesson.storage.slide import TimeFrame
from superlesson.storage.utils import seconds_to_timestamp

from .step import Step, step

logger = logging.getLogger("superlesson")


@dataclass
class TransitionFrame:
    timestamp: float
    path: Path


class Transitions:
    def __init__(self, slides: Slides, transcription_source: LessonFile):
        self._transcription_source = transcription_source
        self.slides = slides

    @step(Step.merge, Step.transcribe)
    def merge_segments(self, using_silences: bool):
        tframes_path = self._transcription_source.path / "tframes"
        try:
            tframes = self._get_transition_frames(tframes_path)
        except FileNotFoundError as e:
            msg = f"Couldn't find transition frames at {tframes_path}"
            raise Exception(msg) from e

        if using_silences:
            references = []
            audio_path = self._transcription_source.extract_audio()
            for threshold_offset in range(-6, -10, -2):
                references = self._detect_silence(audio_path, threshold_offset)
                if len(references) > 0:
                    logger.debug("Found silences: %s", references)
                    break
                logger.debug(
                    "Found no silences with threshold offset %s", threshold_offset
                )
        else:
            references = self._get_period_end_times()

        timestamps = [frame.timestamp for frame in tframes]

        if len(references) != 0:
            improved = self._improve_tts_with_references(timestamps, references, 2.0)
        else:
            logger.warning("No references found, skipping improvement")
            improved = timestamps

        slide_i = 0
        tframe_i = 0
        for time in improved:
            if self.slides.merge(time):
                self.slides[slide_i].tframe = tframes[tframe_i].path
                slide_i += 1
            else:
                logger.warning(
                    f"No slide found for transition {seconds_to_timestamp(time)}"
                )
            tframe_i += 1

        # use this to merge the last slides
        self.slides.merge()

    @staticmethod
    def _get_transition_frames(tframes_dir: Path) -> list[TransitionFrame]:
        def to_timedelta(h, m, s):
            return datetime.timedelta(hours=int(h), minutes=int(m), seconds=int(s))

        tframes = []
        for file in tframes_dir.iterdir():
            match = re.search(r"(\d{2}-\d{2}-\d{2})\.\w+", file.name)
            if match is None:
                logger.warning("Couldn't parse transition time from %s", file.name)
                continue
            timestamp = to_timedelta(*match.group(1).split("-")).total_seconds()
            tframes.append(TransitionFrame(timestamp, file))

        tframes.sort(key=lambda x: x.timestamp)

        logger.debug(
            "Transition times: %s",
            [seconds_to_timestamp(frame.timestamp) for frame in tframes],
        )

        return tframes

    def _get_period_end_times(self) -> list[TimeFrame]:
        punctuation = [".", "?", "!"]

        period_end_times = []
        for slide in self.slides:
            if slide.transcription[-1] in punctuation:
                period_end_times.append(slide.timeframe)

        logger.debug(
            "Period end times: %s",
            period_end_times,
        )
        return period_end_times

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

    @classmethod
    def _improve_tts_with_references(
        cls, timestamps: list[float], references: list[TimeFrame], threshold: float
    ) -> list[float]:
        logger.info("Improving transition times")

        improved = timestamps.copy()

        def format_diff(start, end):
            diff = end - start
            sign = "+" if diff > 0 else "-"
            return f"{sign}{abs(diff):.3f}"

        si = 0
        ti = 0
        while ti < len(timestamps) and si < len(references):
            ref = references[si]
            time = timestamps[ti]
            if ref.start < time < ref.end:
                # long silences shouldn't be a problem
                improved[ti] = ref.end
                ti += 1
            elif ref.end < time:
                # teacher speaks before the slide changes
                if time - ref.end < threshold:
                    improved[ti] = ref.end
                    logger.info(
                        "Replaced transition time %s with %s (%s)",
                        seconds_to_timestamp(time),
                        seconds_to_timestamp(ref.end),
                        format_diff(time, ref.end),
                    )
                    # there probably isn't another timestamp that fits here
                    ti += 1
                si += 1
            elif time < ref.start:
                # teacher silent after the slide changes
                if ref.start - time < threshold:
                    improved[ti] = ref.start
                    logger.info(
                        "Replaced transition time %s with %s (%s)",
                        seconds_to_timestamp(time),
                        seconds_to_timestamp(ref.start),
                        format_diff(time, ref.start),
                    )
                ti += 1

        if improved != timestamps:
            logger.info("Improved transition times")
            logger.debug(
                "%s",
                [seconds_to_timestamp(time) for time in improved],
            )

        return improved
