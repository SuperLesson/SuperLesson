import logging
import os
from pathlib import Path

logger = logging.getLogger("superlesson")


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
