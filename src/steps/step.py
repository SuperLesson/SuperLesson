from __future__ import annotations

import logging
from enum import Enum
from typing import Callable, Optional


class Step(Enum):
    transcribe = "transcribe"
    insert_tmarks = "insert_tmarks"
    verify_tbreaks_with_mpv = "verify_tbreaks_with_mpv"
    replace_words = "replace_words"
    improve_punctuation = "improve_punctuation"
    annotate = "annotate"

    @staticmethod
    def step(step: Step, depends_on: Optional[Step] = None):
        def decorator(func: Callable):
            def wrapper(instance, *args, **kwargs):
                if not instance.slides.load(step):
                    if depends_on is not None:
                        raise Exception(
                            f"Couldn't load from previous step: {step.value} depends on {depends_on}")
                logging.info(f"Running step {step.value}")
                ret = func(instance, *args, **kwargs)
                instance.slides.save(step)
                return ret
            return wrapper
        return decorator
