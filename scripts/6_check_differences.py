#!/usr/bin/env python
# coding: utf-8

# In[3]:


import difflib
import os
import subprocess

lesson_id = ""
script_folder = os.getcwd()
root_folder = os.path.dirname(script_folder)
lesson_folder = root_folder + "/lessons/" + lesson_id
if not os.path.exists(lesson_folder):
    print("Lesson folder does not exist.")


transcription_input = lesson_folder + "/" + lesson_id + "_transcription_tmarks.txt"
transcription_output = lesson_folder + "/" + lesson_id + "_transcription_final.txt"
#transcription_output = lesson_folder + "/" + lesson_id + "_rascunho_2.txt"


#DIFF
command = f"wdiff -n -w $'\033[30;41m' -x $'\033[0m' -y $'\033[30;42m' -z $'\033[0m' \"{transcription_input}\" \"{transcription_output}\"; bash"
subprocess.Popen(['gnome-terminal', '--', 'bash', '-c', command])

