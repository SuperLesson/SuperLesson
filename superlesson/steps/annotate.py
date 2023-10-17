import logging
import os
import tempfile

import pypdf
import typst

from superlesson.storage import LessonFile, Slides

from .step import Step


class Annotate:
    """Class to annotate a lesson."""

    def __init__(self, slides: Slides, lecture_notes: LessonFile):
        self._lecture_notes = lecture_notes
        self.slides = slides

    @Step.step(Step.annotate, Step.insert_tmarks)
    def to_pdf(self):
        with open(self._lecture_notes.full_path, "rb") as a:
            pdf = pypdf.PdfReader(a)
            w = (
                pdf.pages[0].mediabox.width / 72
            )  # dividing by 72 to do pt to inch conversion
            logging.debug(f"Slide width: {w}")
            output = self._transcription_to_pdf(w)
            with open(output, "rb") as t:
                trans = pypdf.PdfReader(t)
                merger = pypdf.PdfWriter()
                for i in range(len(pdf.pages)):
                    merger.append(fileobj=pdf, pages=(i, i + 1))
                    if i < len(trans.pages):
                        merger.append(fileobj=trans, pages=(i, i + 1))

        with open(output, "wb") as f:
            merger.write(f)
        logging.info(f"Annotated PDF saved as {output}")

    def _transcription_to_pdf(self, w) -> str:
        preamble = f"""
#set page(
    width: {w}in,
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

"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(preamble.encode("utf-8"))
            f.write(
                "\n#pagebreak()\n".join(
                    [slide.transcription for slide in self.slides]
                ).encode("utf-8")
            )
            temp_file_name = f.name
            logging.debug(f"Typst temp file saved as {temp_file_name}")
        output = os.path.join(self._lecture_notes.path, "annotations.pdf")
        typst.compile(temp_file_name, output=output)
        return output
