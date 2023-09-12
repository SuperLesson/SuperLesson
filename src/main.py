from argparse import ArgumentParser

from annotate import Annotate
from transcribe import Transcribe
from transitions import Transitions


def main():
    parser = ArgumentParser(
        prog="SuperLesson",
        description="CLI to transcribe lectures",
    )
    parser.add_argument("lesson_id")
    args = parser.parse_args()

    transcribe = Transcribe(args.lesson_id)
    transcribe.single_file()
    input("Press Enter to continue...")
    transitions = Transitions(args.lesson_id)
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
    annotate = Annotate(args.lesson_id)
    annotate.to_pdf()


if __name__ == "__main__":
    main()
