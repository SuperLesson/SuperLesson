import logging
import subprocess
from dataclasses import dataclass

import click

from .collection import Lesson
from .steps.step import Step
from .storage import Slides

logging.basicConfig(
    format="%(asctime)s.%(msecs)03d - %(name)s:%(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
    level=logging.WARNING,
)
logger = logging.getLogger("superlesson")


@dataclass
class Context:
    lesson: Lesson
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
@click.version_option()
@click.pass_context
def cli(ctx, lesson, transcribe_with, annotate_with, verbose, debug):
    """Your CLI application for processing lessons."""
    lesson = Lesson(lesson, transcribe_with, annotate_with)
    ctx.obj = Context(
        lesson,
        Slides(lesson.root, verbose),
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
    ctx.invoke(annotate)


@cli.command()
@click.pass_context
def transcribe(ctx):
    """Transcribe a LESSON."""
    from .steps import Transcribe

    Transcribe(ctx.obj.slides, ctx.obj.lesson.video).single_file()


@cli.command()
@click.pass_context
def merge(ctx):
    """Merge words."""
    from .steps import Merge

    Merge(ctx.obj.slides).segments()


@cli.command()
@click.pass_context
def replace(ctx):
    """Replace bogus words."""
    from .steps import Transcribe

    Transcribe(ctx.obj.slides, ctx.obj.lesson.video).replace_words()


@cli.command()
@click.pass_context
def improve(ctx):
    """Improve text."""
    from .steps import Transcribe

    Transcribe(ctx.obj.slides, ctx.obj.lesson.video).improve_punctuation()


@cli.command()
@click.pass_context
def enumerate(ctx):
    """Enumerate slides."""
    from .steps import Enumerate

    Enumerate(ctx.obj.slides, ctx.obj.lesson.presentation).using_tframes()


@cli.command()
@click.pass_context
def annotate(ctx):
    """Annotate to PDF."""
    from .steps import Annotate

    annotate = Annotate(ctx.obj.slides, ctx.obj.lesson.presentation)
    annotate.to_pdf()


@cli.command()
@click.argument(
    "previous",
    type=click.Choice([step.name for step in Step if step.value.in_storage()]),
)
@click.argument(
    "next", type=click.Choice([step.name for step in Step if step.value.in_storage()])
)
@click.pass_context
def diff(ctx, previous, next):
    """Show differences in a LESSON from ."""
    root = ctx.obj.lesson.root
    prev_slides = Slides(root)
    prev_slides.load_step(Step[previous])
    prev_file = prev_slides.save_temp_txt()

    next_slides = Slides(root)
    next_slides.load_step(Step[next])
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
