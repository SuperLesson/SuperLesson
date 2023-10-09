from __future__ import annotations

import logging
from enum import Enum
from typing import Callable, Iterable, List, Optional


class Step(Enum):
    transcribe = "transcribe"
    insert_tmarks = "insert_tmarks"
    verify_tbreaks_with_mpv = "verify_tbreaks_with_mpv"
    replace_words = "replace_words"
    improve_punctuation = "improve_punctuation"
    annotate = "annotate"

    @staticmethod
    def to_list() -> List[Step]:
        return list([s for s in Step])

    @classmethod
    def get_last(cls, step: Step) -> Iterable[Step]:
        if step is cls.transcribe:
            return
        steps = cls.to_list()
        index = steps.index(step) - 1
        for s in steps[index::-1]:
            yield s

    def __lt__(self, other: Step) -> bool:
        steps = self.to_list()
        return steps.index(self) < steps.index(other)

    @staticmethod
    def step(step: Step, depends_on: Optional[Step] = None):
        def decorator(func: Callable):
            def wrapper(instance, *args, **kwargs):
                if not instance.slides.load(step, depends_on):
                    if depends_on is not None:
                        raise Exception(
                            f"Couldn't load from previous step: {step.value} depends on {depends_on}")
                logging.info(f"Running step {step.value}")
                ret = func(instance, *args, **kwargs)
                instance.slides.save(step)
                return ret
            return wrapper
        return decorator
