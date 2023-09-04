#!/usr/bin/env python
# coding: utf-8

# In[2]:


import pandas as pd
import os
import re

lesson_id = ""
script_folder = os.getcwd()
root_folder = os.path.dirname(script_folder)
lesson_folder = root_folder + "/lessons/" + lesson_id
if not os.path.exists(lesson_folder):
    print("Lesson folder does not exist.")
audio_folder = lesson_folder + "/audios"
if not os.path.exists(audio_folder):
    os.makedirs(audio_folder)
video_path = lesson_folder + "/" + lesson_id + ".mp4"
audio_path = audio_folder + "/" + lesson_id + ".wav"

print(audio_path)

#EXTRACT TRANSITION TIMES (TT) FROM TFRAMES
tt_directory = lesson_folder + "/tframes"
image_names = []
for filename in os.listdir(tt_directory):
    if filename.endswith('.png'):
        image_names.append(filename)
prefix = lesson_id + ".mp4_"
sufix = ".png"
cleaned_terms = [name.replace(prefix, "") for name in image_names]
cleaned_terms = [name.replace(sufix, "") for name in cleaned_terms]
sorted_terms = sorted(cleaned_terms)
first_two = sorted_terms[0][:2]
sorted_terms.insert(0, first_two+"-00-00")

#RELATIVE TIME OF TTS
df_tt = pd.DataFrame(sorted_terms, columns=['time'])
df_tt['time'] = df_tt['time'].str.strip()
df_tt['datetime'] = pd.to_datetime(df_tt['time'], format='%H-%M-%S') #'format' applies for the input, not the output
df_tt['relative_tt'] = pd.NaT
for i in range(len(df_tt)):
    df_tt.at[i,'relative_tt'] = (df_tt.at[i,'datetime'] - df_tt.at[0, 'datetime'])
df_tt['relative_tt'] = pd.to_timedelta(df_tt['relative_tt'])
df_tt = df_tt.drop(columns=['datetime'])
tt_seconds = df_tt['relative_tt'].dt.total_seconds().tolist()


#EXTRACT AUDIO (t= 7 sec for each hour, rough average)
import subprocess
def extract_audio(input_file, output_file, audio_codec='pcm_s16le', channels=1, sample_rate=16000):
    command = f'ffmpeg -loglevel quiet -i "{input_file}" -vn -acodec {audio_codec} -ac {channels} -ar {sample_rate} "{output_file}"'
    subprocess.call(command, shell=True, stdout=subprocess.DEVNULL)
if os.path.isfile(audio_path):
    print("Audio file already exists")
else:
    extract_audio(video_path, audio_path)


#DETECT SILENCE (by far, the slowest step, t= 80 seconds for each hour, rough average)
#possible alternative: silero-vad, which is already in use by whisper
from pydub import AudioSegment, silence
#***look for differente ways to find silence_thresh programatically. With the code bellow I have to make guesses of threshold_factor
def detect_silence(audio_file, silence_threshold_factor=10):
    audio = AudioSegment.from_wav(audio_file)
    silence_thresh = audio.dBFS - silence_threshold_factor
    silences = silence.detect_silence(audio, min_silence_len=800, silence_thresh=silence_thresh, seek_step=1)
    silences = [((start/1000),(stop/1000)) for start,stop in silences] # convert to seconds
    return silences
#silence_threshold_factor=10 worked for lesson_id = "2023-05-22_uc05_transporte_gases"
#silence_threshold_factor=10 or 9 didn't work for lesson_id = "2023-06-12_uc05_envelhecimento_pulmonar_estrutura"
#now trying silence_threshold_factor = 8
try:
    silences #need while in jupyter environment, cause this operation takes +1 minute to execute
except:
    silences = detect_silence(audio_path)


#TRY TO FIND NEAREST SILENCE. IF IT CAN`T FIND, GO BACK TO THE ORIGINAL TT
def nearest(lst, K):
    return lst[min( range(len(lst)) , key = lambda i: abs(lst[i]-K) )]
def improve_tt(times, silences):
    tt_seconds_improved = []
    for i in range(len(times)):
        if i == 0: #ignore tt = 0
            continue
        else:
            nearest_beg = nearest([silence[0] for silence in silences], times[i])
            nearest_end = nearest([silence[1] for silence in silences], times[i])
            tt_seconds_improved.append((nearest_beg + nearest_end)/2)
    return tt_seconds_improved
tt_seconds_improved = improve_tt(tt_seconds, silences)
def convert_seconds(seconds):
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    # Split seconds into whole seconds and milliseconds
    seconds, milliseconds = divmod(seconds, 1)
    return "%02d:%02d:%02d.%03d" % (hours, minutes, seconds, milliseconds*1000)
delta_time_limit = 2.0
count = 0
if len(tt_seconds) == len(tt_seconds_improved)+1:
    for i in range(1, len(tt_seconds)):
        delta = tt_seconds[i] - tt_seconds_improved[i-1]
        if abs(delta) > delta_time_limit:
            count += 1
            tt_seconds_improved[i-1] = tt_seconds[i]
else:
    print("tt and tt_improved should have same len")
print(f"tt improvement failed for {count} out of {len(tt_seconds)} tts")


#TIME ABSOLUTE > TIME RELATIVE TO FIRST LINE
df_tt_improved = pd.DataFrame(tt_seconds_improved, columns=['time'])
new_row = pd.DataFrame({'time': [0]})
df_tt_improved = pd.concat([new_row, df_tt_improved]).reset_index(drop=True)
df_tt_improved = df_tt_improved.round(2)
df_tt_improved['datetime'] = pd.to_datetime(df_tt_improved['time'], unit='s') #'format' applies for the input, not the output
df_tt_improved['relative_tt'] = pd.NaT
for i in range(len(df_tt_improved)):
    df_tt_improved.at[i,'relative_tt'] = (df_tt_improved.at[i,'datetime'] - df_tt_improved.at[0,'datetime'])
df_tt_improved['relative_tt'] = pd.to_timedelta(df_tt_improved['relative_tt'])
df_tt_improved = df_tt_improved.drop(columns=['datetime'])
#print(df_tt_improved.dtypes)


#INPORT TRANSCRIPTION
transcription_path = lesson_folder + "/" + lesson_id + '_transcription.txt'
with open(transcription_path, 'r') as f:
    lines = f.readlines()
data = []
for line in lines:
    start_time, end_time_text = line.split(" -> ")
    end_time, text = end_time_text.split("]  ")
    text = text.strip()
    data.append([float(start_time.replace("[", "").replace("s", "")), float(end_time.replace("s", "")), text])
df_transcription = pd.DataFrame(data, columns=['start_time', 'end_time', 'text'])
new_row = pd.DataFrame({'start_time':[0], 'end_time':[0], 'text':[""]})
df_transcription = pd.concat([new_row, df_transcription]).reset_index(drop=True)


#TIME IN SECONDS -> TIME IN DATETIME -> TIME RELATIVE TO FIRST LINE
df_transcription['start_time_datetime'] = pd.to_datetime(df_transcription['start_time'],dayfirst=True, unit='s')
df_transcription['end_time_datetime'] = pd.to_datetime(df_transcription['end_time'],dayfirst=True, unit='s')
df_transcription['relative_start_time'] = pd.NaT
for i in range(len(df_transcription)):
    df_transcription.at[i,'relative_start_time'] = (df_transcription.at[i,'start_time_datetime'] - df_transcription.at[0,'start_time_datetime'])
df_transcription['relative_start_time'] = pd.to_timedelta(df_transcription['relative_start_time'])
df_transcription['relative_end_time'] = pd.NaT
for i in range(len(df_transcription)):
    df_transcription.at[i,'relative_end_time'] = (df_transcription.at[i,'end_time_datetime'] - df_transcription.at[0,'start_time_datetime'])
df_transcription['relative_end_time'] = pd.to_timedelta(df_transcription['relative_end_time'])
df_transcription = df_transcription.drop(columns=['start_time_datetime','end_time_datetime'])
df_transcription = df_transcription.reindex(columns=['start_time','end_time','relative_start_time', 'relative_end_time', 'text'])
#print(df_transcription)

#ADD TMARK (TRANSITION MARK)
def pd_timedelta_to_str(pd_tdelta: pd.Timedelta) -> str:
    #Convert a pandas Timedelta to a string in the format HH:MM:SS
    total_seconds = pd_tdelta.total_seconds()
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    time_str = "{:02}:{:02}:{:02}".format(int(hours), int(minutes), int(seconds))
    return time_str
for i, row_tt in df_tt_improved.iterrows():
    for j, row_transcription in df_transcription.iterrows():
        dif1 = pd.to_timedelta(row_tt['relative_tt']) - pd.to_timedelta(df_transcription['relative_start_time'].iloc[j])
        if j < len(df_transcription)-1:
            dif2 = pd.to_timedelta(row_tt['relative_tt']) - pd.to_timedelta(df_transcription['relative_start_time'].iloc[j+1])
        else:
            dif2 = pd.to_timedelta(row_tt['relative_tt']) - pd.to_timedelta(row_transcription['relative_end_time'])
        zero_td = pd.Timedelta(0, unit='s')
        if (dif1 >= zero_td) and (dif2 < zero_td):
            if abs(dif1) <= abs(dif2):
                df_transcription.at[j,'text'] = "====" + " n=" + str(i) + " tt=" + pd_timedelta_to_str(df_tt_improved.at[i,'relative_tt']) + "\n" + df_transcription.at[j,'text']
                break
            else:
                if j < len(df_transcription)-1:
                    df_transcription.at[j+1,'text'] = "====" + " n=" + str(i) + " tt=" + pd_timedelta_to_str(df_tt_improved.at[i,'relative_tt']) + "\n" + df_transcription.at[j+1,'text']
                    break
                else:
                    df_transcription.at[j,'text'] = "====" + " n=" + str(i) + " tt=" + pd_timedelta_to_str(df_tt_improved.at[i,'relative_tt']) + "\n" + df_transcription.at[j,'text']
                    break

#Se eu precisar voltar atrás: pd_timedelta_to_str(df_transcription.at[j,'relative_start_time'])

#pd.set_option('display.max_rows', None)
#print(df_transcription.text)

#ADICIONAR VERIFICAÇÃO DE QUEBRAS
#contar quantas tts e verificar se há o mesmo tanto no arquivo de saída
#selected_columns = df_transcription[['start_time', 'end_time', 'text']] #para debug
selected_columns = df_transcription[['text']]
selected_columns_string = selected_columns.to_string(index=False, header=False)
stripped_text = ' '.join(line.strip() for line in selected_columns_string.split('\n') if line.strip())
continuos_text = stripped_text.replace('. ', '.').replace(', ', ',').replace('.', '. ').replace(',', ', ')
paragraphs = re.split(r'(==== n=\d+ tt=\d{2}:\d{2}:\d{2}\\n)', continuos_text)
paragraphs = [para for para in paragraphs if para.strip()]
paragraphs = [re.sub(r'\\n$', '', line) for line in paragraphs]
with open(lesson_folder + "/" + lesson_id + '_transcription_tmarks.txt', 'w', encoding='utf-8') as f:
    for line in paragraphs:
        f.write(line + '\n')



# In[3]:


#DEBUG: EXPORT TTS (don`t delet, it can be very useful for debugging)
#with open(lesson_folder + "/" + lesson_id + "_tt_improved.txt", 'w') as f:
#    for item in tt_seconds_improved:
#        f.write("%s\n" % convert_seconds(item))


#with open(lesson_folder + "/" + lesson_id + "_tt.txt", 'w') as f:
#    for item in tt_seconds:
#        f.write("%s\n" % convert_seconds(item))


# In[177]:


#BREAK AUDIO AND TEXT SHOULD USE THE SAME ALGORITHM
# #EXTRACT AUDIO PIECES RECALCULATING NEAREST SILENCE
# import subprocess

# #improvements: two consecutives audio have small intersection of silence segments, make it smoother
# def extract_segments(input_file, output_file, times, silences, audio_codec='pcm_s16le', channels=1, sample_rate=16000):
#     for i in range(len(times) - 1):
#         start_time = nearest([silence[0] for silence in silences], times[i])
#         end_time = nearest([silence[1] for silence in silences], times[i+1])
#         duration = end_time - start_time
#         output = f"{output_file}_{i}.wav"

#         command = f"ffmpeg -i {input_file} -ss {start_time} -t {duration} -vn -acodec {audio_codec} -ac {channels} -ar {sample_rate} {output}"
#         #subprocess.call(command, shell=True)
#         process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#         stdout, stderr = process.communicate() #communicate closes the opened process

#         if process.returncode != 0:
#             print(f"An error occurred: {stderr.decode('utf-8')}")

# extract_segments(audio_path, audio_folder + "/" + lesson_id, tt_seconds, silences)


