#!/usr/bin/env python
# coding: utf-8

# In[2]:


from faster_whisper import WhisperModel
import time
from datetime import timedelta
import os

lesson_id = ""
script_folder = os.getcwd()
root_folder = os.path.dirname(script_folder)
lesson_folder = os.path.join(root_folder, "lessons", lesson_id) # Using os.path.join for cross-platform compatibility
if not os.path.exists(lesson_folder):
    print(lesson_folder)
    print("Lesson folder does not exist.")
video_input_path = os.path.join(lesson_folder, lesson_id + ".mp4")
transcription_path = os.path.join(lesson_folder, lesson_id + "_transcription.txt")
if os.path.isfile(transcription_path):
    raise Exception('error: a transcription for this video already exists')

start_execution_time = time.time()

model_size = "large-v2"
# Run on GPU with FP16
#model = WhisperModel(model_size, device="cuda", compute_type="float16")
# or run on GPU with INT8
# model = WhisperModel(model_size, device="cuda", compute_type="int8_float16")
# or run on CPU with INT8
model = WhisperModel(model_size, device="cpu", compute_type="int8")
# informações sobre o  função transcribe https://github.com/guillaumekln/faster-whisper/blob/master/faster_whisper/transcribe.py
segments, info = model.transcribe(video_input_path, beam_size=5, language = "pt", vad_filter=True)
#segments, info = model.transcribe(video_path, beam_size=5, language = "pt", vad_filter = True, initial_prompt = prompt)

#print("Detected language '%s' with probability %f" % (info.language, info.language_probability))
lines = []
for i, segment in enumerate(segments):
    print("[%.2fs -> %.2fs] %s" % (segment.start, segment.end, segment.text))
    lines.append("[%.2fs -> %.2fs] %s" % (segment.start, segment.end, segment.text))

end_execution_time = time.time()
execution_time = end_execution_time - start_execution_time
time_str = str(timedelta(seconds=execution_time))
print(time_str)

with open(transcription_path, 'w') as f:
    for item in lines:
        f.write("%s\n" % item)


# In[ ]:


#TESTAR PROGRESS BAR https://github.com/guillaumekln/faster-whisper/issues/80
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


# In[ ]:


#ADICIONAR PROMPT À TRANSCRIÇÃO https://platform.openai.com/docs/guides/speech-to-text/prompting
#https://github.com/openai/whisper/discussions/355
# options = whisper.DecodingOptions(fp16=False, prompt="vocab")


