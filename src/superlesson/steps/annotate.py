import logging
from collections.abc import Sequence
from pathlib import Path

from superlesson.storage import Slides
from superlesson.storage.slide import Page
from superlesson.storage.utils import mktemp

from .step import Step, step

logger = logging.getLogger("superlesson")


class Annotate:
    def __init__(self, slides: Slides, presentation: Path):
        self._presentation = presentation
        self.slides = slides

    @step(Step.annotate, Step.enumerate)
    def to_pdf(self):
        from pypdf import PdfReader, PdfWriter

        pages = self.slides.as_pages()
        small_pdf = self._resize_and_scale(self._presentation, scale=0.7)

        page_width = int(PdfReader(small_pdf).pages[0].mediabox.width / 72)
        transcription_pdf = self._compile_with_typst(pages, width=page_width)

        merger = PdfWriter()
        for i, page in enumerate(pages):
            number = page.number
            logger.debug(f"Adding slide {number} to annotated PDF")
            merger.append(small_pdf, pages=(number, number + 1))
            logger.debug(f"Adding transcription to slide {i}")
            merger.append(transcription_pdf, pages=(i, i + 1))

        output = self._presentation.parent / "annotations.pdf"
        merger.write(output)
        logger.info(f"Annotated PDF saved as {output}")

    @classmethod
    def _resize_and_scale(
        cls, pdf_path: Path, width: int = 10, scale: float = 1
    ) -> Path:
        from pypdf import PdfReader, PdfWriter, Transformation

        pdf = PdfReader(pdf_path)

        # pypdf uses pt as default unit
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
            logger.debug(f"Resizing to {width} inches")
            default_size = width * 72
            ratio = default_size / page_width
            logger.debug("Scaling by %.2f", ratio)
            page_width = default_size
        else:
            ratio = 1
            logger.debug("Page aspect ratio is non-standard, scaling by 1")

        # we will move halfway between the whitespace to the right
        x_translation = (1 - scale) / 2 * page_width
        logger.debug("Translating by %.2f", x_translation / 72)

        op = (
            Transformation()
            .scale(sx=scale * ratio, sy=scale * ratio)
            .translate(tx=x_translation, ty=0)
        )

        temp_pdf = PdfWriter()
        for page in pdf.pages:
            page.mediabox.upper_right = (
                page.mediabox.right * ratio,
                page.mediabox.top * scale * ratio,  # cut top margin
            )
            page.add_transformation(op)
            temp_pdf.add_page(page)

        rescaled_pdf = mktemp(suffix=".pdf")
        temp_pdf.write(rescaled_pdf)
        logger.debug(f"scaled PDF saved as {rescaled_pdf}")
        return rescaled_pdf

    # FIXME: (#110) typst complains about invalid syntax in some documents
    @classmethod
    def _fade_slide(
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

        def emphasize(text: str) -> str:
            return "_" + text + "_"

        current_emphasized = emphasize(current[-current_index:] + " \u21E2")
        logger.debug(f"Fade in text: {current_emphasized}")
        current = current[:-current_index] + current_emphasized
        next_emphasized = emphasize("\u21E2 " + next[:next_index])
        logger.debug(f"Fade out text: {next_emphasized}")
        next = next_emphasized + next[next_index:]

        return current, next

    @classmethod
    def _compile_with_typst(cls, pages: Sequence[Page], width: int = 10) -> Path:
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

        with (typ_out := mktemp(suffix=".typ")).open("wb") as f:
            f.write(preamble.encode("utf-8"))
            f.write(
                "\u21E2 \n#pagebreak()\n \u21E2".join(
                    [page.text for page in pages]
                ).encode("utf-8")
            )
        logger.debug(f"Typst temp file saved as {typ_out}")

        temp_output = mktemp(suffix=".pdf")
        typst.compile(typ_out, output=temp_output)
        logger.debug(f"Typst temp pdf saved as {temp_output}")

        return temp_output
