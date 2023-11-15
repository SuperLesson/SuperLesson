import logging
from datetime import timedelta
from pathlib import Path
from textwrap import fill

logger = logging.getLogger("superlesson")


def format_transcription(text: str) -> str:
    lines = text.splitlines()
    formatted = []
    for line in lines:
        if line == "":
            if len(formatted) and formatted[-1] != "\n\n":
                formatted.append("\n\n")
        else:
            formatted.append(fill(line, width=120, tabsize=4))
    if not len(formatted):
        return ""

    if formatted[-1] == "\n\n":
        return "".join(formatted[:-1])

    return "".join(formatted)


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
