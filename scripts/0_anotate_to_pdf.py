import os

import PyPDF2

lesson_id = ""
script_folder = os.getcwd()
root_folder = os.path.dirname(script_folder)
lesson_folder = root_folder + "/lessons/" + lesson_id
if not os.path.exists(lesson_folder):
    print("Lesson folder does not exist.")


def add_notes_to_pdf(input_file, output_file, note_texts):
    input_pdf = PyPDF2.PdfReader(input_file)
    if input_pdf.is_encrypted:
        input_pdf.decrypt()  # If there's a password, replace the empty string with the password
    output_pdf = PyPDF2.PdfWriter()

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
            note = PyPDF2.generic.DictionaryObject({
                PyPDF2.generic.NameObject("/Type"): PyPDF2.generic.NameObject("/Annot"),
                PyPDF2.generic.NameObject("/Subtype"): PyPDF2.generic.NameObject("/Text"),
                PyPDF2.generic.NameObject("/Rect"): PyPDF2.generic.ArrayObject([
                    PyPDF2.generic.NumberObject(x),
                    PyPDF2.generic.NumberObject(y),
                    PyPDF2.generic.NumberObject(x + 30),
                    PyPDF2.generic.NumberObject(y + 30),
                ]),
                PyPDF2.generic.NameObject("/Contents"): PyPDF2.generic.create_string_object(note_texts[index]),
                PyPDF2.generic.NameObject("/Open"): PyPDF2.generic.BooleanObject(True),
                PyPDF2.generic.NameObject("/Name"): PyPDF2.generic.NameObject("/Comment"),
            })

            # Add the note annotation to the page
            if "/Annots" not in page:
                page[PyPDF2.generic.NameObject("/Annots")] = PyPDF2.generic.ArrayObject()

            page["/Annots"].append(note)

        output_pdf.add_page(page)

    with open(output_file, "wb") as output_file_handle:
        output_pdf.write(output_file_handle)


# Usage example
input_file = lesson_folder + "/" + lesson_id + ".pdf"
output_file = lesson_folder + "/" + lesson_id + "_transcrita.pdf"

# add_notes_to_pdf(input_file, output_file, transcription_per_page)

N = len(PyPDF2.PdfReader(input_file).pages)
blank_transcriptions = [""] * N

add_notes_to_pdf(input_file, output_file, blank_transcriptions)

# BUG:
# for lesson_id = "2023-05-22_uc05_teste_cardiopulmonar_esforco". Comments won't go to the right corner, but to the left

# "LIMPA" O PDF
# input_file = "2023-05-02_uc10_nervos.pdf"
# output_file = "2023-05-02_uc10_nervos_cleaned.pdf"

# def clean_pdf(input_file, output_file):
#     reader = PdfReader(input_file)
#     writer = PdfWriter()

#     for i in range(reader.getNumPages()):
#         page = reader.getPage(i)
#         writer.addPage(page)

#     with open(output_file, "wb") as output_pdf:
#         writer.write(output_pdf)

# clean_pdf(input_file, output_file)
