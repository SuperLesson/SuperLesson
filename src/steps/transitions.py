import datetime
import re
import subprocess
import time
from typing import List

import mpv
import pandas as pd
from pydub import AudioSegment, silence
from storage import LessonFile


class Transitions:
    def __init__(self, transcription_source: LessonFile):
        self._transcription_source = transcription_source

    def insert_tmarks(self, transcription_path):
        # TODO: use audio as source for transcription
        video_path = self._transcription_source.full_path
        audio_path = video_path.with_suffix(".wav")

        # TODO: use logging library here
        print(audio_path)

        relative_times = self._get_relative_times()
        tt_seconds = [_time.total_seconds() for _time in relative_times]

        if audio_path.exists():
            print("Audio file already exists")
        else:
            self._extract_audio(video_path, audio_path)

        # silence_threshold_factor=10 worked for lesson_id = "2023-05-22_uc05_transporte_gases"
        # silence_threshold_factor=10 or 9 didn"t work for lesson_id = "2023-06-12_uc05_envelhecimento_pulmonar_estrutura"
        # now trying silence_threshold_factor = 8
        # TODO: remove this try-except block
        try:
            silences  # need while in jupyter environment, cause this operation takes +1 minute to execute
        except:  # noqa: E722
            silences = self._detect_silence(audio_path)

        tt_seconds_improved = self._improve_tt(tt_seconds, silences)

        delta_time_limit = 2.0
        count = 0
        if len(tt_seconds) == len(tt_seconds_improved) + 1:
            for i in range(1, len(tt_seconds)):
                delta = tt_seconds[i] - tt_seconds_improved[i - 1]
                if abs(delta) > delta_time_limit:
                    count += 1
                    tt_seconds_improved[i - 1] = tt_seconds[i]
        else:
            print("tt and tt_improved should have same len")
        print(
            f"tt improvement failed for {count} out of {len(tt_seconds)} tts")

        # TIME ABSOLUTE > TIME RELATIVE TO FIRST LINE
        df_tt_improved = pd.DataFrame(tt_seconds_improved, columns=["time"])
        new_row = pd.DataFrame({"time": [0]})
        df_tt_improved = pd.concat(
            [new_row, df_tt_improved]).reset_index(drop=True)
        df_tt_improved = df_tt_improved.round(2)
        # "format" applies for the input, not the output
        df_tt_improved["datetime"] = pd.to_datetime(
            df_tt_improved["time"], unit="s")
        df_tt_improved["relative_tt"] = pd.NaT
        for i in range(len(df_tt_improved)):
            df_tt_improved.at[i, "relative_tt"] = (
                df_tt_improved.at[i, "datetime"] - df_tt_improved.at[0, "datetime"])
        df_tt_improved["relative_tt"] = pd.to_timedelta(
            df_tt_improved["relative_tt"])
        df_tt_improved = df_tt_improved.drop(columns=["datetime"])
        # print(df_tt_improved.dtypes)

        # IMPORT TRANSCRIPTION
        with open(transcription_path, "r") as f:
            lines = f.readlines()
        data = []
        for line in lines:
            start_time, end_time_text = line.split(" -> ")
            end_time, text = end_time_text.split("]  ")
            text = text.strip()
            data.append([float(start_time.replace("[", "").replace(
                "s", "")), float(end_time.replace("s", "")), text])
        df_transcription = pd.DataFrame(
            data, columns=["start_time", "end_time", "text"])
        new_row = pd.DataFrame(
            {"start_time": [0], "end_time": [0], "text": [""]})
        df_transcription = pd.concat(
            [new_row, df_transcription]).reset_index(drop=True)

        # TIME IN SECONDS -> TIME IN DATETIME -> TIME RELATIVE TO FIRST LINE
        df_transcription["start_time_datetime"] = pd.to_datetime(
            df_transcription["start_time"], dayfirst=True, unit="s")
        df_transcription["end_time_datetime"] = pd.to_datetime(
            df_transcription["end_time"], dayfirst=True, unit="s")
        df_transcription["relative_start_time"] = pd.NaT
        for i in range(len(df_transcription)):
            df_transcription.at[i, "relative_start_time"] = (
                df_transcription.at[i, "start_time_datetime"] - df_transcription.at[0, "start_time_datetime"])

        df_transcription["relative_start_time"] = pd.to_timedelta(
            df_transcription["relative_start_time"])
        df_transcription["relative_end_time"] = pd.NaT
        for i in range(len(df_transcription)):
            df_transcription.at[i, "relative_end_time"] = (
                df_transcription.at[i, "end_time_datetime"] - df_transcription.at[0, "start_time_datetime"])
        df_transcription["relative_end_time"] = pd.to_timedelta(
            df_transcription["relative_end_time"])
        df_transcription = df_transcription.drop(
            columns=["start_time_datetime", "end_time_datetime"])
        df_transcription = df_transcription.reindex(
            columns=["start_time", "end_time", "relative_start_time", "relative_end_time", "text"])
        # print(df_transcription)

        for i, row_tt in df_tt_improved.iterrows():
            for j, row_transcription in df_transcription.iterrows():
                dif1 = pd.to_timedelta(
                    row_tt["relative_tt"]) - pd.to_timedelta(df_transcription["relative_start_time"].iloc[j])
                if j < len(df_transcription) - 1:
                    dif2 = pd.to_timedelta(row_tt["relative_tt"]) - pd.to_timedelta(
                        df_transcription["relative_start_time"].iloc[j + 1])
                else:
                    dif2 = pd.to_timedelta(
                        row_tt["relative_tt"]) - pd.to_timedelta(row_transcription["relative_end_time"])
                zero_td = pd.Timedelta(0, unit="s")
                if (dif1 >= zero_td) and (dif2 < zero_td):
                    if abs(dif1) <= abs(dif2):
                        df_transcription.at[j, "text"] = "====" + " n=" + str(i) + " tt=" + self._pd_timedelta_to_str(
                            df_tt_improved.at[i, "relative_tt"]) + "\n" + df_transcription.at[j, "text"]
                        break
                    else:
                        if j < len(df_transcription) - 1:
                            df_transcription.at[j + 1, "text"] = "====" + " n=" + str(i) + " tt=" + self._pd_timedelta_to_str(
                                df_tt_improved.at[i, "relative_tt"]) + "\n" + df_transcription.at[j + 1, "text"]
                            break
                        else:
                            df_transcription.at[j, "text"] = "====" + " n=" + str(i) + " tt=" + self._pd_timedelta_to_str(
                                df_tt_improved.at[i, "relative_tt"]) + "\n" + df_transcription.at[j, "text"]
                            break

        # Se eu precisar voltar atrás: _pd_timedelta_to_str(df_transcription.at[j,"relative_start_time"])

        # pd.set_option("display.max_rows", None)
        # print(df_transcription.text)

        # ADICIONAR VERIFICAÇÃO DE QUEBRAS
        # contar quantas tts e verificar se há o mesmo tanto no arquivo de saída
        # selected_columns = df_transcription[["start_time", "end_time", "text"]]  # para debug
        selected_columns = df_transcription[["text"]]
        selected_columns_string = selected_columns.to_string(
            index=False, header=False)
        stripped_text = " ".join(
            line.strip() for line in selected_columns_string.split("\n") if line.strip())
        continuos_text = stripped_text.replace(". ", ".").replace(
            ", ", ",").replace(".", ". ").replace(",", ", ")
        paragraphs = re.split(
            r"(==== n=\d+ tt=\d{2}:\d{2}:\d{2}\\n)", continuos_text)
        paragraphs = [para for para in paragraphs if para.strip()]
        paragraphs = [re.sub(r"\\n$", "", line) for line in paragraphs]
        tmarks_path = self._transcription_source.path / "transcription_tmarks.txt"
        with open(tmarks_path, "w", encoding="utf-8") as f:
            for line in paragraphs:
                f.write(line + "\n")

        # DEBUG: EXPORT TTS (don`t delet, it can be very useful for debugging)
        # with open(lesson_folder + "/" + self.lesson_id + "_tt_improved.txt", "w") as f:
        #     for item in tt_seconds_improved:
        #         f.write("%s\n" % self._convert_seconds(item))

        # with open(lesson_folder + "/" + self.lesson_id + "_tt.txt", "w") as f:
        #     for item in tt_seconds:
        #         f.write("%s\n" % self._convert_seconds(item))

        # BREAK AUDIO AND TEXT SHOULD USE THE SAME ALGORITHM
        # EXTRACT AUDIO PIECES RECALCULATING NEAREST SILENCE

        # import subprocess

        # #improvements: two consecutives audio have small intersection of silence segments, make it smoother
        # def extract_segments(input_file, output_file, times, silences, audio_codec="pcm_s16le", channels=1, sample_rate=16000):
        #     for i in range(len(times) - 1):
        #         start_time = self._nearest([silence[0] for silence in silences], times[i])
        #         end_time = self._nearest([silence[1] for silence in silences], times[i+1])
        #         duration = end_time - start_time
        #         output = f"{output_file}_{i}.wav"

        #         command = f"ffmpeg -i {input_file} -ss {start_time} -t {duration} -vn -acodec {audio_codec} -ac {channels} -ar {sample_rate} {output}"
        #         #subprocess.call(command, shell=True)
        #         process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        #         stdout, stderr = process.communicate() #communicate closes the opened process

        #         if process.returncode != 0:
        #             print(f"An error occurred: {stderr.decode("utf-8")}")

        # extract_segments(audio_path, audio_folder + "/" + self.lesson_id, tt_seconds, silences)

        return tmarks_path

    # DETECT SILENCE (by far, the slowest step, t= 80 seconds for each hour, rough average)
    # possible alternative: silero-vad, which is already in use by whisper

    # look for differente ways to find silence_thresh programatically.
    # with the code bellow I have to make guesses of threshold_factor

    def _get_relative_times(self) -> List[datetime.timedelta]:
        tt_directory = self._transcription_source.path / "tframes"
        png_names = []
        for file in tt_directory.iterdir():
            if file.suffix == ".png":
                png_names.append(file.name)

        def to_timedelta(h, m, s): return datetime.timedelta(
            hours=int(h), minutes=int(m), seconds=int(s))

        # we have png files in the format XXXXXX.mp4_HH-MM-SS.png
        timestamps = []
        for name in png_names:
            match = re.search(r"_(\d{2}-\d{2}-\d{2})\.png", name)
            assert match is not None
            timestamp = to_timedelta(*match.group(1).split("-"))
            timestamps.append(timestamp)

        return sorted(timestamps)

    @staticmethod
    def _detect_silence(audio_file, silence_threshold_factor=10):
        audio = AudioSegment.from_wav(audio_file)
        silence_thresh = audio.dBFS - silence_threshold_factor
        silences = silence.detect_silence(
            audio, min_silence_len=800, silence_thresh=silence_thresh, seek_step=1)
        silences = [((start / 1000), (stop / 1000))
                    for start, stop in silences]  # convert to seconds
        return silences

    def verify_tbreaks_with_mpv(self):
        # EXTRACT TRANSITION TIMES (TT) FROM TFRAMES
        relative_times = self._get_relative_times()

        # GO SLIGHTLY BEFORE TTS
        # TODO: parameterize time translation
        time_translation = datetime.timedelta(seconds=6)
        translated_times_seconds = list()
        for _time in relative_times:
            new_tt = _time - time_translation
            if new_tt < pd.Timedelta(seconds=0):
                new_tt = pd.Timedelta(seconds=0)
            translated_times_seconds.append(new_tt.total_seconds())

        play_duration = 12
        self._play_video_at_times(translated_times_seconds, play_duration)

    def _play_video_at_times(self, times, duration):
        player = mpv.MPV()
        player.play(str(self._transcription_source.full_path))
        player.wait_until_playing()
        for _time in times:
            player.seek(_time, reference="absolute", precision="exact")
            time.sleep(duration)

    # EXTRACT AUDIO (t= 7 sec for each hour, rough average)
    @staticmethod
    def _extract_audio(input_file, output_file, audio_codec="pcm_s16le", channels=1, sample_rate=16000):
        command = f"ffmpeg -loglevel quiet -i {input_file} -vn -acodec {audio_codec} -ac {channels} -ar {sample_rate} {output_file}"
        subprocess.call(command, shell=True, stdout=subprocess.DEVNULL)

    # TRY TO FIND NEAREST SILENCE. IF IT CAN`T FIND, GO BACK TO THE ORIGINAL TT
    @staticmethod
    def _nearest(lst, K):
        return lst[min(range(len(lst)), key=lambda i: abs(lst[i] - K))]

    @staticmethod
    def _convert_seconds(seconds):
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        # Split seconds into whole seconds and milliseconds
        seconds, milliseconds = divmod(seconds, 1)
        return "%02d:%02d:%02d.%03d" % (hours, minutes, seconds, milliseconds * 1000)

    @classmethod
    def _improve_tt(cls, times, silences):
        tt_seconds_improved = []
        for i in range(len(times)):
            if i == 0:  # ignore tt = 0
                continue
            else:
                nearest_beg = cls._nearest(
                    [silence[0] for silence in silences], times[i])
                nearest_end = cls._nearest(
                    [silence[1] for silence in silences], times[i])
                tt_seconds_improved.append((nearest_beg + nearest_end) / 2)
        return tt_seconds_improved

    # ADD TMARK (TRANSITION MARK)
    @staticmethod
    def _pd_timedelta_to_str(pd_tdelta: pd.Timedelta) -> str:
        # Convert a pandas Timedelta to a string in the format HH:MM:SS
        total_seconds = pd_tdelta.total_seconds()
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        time_str = "{:02}:{:02}:{:02}".format(
            int(hours), int(minutes), int(seconds))
        return time_str
