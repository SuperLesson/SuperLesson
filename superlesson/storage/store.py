import json as json_lib
import logging
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from superlesson.steps.step import Step


logger = logging.getLogger("superlesson")


class Format(Enum):
    json = "json"
    txt = "txt"


class Loaded(Enum):
    new = "loaded_new"
    already_run = "already_loaded"
    none = "not_loaded"
    in_memory = "in_memory"


@dataclass
class File:
    name: str
    formats: list[Format]


class Store:
    _storage_map = {
        Step.transcribe: File("transcription", [Format.json]),
        Step.insert_tmarks: File("marked", [Format.json]),
        Step.replace_words: File("replaced", [Format.json]),
        Step.improve_punctuation: File("improved", [Format.json, Format.txt]),
        Step.enumerate_slides: File("enumerated", [Format.json]),
    }

    def __init__(self, lesson_root: Path):
        self._lesson_root = lesson_root
        self._storage_root = lesson_root / ".data"

    @classmethod
    def txt_files(cls) -> list[str]:
        return [f"{file.name}.txt" for file in cls._storage_map.values()]

    def in_storage(self, step: Step) -> bool:
        return self._storage_map.get(step) is not None

    def _get_storage_path(self, step: Step, format: Format) -> Optional[Path]:
        file = self._storage_map[step]
        if format not in file.formats:
            return None
        if format is Format.json:
            if not self._storage_root.exists():
                self._storage_root.mkdir()
            return self._storage_root / f"{file.name}.json"
        return self._lesson_root / f"{file.name}.txt"

    def _parse_txt(self, txt_path: Path) -> list[str]:
        with open(str(txt_path), "r") as f:
            transcriptions = re.split("====== SLIDE .* ======", f.read())[1:]

        return transcriptions

    def _load(self, step: Step) -> Any:
        json_path = self._get_storage_path(step, Format.json)
        assert json_path is not None, f"{step.value} doesn't define a json file"
        if not json_path.exists():
            return None

        with open(str(json_path), "r") as f:
            try:
                data = json_lib.load(f)
            except json_lib.decoder.JSONDecodeError:
                raise Exception(f"Failed to load {step.value} from json file")

        txt_path = self._get_storage_path(step, Format.txt)
        if txt_path is not None and txt_path.exists():
            logger.info(f"Loading {step.value} from txt file")
            transcriptions = self._parse_txt(txt_path)

            if transcriptions:
                for i in range(len(data)):
                    data[i]["transcription"] = transcriptions[i]

        return data

    def load(
        self, step: Step, depends_on: Step, prompt: bool = True
    ) -> tuple[Loaded, Optional[Any]]:
        if self.in_storage(step):
            data = self._load(step)
            if data:
                if not prompt or (
                    input(
                        f"{step.value} has already been run. Run again? (y/N) "
                    ).lower()
                    != "y"
                ):
                    return (Loaded.already_run, data)

        for s in Step.get_last(step):
            if s < depends_on:
                raise Exception(
                    f"Step {step} depends on {depends_on}, but {depends_on} was not run yet."
                )
            if self.in_storage(s):
                data = self._load(s)
                if data:
                    logger.info(f"Loaded step {s.value}")
                    return (Loaded.new, data)

        return (Loaded.none, None)

    def temp_save(self, txt_data: Any) -> Path:
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as temp_file:
            temp_file.write(txt_data)
            temp_path = Path(temp_file.name)

        return temp_path

    def save_json(self, step: Step, data: Any):
        path = self._get_storage_path(step, Format.json)
        if path is not None:
            logger.info(f"Saving {step.value} as json")
            logger.debug(f"to {path}")
            with open(str(path), "w") as f:
                json_lib.dump(data, f)

    def save_txt(self, step: Step, data: Any):
        path = self._get_storage_path(step, Format.txt)
        if path is not None:
            logger.info(f"Saving {step.value} as txt")
            logger.debug(f"to {path}")
            with open(str(path), "w") as f:
                f.write(data)
