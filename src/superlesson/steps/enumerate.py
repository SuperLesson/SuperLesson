import logging
from dataclasses import dataclass
from enum import Enum, unique
from pathlib import Path

from superlesson.storage import Slides

from .step import Step, step

logger = logging.getLogger("superlesson")


class InvalidInputError(Exception):
    """Raised when the user inputs an invalid value."""


@unique
class Command(Enum):
    append = "a"
    none = "n"
    back = "b"
    number = "number"


@dataclass
class Answer:
    command: Command
    value: int | None


class Enumerate:
    def __init__(self, slides: Slides, presentation: Path):
        from pypdf import PdfReader

        self.presentation_len = len(PdfReader(presentation).pages)
        self.slides = slides

    def _get_slide_number_from_user(self, slide_idx: int, default: int) -> Answer:
        if (path := self.slides[slide_idx].tframe) is not None:
            self._sys_open(path)
            user_input = input(
                f"What is the number of this slide? (default: {default + 1}) "
            )
        # TODO: (#111) Remove this once we capture tframes for all slides
        else:
            user_input = input(
                f"What is the number of the last slide? (default: {default + 1}) "
            )

        user_input = user_input.strip().lower()

        if user_input == "":
            return Answer(Command.number, default)

        try:
            number = int(user_input) - 1
        except ValueError as int_err:
            try:
                cmd = Command(user_input[0])
            except ValueError as cmd_err:
                if slide_idx == 0:
                    print(
                        f"Type the number of the current slide (1 to {self.presentation_len}) or (n)ext to skip it"
                    )
                else:
                    print(
                        f"Type the number of the current slide (1 to {self.presentation_len}), (n)ext to skip it, (b)ack to redo the last slide, or (a)ppend to merge the current slide with the previous one"
                    )
                raise InvalidInputError from cmd_err

            if slide_idx == 0:
                match cmd:
                    case Command.back:
                        msg = "Can't go back, already at the first slide"
                        raise InvalidInputError(msg) from int_err
                    case Command.append:
                        msg = "Can't append first slide"
                        raise InvalidInputError(msg) from int_err

            return Answer(cmd, None)

        if -1 < number < self.presentation_len:
            return Answer(Command.number, number)

        msg = f"Invalid slide number: {number + 1} (should be between 1 and {self.presentation_len})"
        raise InvalidInputError(msg)

    @step(Step.enumerate, Step.merge)
    def using_tframes(self):
        i = 0
        last_answer = -1
        while i < len(self.slides):
            if last_answer < self.presentation_len - 1:
                suggestion = last_answer + 1
            else:
                logger.debug("Repeating suggestion")
                suggestion = last_answer

            logger.debug(f"Getting slide number for slide {i}")
            try:
                answer = self._get_slide_number_from_user(i, suggestion)
            except (InvalidInputError, ValueError) as e:
                logger.warning(e)
                logger.warning("Repeating slide")
                continue

            match answer.command:
                case Command.none:
                    logger.info("Slide will be hidden")
                    # keep the default value for the next slide
                    self.slides[i].number = -1
                    i += 1
                case Command.append:
                    logger.info(f"Appending slide {i + 1} to previous slide")
                    # keep the default value for the next slide
                    self.slides.merge(i - 1, i)
                case Command.back:
                    logger.info("Going back to previous slide")
                    # suggest the last slide default again
                    if last_answer >= 0:
                        last_answer -= 1
                    i -= 1
                case Command.number:
                    number = answer.value
                    assert isinstance(number, int)
                    if number == self.presentation_len - 1:
                        logger.info("Reached last slide on presentation")
                    last_answer = number
                    logger.debug("slide number: %d", last_answer)
                    self.slides[i].number = last_answer
                    i += 1

    @staticmethod
    def _sys_open(path: Path) -> int:
        import subprocess

        if not path.exists():
            logger.warning(f"File {path} doesn't exist")
            return 1

        logger.debug(f"Opening {path}")

        ret_code = subprocess.call(["kitty", "+kitten", "icat", str(path)])  # noqa: S607
        if ret_code != 0:
            logger.warning(f"Error opening {path}")

        return ret_code
