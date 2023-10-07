import datetime
import difflib
import os
import re
import subprocess
import time
from datetime import timedelta

import nltk
import openai
from dotenv import load_dotenv
from faster_whisper import WhisperModel
from nltk.tokenize import word_tokenize


class Transcribe:
    """Class to transcribe a lesson."""

    lesson_root: str
    _transcription_path: str

    def __init__(self, lesson_root: str):
        self.lesson_root = lesson_root
        self._transcription_path = os.path.join(
            self.lesson_root, "transcription.txt")
        load_dotenv()
        openai.organization = os.getenv("OPENAI_ORG")
        openai.api_key = os.getenv("OPENAI_TOKEN")

    def single_file(self, transcription_source):
        transcription_path = self._transcription_path
        if os.path.isfile(transcription_path) and input("Transcription file already exists. Overwrite? (y/n) ") != "y":
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
        segments, _ = model.transcribe(
            transcription_source, beam_size=5, language="pt", vad_filter=True)
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
        data_folder = os.path.join(self.lesson_root, "data")
        if not os.path.exists(data_folder):
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
        input_path = os.path.join(data_folder, "resp.txt")
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

        replacement_path = os.path.join(
            self.lesson_root, "transcription_replaced.txt")
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

    def improve_transcription(self, replacement_path):
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

        # IDENTIFY TEXT THAT COULD SURPASS GPT3.5 LIMIT SIZE (4096 TOKENS)
        nltk.download('punkt')

        transcription_per_page_input = transcription_per_page.copy()

        for i, text in enumerate(transcription_per_page):
            max_tokens_input = 1000  # For gpt-3.5-turbo total tokesn = 4096
            # falta contar tokens do contexto
            if self._count_tokens(text) > max_tokens_input:
                sub_chunks = self._split_text(text, max_tokens_input)
                print(
                    f"The text in {i} must be broken into pieces to fit Openai API.")
                print(text[:50])
                print("===")
                # chunks is a list
                transcription_per_page_input[i] = sub_chunks

        # RUNGPT
        start_time = datetime.datetime.now()

        transcription_per_page_output = [
            None] * len(transcription_per_page_input)
        for i, item in enumerate(transcription_per_page_input):
            # lists exists when input is bigger than 4096 tokens
            if not isinstance(item, list):
                messages = [
                    {"role": "system", "content": context},
                    {"role": "user", "content": item},
                ]
                prompt_output = self._try_chat_completion_until_successful(
                    messages)
                transcription_per_page_output[i] = prompt_output['choices'][0]['message']['content']
            else:  # if item is a list
                output_data = []
                for text in item:
                    messages = [
                        {"role": "system", "content": context},
                        {"role": "user", "content": text}
                    ]
                    output_data.append(
                        self._try_chat_completion_until_successful(messages))
                text = []
                for subdata in output_data:
                    text.append(subdata['choices'][0]['message']['content'])
                transcription_per_page_output[i] = " ".join(text)

        end_time = datetime.datetime.now()
        delta_time = end_time - start_time
        print('execution time: ', delta_time)

        transcription_improved = transcription_per_page_output.copy()
        rejected = 0
        if len(transcription_per_page) == len(transcription_improved):
            for i, _ in enumerate(transcription_per_page):
                similarity_ratio = self._calculate_difference(
                    transcription_per_page[i], transcription_improved[i])
                # similarity ratio between 0 and 1, where 1 means the sequences are identical, and 0 means they are completely different
                # print(i)
                # print(len(transcription_per_page[i]))
                # print(similarity_ratio)
                # print("====")
                if similarity_ratio < 0.40 and len(transcription_per_page[i]) > 15:
                    rejected += 1
                    print(similarity_ratio)
                    print(transcription_per_page[i])
                    print(transcription_improved[i])
                    transcription_improved[i] = transcription_per_page[i]
        print('transcrições rejeitadas: ', rejected)

        # CREATE OUTPUT
        paragraphs_output = []
        if len(tt_marks) == len(transcription_improved):
            for i, _ in enumerate(transcription_improved):
                paragraphs_output.append(tt_marks[i])
                paragraphs_output.append(transcription_improved[i])

        # EXPORT RESULT
        improved_transcription_path = os.path.join(
            self.lesson_root, "transcription_improved_gpt3.txt")
        with open(improved_transcription_path, "w", encoding="utf-8") as f:
            for line in paragraphs_output:
                f.write(line + '\n')

        # clean_transcription = []
        # spent_tokens = []

        # for item in prompt_output:
        #     print(item['choices'][0]['message']['content']) #remove after tests
        #     print("====")
        #     clean_transcription.append(item['choices'][0]['message']['content'])
        #     spent_tokens.append(item['usage']['total_tokens'])

        # if len(messages_improve_transcription) != len(clean_transcription):
        #     print("A transcription block was lost")

        return improved_transcription_path

    def check_differences(self, replacement_path, improved_path):
        # DIFF
        command = f"wdiff -n -w $'\033[30;41m' -x $'\033[0m' -y $'\033[30;42m' -z $'\033[0m' \"{replacement_path}\" \"{improved_path}\"; bash"
        subprocess.Popen(["gnome-terminal", "--", "bash", "-c", command])

    @staticmethod
    def _count_tokens(text):
        tokens = word_tokenize(text)
        return len(tokens)

    @staticmethod
    def _split_text(text, max_tokens):
        tokens = word_tokenize(text)
        # print(tokens)
        chunks = []
        current_chunk = []
        current_chunk_tokens = 0
        for token in tokens:
            if current_chunk_tokens + 1 <= max_tokens:
                current_chunk.append(token)
                current_chunk_tokens += 1
            else:
                # Find the last period in the current_chunk
                last_period_index = None
                for i, chunk_token in enumerate(reversed(current_chunk)):
                    if chunk_token == '.':
                        last_period_index = len(current_chunk) - 1 - i
                        break
                # If a period is found, split the chunk there
                if last_period_index is not None:
                    chunks.append(
                        ' '.join(current_chunk[:last_period_index + 1]))
                    current_chunk = current_chunk[last_period_index + 1:]
                    current_chunk_tokens = len(current_chunk)
                # If no period is found, split at the current token
                else:
                    chunks.append(' '.join(current_chunk))
                    current_chunk = [token]
                    current_chunk_tokens = 1
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        return chunks

    @staticmethod
    def _ai(messages, temperature=0):
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            # model="gpt-4",
            messages=messages,
            max_tokens=2048,  # max_tokens + message tokens must be < 4096 tokens
            n=1,
            temperature=temperature
        )
        return response

    # error handling is not correct
    @classmethod
    def _try_chat_completion_until_successful(cls, messages, max_tries=5):
        tries = 0
        success = False
        result = None
        while not success and tries < max_tries:
            try:
                result = cls._ai(messages, 0.1)
                success = True
            except Exception as e:
                print(f"Error: {e}")
                print(messages[1]["content"][:50])
                print(tries)
                print("====")
                time.sleep(20.5)
                tries += 1
        if success:
            return result
        else:
            return []

    # REFUSE GPT HALLUCINATIONS (FALTA TESTAR)
    @staticmethod
    def _calculate_difference(paragraph1, paragraph2):
        words1 = paragraph1.split()
        words2 = paragraph2.split()
        similarity_ratio = difflib.SequenceMatcher(
            None, words1, words2).ratio()
        return similarity_ratio
