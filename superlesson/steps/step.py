from __future__ import annotations

import logging
from collections.abc import Sequence
from enum import Enum
from typing import Callable, Optional


logger = logging.getLogger("superlesson")


class Step(Enum):
    transcribe = "transcribe"
    merge_segments = "merge_segments"
    enumerate_slides = "enumerate_slides"
    replace_words = "replace_words"
    improve_punctuation = "improve_punctuation"
    annotate = "annotate"

    @staticmethod
    def to_list() -> list[Step]:
        return list([s for s in Step])

    @classmethod
    def get_last(cls, step: Step) -> Sequence[Step]:
        if step is cls.transcribe:
            return []
        steps = cls.to_list()
        index = steps.index(step) - 1
        return steps[index::-1]

    def __lt__(self, other: Step) -> bool:
        steps = self.to_list()
        return steps.index(self) < steps.index(other)

    @staticmethod
    def step(step: Step, depends_on: Optional[Step] = None):
        def decorator(func: Callable):
            def wrapper(instance, *args, **kwargs):
                from superlesson.storage.store import Loaded

                match instance.slides.load(step, depends_on):
                    case Loaded.none:
                        if depends_on is not None:
                            raise Exception(
                                f"Couldn't load from previous step: {step.value} depends on {depends_on}"
                            )
                    case Loaded.already_run:
                        return
                logger.info(f"Running step {step.value}")
                ret = func(instance, *args, **kwargs)
                instance.slides.save(step)
                return ret

            return wrapper

        return decorator
