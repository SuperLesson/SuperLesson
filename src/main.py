from argparse import ArgumentParser, Namespace

from annotate import Annotate
from transcribe import Transcribe
from transitions import Transitions


def main(args: Namespace):
    lesson_id = args.lesson_id

    transcribe = Transcribe(lesson_id)
    transcribe.single_file()
    input("Press Enter to continue...")
    transitions = Transitions(lesson_id)
    transitions.insert_tmarks()
    input("Press Enter to continue...")
    transitions.verify_tbreaks_with_mpv()
    input("Press Enter to continue...")
    transcribe.replace_words()
    input("Press Enter to continue...")
    transcribe.improve_transcription()
    input("Press Enter to continue...")
    transcribe.check_differences()
    input("Press Enter to continue...")
    annotate = Annotate(lesson_id)
    annotate.to_pdf()


def parse_args() -> Namespace:
    parser = ArgumentParser(
        prog="SuperLesson",
        description="CLI to transcribe lectures",
    )
    parser.add_argument("lesson_id")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args)
