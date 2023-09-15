from argparse import ArgumentParser, Namespace

from annotate import Annotate
from transcribe import Transcribe
from transitions import Transitions
from utils import FileType, LessonFiles


def main(args: Namespace):
    lesson_files = LessonFiles(args.lesson, args.transcribe_with, args.annotate_with)
    lesson_root = lesson_files.lesson_root

    transcribe = Transcribe(lesson_root)
    transcription_source = lesson_files.transcription_source.path
    transcription_output = transcribe.single_file(transcription_source)
    input("Press Enter to continue...")
    # TODO: Add option to use audio as source for transcription
    if lesson_files.transcription_source.file_type == FileType.audio:
        raise NotImplementedError("Transcribing from audio is not implemented yet")
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
    if lesson_files.lecture_notes.file_type == FileType.video:
        raise NotImplementedError("Annotating from video is not implemented yet")
    annotate = Annotate(lesson_root)
    annotate.to_pdf(lesson_files.lecture_notes)


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
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args)
