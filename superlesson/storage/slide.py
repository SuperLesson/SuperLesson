import logging
from collections import UserList
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from textwrap import dedent, fill
from typing import List, Optional, Tuple

from superlesson.steps.step import Step

from .store import Loaded, Store


@dataclass
class TimeFrame:
    start: timedelta
    end: timedelta

    def __init__(self, start: float, end: float):
        self.start = timedelta(seconds=start)
        self.end = timedelta(seconds=end)

    def to_dict(self):
        return {
            "start": self.start.total_seconds(),
            "end": self.end.total_seconds(),
        }

    @staticmethod
    def _repr_time(time: timedelta) -> str:
        return str(time).split(".")[0]

    def __repr__(self):
        return f"{self._repr_time(self.start)} - {self._repr_time(self.end)}"


@dataclass
class Slide:
    transcription: str
    timeframe: TimeFrame
    png_path: Optional[Path] = None
    number: Optional[int] = None
    merged: bool = False

    def __init__(self, transcription: str, timeframe: Tuple[float, float]):
        self.transcription = transcription
        self.timeframe = TimeFrame(*timeframe)

    def to_dict(self):
        return {
            "transcription": self.transcription,
            "timeframe": self.timeframe.to_dict(),
            "png_path": str(self.png_path),
            "number": self.number,
        }

    def __repr__(self):
        return f"====== SLIDE {self.number} ({self.timeframe}) ======\n{fill(self.transcription, width=120)}"


class Slides(UserList):
    def __init__(self, lesson_root: Path, run_all: bool):
        super().__init__()
        self.lesson_root = lesson_root
        self._store = Store(lesson_root, run_all)
        self._last_state = None

    @staticmethod
    def _load_slide(slide_obj: dict) -> Slide:
        start, end = slide_obj["timeframe"]["start"], slide_obj["timeframe"]["end"]
        assert isinstance(start, float), "Couldn't find timestamps"
        start, end = float(start), float(end)
        slide = Slide(slide_obj["transcription"], (start, end))
        png_path = slide_obj["png_path"]
        if png_path is not None:
            slide.png_path = Path(png_path)
        if slide_obj["number"] is not None:
            slide.number = slide_obj["number"]
        return slide

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
                if slide.timeframe.end.total_seconds() >= end:
                    if i != 0:
                        last = i - 1
                    else:
                        last = i
                    break
        else:
            end = self.data[last].timeframe.end.total_seconds()

        if first == last:
            logging.debug(dedent(f"""
                Can't merge slide {first} with itself:
                    First matched: {self.data[first].timeframe}
                    Last matched: {self.data[last].timeframe}
                """))
            return

        logging.info(f"Merging slides {first} until {last}")
        logging.debug(dedent(f"""
                First matched: {self.data[first].timeframe}
                Last matched: {self.data[last].timeframe}
            """))

        transcription = "\n".join([
            slide.transcription for slide in self.data[first:last + 1]
        ])
        assert end is not None
        start = self.data[first - 1].timeframe.end.total_seconds()
        new_slide = Slide(transcription, (start, end))
        new_slide.merged = True
        self.data = self.data[:first] + [new_slide] + self.data[last + 1:]

    def has_data(self) -> bool:
        return len(self.data) != 0

    def load(self, step: Step, depends_on: Step) -> Loaded:
        if (self._last_state is Loaded.in_memory
                and self.has_data()):
            logging.debug("Data already loaded")
            return Loaded.in_memory
        loaded, obj = self._store.load(step, depends_on)
        if loaded is Loaded.none:
            logging.debug("No data to load")
            return Loaded.none
        assert obj is not None, "Slides object should be populated"
        data: List[Slide] = []
        for i in range(len(obj)):
            data.append(self._load_slide(obj[i]))
        self.data = data
        self._last_state = loaded
        return loaded

    def save(self, step: Step):
        self._last_state = Loaded.in_memory
        if self._store.in_storage(step):
            self._store.save_json(step, [
                slide.to_dict() for slide in self.data
            ])
            self._store.save_txt(step, "\n".join([
                str(slide) + '\n' for slide in self.data
            ]))
