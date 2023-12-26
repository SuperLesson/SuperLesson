import logging
import mimetypes
from collections.abc import Generator
from enum import Enum, unique
from pathlib import Path

logger = logging.getLogger("superlesson")


@unique
class FileType(Enum):
    video = "video"
    audio = "audio"
    slides = "slides"


PathIterator = Generator[Path, None, None]


class Lesson:
    """User lesson"""

    root: Path

    def __init__(
        self,
        lesson: str,
        transcription_source: Path | None = None,
        presentation: Path | None = None,
    ):
        self.root = self.find_root(lesson)

        if transcription_source:
            if self.guess_type(transcription_source.name) is not FileType.video:
                msg = f"{transcription_source} must be a video file"
                raise ValueError(msg)
            # TODO: we should use lesson_root for storing data unconditionally
            if transcription_source.resolve().parent != self.root:
                msg = f"Transcription source must be in lesson root: {self.root}"
                raise ValueError(msg)
            self._video = transcription_source
        else:
            self._video = None

        if presentation:
            if self.guess_type(presentation.name) is not FileType.slides:
                msg = f"{presentation} must be a PDF file"
                raise ValueError(msg)
            if presentation.resolve().parent != self.root:
                msg = f"Presentation must be in lesson root: {self.root}"
                raise ValueError(msg)
            self._presentation = presentation
        else:
            self._presentation = None

        self._files: list[Path] = []

    @staticmethod
    def find_root(lesson: str) -> Path:
        lesson_root = Path(lesson)
        if not lesson_root.exists():
            lesson_root = Path.cwd() / "lessons" / lesson

            if not lesson_root.exists():
                msg = f"Lesson {lesson} not found"
                raise ValueError(msg)

        logger.debug(f"Found lesson root: {lesson_root}")
        return lesson_root

    @property
    def files(self) -> list[Path]:
        if not self._files:
            self._files = list(self.get_files(self.root))

        return self._files

    @staticmethod
    def guess_type(name: str) -> FileType | None:
        """Return the MIME file type of a given file name."""
        if name.endswith(".pdf"):
            return FileType.slides

        mime_type, _ = mimetypes.guess_type(name)
        if not mime_type:
            msg = f"File type not found for {name}"
            raise ValueError(msg)
        if mime_type.split("/")[0] == "video":
            return FileType.video
        return None

    @classmethod
    def get_files(cls, root: Path, max_depth: int = 0) -> PathIterator:
        """All usable files in lesson folder."""
        logger.info(f"Searching for files on {root}")
        for path in root.iterdir():
            if (
                path.name.startswith(".")
                or path.suffix == ".txt"
                or path.name == "annotations.pdf"
            ):
                continue
            if path.is_dir():
                if max_depth > 0:
                    yield from cls.get_files(path, max_depth - 1)
            else:
                yield path

    @property
    def video(self) -> Path:
        if self._video is None:
            if not (path := self._find_first(FileType.video)):
                msg = f"Transcription file not found on {self.root}"
                raise ValueError(msg)
            self._video = path
            logger.debug(f"Transcription source: {self._video}")

        return self._video

    @property
    def presentation(self) -> Path:
        if self._presentation is None:
            if not (path := self._find_first(FileType.slides)):
                msg = f"Presentation file not found on {self.root}"
                raise ValueError(msg)
            self._presentation = path
            logger.debug(f"Presentation: {self._presentation}")

        return self._presentation

    def _find_first(self, type: FileType) -> Path | None:
        try:
            return next(
                file for file in self.files if self.guess_type(file.name) == type
            )
        except StopIteration:
            return None
