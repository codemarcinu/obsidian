import os
import torch
import logging
import yt_dlp
import warnings
from typing import List, Dict, Optional, Any
from faster_whisper import WhisperModel
from pyannote.audio import Pipeline

from config import ProjectConfig, logger

# Silence annoying warnings
warnings.filterwarnings("ignore", category=UserWarning, module="torchaudio")

class VideoTranscriber:
    """
    Advanced Media Transcription & Diarization Pipeline.
    Architecture: Singleton-ready. Models are loaded on init to persist in VRAM.
    """

    def __init__(self, model_size: str = "medium"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.compute_type = "float16" if self.device == "cuda" else "int8"
        self.logger = logging.getLogger("VideoTranscriber")
        
        self.logger.info(
            f"Initializing VideoTranscriber on {self.device} ({self.compute_type})...", 
            extra={"tags": "MEDIA-INIT"}
        )
        
        # 1. Load Whisper Model ONCE
        try:
            self.whisper_model = WhisperModel(
                model_size, 
                device=self.device, 
                compute_type=self.compute_type
            )
            self.logger.info(f"Whisper ({model_size}) loaded into VRAM.", extra={"tags": "MODEL-LOAD"})
        except Exception as e:
            self.logger.error(f"Failed to load Whisper: {e}", extra={"tags": "FATAL"})
            raise e

        # 2. Pre-load Diarization Pipeline (Lazy loading optional, but strictly typed here)
        self.diarization_pipeline = None
        if ProjectConfig.HF_TOKEN:
            try:
                self.diarization_pipeline = Pipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.1",
                    use_auth_token=ProjectConfig.HF_TOKEN
                ).to(torch.device(self.device))
                self.logger.info("Pyannote pipeline loaded.", extra={"tags": "MODEL-LOAD"})
            except Exception as e:
                self.logger.warning(f"Failed to load Pyannote: {e}. Diarization disabled.", extra={"tags": "COMPLIANCE-WARN"})
        else:
            self.logger.warning("No HF_TOKEN found. Diarization disabled.", extra={"tags": "CONFIG-INFO"})

    def download_video(self, url: str, progress_callback=None) -> str:
        """Downloads audio from various sources using yt-dlp."""
        output_dir = str(ProjectConfig.TEMP_DIR)
        out_template = os.path.join(output_dir, '%(id)s.%(ext)s')

        def progress_hook(d):
            if d['status'] == 'downloading':
                if progress_callback:
                    percent = d.get('_percent_str', 'N/A')
                    eta = d.get('_eta_str', 'N/A')
                    progress_callback(f"Pobieranie: {percent} | ETA: {eta}")

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
            'restrictfilenames': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'progress_hooks': [progress_hook],
            'default_search': 'auto',
            'source_address': '0.0.0.0',
            # Imitate a real browser to avoid 403
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                final_path = os.path.join(output_dir, f"{info['id']}.mp3")
                self.logger.info(f"Downloaded media: {final_path}", extra={"tags": "MEDIA-DOWNLOAD"})
                return final_path
        except Exception as e:
            self.logger.error(f"Download failed: {e}", extra={"tags": "MEDIA-ERROR"})
            raise

    def transcribe_and_diarize(self, audio_path: str, language: str = "pl", progress_callback=None) -> List[Dict[str, Any]]:
        """
        Full Pipeline using pre-loaded models.
        """
        try:
            # 1. Transcribe (Reuse self.whisper_model)
            self.logger.info(f"Starting transcription...", extra={"tags": "WHISPER"})
            segments, info = self.whisper_model.transcribe(audio_path, language=language, vad_filter=True)
            
            transcript_segments = []
            total_duration = info.duration
            
            # Whisper generator must be consumed
            for segment in segments:
                transcript_segments.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip()
                })
                if progress_callback and total_duration > 0:
                    percent = int((segment.end / total_duration) * 100)
                    progress_callback(percent)

            if not self.diarization_pipeline:
                return transcript_segments

            # 2. Diarization (Reuse self.diarization_pipeline)
            self.logger.info("Starting diarization...", extra={"tags": "PYANNOTE"})
            diarization = self.diarization_pipeline(audio_path)
            
            # 3. Join logic
            return self._merge_results(transcript_segments, diarization)

        except Exception as e:
            self.logger.error(f"Pipeline failed: {e}", extra={"tags": "MEDIA-ERROR"})
            raise

    def _merge_results(self, transcript, diarization) -> List[Dict[str, Any]]:
        """Aligns Whisper timestamps with Pyannote speaker turns."""
        final = []
        for seg in transcript:
            speaker = "Unknown"
            max_intersection = 0
            
            for turn, _, label in diarization.itertracks(yield_label=True):
                intersection = min(seg['end'], turn.end) - max(seg['start'], turn.start)
                if intersection > max_intersection:
                    max_intersection = intersection
                    speaker = label
            
            seg['speaker'] = speaker
            final.append(seg)
        return final
