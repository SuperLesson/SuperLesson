import logging
import os
import tempfile
from pathlib import Path

from superlesson.storage import LessonFile, Slides

from .step import Step


class Annotate:
    """Class to annotate a lesson."""

    def __init__(self, slides: Slides, lecture_notes: LessonFile):
        self._lecture_notes = lecture_notes
        self.slides = slides

    @Step.step(Step.enumerate_slides, Step.insert_tmarks)
    def enumerate_slides_from_tframes(self):
        from pypdf import PdfReader

        max_slide_number = len(PdfReader(self._lecture_notes.full_path).pages)

        def get_slide_number_from_user(default: int) -> int:
            user_input = input(f"What is the number of this slide? (default: {default}) ")

            if user_input == "":
                return default
            elif user_input.lower().startswith("n"):
                return 0

            try:
                number = int(user_input)
            except ValueError:
                return default

            if 0 < number < max_slide_number + 1:
                return number

            logging.warning(
                f"There's no such slide number: {number} (should be between 1 and {max_slide_number})"
            )
            return default

        last_answer = 0
        for i, slide in enumerate(self.slides):
            path = slide.png_path
            assert path is not None, f"Slide {i} doesn't have a png_path"
            self._sys_open(path)
            number = get_slide_number_from_user(last_answer + 1)
            if number == 0:
                slide.number = None
                continue
            # if the user answered the last slide, we keep repeating
            # TODO:is there a better heuristic?
            if number >= max_slide_number:
                last_answer = max_slide_number
            else:
                last_answer = number
            slide.number = last_answer - 1

    @staticmethod
    def _sys_open(path: Path) -> int:
        import subprocess

        if not path.exists():
            logging.warning(f"File {path} doesn't exist")
            return 1

        ret_code = subprocess.call(["kitty", "+kitten", "icat", str(path)])
        if ret_code != 0:
            logging.warning(f"Error opening {path}")

        return ret_code

    @Step.step(Step.annotate, Step.enumerate_slides)
    def to_pdf(self):
        from pypdf import PdfReader, PdfWriter

        pdf = PdfReader(self._lecture_notes.full_path)

        # pt -> inch
        slide_width = pdf.pages[0].mediabox.width / 72
        logging.debug(f"Slide width: {slide_width}")
        output = self._transcription_to_pdf(width=slide_width)

        trans = PdfReader(output)

        merger = PdfWriter()
        for i in range(len(self.slides)):
            number = self.slides[i].number

            if number is None:
                continue
            logging.debug(f"Adding slide {number} to annotated PDF")
            merger.append(fileobj=pdf, pages=(number, number + 1))
            logging.debug(f"Adding transcription to slide {i}")
            merger.append(fileobj=trans, pages=(i, i + 1))

        merger.write(output)
        logging.info(f"Annotated PDF saved as {output}")

    @staticmethod
    def emphasize(text: str) -> str:
        return "_" + text + "_"

    @classmethod
    def fade_slide(cls, current: str, next: str, threshold: int = 20) -> tuple[str, str]:
        dots = ['.', '!', '?']

        def text_before_dots(text: str, reverse: bool = False) -> tuple[int, int]:
            text = reversed(text) if reverse else text
            word_count = 0
            last_index = 0
            for index, char in enumerate(text):
                if char == ' ':
                    last_index = index
                    word_count += 1
                    continue
                if word_count > threshold:
                    break
                if char in dots:
                    if not reverse:
                        last_index = index + 1
                    break
            return last_index, word_count

        current_index, words_in_current = text_before_dots(current, True)
        logging.debug(f"Fade in at word {words_in_current}")

        next_index, words_in_next = text_before_dots(next, False)
        logging.debug(f"Fade out at word {words_in_next}")

        current_emphasized = cls.emphasize(current[-current_index:] + " \u21E2")
        logging.debug(f"Fade in text: {current_emphasized}")
        current = current[:-current_index] + current_emphasized
        next_emphasized = cls.emphasize("\u21E2 " + next[:next_index])
        logging.debug(f"Fade out text: {next_emphasized}")
        next = next_emphasized + next[next_index:]

        return current, next

    def _transcription_to_pdf(self, width: int = 11) -> str:
        import typst

        preamble = f"""
#set page(
    width: {width}in,
    height: auto,
    margin: (
        top: 2in,
        bottom: 2in,
        left: 1in,
        right: 1in,
    ),
    fill: rgb("#fbfafa")
)

#set text(
    size: 18pt,
    hyphenate: false,
    font: (
        "Arial",
    )
)

#set par(
    justify: true,
    leading: 1em,
    first-line-indent: 0pt,
    linebreaks: "optimized",
)

#show emph: it => (
  text(rgb("#3f3f3f"), it.body)
)

"""
        formatted_texts: list[str] = []
        current_text = self.slides[0].transcription
        for next in range(1, len(self.slides)):
            current_text, next_text = self.fade_slide(current_text, self.slides[next].transcription)
            formatted_texts.append(current_text)
            current_text = next_text
        formatted_texts.append(current_text)

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(preamble.encode("utf-8"))
            f.write(
                "\n#pagebreak()\n".join(
                    [text for text in formatted_texts]
                ).encode("utf-8")
            )
            temp_file_name = f.name
            logging.debug(f"Typst temp file saved as {temp_file_name}")
        output = os.path.join(self._lecture_notes.path, "annotations.pdf")
        typst.compile(temp_file_name, output=output)
        return output
