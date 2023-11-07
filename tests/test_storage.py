import pytest

from src.storage import LessonFiles


def lesson_files(tmp_path_factory):
    # we need an mp4 and a pdf
    lesson_root = tmp_path_factory.mktemp("lesson-1")
    lesson_root.joinpath("video.mp4").write_text("video")
    lesson_root.joinpath("presentation.pdf").write_text("slides")

    return LessonFiles(str(lesson_root))


def test_lesson_root(tmp_path, lesson_files):
    lesson_root = tmp_path / "lesson-1"
    assert lesson_files.lesson_root == str(lesson_root)


def test_discovery(lesson_files):
    assert len(lesson_files.files) == 2


def test_transcription_source(lesson_files):
    assert lesson_files.transcription_source.name == "lesson-1.mp4"


def test_notes_file(lesson_files):
    assert lesson_files.presentation.name == "lesson-1.pdf"
