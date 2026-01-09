import os
import re
import shutil
import subprocess
import time
import requests
import yt_dlp
import torch
from faster_whisper import WhisperModel

# Domyślne wartości
DEFAULT_MODEL_SIZE = "medium"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
COMPUTE_TYPE = "float16" if DEVICE == "cuda" else "int8"

class VideoTranscriber:
    def __init__(self, log_callback=None, progress_callback=None):
        self.log = log_callback if log_callback else self._default_log
        self.progress = progress_callback if progress_callback else self._default_progress
        self.stop_event_set = False # Simple flag instead of threading.Event for now

    def _default_log(self, message):
        print(f"[Log] {message}")

    def _default_progress(self, percent, stage, details=None):
        print(f"[Progress] {stage}: {percent}% ({details})")

    def stop(self):
        self.stop_event_set = True

    def validate_url(self, url):
        if not url or not url.strip():
            return False
        youtube_regex = (
            r"(https?://)?(www\.)?"
            r"(youtube|youtu|youtube-nocookie)\.(com|be)/"
            r"(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})"
        )
        return re.match(youtube_regex, url.strip())

    def get_file_size(self, filepath):
        try:
            size = os.path.getsize(filepath)
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024.0:
                    return f"{size:.2f} {unit}"
                size /= 1024.0
            return f"{size:.2f} TB"
        except:
            return "Unknown"

    def download_video(self, url, save_path, quality="best", audio_quality="192"):
        if self.stop_event_set: raise InterruptedError("Cancelled")
        
        self.log(f"Pobieranie wideo z URL: {url} (Jakość: {quality})...")
        self.progress(0, "downloading")

        common_opts = {
            "outtmpl": os.path.join(save_path, "% (title)s.%(ext)s"),
            "progress_hooks": [self._yt_dlp_hook],
            "writethumbnail": False,
            "writeinfojson": False,
            "keepvideo": False,
            "noplaylist": True,
            "socket_timeout": 30,
        }

        if quality == "audio_only":
            ydl_opts = {
                **common_opts,
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": audio_quality,
                }],
            }
        else: # best or worst video
            fmt = "bestvideo+bestaudio/best" if quality == "best" else "worst"
            ydl_opts = {
                **common_opts,
                "format": fmt,
                "merge_output_format": "mp4",
                "postprocessors": [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}],
            }

        filename = ""
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                
                # Fix filename extension for audio_only
                base = os.path.splitext(filename)[0]
                if quality == "audio_only":
                    filename = base + ".mp3"
                else:
                    filename = base + ".mp4"
                
                if os.path.exists(filename):
                    size_str = self.get_file_size(filename)
                    self.log(f"Pobrano plik: {filename} ({size_str})")

        except Exception as e:
            raise Exception(f"Błąd pobierania: {str(e)}")

        self.progress(100, "downloading")
        return filename

    def _yt_dlp_hook(self, d):
        if self.stop_event_set: raise InterruptedError("Cancelled")
        if d["status"] == "downloading":
            try:
                p = d.get("_percent_str", "0%").replace("%", "")
                percent = float(p)
                self.progress(percent, "downloading")
            except: pass

    def convert_to_mp3(self, input_path, output_path=None):
        if self.stop_event_set: raise InterruptedError("Cancelled")
        
        if not output_path:
            base, _ = os.path.splitext(input_path)
            output_path = base + ".mp3"

        self.log(f"Konwersja do MP3: {os.path.basename(input_path)} -> {os.path.basename(output_path)}")
        self.progress(0, "converting")

        try:
            cmd = [
                "ffmpeg", "-y",
                "-loglevel", "error", "-nostats",
                "-i", input_path,
                "-codec:a", "libmp3lame",
                "-qscale:a", "2",
                output_path
            ]
            
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.progress(100, "converting")
            return output_path
        except subprocess.CalledProcessError as e:
            raise Exception(f"Błąd FFmpeg: {e.stderr.decode() if e.stderr else str(e)}")
        except Exception as e:
            raise Exception(f"Błąd konwersji: {str(e)}")

    def transcribe_video(self, filename, language="pl", model_size=DEFAULT_MODEL_SIZE):
        if self.stop_event_set: raise InterruptedError("Cancelled")
        
        self.log(f"Inicjalizacja modelu Whisper ({model_size}) na {DEVICE}...")
        
        models_dir = os.path.join(os.getcwd(), "models")
        os.makedirs(models_dir, exist_ok=True)

        try:
            model = WhisperModel(model_size, device=DEVICE, compute_type=COMPUTE_TYPE, download_root=models_dir)
        except Exception as e:
            raise Exception(f"Nie można załadować modelu Whisper: {str(e)}")

        self.log(f"Rozpoczynam transkrypcję pliku: {os.path.basename(filename)}")
        self.progress(0, "transcribing")

        try:
            segments, info = model.transcribe(
                filename,
                language=language if language != "auto" else None,
                beam_size=5,
                vad_filter=True,
            )
            
            # Faster Whisper returns a generator, so we iterate to get progress
            # However, we don't know total duration easily unless we probe file or use info.duration
            
            collected_segments = []
            total_duration = info.duration
            
            for segment in segments:
                if self.stop_event_set: raise InterruptedError("Cancelled")
                collected_segments.append(segment)
                if total_duration > 0:
                    percent = (segment.end / total_duration) * 100
                    self.progress(min(percent, 99), "transcribing")
            
            self.progress(100, "transcribing")
            return collected_segments, info
            
        except Exception as e:
            raise Exception(f"Błąd transkrypcji: {str(e)}")

    def save_transcription(self, segments, info, output_path_base):
        # Save as simple TXT with timestamps
        txt_path = output_path_base + "_transkrypcja.txt"
        
        full_text = ""
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"Język wykryty: {info.language} (pewność: {info.language_probability:.2%})\n")
            f.write("-" * 40 + "\n\n")
            
            for segment in segments:
                line = f"[{self._format_time(segment.start)} -> {self._format_time(segment.end)}] {segment.text}\n"
                f.write(line)
                full_text += segment.text + " "
        
        return txt_path, full_text.strip()

    def _format_time(self, seconds):
        m, s = divmod(int(seconds), 60)
        return f"{m:02d}:{s:02d}"

    def summarize_text(self, text, model_name="bielik", style="standard"):
        if self.stop_event_set: raise InterruptedError("Cancelled")
        
        self.log("Generowanie podsumowania przez Ollama...")
        self.progress(0, "summarizing")
        
        # Simple prompt logic
        if style == "short":
            prompt_instruction = "Napisz bardzo krótkie streszczenie tego tekstu w jednym akapicie (po polsku)."
        elif style == "detailed":
            prompt_instruction = "Sporządź szczegółowe podsumowanie, uwzględniając najważniejsze wątki techniczne."
        else:
            prompt_instruction = "Stwórz zwięzłe podsumowanie w punktach (po polsku)."

        prompt = f"{prompt_instruction} Tekst:\n\n{text[:15000]}" # Limit context

        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": model_name, "prompt": prompt, "stream": False},
                timeout=300,
            )
            
            if response.status_code == 200:
                self.progress(100, "summarizing")
                return response.json().get("response")
            else:
                self.log(f"Błąd Ollama: {response.status_code}")
                return None
        except Exception as e:
            self.log(f"Błąd połączenia z Ollama: {e}")
            return None
