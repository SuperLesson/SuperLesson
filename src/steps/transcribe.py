import datetime
import difflib
import os
import re
import subprocess
import time
from datetime import timedelta
from pathlib import Path

import openai
import tiktoken
from dotenv import load_dotenv
from faster_whisper import WhisperModel
from storage import LessonFile


class Transcribe:
    """Class to transcribe a lesson."""

    def __init__(self, transcription_source: LessonFile):
        self._transcription_source = transcription_source
        load_dotenv()
        openai.organization = os.getenv("OPENAI_ORG")
        openai.api_key = os.getenv("OPENAI_TOKEN")

    def single_file(self) -> Path:
        transcription_path = self._transcription_source.path / "transcription.txt"
        if transcription_path.exists() and input("Transcription file already exists. Overwrite? (y/n) ") != "y":
            return transcription_path

        start_execution_time = time.time()

        # TODO: add a flag to select the model size
        model_size = "large-v2"
        # model_size = "small"
        # Run on GPU with FP16
        # model = WhisperModel(model_size, device="cuda", compute_type="float16")
        # or run on GPU with INT8
        model = WhisperModel(model_size, device="cuda",
                             compute_type="int8_float16")
        # or run on CPU with INT8
        # model = WhisperModel(model_size, device="cpu", cpu_threads=16, compute_type="auto")

        # informações sobre a função transcribe
        # https://github.com/guillaumekln/faster-whisper/blob/master/faster_whisper/transcribe.py
        segments, _ = model.transcribe(str(self._transcription_source.full_path), beam_size=5,
                                       language="pt", vad_filter=True)
        # segments, info = model.transcribe(video_path, beam_size=5, language = "pt", vad_filter = True, initial_prompt = prompt)

        # print("Detected language "%s" with probability %f" % (info.language, info.language_probability))
        lines = []
        for segment in segments:
            print("[%.2fs -> %.2fs] %s" %
                  (segment.start, segment.end, segment.text))
            lines.append("[%.2fs -> %.2fs] %s" %
                         (segment.start, segment.end, segment.text))

        end_execution_time = time.time()
        execution_time = end_execution_time - start_execution_time
        time_str = str(timedelta(seconds=execution_time))
        print(time_str)

        with open(transcription_path, "w") as f:
            for item in lines:
                f.write("%s\n" % item)

        # TESTAR PROGRESS BAR https://github.com/guillaumekln/faster-whisper/issues/80
        # from tqdm import tqdm
        # from faster_whisper import WhisperModel

        # model = WhisperModel("tiny")
        # segments, info = model.transcribe("audio.mp3", vad_filter=True)

        # total_duration = round(info.duration, 2)  # Same precision as the Whisper timestamps.
        # timestamps = 0.0  # to get the current segments

        # with tqdm(total=total_duration, unit=" audio seconds") as pbar:
        #     for segment in segments:
        #         pbar.update(segment.end - timestamps)
        #         timestamps = segment.end
        #     if timestamps < info.duration: # silence at the end of the audio
        #         pbar.update(info.duration - timestamps)

        # ADICIONAR PROMPT À TRANSCRIÇÃO https://platform.openai.com/docs/guides/speech-to-text/prompting
        # https://github.com/openai/whisper/discussions/355
        # options = whisper.DecodingOptions(fp16=False, prompt="vocab")
        return transcription_path

    def replace_words(self, tmarks_path):
        data_folder = self._transcription_source.path / "data"
        if not data_folder.exists():
            print(f"{data_folder} doesn't exist, so no replacements will be done")
            return None

        # INPUT TRANSCRIPTION
        with open(tmarks_path, "r") as file:
            transcription = file.read()
        paragraphs = re.split(
            r"(==== n=\d+ tt=\d{2}:\d{2}:\d{2})", transcription)
        paragraphs = [para.strip() for para in paragraphs if para.strip()]
        # print(paragraphs)

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

        paragraphs_output = []
        for item in paragraphs:
            paragraphs_output.append(self._replace_strings(prompt_words, item))

        replacement_path = self._transcription_source.path / "transcription_replaced.txt"
        with open(replacement_path, "w", encoding="utf-8") as f:
            for line in paragraphs_output:
                f.write(line + "\n")

        return replacement_path

    # SUBSTITUTE
    @staticmethod
    def _replace_strings(dictionary, string):
        for old_string, new_string in dictionary.items():
            string = string.replace(old_string, new_string)
        return string

    def improve_punctuation(self, replacement_path):
        # INPUT TRANSCRIPTION WITH MARKS
        with open(replacement_path, 'r') as file:
            transcription = file.read()
        paragraphs = re.split(
            r'(==== n=\d+ tt=\d{2}:\d{2}:\d{2})', transcription)
        paragraphs = [para.strip() for para in paragraphs if para.strip()]
        tt_marks = paragraphs[::2]
        transcription_per_page = paragraphs[1::2]

        context = """O texto a seguir precisa ser preparado para impressão.
        - formate o texto, sem fazer modificações de conteúdo.
        - corrija qualquer erro de digitação ou de grafia.
        - faça as quebras de paragrafação que forem necessárias.
        - coloque as pontuações adequadas.
        - a saída deve ser somente a resposta, sem frases como "aqui está o texto revisado e formatado".
        - NÃO FAÇA NENHUMA MODIFICAÇÃO DE CONTEÚDO, SOMENTE DE FORMATAÇÃO.
        """

        sys_tokens = self._count_tokens(context)
        sys_message = {"role": "system", "content": context}

        margin = 20  # to avoid errors
        max_input_tokens = (4096 - sys_tokens) // 2 - margin

        start_time = datetime.datetime.now()

        # RUN GPT
        improved_transcription = []
        for text in transcription_per_page:
            total_tokens = self._count_tokens(text)
            if total_tokens <= max_input_tokens:
                improved_transcription.append(
                    self._improve_text_with_chatgpt(text, sys_message, max_input_tokens)
                )
                continue

            print("The text must be broken into pieces to fit ChatGPT-3.5-turbo prompt.")
            print(text[:50])
            print("===")

            gpt_chunks = []
            for chunk in self._split_text(text, max_input_tokens):
                gpt_chunks.append(
                    self._improve_text_with_chatgpt(chunk, sys_message, max_input_tokens)
                )
            improved_transcription.append(" ".join(gpt_chunks))

        end_time = datetime.datetime.now()
        delta_time = end_time - start_time
        print('execution time: ', delta_time)

        # CREATE OUTPUT
        paragraphs_output = []
        for tt_mark, improved_text in zip(tt_marks, improved_transcription):
            paragraphs_output.append(tt_mark)
            paragraphs_output.append(improved_text)

        # EXPORT RESULT
        improved_transcription_path = self._transcription_source / "transcription_improved_gpt3.txt"
        with open(improved_transcription_path, "w", encoding="utf-8") as f:
            for line in paragraphs_output:
                f.write(line + '\n')

        return improved_transcription_path

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
        # print(i)
        # print(len(transcription_per_page[i]))
        # print(similarity_ratio)
        # print("====")
        if similarity_ratio < 0.40 and len(text) > 15:
            print(similarity_ratio)
            print(text)
            print(improved_text)
            return text
        else:
            return improved_text

    def check_differences(self, replacement_path, improved_path):
        # DIFF
        command = f"wdiff -n -w $'\033[30;41m' -x $'\033[0m' -y $'\033[30;42m' -z $'\033[0m' \"{replacement_path}\" \"{improved_path}\"; bash"
        subprocess.Popen(["gnome-terminal", "--", "bash", "-c", command])

    @staticmethod
    def _count_tokens(text: str) -> int:
        # Based on: https://github.com/openai/openai-cookbook/blob/main/examples/How_to_count_tokens_with_tiktoken.ipynb
        tokens_per_message = 4
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text)) + tokens_per_message

    @classmethod
    def _split_text(cls, text, max_tokens):
        periods = text.split('.')
        if len(periods) > 1:
            chunks = []
            total_tokens = 0
            start = 0
            for i in range(len(periods)):
                tokens = cls._count_tokens(periods[i])
                if tokens > max_tokens:
                    if start != i:
                        chunks.append('. '.join(periods[start:i]))
                    chunks.extend(cls._split_text(periods[i], max_tokens))
                    start = i + 1
                    total_tokens = 0
                elif total_tokens + tokens > max_tokens:
                    chunks.append('. '.join(periods[start:i]))
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
                chunks.append(' '.join(words[start:i]))
                start = i
                total_tokens = tokens
            else:
                total_tokens += tokens

        return chunks

    @staticmethod
    def _ai(messages, temperature=0):
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            # model="gpt-4",
            messages=messages,
            n=1,
            temperature=temperature
        )
        return response

    # error handling is not correct
    @classmethod
    def _try_chat_completion_until_successful(cls, messages, max_tries=5):
        for tries in range(max_tries):
            try:
                result = cls._ai(messages, 0.1)
                return result['choices'][0]['message']['content']
            except Exception as e:
                print(f"Error: {e}")
                print(messages[1]["content"][:50])
                print(tries)
                print("====")
                time.sleep(20.5)

    # REFUSE GPT HALLUCINATIONS (FALTA TESTAR)
    @staticmethod
    def _calculate_difference(paragraph1, paragraph2):
        words1 = paragraph1.split()
        words2 = paragraph2.split()
        similarity_ratio = difflib.SequenceMatcher(
            None, words1, words2).ratio()
        return similarity_ratio
