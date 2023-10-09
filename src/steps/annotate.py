import logging

import pypdf
from storage import LessonFile, Slides

from .step import Step


class Annotate:
    """Class to annotate a lesson."""

    def __init__(self, slides: Slides, lecture_notes: LessonFile):
        self._lecture_notes = lecture_notes
        self.slides = slides

    @Step.step(Step.annotate, Step.insert_tmarks)
    def to_pdf(self):
        N = len(pypdf.PdfReader(self._lecture_notes.full_path).pages)
        blank_transcription = [""] * N

        self._add_notes_to_pdf(blank_transcription)

    def _add_notes_to_pdf(self, note_texts):
        lesson_notes = self._lecture_notes.full_path
        input_pdf = pypdf.PdfReader(lesson_notes)
        if input_pdf.is_encrypted:
            # If there's a password, replace the empty string with the password
            input_pdf.decrypt("")
        output_pdf = pypdf.PdfWriter()

        for index in range(len(input_pdf.pages)):
            page = input_pdf.pages[index]

            # Check if there"s a note for this page
            if index < len(note_texts):
                # Get the page size
                page_width, page_height = page.mediabox.upper_right

                # Calculate the x and y coordinates for the top right corner
                x = page_width - 50  # Subtract 50 to account for the width of the note
                y = page_height - 35  # 30 muito pouco, 40 muito
                # iterei por algum tempo nos valores de x e y, esses foram os melhores pois:
                # se encaixam em slides muito cheios e atendem também ao mobile

                # Create a new note annotation
                note = pypdf.generic.DictionaryObject({
                    pypdf.generic.NameObject("/Type"): pypdf.generic.NameObject("/Annot"),
                    pypdf.generic.NameObject("/Subtype"): pypdf.generic.NameObject("/Text"),
                    pypdf.generic.NameObject("/Rect"): pypdf.generic.ArrayObject([
                        pypdf.generic.NumberObject(x),
                        pypdf.generic.NumberObject(y),
                        pypdf.generic.NumberObject(x + 30),
                        pypdf.generic.NumberObject(y + 30),
                    ]),
                    pypdf.generic.NameObject("/Contents"): pypdf.generic.create_string_object(note_texts[index]),
                    pypdf.generic.NameObject("/Open"): pypdf.generic.BooleanObject(True),
                    pypdf.generic.NameObject("/Name"): pypdf.generic.NameObject("/Comment"),
                })

                # Add the note annotation to the page
                if "/Annots" not in page:
                    page[pypdf.generic.NameObject(
                        "/Annots")] = pypdf.generic.ArrayObject()

                page["/Annots"].append(note)

            output_pdf.add_page(page)

        output_path = self._lecture_notes.path / "transcription.pdf"
        logging.info(f"Saving annotated pdf to {output_path}")
        with open(output_path, "wb") as f:
             output_pdf.write(f)
