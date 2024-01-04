import json as json_lib
import logging
import re
from datetime import time
from enum import Enum, unique
from pathlib import Path
from typing import Any

from .utils import mktemp

logger = logging.getLogger("superlesson")


@unique
class Format(Enum):
    json = "json"
    txt = "txt"


class Store:
    def __init__(self, root: Path):
        self._root = root
        self._data_path = root / ".data"

    def _get_storage_path(self, filename: str, format: Format) -> Path:
        if format is Format.json:
            if not self._data_path.exists():
                self._data_path.mkdir()
            return self._data_path / f"{filename}.json"
        return self._root / f"{filename}.txt"

    @staticmethod
    def _parse_txt(txt_path: Path) -> list[dict[str, Any]]:
        raw_slides = re.split(
            r"====== SLIDE (\S*) \((\S*) - (\S*)\) ======", txt_path.read_text()
        )

        def timestamp_to_seconds(timestamp: str) -> float:
            if len(timestamp.split(":")[0]) == 1:
                timestamp = "0" + timestamp
            t = time.fromisoformat(timestamp)
            return (t.hour * 60 + t.minute) * 60 + t.second + t.microsecond / 1e6

        def parse_to_int(value):
            if "0" < value[0] < "9":
                return int(value)
            return None

        return [
            {
                "number": parse_to_int(raw_slides[i]),
                "timeframe": {
                    "start": timestamp_to_seconds(raw_slides[i + 1]),
                    "end": timestamp_to_seconds(raw_slides[i + 2]),
                },
                "transcription": raw_slides[i + 3],
            }
            for i in range(1, len(raw_slides), 4)
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

    def load(self, filename: str, load_txt: bool) -> list[Any] | None:
        if load_txt:
            if (txt_path := self._get_storage_path(filename, Format.txt)).exists():
                logger.info(f"Loading {txt_path}")
                return self._parse_txt(txt_path)

            logger.info(
                f"Couldn't load from file {txt_path}, make sure it's properly formatted"
            )

        json_path = self._get_storage_path(filename, Format.json)
        if json_path.exists():
            logger.info(f"Loading {json_path}")
            return self._parse_json(json_path)

        return None

    @staticmethod
    def temp_save(txt_data: Any) -> Path:
        with (temp_path := mktemp(suffix=".txt")).open("w") as temp_file:
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
