import os
import torch
import logging
import yt_dlp
import warnings
from typing import List, Dict, Optional, Any
from faster_whisper import WhisperModel
from pyannote.audio import Pipeline
from config import ProjectConfig

# Wyciszenie specyficznych warningów
warnings.filterwarnings("ignore", category=UserWarning, module="torchaudio")

class VideoTranscriber:
    def __init__(self, model_size: str = "medium", log_callback=None, progress_callback=None):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.compute_type = "float16" if self.device == "cuda" else "int8"
        self.logger = logging.getLogger("VideoTranscriber")
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        
        self.logger.info(f"VideoTranscriber initialized on {self.device} ({self.compute_type})")

    def download_video(self, url: str, save_path: str = None) -> str:
        """
        Downloads video/audio from YouTube using yt-dlp with SAFE filenames.
        """
        output_dir = save_path if save_path else str(ProjectConfig.TEMP_DIR)
        
        # Używamy ID wideo jako nazwy pliku, aby uniknąć problemów ze znakami specjalnymi w tytułach
        # %(id)s.%(ext)s gwarantuje unikalność i brak spacji.
        out_template = os.path.join(output_dir, '%(id)s.%(ext)s')

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': out_template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
            'restrictfilenames': True, # Dodatkowe zabezpieczenie nazwy
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                if self.log_callback: self.log_callback("Pobieranie metadanych...")
                info_dict = ydl.extract_info(url, download=True)
                
                # Pobierz rzeczywistą nazwę pliku po post-processingu (zamiana na mp3)
                video_id = info_dict.get('id', 'video')
                # yt-dlp z automatu zmienia rozszerzenie na mp3 po konwersji
                final_filename = f"{video_id}.mp3"
                final_path = os.path.join(output_dir, final_filename)
                
                self.logger.info(f"Downloaded audio to: {final_path}")
                
                # Zwracamy też tytuł, może się przydać w metadanych (opcjonalnie można go zwrócić jako tuple)
                # Na potrzeby interfejsu zwracamy ścieżkę.
                return final_path

        except Exception as e:
            self.logger.error(f"Download failed: {e}")
            raise e

    def transcribe_and_diarize(self, audio_path: str, language: str = "pl", 
                             model_size: str = "medium", use_diarization: bool = True) -> List[Dict[str, Any]]:
        """
        Runs Whisper for transcription and Pyannote for speaker diarization.
        """
        if self.progress_callback: self.progress_callback(10, "Ładowanie modelu Whisper...")
        
        try:
            # 1. Transcribe
            model = WhisperModel(model_size, device=self.device, compute_type=self.compute_type)
            segments, info = model.transcribe(audio_path, language=language, vad_filter=True)
            
            transcript_segments = []
            if self.progress_callback: self.progress_callback(30, "Transkrypcja w toku...")
            
            # Konwersja generatora na listę, aby móc wielokrotnie iterować
            for segment in segments:
                transcript_segments.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip()
                })

            if not use_diarization:
                return transcript_segments

            # 2. Diarization (Optional but recommended)
            # Uwaga: Pyannote wymaga tokena HF. Jeśli go nie ma, pomijamy diaryzację z warningiem.
            hf_token = os.getenv("HF_TOKEN")
            if not hf_token:
                self.logger.warning("Brak HF_TOKEN. Pomijam diaryzację.")
                return transcript_segments

            if self.progress_callback: self.progress_callback(60, "Diaryzacja (rozpoznawanie mówców)...")
            
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=hf_token
            ).to(torch.device(self.device))
            
            diarization = pipeline(audio_path)
            
            # 3. Merge Whisper + Diarization
            if self.progress_callback: self.progress_callback(80, "Łączenie wyników...")
            final_segments = self._assign_speakers(transcript_segments, diarization)
            
            if self.progress_callback: self.progress_callback(100, "Gotowe!")
            return final_segments

        except Exception as e:
            self.logger.error(f"Transcription error: {e}")
            raise e

    def _assign_speakers(self, transcript_segments, diarization_result):
        """
        Prosty algorytm mapowania segmentów czasowych Whisper na mówców z Pyannote.
        """
        final_output = []
        
        for seg in transcript_segments:
            # Znajdź mówcę, który mówił najdłużej w czasie trwania segmentu
            seg_start = seg["start"]
            seg_end = seg["end"]
            
            # Pobranie wszystkich nakładających się segmentów mówców
            speakers = []
            for turn, _, speaker in diarization_result.itertracks(yield_label=True):
                # Sprawdź przecięcie (intersection)
                intersection_start = max(seg_start, turn.start)
                intersection_end = min(seg_end, turn.end)
                
                if intersection_end > intersection_start:
                    duration = intersection_end - intersection_start
                    speakers.append((speaker, duration))
            
            # Wybierz dominującego mówcę
            if speakers:
                best_speaker = max(speakers, key=lambda x: x[1])[0]
                seg["speaker"] = best_speaker
            else:
                seg["speaker"] = "Unknown"
                
            final_output.append(seg)
            
        return final_output
