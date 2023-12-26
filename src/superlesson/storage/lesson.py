import logging
import mimetypes
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .utils import mktemp

logger = logging.getLogger("superlesson")


class FileType(Enum):
    video = "video"
    audio = "audio"
    slides = "slides"


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

    def extract_audio(
        self,
        audio_codec: str = "pcm_s16le",
        channels: int = 1,
        sample_rate: int = 16000,
    ) -> Path:
        if self.file_type is FileType.audio:
            logger.debug(f"{self.full_path} is already an audio file")
            return self.full_path

        output_path = mktemp(suffix=".wav")
        logger.info(f"Extracting audio from {self.full_path}")

        subprocess.run(
            [  # noqa: S607
                "ffmpeg",
                "-loglevel",
                "quiet",
                "-i",
                self.full_path,
                "-vn",
                "-acodec",
                str(audio_codec),
                "-ac",
                str(channels),
                "-ar",
                str(sample_rate),
                output_path,
            ],
            stdout=subprocess.DEVNULL,
        )

        logger.debug(f"Audio saved as {output_path}")
        return output_path

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
            case "text":
                file_type = FileType.slides
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
            self._transcription_source = LessonFile(
                transcription_source_path.name,
                root,
            )
        self._presentation = None
        if presentation_path is not None:
            root = presentation_path.resolve().parent
            if root != self.lesson_root:
                msg = "Presentation must be in lesson root"
                raise ValueError(msg)
            self._presentation = LessonFile(
                presentation_path.name, presentation_path.resolve().parent
            )

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
            files = self._find_lesson_files([FileType.video, FileType.audio])
            if not files:
                msg = f"Transcription file not found on {self.lesson_root}"
                raise ValueError(msg)
            self._transcription_source = files[0]
            logger.debug(f"Transcription source: {self._transcription_source}")

        return self._transcription_source

    @property
    def presentation(self) -> LessonFile:
        """The file to be used for annotation."""
        if self._presentation is None:
            files = self._find_lesson_files([FileType.slides])
            for file in files:
                if file.name.endswith(".pdf"):
                    self._presentation = file
                    logger.debug(f"Presentation: {self._presentation}")
                    break
            if self._presentation is None:
                msg = f"Presentation file not found on {self.lesson_root}"
                raise ValueError(msg)

        return self._presentation

    def _find_lesson_files(
        self, accepted_types: list[FileType | None]
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
