import logging
import re
import subprocess
import tempfile
from datetime import timedelta
from pathlib import Path
from textwrap import fill

logger = logging.getLogger("superlesson")


def format_transcription(text: str) -> str:
    lines = text.splitlines()
    paragraphs = []
    current_para = []
    for line in lines:
        if line == "":
            if current_para:
                paragraphs.append(current_para)
                current_para = []
        else:
            line = re.sub(r"\s+", " ", line)
            current_para.append(line)

    if current_para:
        paragraphs.append(current_para)

    return "\n\n".join(
        [fill(" ".join(para), width=120, tabsize=4) for para in paragraphs]
    )


def seconds_to_timestamp(s: float) -> str:
    timestamp = str(timedelta(seconds=s))
    if "." in timestamp:
        timestamp = timestamp[:-3]
    return timestamp


def diff_words(before: Path, after: Path):
    start_red = r"$'\033[30;41m'"
    start_green = r"$'\033[30;42m'"
    reset = r"$'\033[0m'"

    subprocess.run(
        " ".join(
            [
                "wdiff",
                "-n",
                "-w",
                start_red,
                "-x",
                reset,
                "-y",
                start_green,
                "-z",
                reset,
                str(before),
                str(after),
            ],
        ),
        shell=True,
    )


def extract_audio(
    video: Path,
    audio_codec: str = "pcm_s16le",
    channels: int = 1,
    sample_rate: int = 16000,
) -> Path:
    output_path = mktemp(suffix=".wav")

    logger.info(f"Extracting audio from {video}")
    subprocess.run(
        [  # noqa: S607
            "ffmpeg",
            "-loglevel",
            "quiet",
            "-i",
            video,
            "-vn",
            "-acodec",
            str(audio_codec),
            "-ac",
            str(channels),
            "-ar",
            str(sample_rate),
            output_path,
        ],
        stdout=subprocess.DEVNULL,
    )

    logger.debug(f"Audio saved as {output_path}")
    return output_path


def mktemp(suffix: str = "") -> Path:
    return Path(tempfile.NamedTemporaryFile(suffix=suffix, delete=False).name)
