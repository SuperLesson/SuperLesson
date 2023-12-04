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

        if tframes:
            improved = self._improve_transitions(
                [frame.timestamp for frame in tframes], using_silences
            )

            start = 0
            for tframe, time in zip(tframes, improved, strict=True):
                end = next(
                    (
                        i
                        for i, slide in enumerate(self.slides)
                        if (end_time := slide.timeframe).end >= time
                    ),
                    len(self.slides),
                )

                logger.debug(
                    f"Found segment {end + 1} with timeframe {end_time} >= {seconds_to_timestamp(time)}"
                )

                logger.info(f"Merging {end - start} words into slide {start + 1}")
                try:
                    self.slides.merge(start, end)
                    self.slides[start].tframe = tframe.path
                    start += 1
                except ValueError as e:
                    logger.warning(e)

                    logger.warning(
                        f"No transcription available between {self.slides[start].timeframe.start} and {seconds_to_timestamp(time)}"
                    )
                    logger.warning(f"Skipping tframe {tframe.path}")

            self.slides.merge(start, len(self.slides) - 1)
        else:
            logger.warning("No transition frames found, merging all slides")
            self.slides.merge(0, len(self.slides) - 1)

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

    def _improve_transitions(
        self, timestamps: list[float], using_silences: bool, threshold: float = 3.0
    ) -> list[float]:
        references = (
            self._find_silence_references()
            if using_silences
            else self._get_period_end_times()
        )

        if not references:
            logger.warning("No references found, skipping improvement")
            return timestamps

        logger.info("Improving transition times")

        improved = timestamps.copy()

        def log(before, after):
            diff = after - before
            sign = "+" if diff > 0 else "-"
            logger.info(
                "Replaced transition time %s with %s (%s)",
                seconds_to_timestamp(before),
                seconds_to_timestamp(after),
                f"{sign}{abs(diff):.3f}",
            )

        si = 0
        for ti, time in enumerate(timestamps):
            while si < len(references) and references[si].end < time:
                si += 1
            if si < len(references):
                ref = references[si]
                if ref.start <= time <= ref.end:
                    # long silences shouldn't be a problem
                    improved[ti] = ref.end
                    log(time, ref.end)
                elif time < ref.start and abs(timestamps[ti] - ref.start) < threshold:
                    improved[ti] = ref.start
                    log(time, ref.start)

        if improved != timestamps:
            logger.info("Improved transition times")
            logger.debug("%s", [seconds_to_timestamp(time) for time in improved])

        return improved

    def _find_silence_references(self) -> list[TimeFrame]:
        import pydub

        audio_path = self._transcription_source.extract_audio()
        audio = pydub.AudioSegment.from_wav(audio_path)
        logger.debug("Audio duration: %s", seconds_to_timestamp(audio.duration_seconds))

        silences = []
        for threshold_offset in range(-6, -10, -2):
            silence_thresh = audio.dBFS + threshold_offset
            logger.info("Looking for silences using threshold %s", silence_thresh)
            silences = pydub.silence.detect_silence(
                audio,
                min_silence_len=800,
                silence_thresh=silence_thresh,
                seek_step=1,
            )
            if len(silences) > 0:
                logger.debug("Found silences: %s", silences)
                break
            logger.debug("Found no silences with threshold offset %s", threshold_offset)
        return [TimeFrame((start / 1000), (end / 1000)) for start, end in silences]

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