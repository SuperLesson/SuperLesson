import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path

from superlesson.storage import LessonFile, Slides

from .step import Step, step

logger = logging.getLogger("superlesson")


@dataclass
class Page:
    text: str
    number: int


class Annotate:
    def __init__(self, slides: Slides, presentation: LessonFile):
        self._presentation = presentation
        self.slides = slides

    @step(Step.enumerate, Step.merge)
    def enumerate_slides_from_tframes(self):
        from pypdf import PdfReader

        max_slide_number = len(PdfReader(self._presentation.full_path).pages)

        def get_slide_number_from_user(
            default: int = max_slide_number - 1, is_last: bool = False
        ) -> int:
            if is_last:
                user_input = input(
                    f"What is the number of the last slide? (default: {default + 1}) "
                )
            else:
                user_input = input(
                    f"What is the number of this slide? (default: {default + 1}) "
                )

            if user_input == "":
                return default
            elif user_input.lower().startswith("n"):
                return 0

            try:
                number = int(user_input) - 1
            except ValueError:
                logger.warning(f"Invalid input: {user_input}")
                return default

            if -1 < number < max_slide_number:
                return number

            logger.warning(
                f"There's no such slide number: {number + 1} (should be between 1 and {max_slide_number})"
            )
            return default

        last_answer = -1
        for i, slide in enumerate(self.slides):
            path = slide.tframe
            if path is not None:
                self._sys_open(path)
                if last_answer < max_slide_number - 1:
                    suggestion = last_answer + 1
                else:
                    logger.debug("Repeating last suggestion")
                    suggestion = max_slide_number - 1
                number = get_slide_number_from_user(suggestion)
            else:
                assert i == len(self.slides) - 1, f"Slide {i} doesn't have a tframe"
                number = get_slide_number_from_user(is_last=True)

            if number == 0:
                logger.info("Slide will be hidden")
                # keep the default value for the next slide
                slide.number = -1
            else:
                # keep repeating
                if number >= max_slide_number:
                    logger.warning(
                        f"{number + 1} is greater than the number of slides provided ({max_slide_number}), using {max_slide_number}"
                    )
                    last_answer = max_slide_number - 1
                else:
                    if number == max_slide_number - 1:
                        logger.info("Reached last slide on presentation")
                    last_answer = number
                logger.debug("slide number: %d", last_answer)
                slide.number = last_answer

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

    @step(Step.annotate, Step.enumerate)
    def to_pdf(self):
        from pypdf import PdfReader, PdfWriter, Transformation

        pages = []
        # FIXME: (#110) typst complains about invalid syntax in some documents
        # current = self.slides[0].transcription
        # for i in range(1, len(self.slides)):
        #     current, next = self.fade_slide(
        #         current, self.slides[i].transcription
        #     )
        #     pages.append(current)
        #     current = next
        # pages.append(current)

        pdf = PdfReader(self._presentation.full_path)

        page_width = pdf.pages[0].mediabox.width
        page_height = pdf.pages[0].mediabox.height

        logger.debug(f"Original page size: {page_width} x {page_height}")

        def is_rectangle(width: float, height: float) -> bool:
            page_ratio = width / height
            squarish = 4 / 3
            default = 16 / 9
            # let's forgive badly cropped pages
            tolerance = 0.1
            # we don't want to use a range percentage as this is not linear
            return squarish * (1 - tolerance) < page_ratio < default * (1 + tolerance)

        if is_rectangle(page_width, page_height):
            logger.debug("Resizing to 10 inches")
            default_size = 10 * 72  # 10 inches
            ratio = default_size / page_width
            logger.debug("Scaling by %.2f", ratio)
            page_width = default_size
        else:
            ratio = 1
            logger.debug("Page aspect ratio is non-standard, scaling by 1")

        # as page_width is already scaled, we only need to translate in relation to the 70% scale
        # we will move halfway between the whitespace to the right
        x_translation = (1 - 0.7) / 2 * page_width
        logger.debug("Translating by %.2f", x_translation / 72)

        op = (
            Transformation()
            .scale(sx=0.7 * ratio, sy=0.7 * ratio)
            .translate(tx=x_translation, ty=0)
        )

        temp_pdf = PdfWriter()

        for page in pdf.pages:
            page.mediabox.upper_right = (
                page.mediabox.right * ratio,
                page.mediabox.top * 0.7 * ratio,  # cut top margin
            )
            page.add_transformation(op)
            temp_pdf.add_page(page)

        temp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        small_pdf_path = temp_file.name
        temp_pdf.write(small_pdf_path)
        logger.debug(f"scaled PDF saved as {small_pdf_path}")

        for slide in self.slides:
            number = slide.number

            if number < 0 or number is None:
                continue

            pages.append(Page(slide.transcription, number))

        # pt -> inch
        width_in = page_width // 72
        transcription_pdf = self._compile_with_typst(pages, width=width_in)

        merger = PdfWriter()
        for i, page in enumerate(pages):
            number = page.number
            logger.debug(f"Adding slide {number} to annotated PDF")
            merger.append(small_pdf_path, pages=(number, number + 1))
            logger.debug(f"Adding transcription to slide {i}")
            merger.append(transcription_pdf, pages=(i, i + 1))

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

    @classmethod
    def _compile_with_typst(cls, pages: list[Page], width: int = 10) -> str:
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

        with tempfile.NamedTemporaryFile(suffix=".typ", delete=False) as f:
            f.write(preamble.encode("utf-8"))
            f.write(
                "\u21E2 \n#pagebreak()\n \u21E2".join(
                    [page.text for page in pages]
                ).encode("utf-8")
            )
            temp_file_name = f.name
            logger.debug(f"Typst temp file saved as {temp_file_name}")

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            temp_output = f.name
            typst.compile(temp_file_name, output=temp_output)
            logger.debug(f"Typst temp pdf saved as {temp_output}")

        return temp_output
