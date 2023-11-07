import logging
import subprocess
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Any

from .steps import Annotate, Transcribe, Transitions
from .steps.step import Step
from .storage import LessonFiles, Slides
from .storage.lesson import FileType
from .storage.utils import find_lesson_root

logging.basicConfig(
    format="%(asctime)s.%(msecs)03d - %(name)s:%(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
    level=logging.WARNING,
)
logger = logging.getLogger("superlesson")


def main():
    args = parse_args()
    set_log_level(args)

    if args.diff is not None:
        step1 = Step[args.diff[0]]
        step2 = Step[args.diff[1]]
        if step1 == step2:
            raise Exception("Cannot compare the same step")
        if step1 > step2:
            step1, step2 = step2, step1
        check_differences(args.lesson, step1, step2)
        return

    lesson_files = LessonFiles(args.lesson, args.transcribe_with, args.annotate_with)

    slides = Slides(lesson_files.lesson_root, args.debug)
    transcribe = Transcribe(slides, lesson_files.transcription_source)
    if args.with_docker:
        run_docker()
    else:
        transcribe.single_file(args.model_size, args.transcribe_locally)
    input("Press Enter to continue...")
    # TODO: Add option to use audio as source for transcription
    if lesson_files.transcription_source.file_type == FileType.audio:
        raise NotImplementedError("Transcribing from audio is not implemented yet")
    transitions = Transitions(slides, lesson_files.transcription_source)
    transitions.merge_segments(args.use_silences)
    input("Press Enter to continue...")
    annotate = Annotate(slides, lesson_files.presentation)
    annotate.enumerate_slides_from_tframes()
    input("Press Enter to continue...")
    transcribe.replace_words()
    input("Press Enter to continue...")
    transcribe.improve_punctuation()
    input("Press Enter to continue...")
    if lesson_files.presentation.file_type == FileType.video:
        raise NotImplementedError("Annotating from video is not implemented yet")
    annotate.to_pdf()


def parse_args() -> Namespace:
    parser = ArgumentParser(
        prog="SuperLesson",
        description="CLI to transcribe lectures",
    )
    parser.add_argument("lesson", help="Lesson name or path to lesson directory")
    parser.add_argument(
        "--diff",
        default=None,
        nargs=2,
        choices=[step.name for step in Step if step.value.in_storage()],
        help="Diff between two steps",
    )
    parser.add_argument(
        "--transcribe-with",
        type=Path,
        default=None,
        help="Path to transcription source (has to be a video file)",
    )
    parser.add_argument(
        "--annotate-with",
        type=Path,
        default=None,
        help="Path to annotation source (has to be a PDF file)",
    )
    parser.add_argument(
        "--model-size",  # model only works with pt now
        choices=[
            "tiny",  # "tiny.en",
            "base",  # "base.en",
            "small",  # "small.en",
            "medium",  # "medium.en",
            "large-v1",
            "large-v2",
            "large",
        ],
        default="large-v2",
        help="Choose whisper model size",
    )
    parser.add_argument(
        "--transcribe-locally",
        action="store_true",
        help="Use faster whisper to transcribe locally",
    )
    parser.add_argument(
        "--use-silences",
        action="store_true",
        help="Use silences to improve transition times",
    )
    parser.add_argument(
        "--with-docker",
        action="store_true",
        help="Run transcription step using the docker environment",
    )
    mut_group = parser.add_mutually_exclusive_group()
    mut_group.add_argument(
        "--verbose", "-v", action="store_true", help="Increase output verbosity"
    )
    mut_group.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Print debug information and save step outputs as txt",
    )
    return parser.parse_args()


def set_log_level(args: Namespace):
    if args.debug:
        logger.setLevel(logging.DEBUG)
    elif args.verbose:
        logger.setLevel(logging.INFO)


def single_step_setup(_class: Any) -> tuple[Namespace, Any]:
    args = parse_args()
    set_log_level(args)

    lesson_files = LessonFiles(args.lesson, args.transcribe_with, args.annotate_with)

    slides = Slides(lesson_files.lesson_root, args.debug)
    if _class is Annotate:
        instance = _class(slides, lesson_files.presentation)
    else:
        instance = _class(slides, lesson_files.transcription_source)
    return args, instance


def transcribe_step():
    args, transcribe = single_step_setup(Transcribe)

    if args.with_docker:
        run_docker()
    else:
        transcribe.single_file(args.model_size, args.transcribe_locally)


def run_docker():
    subprocess.run(["docker", "build", "-t", "superlesson", "."])
    subprocess.run(
        [
            "docker",
            "run",
            "-it",
            "--rm",
            "--name",
            "superlesson",
            "-v",
            "./lessons:/SuperLesson/lessons",
            "--gpus",
            "all",
            "superlesson",
            "poetry",
            "run",
            "transcribe",
        ]
        + [arg for arg in sys.argv[1:] if arg != "--with-docker"]
    )


def check_differences(lesson: str, prev: Step, next: Step):
    lesson_root = find_lesson_root(lesson)
    prev_slides = Slides(lesson_root)
    prev_slides.load_step(prev)
    prev_file = prev_slides.save_temp_txt()

    next_slides = Slides(lesson_root)
    next_slides.load_step(next)
    next_file = next_slides.save_temp_txt()

    logger.debug("Running wdiff")

    subprocess.run(
        " ".join(
            [
                "wdiff",
                "-n -w $'\033[30;41m' -x $'\033[0m' -y $'\033[30;42m' -z $'\033[0m'",
                str(prev_file),
                str(next_file),
            ]
        ),
        shell=True,
    )


def merge_step():
    args, transitions = single_step_setup(Transitions)
    transitions.merge_segments(args.use_silences)


def replace_step():
    _, transcribe = single_step_setup(Transcribe)
    transcribe.replace_words()


def improve_step():
    _, transcribe = single_step_setup(Transcribe)
    transcribe.improve_punctuation()


def enumerate_step():
    _, annotate = single_step_setup(Annotate)
    annotate.enumerate_slides_from_tframes()


def annotate_step():
    _, annotate = single_step_setup(Annotate)
    annotate.to_pdf()
