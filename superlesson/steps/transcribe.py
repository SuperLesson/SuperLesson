import logging
from datetime import datetime
import time

from superlesson.storage import LessonFile, Slide, Slides

from .step import Step


logger = logging.getLogger("superlesson")


class Transcribe:
    """Class to transcribe a lesson."""

    def __init__(self, slides: Slides, transcription_source: LessonFile):
        self._transcription_source = transcription_source
        self.slides = slides

    @Step.step(Step.transcribe)
    def single_file(self, model_size: str):
        from faster_whisper import WhisperModel
        from os import cpu_count

        bench_start = datetime.now()

        if self._has_nvidia_gpu():
            model = WhisperModel(model_size, device="cuda", compute_type="int8_float16")
        else:
            model = WhisperModel(
                model_size, device="cpu", cpu_threads=cpu_count(), compute_type="auto"
            )

        segments, info = model.transcribe(
            str(self._transcription_source.full_path),
            beam_size=5,
            language="pt",
            vad_filter=True,
        )

        logger.info(
            f"Detected language {info.language} with probability {info.language_probability}"
        )
        segments = self._run_with_pbar(segments, info)

        for segment in segments:
            self.slides.append(Slide(segment.text, (segment.start, segment.end)))
            logger.info(
                "[%.2fs -> %.2fs] %s" % (segment.start, segment.end, segment.text)
            )

        bench_duration = datetime.now() - bench_start
        logger.info(f"Transcription took {bench_duration}")

    @staticmethod
    def _has_nvidia_gpu():
        from subprocess import check_output

        try:
            check_output("nvidia-smi")
            return True
        except Exception:
            return False

    # taken from https://github.com/guillaumekln/faster-whisper/issues/80#issuecomment-1565032268
    def _run_with_pbar(self, segments, info):
        import io
        from threading import Thread
        from tqdm import tqdm

        duration = round(info.duration)
        bar_f = "{percentage:3.0f}% |  {remaining}  | {rate_noinv_fmt}"
        print("  %  | remaining |  rate")

        capture = io.StringIO()  # capture progress bars from tqdm

        with tqdm(
            file=capture,
            total=duration,
            unit=" audio seconds",
            smoothing=0.00001,
            bar_format=bar_f,
        ) as pbar:
            global timestamp_prev, timestamp_last
            timestamp_prev = 0  # last timestamp in previous chunk
            timestamp_last = 0  # current timestamp
            last_burst = 0.0  # time of last iteration burst aka chunk
            set_delay = (
                0.1
            )  # max time it takes to iterate chunk & minimum time between chunks
            jobs = []
            transcription_segments = []
            for segment in segments:
                transcription_segments.append(segment)
                logger.info(
                    "[%.2fs -> %.2fs] %s" % (segment.start, segment.end, segment.text)
                )
                timestamp_last = round(segment.end)
                time_now = time.time()
                if time_now - last_burst > set_delay:  # catch new chunk
                    last_burst = time_now
                    job = Thread(
                        target=self._pbar_delayed(set_delay, capture, pbar),
                        daemon=False,
                    )
                    jobs.append(job)
                    job.start()

            for job in jobs:
                job.join()

            if timestamp_last < duration:  # silence at the end of the audio
                pbar.update(duration - timestamp_last)
                print(
                    "\33]0;" + capture.getvalue().splitlines()[-1] + "\a",
                    end="",
                    flush=True,
                )
                print(capture.getvalue().splitlines()[-1])

        return transcription_segments

    @staticmethod
    def _pbar_delayed(set_delay, capture, pbar):
        """Gets last timestamp from chunk"""

        def pbar_update():
            global timestamp_prev
            time.sleep(set_delay)  # wait for whole chunk to be iterated
            pbar.update(timestamp_last - timestamp_prev)
            print(
                "\33]0;" + capture.getvalue().splitlines()[-1] + "\a",
                end="",
                flush=True,
            )
            print(capture.getvalue().splitlines()[-1])
            timestamp_prev = timestamp_last

        return pbar_update

    @Step.step(Step.replace_words, Step.merge_segments)
    def replace_words(self):
        data_folder = self._transcription_source.path / "data"
        if not data_folder.exists():
            logger.warning(
                f"{data_folder} doesn't exist, so no replacements will be done"
            )
            return

        # TODO: make this portable
        # INPUT DATA FOR SUBSTITUTION
        input_path = data_folder / "resp.txt"
        with open(input_path, "r") as file:
            prompt_words = {}
            for line in file:
                parts = line.split("->")  # Split each line on the "->"
                if len(parts) == 2:  # Make sure there are actually two parts
                    # Remove any leading/trailing whitespace and quotation marks
                    key = parts[0].strip().strip('"')
                    # Check if there"s a word in parentheses at the end, and if so, remove it
                    value = parts[1].split("(")[0].strip().strip('"')
                    prompt_words[key] = value  # Add to dictionary

        for i in range(len(self.slides)):
            transcription = self.slides[i].transcription
            replaced = self._replace_strings(prompt_words, transcription)
            self.slides[i].transcription = replaced

    # SUBSTITUTE
    @staticmethod
    def _replace_strings(dictionary, string):
        for old_string, new_string in dictionary.items():
            string = string.replace(old_string, new_string)
        return string

    @Step.step(Step.improve_punctuation, Step.merge_segments)
    def improve_punctuation(self):
        self._load_openai_key()

        context = """The following is a transcription of a lecture.
        The transcription is complete, but it has formatting and punctuation mistakes.
        Fix ONLY the formatting and punctuation mistakes. Do not change the content.
        The output must be only the transcription, without any other text.
        """

        sys_tokens = self._count_tokens(context)
        sys_message = {"role": "system", "content": context}

        margin = 20  # to avoid errors
        max_input_tokens = (4096 - sys_tokens) // 2 - margin

        bench_start = datetime.now()

        for slide in self.slides:
            text = slide.transcription
            total_tokens = self._count_tokens(text)
            if total_tokens <= max_input_tokens:
                slide.transcription = self._improve_text_with_chatgpt(
                    text, sys_message, max_input_tokens
                )
                continue

            logger.info(
                "The text must be broken into pieces to fit ChatGPT-3.5-turbo prompt."
            )
            logger.debug(text[:50])

            gpt_chunks = []
            for chunk in self._split_text(text, max_input_tokens):
                gpt_chunks.append(
                    self._improve_text_with_chatgpt(
                        chunk, sys_message, max_input_tokens
                    )
                )
            slide.transcription = " ".join(gpt_chunks)

        bench_duration = datetime.now() - bench_start
        logger.info(f"Transcription took {bench_duration}")

    @staticmethod
    def _load_openai_key():
        from dotenv import load_dotenv
        import openai
        import os

        load_dotenv()
        openai.organization = os.getenv("OPENAI_ORG")
        openai.api_key = os.getenv("OPENAI_TOKEN")

    @classmethod
    def _improve_text_with_chatgpt(cls, text, sys_message, max_tokens):
        messages = [
            sys_message,
            {"role": "user", "content": text},
        ]
        improved_text = cls._try_chat_completion_until_successful(messages)

        if improved_text is None:
            return text

        similarity_ratio = cls._calculate_difference(text, improved_text)
        # different = 0 < similarity_ratio < 1 = same
        if similarity_ratio < 0.40 and len(text) > 15:
            logger.info("The text was not improved by ChatGPT-3.5-turbo.")
            logger.debug(f"Similarity: {similarity_ratio}")
            logger.debug(f"ORIGINAL:\n{text}")
            logger.debug(f"IMPROVED:\n{improved_text}")
            return text
        else:
            return improved_text

    @staticmethod
    def _count_tokens(text: str) -> int:
        import tiktoken

        # Based on: https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb
        tokens_per_message = 4
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text)) + tokens_per_message

    @classmethod
    def _split_text(cls, text, max_tokens):
        periods = text.split(".")
        if len(periods) > 1:
            chunks = []
            total_tokens = 0
            start = 0
            for i in range(len(periods)):
                tokens = cls._count_tokens(periods[i])
                if tokens > max_tokens:
                    if start != i:
                        chunks.append(". ".join(periods[start:i]))
                    chunks.extend(cls._split_text(periods[i], max_tokens))
                    start = i + 1
                    total_tokens = 0
                elif total_tokens + tokens > max_tokens:
                    chunks.append(". ".join(periods[start:i]))
                    start = i
                    total_tokens = tokens
                else:
                    total_tokens += tokens

            return chunks

        words = text.split()
        chunks = []
        start = 0
        total_tokens = 0
        for i in range(len(words)):
            tokens = cls._count_tokens(words[i])
            if total_tokens + tokens > max_tokens:
                chunks.append(" ".join(words[start:i]))
                start = i
                total_tokens = tokens
            else:
                total_tokens += tokens

        return chunks

    @staticmethod
    def _ai(messages, temperature=0):
        import openai

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            # model="gpt-4",
            messages=messages,
            n=1,
            temperature=temperature,
        )
        return response

    # error handling is not correct
    @classmethod
    def _try_chat_completion_until_successful(cls, messages, max_tries=5):
        for tries in range(max_tries):
            try:
                logger.info("Asking GPT to improve punctuation")
                result = cls._ai(messages, 0.1)
                return result["choices"][0]["message"]["content"]
            except Exception as e:
                logger.info(f"Retrying {tries} out of {max_tries}")
                logger.debug("Error:", e)
                logger.debug("Message:", messages[1]["content"][:50])
                time.sleep(20.5)

    # REFUSE GPT HALLUCINATIONS (FALTA TESTAR)
    @staticmethod
    def _calculate_difference(paragraph1, paragraph2):
        import difflib

        words1 = paragraph1.split()
        words2 = paragraph2.split()
        similarity_ratio = difflib.SequenceMatcher(None, words1, words2).ratio()
        return similarity_ratio
