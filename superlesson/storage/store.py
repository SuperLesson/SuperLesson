import json as json_lib
import logging
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, List, Optional, Tuple

from superlesson.steps.step import Step


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
    formats: List[Format]


class Store:
    _storage_map = {
        Step.transcribe: File("transcription", [Format.json]),
        Step.insert_tmarks: File("marked", [Format.json]),
        Step.replace_words: File("replaced", [Format.json]),
        Step.improve_punctuation: File("improved", [Format.json, Format.txt]),
    }

    def __init__(self, lesson_root: Path, run_all: bool):
        self._lesson_root = lesson_root
        self._storage_root = lesson_root / ".data"
        self._run_all = run_all

    @classmethod
    def txt_files(cls) -> List[str]:
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

    def _load(self, step: Step) -> Any:
        txt_path = self._get_storage_path(step, Format.txt)
        transcriptions = None
        if txt_path is not None and txt_path.exists():
            with open(str(txt_path), "r") as f:
                transcriptions = re.split("====== SLIDE .* ======", f.read())[1:]

            if len(transcriptions) == 0:
                transcriptions = None

        json_path = self._get_storage_path(step, Format.json)
        assert json_path is not None, f"{step.value} doesn't define a json file"
        data = None
        if json_path.exists():
            with open(str(json_path), "r") as f:
                try:
                    data = json_lib.load(f)
                except json_lib.decoder.JSONDecodeError:
                    logging.error(
                        f"Failed to load {step.value} from json. Try running the step again.")
                    
        if transcriptions is not None and data is not None:
            for i in range(len(data)):
                data[i]["transcription"] = transcriptions[i].strip()

        return data

    def load(self, step: Step, depends_on: Step) -> Tuple[Loaded, Optional[Any]]:
        if not self._run_all and self.in_storage(step):
            data = self._load(step)
            if data:
                if input(f"{step.value} has already been run. Run again? (y/N) ").lower() != "y":
                    return (Loaded.already_run, data)

        for s in Step.get_last(step):
            if s < depends_on:
                raise Exception(
                    f"Step {step} depends on {depends_on}, but {depends_on} was not run yet.")
            if self.in_storage(s):
                data = self._load(s)
                if data:
                    return (Loaded.new, data)

        return (Loaded.none, None)

    def save_json(self, step: Step, data: Any):
        path = self._get_storage_path(step, Format.json)
        if path is not None:
            logging.info(f"Saving {step.value} as json")
            logging.debug(f"to {path}")
            with open(str(path), "w") as f:
                json_lib.dump(data, f)

    def save_txt(self, step: Step, data: Any):
        path = self._get_storage_path(step, Format.txt)
        if path is not None:
            logging.info(f"Saving {step.value} as txt")
            logging.debug(f"to {path}")
            with open(str(path), "w") as f:
                f.write(data)
