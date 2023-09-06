import os
import subprocess
import time

import pandas as pd

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

# EXTRACT TRANSITION TIMES (TT) FROM TFRAMES
tt_directory = lesson_folder + "/tframes"
image_names = []
for filename in os.listdir(tt_directory):
    if filename.endswith(".png"):
        image_names.append(filename)
prefix = lesson_id + ".mp4_"
sufix = ".png"
cleaned_terms = [name.replace(prefix, "") for name in image_names]
cleaned_terms = [name.replace(sufix, "") for name in cleaned_terms]
sorted_terms = sorted(cleaned_terms)
first_two = sorted_terms[0][:2]
sorted_terms.insert(0, first_two + "-00-00")

# RELATIVE TIME OF TTS
df_tt = pd.DataFrame(sorted_terms, columns=["time"])
df_tt["time"] = df_tt["time"].str.strip()
df_tt["datetime"] = pd.to_datetime(df_tt["time"], format="%H-%M-%S")  # "format" applies for the input, not the output
df_tt["relative_tt"] = pd.NaT
for i in range(len(df_tt)):
    df_tt.at[i, "relative_tt"] = (df_tt.at[i, "datetime"] - df_tt.at[0, "datetime"])
df_tt["relative_tt"] = pd.to_timedelta(df_tt["relative_tt"])
df_tt = df_tt.drop(columns=["datetime"])

# GO SLIGHTLY BEFORE TTS
time_translation = 6
df_tt_translated = pd.DataFrame(sorted_terms, columns=["time"])
df_tt_translated["relative_time"] = df_tt["relative_tt"] - pd.Timedelta(seconds=time_translation)
tt_seconds = df_tt_translated["relative_time"].dt.total_seconds().tolist()
tt_seconds = [int(time) for time in tt_seconds]


def seconds_to_hms(seconds):
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    time_string = "{:02}:{:02}:{:02}".format(hours, minutes, seconds)
    return time_string


tt_seconds = [seconds_to_hms(time) for time in tt_seconds]


def play_video_at_times(file_path, times, duration):
    for time_string in times:
        command = ["mpv", "--start={}".format(time_string), "--length={}".format(duration), "--geometry=45%x100%-0+0", file_path]
        subprocess.run(command)
        time.sleep(2)  # Sleep for a second between runs


play_duration = 12
play_video_at_times(video_path, tt_seconds[1:], play_duration)
