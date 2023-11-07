import logging
import tempfile
from pathlib import Path

from superlesson.storage import LessonFile, Slides

from .step import Step

logger = logging.getLogger("superlesson")


class Annotate:
    def __init__(self, slides: Slides, presentation: LessonFile):
        self._presentation = presentation
        self.slides = slides

    @Step.step(Step.enumerate, Step.merge)
    def enumerate_slides_from_tframes(self):
        from pypdf import PdfReader

        max_slide_number = len(PdfReader(self._presentation.full_path).pages)

        def get_slide_number_from_user(default: int, is_first: bool = False) -> int:
            if is_first:
                user_input = input(
                    f"What is the number of the first slide? (default: {default}) "
                )
            else:
                user_input = input(
                    f"What is the number of this slide? (default: {default}) "
                )

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

            logger.warning(
                f"There's no such slide number: {number} (should be between 1 and {max_slide_number})"
            )
            return default

        last_answer = get_slide_number_from_user(1, True)
        if last_answer > max_slide_number:
            last_answer = max_slide_number
        logger.debug("First slide number: %d", last_answer - 1)
        self.slides[0].number = last_answer - 1

        for i in range(1, len(self.slides)):
            slide = self.slides[i]
            path = slide.png_path
            assert path is not None, f"Slide {i} doesn't have a png_path"
            self._sys_open(path)
            last_answer = get_slide_number_from_user(last_answer + 1)
            if last_answer == 0:
                slide.number = None
                continue
            # if the user answered the last slide, we keep repeating
            # TODO:is there a better heuristic?
            if last_answer > max_slide_number:
                last_answer = max_slide_number
            logger.debug("slide number: %d", last_answer - 1)
            slide.number = last_answer - 1

    @staticmethod
    def _sys_open(path: Path) -> int:
        import subprocess

        if not path.exists():
            logger.warning(f"File {path} doesn't exist")
            return 1

        ret_code = subprocess.call(["kitty", "+kitten", "icat", str(path)])
        if ret_code != 0:
            logger.warning(f"Error opening {path}")

        return ret_code

    @Step.step(Step.annotate, Step.enumerate)
    def to_pdf(self):
        from pypdf import PdfReader, PdfWriter, Transformation

        pdf = PdfReader(self._presentation.full_path)

        page_width = pdf.pages[0].mediabox.width
        # pt -> inch
        width_in = page_width / 72
        logger.debug(f"First page width: {width_in} inches")
        transcription_pdf = self._transcription_to_pdf(width=width_in)

        trans = PdfReader(transcription_pdf)
        op = (
            Transformation().scale(sx=0.7, sy=0.7).translate(tx=page_width * 0.15, ty=0)
        )

        merger = PdfWriter()
        for i, slide in enumerate(self.slides):
            number = slide.number

            if number is None:
                continue
            logger.debug(f"Adding slide {number} to annotated PDF")
            merger.append(fileobj=pdf, pages=(number, number + 1))
            page = merger.pages[-1]
            page.mediabox.upper_right = (
                page.mediabox.right,
                page.mediabox.top * 0.7,
            )  # cropping the top of each page
            page.add_transformation(op)
            logger.debug(f"Adding transcription to slide {i}")
            merger.append(fileobj=trans, pages=(i, i + 1))

        output = self._presentation.path / "annotations.pdf"
        merger.write(output)
        logger.info(f"Annotated PDF saved as {output}")

    @staticmethod
    def emphasize(text: str) -> str:
        return "_" + text + "_"

    @classmethod
    def fade_slide(
        cls, current: str, next: str, threshold: int = 20
    ) -> tuple[str, str]:
        dots = [".", "!", "?"]

        def text_before_dots(text: str, reverse: bool = False) -> tuple[int, int]:
            text = reversed(text) if reverse else text
            word_count = 0
            last_index = 0
            for index, char in enumerate(text):
                if char == " ":
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
        logger.debug(f"Fade in at word {words_in_current}")

        next_index, words_in_next = text_before_dots(next, False)
        logger.debug(f"Fade out at word {words_in_next}")

        current_emphasized = cls.emphasize(current[-current_index:] + " \u21E2")
        logger.debug(f"Fade in text: {current_emphasized}")
        current = current[:-current_index] + current_emphasized
        next_emphasized = cls.emphasize("\u21E2 " + next[:next_index])
        logger.debug(f"Fade out text: {next_emphasized}")
        next = next_emphasized + next[next_index:]

        return current, next

    def _transcription_to_pdf(self, width: int = 11) -> str:
        import typst

        preamble = f"""
#set page(
    width: {width}in,
    height: auto,
    margin: (
        top: 0.5in,
        bottom: 0.5in,
        left: 1.5in,
        right: 1.5in,
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
    leading: 0.65em,
    first-line-indent: 0pt,
    linebreaks: "optimized",
)

#show emph: it => (
  text(rgb("#000000"), it.body)
)

"""
        formatted_texts: list[str] = []
        current_text = self.slides[0].transcription
        for next in range(1, len(self.slides)):
            current_text, next_text = self.fade_slide(
                current_text, self.slides[next].transcription
            )
            formatted_texts.append(current_text)
            current_text = next_text
        formatted_texts.append(current_text)

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(preamble.encode("utf-8"))
            f.write(
                "\n#pagebreak()\n".join([text for text in formatted_texts]).encode(
                    "utf-8"
                )
            )
            temp_file_name = f.name
            logger.debug(f"Typst temp file saved as {temp_file_name}")

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            temp_output = f.name
            typst.compile(temp_file_name, output=temp_output)
            logger.debug(f"Typst temp pdf saved as {temp_output}")

        return temp_output
