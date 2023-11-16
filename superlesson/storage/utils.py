import logging
from datetime import timedelta
from pathlib import Path
from textwrap import fill
import re

logger = logging.getLogger("superlesson")


def format_transcription(text: str) -> str:
    lines = text.splitlines()
    paragraphs = []
    current_para = []
    for line in lines:
        if line == "":
            if current_para:
                paragraphs.append(current_para)
                current_para = []
        else:
            line = re.sub(r"\s+", " ", line)
            current_para.append(line)

    if current_para:
        paragraphs.append(current_para)

    return "\n\n".join(
        [fill(" ".join(para), width=120, tabsize=4) for para in paragraphs]
    )


def seconds_to_timestamp(s: float) -> str:
    timestamp = str(timedelta(seconds=s))
    if "." in timestamp:
        timestamp = timestamp[:-3]
    return timestamp


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
