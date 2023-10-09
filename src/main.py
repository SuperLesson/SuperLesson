import logging
from argparse import ArgumentParser, Namespace

from steps import Annotate, Transcribe, Transitions
from storage import LessonFiles, Slides
from storage.lesson import FileType


def main(args: Namespace):
    lesson_files = LessonFiles(
        args.lesson, args.transcribe_with, args.annotate_with)

    slides = Slides(lesson_files.lesson_root, args.run_all)
    transcribe = Transcribe(slides, lesson_files.transcription_source)
    transcribe.single_file()
    input("Press Enter to continue...")
    # TODO: Add option to use audio as source for transcription
    if lesson_files.transcription_source.file_type == FileType.audio:
        raise NotImplementedError(
            "Transcribing from audio is not implemented yet")
    transitions = Transitions(slides, lesson_files.transcription_source)
    transitions.insert_tmarks()
    input("Press Enter to continue...")
    transitions.verify_tbreaks_with_mpv()
    input("Press Enter to continue...")
    transcribe.replace_words()
    input("Press Enter to continue...")
    transcribe.improve_punctuation()
    # TODO: fix this
    # transcribe.check_differences(replacement_path, improved_path)
    input("Press Enter to continue...")
    if lesson_files.lecture_notes.file_type == FileType.video:
        raise NotImplementedError(
            "Annotating from video is not implemented yet")
    annotate = Annotate(slides, lesson_files.lecture_notes)
    annotate.to_pdf()


def parse_args() -> Namespace:
    parser = ArgumentParser(
        prog="SuperLesson",
        description="CLI to transcribe lectures",
    )
    parser.add_argument("lesson",
                        help="Lesson name or path to lesson directory")
    parser.add_argument("--transcribe-with",
                        choices=[FileType.video.value, FileType.audio.value],
                        default=None,
                        help="Use audio or video file for transcription")
    parser.add_argument("--annotate-with",
                        choices=[FileType.notes.value, FileType.video.value],
                        default=None,
                        help="Use text/pdf or video as source for lecture notes")
    parser.add_argument("--run-all",
                        action="store_true",
                        help="Run all steps")
    mut_group = parser.add_mutually_exclusive_group()
    mut_group.add_argument("--verbose", "-v",
                           action="store_true",
                           help="Increase output verbosity")
    mut_group.add_argument("--debug", "-d",
                           action="store_true",
                           help="Print debug information")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    elif args.verbose:
        logging.basicConfig(level=logging.INFO)
    main(args)
