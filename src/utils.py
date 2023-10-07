import mimetypes
import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class FileType(Enum):
    video = "video"
    audio = "audio"
    notes = "notes"


@dataclass
class LessonFile:
    """Class to represent a lesson file."""

    name: str
    path: str
    file_type: FileType

    def __init__(self, name: str, path: str):
        self.name = name
        self.path = path
        self.file_type = self._file_type(name)

    @staticmethod
    def _file_type(name: str) -> FileType:
        """Return the file type of a given file name."""
        mime_type, _ = mimetypes.guess_type(name)
        if mime_type is None:
            raise ValueError(f"File type not found for {name}")
        mime_type = mime_type.split("/")[0]
        match mime_type:
            case "video":
                file_type = FileType.video
            case "audio":
                file_type = FileType.audio
            case "text":
                file_type = FileType.notes
            case _:
                if name.endswith(".pdf"):
                    file_type = FileType.notes
                else:
                    raise ValueError(f"File type not found for {name}")
        return file_type


class LessonFiles:
    """Class to find all files for a given lesson id."""

    lesson_root: str

    def __init__(self, lesson: str,
                 transcribe_with: Optional[FileType] = None,
                 annotate_with: Optional[FileType] = None):
        current_script_directory = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(
            os.path.join(current_script_directory, '..'))

        lesson_root = os.path.join(project_root, 'lessons', lesson)
        if os.path.exists(lesson_root):
            self.lesson_root = lesson_root
        elif os.path.exists(lesson):
            self.lesson_root = lesson
        else:
            raise ValueError(f"Lesson {lesson} not found")

        self._files: list[LessonFile] = []
        self._transcribe_with = transcribe_with
        self._annotate_with = annotate_with
        self._transcription_source: Optional[LessonFile] = None
        self._lecture_notes: Optional[LessonFile] = None

    @property
    def files(self) -> list[LessonFile]:
        """All usable files in lesson folder."""
        if len(self._files) > 0:
            return self._files

        print("Searching for files...")
        for root, _, _files in os.walk(self.lesson_root):
            for file in _files:
                file_path = os.path.join(root, file)
                try:
                    self._files.append(LessonFile(file, file_path))
                except ValueError:
                    pass

        # TODO: test for duplicate file types

        return self._files

    @property
    def transcription_source(self) -> LessonFile:
        """The file to be used for transcription."""
        if self._transcription_source is None:
            transcription_file = self._find_lesson_file(
                [self._transcribe_with, FileType.video, FileType.audio])
            if transcription_file is None:
                raise ValueError(
                    f"Transcription file not found on {self.lesson_root}")
            self._transcription_source = transcription_file

        return self._transcription_source

    @property
    def lecture_notes(self) -> LessonFile:
        """The file to be used for annotation."""
        if self._lecture_notes is None:
            notes_file = self._find_lesson_file(
                [self._annotate_with, FileType.notes, FileType.video])
            if notes_file is None:
                raise ValueError(f"Notes file not found on {self.lesson_root}")
            self._lecture_notes = notes_file

        return self._lecture_notes

    def _find_lesson_file(self, accepted_types: list[Optional[FileType]]) -> Optional[LessonFile]:
        for file_type in accepted_types:
            if file_type is None:
                continue
            files = self._get_files(file_type)
            if len(files) > 0:
                return files[0]

        return None

    def _get_files(self, file_type: FileType) -> list[LessonFile]:
        """Get all files of a given type."""
        return [file for file in self.files if file.file_type == file_type]
