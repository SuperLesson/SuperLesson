import logging
import mimetypes
from dataclasses import dataclass
from enum import Enum, unique
from pathlib import Path

logger = logging.getLogger("superlesson")


@unique
class FileType(Enum):
    video = "video"
    audio = "audio"
    slides = "slides"


@dataclass
class LessonFile:
    """Class to represent a lesson file."""

    path: Path

    def __post_init__(self):
        self.type = self._file_type(self.path.name)

    @staticmethod
    def _file_type(name: str) -> FileType:
        """Return the file type of a given file name."""
        mime_type, _ = mimetypes.guess_type(name)
        if mime_type is None:
            msg = f"File type not found for {name}"
            raise ValueError(msg)
        mime_type = mime_type.split("/")[0]
        match mime_type:
            case "video":
                file_type = FileType.video
            case "audio":
                file_type = FileType.audio
            case _:
                # application
                if name.endswith(".pdf"):
                    file_type = FileType.slides
                else:
                    msg = f"File type not found for {name}"
                    raise ValueError(msg)
        return file_type


class LessonFiles:
    """Class to find all files for a given lesson id."""

    lesson_root: Path

    def __init__(
        self,
        lesson: str,
        transcription_source_path: Path | None = None,
        presentation_path: Path | None = None,
    ):
        self.lesson_root = self.find_lesson_root(lesson)

        self._files: list[LessonFile] = []

        self._transcription_source = None
        if transcription_source_path is not None:
            # TODO: we should use lesson_root for storing data unconditionally
            root = transcription_source_path.resolve().parent
            if root != self.lesson_root:
                msg = "Transcription source must be in lesson root"
                raise ValueError(msg)
            self._transcription_source = LessonFile(transcription_source_path)
        self._presentation = None
        if presentation_path is not None:
            root = presentation_path.resolve().parent
            if root != self.lesson_root:
                msg = "Presentation must be in lesson root"
                raise ValueError(msg)
            self._presentation = LessonFile(presentation_path)

    @staticmethod
    def find_lesson_root(lesson: str) -> Path:
        lesson_root = Path(lesson)
        if not lesson_root.exists():
            lesson_root = Path.cwd() / "lessons" / lesson

            if not lesson_root.exists():
                msg = f"Lesson {lesson} not found"
                raise ValueError(msg)

        logger.debug(f"Found lesson root: {lesson_root}")
        return lesson_root

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
                self._files.append(LessonFile(file))
                logger.debug(f"Found file: {file}")
            except ValueError:
                logger.debug(f"Skipping file: {file}")

        # TODO: test for duplicate file types

        return self._files

    @property
    def transcription_source(self) -> Path:
        """The file to be used for transcription."""
        if self._transcription_source is None:
            file = self._find_first(FileType.video)
            if not file:
                msg = f"Transcription file not found on {self.lesson_root}"
                raise ValueError(msg)
            self._transcription_source = file
            logger.debug(f"Transcription source: {self._transcription_source}")

        return self._transcription_source.path

    @property
    def presentation(self) -> Path:
        """The file to be used for annotation."""
        if self._presentation is None:
            file = self._find_first(FileType.slides)
            if not file:
                msg = f"Presentation file not found on {self.lesson_root}"
                raise ValueError(msg)
            self._presentation = file
            logger.debug(f"Presentation: {self._presentation}")

        return self._presentation.path

    def _find_first(self, type: FileType) -> LessonFile | None:
        try:
            return next(file for file in self.files if file.type is type)
        except StopIteration:
            return None
