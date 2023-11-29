import logging
import re
from datetime import timedelta
from pathlib import Path
from sys import argv
from typing import Any

from superlesson.steps import Annotate, Transitions
from superlesson.steps.step import Step
from superlesson.storage import LessonFiles, Slides
from superlesson.storage.utils import seconds_to_timestamp

logging.basicConfig(
    format="%(asctime)s.%(msecs)03d - %(name)s:%(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
    level=logging.WARNING,
)
logger = logging.getLogger("superlesson")


def parse_old_format(txt_path: Path) -> list[dict[str, Any]]:
    txt = txt_path.read_text()

    # ==== xxxx tt=HH:MM:SS xxxxx
    segments = re.split(r"====.*tt=(\d{2}:\d{2}:\d{2}).*\n", txt)

    if segments[0] == "":
        segments = segments[1:]

    assert len(segments) % 2 == 0, "Invalid number of segments"

    def to_timedelta(h, m, s):
        return timedelta(hours=int(h), minutes=int(m), seconds=int(s))

    times = [to_timedelta(*segment.split(":")) for segment in segments[::2]]
    return [
        {
            "transcription": transcription,
            "timeframe": {
                "start": 0,
                "end": 0,
            },
            "timestamp": _time.total_seconds(),
            "tframe": None,
            "number": None,
        }
        for transcription, _time in zip(segments[1::2], times, strict=True)
    ]


def nearest(tframes, timestamp):
    return min(tframes, key=lambda x: abs(x.timestamp - timestamp))


def main():
    logger.setLevel(logging.INFO)

    lesson = argv[1]
    lesson_files = LessonFiles(lesson)
    lesson_root = lesson_files.lesson_root

    txt_path = lesson_root / "old.txt"

    if not txt_path.exists():
        raise Exception(f"File {txt_path} doesn't exist")

    logger.debug("Found old source")

    data = parse_old_format(txt_path)
    tframes = Transitions._get_transition_frames(lesson_root / "tframes")

    if tframes[0].timestamp > timedelta(hours=21).total_seconds():
        for tframe in tframes:
            tframe.timestamp -= timedelta(hours=21).total_seconds()

    for i, obj in enumerate(data[1:]):
        improved = obj["timestamp"]
        tframe = nearest(tframes, improved)
        logger.debug(
            f"Slide {i}: found tframe for {seconds_to_timestamp(tframe.timestamp)}"
        )
        if abs(tframe.timestamp - improved) > 2.0:
            logger.warning(
                f"Difference between {tframe.timestamp} and {improved} is too big"
            )
        data[i]["tframe"] = tframe.path

    slides = Slides(lesson_root, True)
    slides._load_slides(data)
    slides.save(Step.merge)

    annotate = Annotate(slides, lesson_files.presentation)
    annotate.enumerate_slides_from_tframes()
    annotate.to_pdf()


if __name__ == "__main__":
    main()
