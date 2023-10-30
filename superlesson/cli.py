import sys
import logging
import subprocess
from argparse import ArgumentParser, Namespace
from typing import Any, Tuple

from .steps import Annotate, Transcribe, Transitions
from .storage import LessonFiles, Slides
from .storage.lesson import FileType


def main():
    args = parse_args()
    set_log_level(args)

    lesson_files = LessonFiles(
        args.lesson, args.transcribe_with, args.annotate_with)

    slides = Slides(lesson_files.lesson_root)
    transcribe = Transcribe(slides, lesson_files.transcription_source)
    if args.with_docker:
        run_docker()
    else:
        transcribe.single_file(args.model_size)
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
    parser.add_argument("--model-size",  # model only works with pt now
                        choices=["tiny",  # "tiny.en",
                                 "base",  # "base.en",
                                 "small",  # "small.en",
                                 "medium",  # "medium.en",
                                 "large-v1", "large-v2", "large"],
                        default="large-v2",
                        help="Choose whisper model size")
    parser.add_argument("--with-docker",
                        action="store_true",
                        help="Run transcription step using the docker environment")
    mut_group = parser.add_mutually_exclusive_group()
    mut_group.add_argument("--verbose", "-v",
                           action="store_true",
                           help="Increase output verbosity")
    mut_group.add_argument("--debug", "-d",
                           action="store_true",
                           help="Print debug information")
    return parser.parse_args()

def set_log_level(args: Namespace):
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    elif args.verbose:
        logging.basicConfig(level=logging.INFO)

def single_step_setup(_class: Any) -> Tuple[Namespace, Any]:
    args = parse_args()
    set_log_level(args)

    lesson_files = LessonFiles(
        args.lesson, args.transcribe_with, args.annotate_with)

    slides = Slides(lesson_files.lesson_root)
    if _class is Annotate:
        instance = _class(slides, lesson_files.lecture_notes)
    else:
        instance = _class(slides, lesson_files.transcription_source)
    return args, instance


def transcribe_step():
    args, transcribe = single_step_setup(Transcribe)

    if args.with_docker:
        run_docker()
    else:
        transcribe.single_file(args.model_size)

def run_docker():
    subprocess.run(["docker", "build", "-t", "superlesson", "."])
    subprocess.run(
        [
            "docker", "run",
            "-it", "--rm",
            "--name", "superlesson",
            "-v", "./lessons:/SuperLesson/lessons",
            "--gpus", "all",
            "superlesson",
            "poetry", "run", "transcribe"
        ] + [
            arg
            for arg in sys.argv[1:]
            if arg != "--with-docker"
        ]
    )


def tmarks_step():
    _, transitions = single_step_setup(Transitions)
    transitions.insert_tmarks()


def verify_step():
    _, transitions = single_step_setup(Transitions)
    transitions.verify_tbreaks_with_mpv()


def replace_step():
    _, transcribe = single_step_setup(Transcribe)
    transcribe.replace_words()


def improve_step():
    _, transcribe = single_step_setup(Transcribe)
    transcribe.improve_punctuation()


def annotate_step():
    _, annotate = single_step_setup(Annotate)
    annotate.to_pdf()
