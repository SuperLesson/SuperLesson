import logging
import subprocess
from dataclasses import dataclass

import click

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


@dataclass
class Context:
    lesson_files: LessonFiles
    slides: Slides


@click.group(invoke_without_command=True)
@click.argument("lesson")
@click.option(
    "--transcribe-with",
    "-t",
    type=click.Path(),
    help="Path for transcribe configuration.",
)
@click.option(
    "--annotate-with", "-a", type=click.Path(), help="Path for annotate configuration."
)
@click.option("--verbose", "-v", is_flag=True, help="Enables verbose mode.")
@click.option("--debug", is_flag=True, help="Enables verbose mode.")
@click.pass_context
def cli(ctx, lesson, transcribe_with, annotate_with, verbose, debug):
    """Your CLI application for processing lessons."""
    if ctx.invoked_subcommand == "diff":
        return

    lesson_files = LessonFiles(lesson, transcribe_with, annotate_with)
    ctx.obj = Context(
        lesson_files,
        Slides(lesson_files.lesson_root, verbose),
    )

    if debug:
        logger.setLevel(logging.DEBUG)
    elif verbose:
        logger.setLevel(logging.INFO)

    if ctx.invoked_subcommand is not None:
        return

    ctx.invoke(transcribe)
    input("Press Enter to merge segments.")
    ctx.invoke(merge)
    input("Press Enter to replace words.")
    ctx.invoke(replace)
    input("Press Enter to improve text.")
    ctx.invoke(improve)
    input("Press Enter to enumerate slides.")
    ctx.invoke(enumerate)
    input("Press Enter to annotate.")
    if lesson_files.presentation.file_type == FileType.video:
        msg = "Annotating from video is not implemented yet"
        raise NotImplementedError(msg)
    annotate.to_pdf()


@cli.command()
@click.pass_context
def transcribe(ctx):
    """Transcribe a LESSON."""
    from .steps import Transcribe

    Transcribe(ctx.obj.slides, ctx.obj.lesson_files.transcription_source).single_file()


@cli.command()
@click.pass_context
def merge(ctx):
    """Merge words."""
    from .steps import Transitions

    Transitions(
        ctx.obj.slides, ctx.obj.lesson_files.transcription_source
    ).merge_segments()


@cli.command()
@click.pass_context
def enumerate(ctx):
    """Enumerate slides."""
    from .steps import Annotate

    Annotate(
        ctx.obj.slides, ctx.obj.lesson_files.presentation
    ).enumerate_slides_from_tframes()


@cli.command()
@click.pass_context
def replace(ctx):
    """Replace bogus words."""
    from .steps import Transcribe

    Transcribe(
        ctx.obj.slides, ctx.obj.lesson_files.transcription_source
    ).replace_words()


@cli.command()
@click.pass_context
def improve(ctx):
    """Improve text."""
    from .steps import Transcribe

    Transcribe(
        ctx.obj.slides, ctx.obj.lesson_files.transcription_source
    ).improve_punctuation()


@cli.command()
@click.option(
    "--to-pdf", "output_format", flag_value="pdf", help="Output annotation to PDF."
)
@click.option(
    "--to-gdoc",
    "output_format",
    flag_value="gdoc",
    default=True,
    help="Output annotation to Google Doc.",
)
@click.pass_context
def annotate(ctx, output_format):
    """Annotate a LESSON."""
    from .steps import Annotate

    annotate = Annotate(ctx.obj.slides, ctx.obj.lesson_files.presentation)
    if output_format == "pdf":
        annotate.to_pdf()
    else:
        msg = "Google Doc output is not implemented yet."
        raise NotImplementedError(msg)


@cli.command()
@click.argument("lesson")
@click.argument("previous", type=click.Choice([step.name for step in Step]))
@click.argument("next", type=click.Choice([step.name for step in Step]))
def diff(lesson, previous, next):
    """Show differences in a LESSON from ."""
    lesson_root = find_lesson_root(lesson)
    prev_slides = Slides(lesson_root)
    prev_slides.load_step(previous)
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


if __name__ == "__main__":
    print("meow")
    cli()
