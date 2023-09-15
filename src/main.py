from argparse import ArgumentParser, Namespace

from annotate import Annotate
from transcribe import Transcribe
from transitions import Transitions
from utils import LessonFiles


def main(args: Namespace):
    lesson_files = LessonFiles(args.lesson)
    lesson_root = lesson_files.lesson_root

    transcribe = Transcribe(lesson_root)
    transcription_source = lesson_files.transcription_source
    transcription_output = transcribe.single_file(transcription_source)
    input("Press Enter to continue...")
    transitions = Transitions(lesson_root)
    tmarks_path = transitions.insert_tmarks(transcription_source, transcription_output)
    input("Press Enter to continue...")
    transitions.verify_tbreaks_with_mpv(transcription_source)
    input("Press Enter to continue...")
    replacement_path = transcribe.replace_words(tmarks_path)
    if replacement_path is not None:
        input("Press Enter to continue...")
    else:
        replacement_path = tmarks_path
    improved_path = transcribe.improve_transcription(replacement_path)
    transcribe.check_differences(replacement_path, improved_path)
    input("Press Enter to continue...")
    annotate = Annotate(lesson_root)
    annotate.to_pdf(lesson_files.lecture_notes)


def parse_args() -> Namespace:
    parser = ArgumentParser(
        prog="SuperLesson",
        description="CLI to transcribe lectures",
    )
    parser.add_argument("lesson",
                        help="Lesson name or path to lesson directory")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args)
