from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, unique

logger = logging.getLogger("superlesson")


RAN_STEP = False


@dataclass
class StepMetadata:
    name: str
    filename: str | None = None
    instructions: str | None = None

    def in_storage(self):
        return self.filename is not None


@unique
class Step(Enum):
    transcribe = StepMetadata(name="transcribe", filename="transcription")
    merge = StepMetadata(name="merge segments", filename="merged")
    replace = StepMetadata(name="replace words", filename="replaced")
    improve = StepMetadata(name="improve punctuation", filename="improved")
    enumerate = StepMetadata(name="enumerate slides", filename="enumerated")
    manual = StepMetadata(name="manual revision", filename="manual")
    # TODO: annotated pdf should be managed by storage layer
    annotate = StepMetadata(name="annotate")

    def __lt__(self, other: Step) -> bool:
        steps = list(Step)
        return steps.index(self) < steps.index(other)


def step(step: Step, depends_on: Step | None = None):
    def decorator(func: Callable):
        def wrapper(instance, *args, **kwargs):
            from superlesson.storage import Slides

            # HACK: to preserve behavior from Loaded.already_ran, we have to track if
            # any step has already been run
            global RAN_STEP

            slides = instance.slides
            assert isinstance(slides, Slides)
            if not RAN_STEP and slides.load(step, depends_on) is step:
                return None
            logger.info(f"Running step {step.value}")
            ret = func(instance, *args, **kwargs)
            instance.slides.save(step)
            RAN_STEP = True
            return ret

        return wrapper

    return decorator
