import logging
import os
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from superlesson.storage import Slide, Slides
from superlesson.storage.slide import TimeFrame
from superlesson.storage.utils import extract_audio

from .step import Step, step

logger = logging.getLogger("superlesson")


@dataclass
class Segment:
    text: str
    start: float
    end: float


@dataclass
class Prompt:
    body: str
    slide: int = 0


class Transcribe:
    _bucket_name = "lesson-audios"

    def __init__(self, slides: Slides, video: Path):
        from dotenv import load_dotenv

        load_dotenv()

        self._video = video
        self.slides = slides

    @step(Step.transcribe)
    def single_file(self):
        bench_start = time.time()

        s3_url = self._upload_file_to_s3(extract_audio(self._video))

        bench_duration = time.time() - bench_start
        logger.info(f"Took {bench_duration} to upload to S3")

        if not os.getenv("REPLICATE_API_TOKEN"):
            msg = "See README.md for instructions on how to set up your environment to run superlesson."
            raise Exception(msg)

        for segment in self._transcribe_with_replicate(s3_url):
            self.slides.append(
                Slide(segment.text, TimeFrame(segment.start, segment.end))
            )

        bench_duration = time.time() - bench_start
        logger.info(f"Transcription took {bench_duration} to finish")

    @classmethod
    def _transcribe_with_replicate(cls, url: str) -> list[Segment]:
        import replicate

        logger.info("Running replicate")
        output = replicate.run(
            "isinyaaa/whisperx:f2f27406afdd5f2bd8aab728e9c50eec8378dcf67381b42009051a156d83ddba",
            input={
                "audio": url,
                "language": "pt",
                "batch_size": 13,
                "align_output": True,
            },
        )
        logger.info("Replicate finished")
        assert isinstance(output, dict), "Expected a dict"
        segments = []
        for segment in output["word_segments"]:
            if "start" in segment:
                segments.append(
                    Segment(segment["word"], segment["start"], segment["end"])
                )
            elif len(segments) != 0:
                segments[-1].text += " " + segment["word"]
        return segments

    @classmethod
    def _upload_file_to_s3(cls, path: Path) -> str:
        import boto3
        from botocore.exceptions import ClientError

        s3 = boto3.client("s3")

        # TODO: we should salt it to improve privacy
        # ideally, we should also encrypt the data, or figure out a way to
        # authenticate from replicate
        with open(path, "rb") as file:
            data = file.read()
            s3_name = sha256(data).hexdigest()

        s3_path = f"https://{cls._bucket_name}.s3.amazonaws.com/{s3_name}"

        try:
            s3.head_object(Bucket=cls._bucket_name, Key=s3_name)
            return s3_path
        except ClientError:
            pass

        logger.info(f"Uploading file {file} to S3")

        s3.upload_file(path, cls._bucket_name, s3_name)

        logger.info(f"{file} uploaded to S3 as {s3_name}")
        return s3_path
