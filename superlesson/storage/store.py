from enum import Enum, unique
import json as json_lib
import logging
import re
from pathlib import Path
from typing import Any, Optional

from superlesson.steps.step import Step

logger = logging.getLogger("superlesson")


@unique
class Format(Enum):
    json = "json"
    txt = "txt"


class Loaded(Enum):
    new = "loaded_new"
    already_run = "already_loaded"
    none = "not_loaded"
    in_memory = "in_memory"


class Store:
    def __init__(self, lesson_root: Path):
        self._lesson_root = lesson_root
        self._storage_root = lesson_root / ".data"

    def _get_storage_path(self, step: Step, format: Format) -> Path:
        file = step.value.filename
        if format is Format.json:
            if not self._storage_root.exists():
                self._storage_root.mkdir()
            return self._storage_root / f"{file}.json"
        return self._lesson_root / f"{file}.txt"

    def _parse_txt(self, txt_path: Path) -> list[str]:
        with open(str(txt_path), "r") as f:
            transcriptions = re.split(r"====== SLIDE .* ======", f.read())[1:]

        for i, text in enumerate(transcriptions):
            text = text.strip()
            text = re.sub(r"\n\n", "<br>", text)
            text = re.sub(r"\s+", " ", text)
            text = re.sub(r"<br>", "\n\n", text)
            transcriptions[i] = text

        return transcriptions

    def _load(self, step: Step) -> Any:
        json_path = self._get_storage_path(step, Format.json)
        if not json_path.exists():
            return None

        with open(str(json_path), "r") as f:
            try:
                data = json_lib.load(f)
            except json_lib.decoder.JSONDecodeError:
                raise Exception(f"Failed to load {step.value} from json file")

        if step is Step.transcribe:
            logger.info("Skipping txt file parsing for transcribe step")
            return data

        txt_path = self._get_storage_path(step, Format.txt)
        if txt_path.exists():
            logger.info(f"Loading {step.value} from txt file")
            transcriptions = self._parse_txt(txt_path)

            if transcriptions and len(transcriptions) == len(data):
                for i in range(len(data)):
                    data[i]["transcription"] = transcriptions[i]
            else:
                logger.warning(
                    f"Couldn't load from file {txt_path}, make sure it's properly formatted"
                )

        return data

    def load(
        self, step: Step, depends_on: Step, prompt: bool = True
    ) -> tuple[Loaded, Optional[Any]]:
        if step.value.in_storage():
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
            if s.value.in_storage():
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
            temp_path = Path(temp_file.name)
            logger.debug(f"Saving temp file to {temp_file.name}")
            temp_file.write(txt_data)

        return temp_path

    def save_json(self, step: Step, data: Any):
        path = self._get_storage_path(step, Format.json)
        logger.info(f"Saving {step.value} as json")
        logger.debug(f"to {path}")
        with open(str(path), "w") as f:
            json_lib.dump(data, f)

    def save_txt(self, step: Step, data: Any):
        path = self._get_storage_path(step, Format.txt)
        logger.info(f"Saving {step.value} as txt")
        logger.debug(f"to {path}")
        with open(str(path), "w") as f:
            f.write(data)
