import pytest
from superlesson.collection import Lesson


@pytest.fixture()
def lesson(tmp_path_factory):
    # we need an mp4 and a pdf
    lesson_root = tmp_path_factory.mktemp("lesson-1")
    lesson_root.joinpath("video.mp4").write_text("video")
    lesson_root.joinpath("presentation.pdf").write_text("slides")

    return Lesson(str(lesson_root))


def test_lesson_root(tmp_path, lesson):
    assert lesson.root == tmp_path / "lesson-1"


def test_discovery(lesson):
    assert lesson.video.name == "video.mp4"
    assert lesson.presentation.name == "presentation.pdf"
    assert len(lesson.files) == 2
