import logging
from datetime import timedelta
from pathlib import Path

logger = logging.getLogger("superlesson")


def seconds_to_timestamp(s: float) -> str:
    timestamp = str(timedelta(seconds=s))
    if "." in timestamp:
        timestamp = timestamp[:-3]
    return timestamp


def timeframe_to_timestamp(timeframe: tuple[float, float]) -> str:
    start = seconds_to_timestamp(timeframe[0])
    end = seconds_to_timestamp(timeframe[1])
    return f"{start} - {end}"


def find_lesson_root(lesson: str) -> Path:
    lesson_root = Path(lesson)
    if not lesson_root.exists():
        src_path = Path(__file__).parent
        lesson_root = src_path / "../../lessons" / lesson
        lesson_root = lesson_root.resolve()

        if not lesson_root.exists():
            raise ValueError(f"Lesson {lesson} not found")

    logger.debug(f"Found lesson root: {lesson_root}")
    return lesson_root
