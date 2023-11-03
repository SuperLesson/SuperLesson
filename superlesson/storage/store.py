from enum import Enum, unique
import json as json_lib
import logging
import re
from pathlib import Path
from typing import Any, Optional

from .utils import format_transcription

logger = logging.getLogger("superlesson")


@unique
class Format(Enum):
    json = "json"
    txt = "txt"


class Store:
    def __init__(self, lesson_root: Path):
        self._lesson_root = lesson_root
        self._storage_root = lesson_root / ".data"

    def _get_storage_path(self, filename: str, format: Format) -> Path:
        if format is Format.json:
            if not self._storage_root.exists():
                self._storage_root.mkdir()
            return self._storage_root / f"{filename}.json"
        return self._lesson_root / f"{filename}.txt"

    @staticmethod
    def _parse_txt(txt_path: Path) -> list[str]:
        return [
            format_transcription(text)
            for text in re.split(r"====== SLIDE .* ======", txt_path.read_text())[1:]
        ]

    @staticmethod
    def _parse_json(json_path: Path) -> list[dict[str, Any]]:
        json_data = json_path.read_text()
        data = json_lib.loads(json_data)

        for e in data:
            for k, v in e.items():
                if v == "None":
                    e[k] = None

        return data

    def load(self, filename: str, load_txt: bool) -> Optional[list[Any]]:
        json_path = self._get_storage_path(filename, Format.json)
        if not json_path.exists():
            return None

        logger.debug(f"Loading {json_path}")
        data = self._parse_json(json_path)

        txt_path = self._get_storage_path(filename, Format.txt)
        if not load_txt or not txt_path.exists():
            return data

        logger.info(f"Loading {txt_path}")
        transcriptions = self._parse_txt(txt_path)

        if transcriptions and len(transcriptions) == len(data):
            for i in range(len(data)):
                data[i]["transcription"] = transcriptions[i]
        else:
            logger.warning(
                f"Couldn't load from file {txt_path}, make sure it's properly formatted"
            )

        return data

    @staticmethod
    def temp_save(txt_data: Any) -> Path:
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as temp_file:
            temp_path = Path(temp_file.name)
            logger.debug(f"Saving temp file to {temp_file.name}")
            temp_file.write(txt_data)

        return temp_path

    def save_json(self, filename: str, data: Any):
        path = self._get_storage_path(filename, Format.json)
        logger.info(f"Saving {path}")
        with open(str(path), "w") as f:
            json_lib.dump(data, f)

    def save_txt(self, filename: str, data: Any):
        path = self._get_storage_path(filename, Format.txt)
        logger.info(f"Saving {path}")
        with open(str(path), "w") as f:
            f.write(data)
