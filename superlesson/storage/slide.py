import logging
from collections import UserList, namedtuple
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent, fill
from typing import Any, Optional

from superlesson.steps.step import Step

from .store import Loaded, Store
from .utils import timeframe_to_timestamp

logger = logging.getLogger("superlesson")


TimeFrame = namedtuple("TimeFrame", ["start", "end"])


@dataclass
class Slide:
    transcription: str
    timeframe: TimeFrame
    png_path: Optional[Path] = None
    number: Optional[int] = None
    merged: bool = False

    def to_dict(self):
        return {
            "transcription": self.transcription,
            "timeframe": {
                "start": self.timeframe.start,
                "end": self.timeframe.end,
            },
            "png_path": str(self.png_path),
            "number": self.number,
        }

    def __repr__(self):
        return f"====== SLIDE {self.number} ({timeframe_to_timestamp(self.timeframe)}) ======\n{fill(self.transcription, width=120)}"


class Slides(UserList):
    def __init__(self, lesson_root: Path, always_export_txt: bool = False):
        super().__init__()
        self.lesson_root = lesson_root
        self._store = Store(lesson_root)
        self._last_state = None
        self._always_export_txt = always_export_txt

    def merge(self, end: Optional[float] = None):
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
            logger.debug(
                dedent(
                    f"""Can't merge slide {first} with itself:
                    First matched: {timeframe_to_timestamp(self.data[first].timeframe)}
                    Last matched: {timeframe_to_timestamp(self.data[last].timeframe)}"""
                )
            )
            return

        if not logger.isEnabledFor(logging.DEBUG):
            logger.info(f"Merging slides {first} until {last}")
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

    def has_data(self) -> bool:
        return len(self.data) != 0

    @staticmethod
    def _load_slide(slide_obj: dict) -> Slide:
        timeframe = slide_obj["timeframe"].values()
        assert len(timeframe) == 2, "Couldn't find timestamps"
        png_path = slide_obj["png_path"]
        if png_path is not None:
            png_path = Path(png_path)
        slide = Slide(
            slide_obj["transcription"],
            TimeFrame(*timeframe),
            png_path=png_path,
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

    def load(self, step: Step, depends_on: Step, prompt: bool = True) -> Loaded:
        if self._last_state is Loaded.in_memory and self.has_data():
            logger.debug("Data already loaded")
            return Loaded.in_memory
        loaded, obj = self._store.load(step, depends_on, prompt)
        if loaded is Loaded.none:
            logger.debug("No data to load")
            return Loaded.none
        assert obj is not None, "Slides object should be populated"
        self._load_slides(obj, step is not Step.transcribe)
        self._last_state = loaded
        return loaded

    def save_temp_txt(self) -> Path:
        return self._store.temp_save(
            "\n".join([str(slide) + "\n" for slide in self.data])
        )

    def save(self, step: Step):
        self._last_state = Loaded.in_memory
        if self._store.in_storage(step):
            self._store.save_json(step, [slide.to_dict() for slide in self.data])
            if step is Step.transcribe:
                return
            if self._always_export_txt or step is Step.improve:
                self._store.save_txt(
                    step, "\n".join([repr(slide) + "\n" for slide in self.data])
                )
