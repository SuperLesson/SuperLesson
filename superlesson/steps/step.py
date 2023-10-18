from __future__ import annotations

import logging
from enum import Enum
from typing import Callable, Iterable, List, Optional


class Step(Enum):
    """
    Enum class for each step of the SuperLesson process.
    """
    transcribe = "transcribe"
    insert_tmarks = "insert_tmarks"
    verify_tbreaks_with_mpv = "verify_tbreaks_with_mpv"
    replace_words = "replace_words"
    improve_punctuation = "improve_punctuation"
    annotate = "annotate"

    @staticmethod
    def to_list() -> list[Step]:
        """
        Static method which returns a list of all steps.
        """
        return list([s for s in Step])

    @classmethod
    def get_last(cls, step: Step) -> Iterable[Step]:
        """
        Class method to get last last executed step
        """
        if step is cls.transcribe:
            return
        steps = cls.to_list()
        index = steps.index(step) - 1
        yield from steps[index::-1]

    def __lt__(self, other: Step) -> bool:
        steps = self.to_list()
        return steps.index(self) < steps.index(other)

    @staticmethod
    def step(step: Step, depends_on: Step | None = None):
        """
        Static method which executes a step.
        Will raise an exception if the step it depends on could not be loaded.
        """
        def decorator(func: Callable):
            def wrapper(instance, *args, **kwargs):
                from superlesson.storage.store import Loaded
                match instance.slides.load(step, depends_on):
                    case Loaded.none:
                        if depends_on is not None:
                            raise Exception(
                                f"Couldn't load from previous step: {step.value} depends on {depends_on}")
                    case Loaded.already_run:
                        return
                logging.info(f"Running step {step.value}")
                ret = func(instance, *args, **kwargs)
                instance.slides.save(step)
                return ret
            return wrapper
        return decorator
