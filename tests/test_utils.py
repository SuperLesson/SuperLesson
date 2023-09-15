import pytest

from src.utils import LessonFiles


class TestLessonFiles:
    @pytest.fixture(scope='class')
    def lesson_files(self, tmp_path_factory):
        # we need an mp4 and a pdf
        lesson_root = tmp_path_factory.mktemp('lesson-1')
        lesson_root.joinpath('lesson-1.mp4').write_text('video')
        lesson_root.joinpath('lesson-1.pdf').write_text('notes')

        return LessonFiles(str(lesson_root))

    # TODO: test the directory lesson root points to
    # def test_lesson_root(self, tmp_path, lesson_files):
    #     lesson_root = tmp_path / 'lesson-1'
    #     assert lesson_files.lesson_root == str(lesson_root)

    def test_discovery(self, lesson_files):
        assert len(lesson_files.files) == 2

    def test_transcription_source(self, lesson_files):
        assert lesson_files.transcription_source.name == 'lesson-1.mp4'

    def test_notes_file(self, lesson_files):
        assert lesson_files.lecture_notes.name == 'lesson-1.pdf'
