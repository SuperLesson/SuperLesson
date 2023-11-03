import logging
from collections.abc import Sequence
from collections import UserList, namedtuple
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent, fill
from typing import Any, Optional

from superlesson.steps.step import Step

from .store import Store
from .utils import format_transcription, timeframe_to_timestamp

logger = logging.getLogger("superlesson")


TimeFrame = namedtuple("TimeFrame", ["start", "end"])


@dataclass
class Slide:
    transcription: str
    timeframe: TimeFrame
    tframe: Optional[Path] = None
    number: Optional[int] = None
    merged: bool = False

    def to_dict(self):
        return {
            "transcription": self.transcription,
            "timeframe": {
                "start": self.timeframe.start,
                "end": self.timeframe.end,
            },
            "tframe": str(self.tframe),
            "number": self.number,
        }

    def __str__(self):
        if self.number is None:
            number = "##"
        elif self.number == -1:
            number = "hidden"
        else:
            number = self.number + 1
        return f"====== SLIDE {number} ({timeframe_to_timestamp(self.timeframe)}) ======\n{format_transcription(self.transcription)}"


class Slides(UserList):
    def __init__(self, lesson_root: Path, always_export_txt: bool = False):
        super().__init__()
        self.lesson_root = lesson_root
        self._store = Store(lesson_root)
        self._step_in_memory = None
        self._always_export_txt = always_export_txt

    def merge(self, end: Optional[float] = None) -> bool:
        if len(self.data) == 0:
            raise ValueError("No slides to merge")

        first = 0
        for i in range(len(self.data)):
            slide = self.data[i]
            if not slide.merged:
                first = i
                break

        last = len(self.data) - 1
        if end is not None:
            for i in range(len(self.data)):
                slide = self.data[i]
                if slide.timeframe.end >= end:
                    last = i
                    break
        else:
            end = self.data[last].timeframe.end

        if first == last:
            logger.warning(
                dedent(
                    f"""Can't merge slide {first} with itself:
                    First matched: {timeframe_to_timestamp(self.data[first].timeframe)}
                    Last matched: {timeframe_to_timestamp(self.data[last].timeframe)}"""
                )
            )
            return False

        if not logger.isEnabledFor(logging.DEBUG):
            logger.info(f"Merging slides {first + 1} until {last + 1}")
        else:
            logger.debug(
                dedent(
                    f"""Merging slides {first} until {last}:
                    First matched: {timeframe_to_timestamp(self.data[first].timeframe)}
                    Last matched: {timeframe_to_timestamp(self.data[last].timeframe)}"""
                )
            )

        transcription = " ".join(
            [slide.transcription.strip() for slide in self.data[first : last + 1]]
        )
        assert end is not None
        if first > 0:
            start = self.data[first - 1].timeframe.end
        else:
            start = self.data[0].timeframe.start
        new_slide = Slide(transcription, TimeFrame(start, end))
        new_slide.merged = True
        self.data = self.data[:first] + [new_slide] + self.data[last + 1 :]
        return True

    def has_data(self) -> bool:
        return len(self.data) != 0

    @staticmethod
    def _load_slide(slide_obj: dict) -> Slide:
        timeframe = slide_obj["timeframe"].values()
        assert len(timeframe) == 2, "Couldn't find timestamps"
        # TODO: remove this before releasing
        tframe_path = slide_obj.get("tframe") or slide_obj.get("png_path")
        if tframe_path is not None:
            tframe_path = Path(tframe_path)
        slide = Slide(
            slide_obj["transcription"],
            TimeFrame(*timeframe),
            tframe=tframe_path,
            number=slide_obj["number"],
        )
        return slide

    def _load_slides(self, data: list[Any], verbose: bool = False):
        slides: list[Slide] = []
        for obj in data:
            slide = self._load_slide(obj)
            # HACK: loading from transcribe will show too many segments so let's just skip those
            if verbose:
                logger.debug("Loaded slide: %s", repr(slide))
            slides.append(slide)

        if not verbose:
            logger.debug("Loaded raw transcription")
        self.data = slides

    def load_step(self, step: Step) -> bool:
        meta = step.value
        assert meta.filename is not None
        logger.debug(f"Loading data from step {step.value.name}")
        verbose = step is not Step.transcribe
        data = self._store.load(meta.filename, verbose)
        if data is not None:
            self._load_slides(data, verbose)
            self._step_in_memory = step
            return True
        return False

    def in_memory(self, step: Step) -> bool:
        logger.debug(f"Step in memory: {self._step_in_memory}")
        return self._step_in_memory is step

    @staticmethod
    def valid_dependencies(step: Step, depends_on: Step) -> Sequence[Step]:
        steps = Step.to_list()
        last = steps.index(step) - 1
        if depends_on is Step.transcribe:
            return steps[last::-1]
        else:
            first = steps.index(depends_on) - 1
            return steps[last:first:-1]

    def load_from_dependencies(self, step: Step, depends_on: Step) -> Optional[Step]:
        for s in self.valid_dependencies(step, depends_on):
            logging.debug(f"Trying to load {s.value.filename}")
            if s.value.in_storage():
                if self.in_memory(s):
                    logger.debug("Using data from memory")
                    return s
                if self.load_step(s):
                    return s

    def load(self, step: Step, depends_on: Optional[Step] = None) -> Optional[Step]:
        if step.value.in_storage() and self.load_step(step):
            if (
                input(
                    f'"{step.value.name}" has already been run. Run again? [y/N] '
                ).lower()
                != "y"
            ):
                return step

            if depends_on is None:
                return None

        if depends_on is None:
            return None

        loaded = self.load_from_dependencies(step, depends_on)
        if loaded is not None:
            return loaded

        raise Exception(
            f'Step "{step.value.name}" depends on "{depends_on.value.name}", but "{depends_on.value.name}" has not been run yet.'
        )

    def save_temp_txt(self) -> Path:
        return self._store.temp_save(
            "\n".join([str(slide) + "\n" for slide in self.data])
        )

    def save(self, step: Step):
        self._step_in_memory = step
        meta = step.value
        if meta.in_storage():
            assert meta.filename is not None
            self._store.save_json(
                meta.filename, [slide.to_dict() for slide in self.data]
            )
            if meta is Step.transcribe:
                return
            if self._always_export_txt or meta is Step.improve:
                self._store.save_txt(
                    meta.filename,
                    "\n".join([str(slide) + "\n" for slide in self.data]),
                )
