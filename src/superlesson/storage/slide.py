import logging
from collections import UserList
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from superlesson.steps.step import Step

from .store import Store
from .utils import seconds_to_timestamp

logger = logging.getLogger("superlesson")


@dataclass
class TimeFrame:
    start: float
    end: float

    def __repr__(self) -> str:
        start = seconds_to_timestamp(self.start)
        end = seconds_to_timestamp(self.end)
        return f"{start} - {end}"


@dataclass
class Slide:
    transcription: str
    timeframe: TimeFrame
    tframe: Path | None = None
    number: int | None = None

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
        return (
            f"====== SLIDE {number} ({self.timeframe}) ======\n\n{self.transcription}"
        )


@dataclass
class Page:
    text: str
    number: int


class Slides(UserList):
    def __init__(self, lesson_root: Path, always_export_txt: bool = False):
        super().__init__()
        self.lesson_root = lesson_root
        self._store = Store(lesson_root)
        self._step_in_memory = None
        self._always_export_txt = always_export_txt

    def merge(self, start: int, end: int):
        if len(self.data) == 0:
            msg = "No slides to merge"
            raise ValueError(msg)

        if (
            start < 0
            or end >= len(self.data)
            or end < start
            or end - start > len(self.data)
        ):
            msg = f"Invalid slide range: {start} - {end}"
            raise ValueError(msg)

        transcription = " ".join(
            [slide.transcription.strip() for slide in self.data[start : end + 1]]
        )
        timeframe = TimeFrame(
            self.data[start].timeframe.start, self.data[end].timeframe.end
        )
        new_slide = Slide(
            transcription,
            timeframe,
            tframe=self.data[start].tframe,
            number=self.data[start].number,
        )
        self.data = self.data[:start] + [new_slide] + self.data[end + 1 :]

    def has_data(self) -> bool:
        return len(self.data) != 0

    def as_pages(self) -> Sequence[Page]:
        return [
            Page(slide.transcription, number)
            for slide in self.data
            if (number := slide.number) and number > 0
        ]

    @staticmethod
    def _load_slide(slide_obj: dict) -> Slide:
        timeframe = slide_obj["timeframe"].values()
        assert len(timeframe) == 2, "Couldn't find timestamps"
        # TODO: remove this before releasing
        tframe_path = slide_obj.get("tframe") or slide_obj.get("png_path")
        if tframe_path is not None:
            tframe_path = Path(tframe_path)
        return Slide(
            slide_obj["transcription"],
            TimeFrame(*timeframe),
            tframe=tframe_path,
            number=slide_obj["number"],
        )

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
        data = self._store.load(meta.filename, load_txt=step > Step.enumerate)
        if data is not None:
            self._load_slides(data, verbose=step is Step.transcribe)
            self._step_in_memory = step
            return True
        return False

    def in_memory(self, step: Step) -> bool:
        logger.debug(f"Step in memory: {self._step_in_memory}")
        return self._step_in_memory is step

    @staticmethod
    def valid_dependencies(step: Step, depends_on: Step) -> Sequence[Step]:
        steps = list(Step)
        last = steps.index(step) - 1
        if depends_on is Step.transcribe:
            return steps[last::-1]

        first = steps.index(depends_on) - 1
        return steps[last:first:-1]

    def load_from_dependencies(self, step: Step, depends_on: Step) -> Step | None:
        """Load data from previous steps.

        Look for valid data from previous steps, from the current until depends_on.

        Args:
            step: The current step
            depends_on: The step to stop loading at. Defaults to None

        Returns:
            The step that was loaded
        """
        for s in self.valid_dependencies(step, depends_on):
            logging.debug(f"Trying to load {s.value.filename}")
            if s.value.in_storage():
                if self.in_memory(s):
                    logger.debug("Using data from memory")
                    return s
                if self.load_step(s):
                    return s

        return None

    def load(self, step: Step, depends_on: Step | None = None) -> Step | None:
        """Load data.

        Checks for data from the current step, if found, it prompts the user if they want to run
        run again or skip.

        Note that running again will discard previous data, including that from subsequent steps
        that run.

        If data from the current step is not found, it tries to load from previous steps.

        Args:
            step: The step to load
            depends_on: The step to stop loading at. Defaults to None.

        Returns:
            The step that was loaded

        Raises:
            Exception: If the step depends on another step that has not been run yet.
        """
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

        # TODO: use a custom exception
        msg = f'Step "{step.value.name}" depends on "{depends_on.value.name}", but "{depends_on.value.name}" has not been run yet.'
        raise Exception(msg)

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
            if step is Step.transcribe:
                return
            if self._always_export_txt or step is Step.improve:
                self._store.save_txt(
                    meta.filename,
                    "\n".join([str(slide) + "\n" for slide in self.data]),
                )
