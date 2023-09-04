#!/usr/bin/env python
# coding: utf-8

# In[4]:


import os
import re

lesson_id = ""
data_id = "resp"
script_folder = os.getcwd()
root_folder = os.path.dirname(script_folder)
lesson_folder = root_folder + "/lessons/" + lesson_id
data_folder = root_folder + "/data/"
if not (os.path.exists(lesson_folder) and os.path.exists(data_folder)):
    print("Lesson or Data folder do not exist.")

#INPUT TRANSCRIPTION
transcription_path = lesson_folder + "/" + lesson_id + "_transcription_tmarks.txt"
with open(transcription_path, 'r') as file:
    transcription = file.read()
paragraphs = re.split(r'(==== n=\d+ tt=\d{2}:\d{2}:\d{2})', transcription)
paragraphs = [para.strip() for para in paragraphs if para.strip()]
#print(paragraphs)


#INPUT DATA FOR SUBSTITUTION
input_path = data_folder + "/" + data_id + ".txt"
with open(input_path, 'r') as file:
    prompt_words = {}
    for line in file:
        parts = line.split('->')  # Split each line on the '->'
        if len(parts) == 2:  # Make sure there are actually two parts
            key = parts[0].strip().strip('"')  # Remove any leading/trailing whitespace and quotation marks
            # Check if there's a word in parentheses at the end, and if so, remove it
            value = parts[1].split('(')[0].strip().strip('"')
            prompt_words[key] = value  # Add to dictionary

#SUBSTITUTE
def replace_strings(dictionary, string):
    for old_string, new_string in dictionary.items():
        string = string.replace(old_string, new_string)
    return string

paragraphs_output = []
for item in paragraphs:
    paragraphs_output.append(replace_strings(prompt_words, item))

with open(lesson_folder + "/" + lesson_id + '_transcription_tmarks_replaced.txt', 'w', encoding='utf-8') as f:
    for line in paragraphs_output:
        f.write(line + '\n')

