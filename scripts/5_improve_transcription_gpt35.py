#!/usr/bin/env python
# coding: utf-8

# In[5]:


import os
import time
import pandas as pd
import openai
import re
openai.organization = ""
openai.api_key = ""

lesson_id = ""
script_folder = os.getcwd()
root_folder = os.path.dirname(script_folder)
lesson_folder = root_folder + "/lessons/" + lesson_id
if not os.path.exists(lesson_folder):
    print("Lesson folder does not exist.")

#INPUT TRANSCRIPTION WITH MARKS
transcription_with_marks_path = lesson_folder + "/" + lesson_id + "_transcription_tmarks_replaced.txt"
with open(transcription_with_marks_path, 'r') as file:
    transcription = file.read()
paragraphs = re.split(r'(==== n=\d+ tt=\d{2}:\d{2}:\d{2})', transcription)
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

#IDENTIFY TEXT THAT COULD SURPASS GPT3.5 LIMIT SIZE (4096 TOKENS)
import nltk
#nltk.download('punkt')
from nltk.tokenize import word_tokenize
import re

def count_tokens(text):
    tokens = word_tokenize(text)
    return len(tokens)

def split_text(text, max_tokens):
    tokens = word_tokenize(text)
    #print(tokens)
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
                chunks.append(' '.join(current_chunk[:last_period_index + 1]))
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

transcription_per_page_input = transcription_per_page.copy()

for i, text in enumerate(transcription_per_page):
    max_tokens_input = 1000  # For gpt-3.5-turbo total tokesn = 4096
    #***falta contar tokens do contexto
    if count_tokens(text) > max_tokens_input:
        sub_chunks = split_text(text, max_tokens_input)
        print(f"The text in {i} must be broken into pieces to fit Openai API.")
        print(text[:50])
        print("===")
        transcription_per_page_input[i] = sub_chunks #chunks is a list


# In[6]:


#RUNGPT
import datetime
start_time = datetime.datetime.now()

def ai(messages, temperature = 0):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        #model="gpt-4",
        messages = messages,
        max_tokens=2048, #max_tokens + message tokens must be < 4096 tokens
        n=1,
        temperature = temperature
    )
    return response

##***error handling is not correct
def try_chat_completion_until_successful(messages, max_tries=5):
    tries = 0
    success = False
    result = None
    while not success and tries < max_tries:
        try:
            result = ai(messages,0.1)
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

transcription_per_page_output = [None] * len(transcription_per_page_input)
for i, item in enumerate(transcription_per_page_input):
    if not isinstance(item, list): #lists exists when input is bigger than 4096 tokens
        messages = [
            {"role": "system", "content": "%s"%context},
            {"role": "user", "content": "%s"%item}
            ]
        prompt_output = try_chat_completion_until_successful(messages)
        transcription_per_page_output[i] = prompt_output['choices'][0]['message']['content']
    else: #if item is a list
        output_data = []
        for text in item:
            messages = [
                {"role": "system", "content": "%s"%context},
                {"role": "user", "content": "%s"%text}
            ]
            output_data.append(try_chat_completion_until_successful(messages))
        text = []
        for subdata in output_data:
            text.append(subdata['choices'][0]['message']['content'])
        transcription_per_page_output[i] = " ".join(text)

end_time = datetime.datetime.now()
delta_time = end_time - start_time
print('execution time: ', delta_time)


# In[7]:


#REFUSE GPT HALLUCINATIONS (FALTA TESTAR)
import difflib
def calculate_difference(paragraph1, paragraph2):
    words1 = paragraph1.split()
    words2 = paragraph2.split()
    similarity_ratio = difflib.SequenceMatcher(None, words1, words2).ratio()
    return similarity_ratio

transcription_improved = transcription_per_page_output.copy()
rejected = 0
if len(transcription_per_page) == len(transcription_improved):
    for i, _ in enumerate(transcription_per_page):
        similarity_ratio = calculate_difference(transcription_per_page[i], transcription_improved[i])
        #similarity ratio between 0 and 1, where 1 means the sequences are identical, and 0 means they are completely different
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


# In[8]:


#CREATE OUTPUT
paragraphs_output = []
if len(tt_marks) == len(transcription_improved):
    for i, _ in enumerate(transcription_improved):
        paragraphs_output.append(tt_marks[i])
        paragraphs_output.append(transcription_improved[i])

#EXPORT RESULT
with open(lesson_folder + "/" + lesson_id + '_transcription_improved_gpt3.txt', 'w', encoding='utf-8') as f:
    for line in paragraphs_output:
        f.write(line + '\n')


# In[26]:


# clean_transcription = []
# spent_tokens = []

# for item in prompt_output:
#     print(item['choices'][0]['message']['content']) #remove after tests
#     print("====")
#     clean_transcription.append(item['choices'][0]['message']['content'])
#     spent_tokens.append(item['usage']['total_tokens'])

# if len(messages_improve_transcription) != len(clean_transcription):
#     print("A transcription block was lost")


