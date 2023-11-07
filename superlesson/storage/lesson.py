import logging
import mimetypes
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from .utils import find_lesson_root

logger = logging.getLogger("superlesson")


class FileType(Enum):
    video = "video"
    audio = "audio"
    notes = "notes"


@dataclass
class LessonFile:
    """Class to represent a lesson file."""

    name: str
    path: Path
    file_type: FileType

    def __init__(self, name: str, path: Path):
        self.name = name
        self.path = path
        self.file_type = self._file_type(name)

    @property
    def full_path(self) -> Path:
        return self.path / self.name

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
                # application
                if name.endswith(".pdf"):
                    file_type = FileType.notes
                else:
                    raise ValueError(f"File type not found for {name}")
        return file_type


class LessonFiles:
    """Class to find all files for a given lesson id."""

    lesson_root: Path

    def __init__(
        self,
        lesson: str,
        transcribe_with: Optional[FileType] = None,
        annotate_with: Optional[FileType] = None,
    ):
        self.lesson_root = find_lesson_root(lesson)

        self._files: list[LessonFile] = []
        self._transcribe_with = transcribe_with
        self._annotate_with = annotate_with
        self._transcription_source: Optional[LessonFile] = None
        self._presentation: Optional[LessonFile] = None

    @property
    def files(self) -> list[LessonFile]:
        """All usable files in lesson folder."""
        if len(self._files) > 0:
            return self._files

        logger.info("Searching for files...")
        for file in self.lesson_root.iterdir():
            if file.name == "annotations.pdf":
                continue
            if file.is_dir():
                continue
            if file.name.startswith("."):
                continue
            if file.suffix == ".txt":
                continue
            try:
                self._files.append(LessonFile(file.name, self.lesson_root))
                logger.debug(f"Found file: {file}")
            except ValueError:
                logger.debug(f"Skipping file: {file}")

        # TODO: test for duplicate file types

        return self._files

    @property
    def transcription_source(self) -> LessonFile:
        """The file to be used for transcription."""
        if self._transcription_source is None:
            files = self._find_lesson_files(
                [self._transcribe_with, FileType.video, FileType.audio]
            )
            if not files:
                raise ValueError(f"Transcription file not found on {self.lesson_root}")
            self._transcription_source = files[0]
            logger.debug(f"Transcription source: {self._transcription_source}")

        return self._transcription_source

    @property
    def presentation(self) -> LessonFile:
        """The file to be used for annotation."""
        if self._presentation is None:
            files = self._find_lesson_files(
                [self._annotate_with, FileType.notes, FileType.video]
            )
            if not files:
                raise ValueError(f"Notes file not found on {self.lesson_root}")
            for file in files:
                if file.name.endswith(".pdf"):
                    self._presentation = file
                    logger.debug(f"Presentation: {self._presentation}")
                    break
            if self._presentation is None:
                raise ValueError(f"Notes file not found on {self.lesson_root}")

        return self._presentation

    def _find_lesson_files(
        self, accepted_types: list[Optional[FileType]]
    ) -> list[LessonFile]:
        for file_type in accepted_types:
            if file_type is None:
                continue
            files = self._get_files(file_type)
            if len(files) > 0:
                return files

        return []

    def _get_files(self, file_type: FileType) -> list[LessonFile]:
        """Get all files of a given type."""
        return [file for file in self.files if file.file_type == file_type]
