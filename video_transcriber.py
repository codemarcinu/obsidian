import os
import re
import shutil
import subprocess
import time
import logging
from datetime import timedelta
import requests
import yt_dlp
import torch
from faster_whisper import WhisperModel
from config import ProjectConfig

# Optional PyAnnote import
try:
    from pyannote.audio import Pipeline
    PYANNOTE_AVAILABLE = True
except ImportError:
    PYANNOTE_AVAILABLE = False

logger = logging.getLogger("VideoTranscriber")

class VideoTranscriber:
    def __init__(self, log_callback=None, progress_callback=None):
        self.log = log_callback if log_callback else self._default_log
        self.progress = progress_callback if progress_callback else self._default_progress
        self.stop_event_set = False
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.compute_type = "float16" if self.device == "cuda" else "int8"
        
        logger.info(f"VideoTranscriber initialized on {self.device} ({self.compute_type})")

    def _default_log(self, message):
        logger.info(message)

    def _default_progress(self, percent, stage, details=None):
        pass

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

    def download_video(self, url, save_path=None, quality="best"):
        if self.stop_event_set: raise InterruptedError("Cancelled")
        
        # Use TEMP_DIR from config if save_path not provided
        target_dir = save_path if save_path else str(ProjectConfig.TEMP_DIR)
        
        self.log(f"Downloading video from: {url} to {target_dir}")
        self.progress(0, "downloading")

        ydl_opts = {
            "outtmpl": os.path.join(target_dir, "% (title)s.%(ext)s"),
            "progress_hooks": [self._yt_dlp_hook],
            "writethumbnail": False,
            "writeinfojson": False,
            "keepvideo": False,
            "noplaylist": True,
            "format": "bestaudio/best", # Prefer audio for transcription efficiency
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                },
            ],
        }

        filename = ""
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                # yt-dlp with postprocessor changes ext to mp3
                filename = os.path.splitext(filename)[0] + ".mp3"
                
        except Exception as e:
            raise Exception(f"Download failed: {str(e)}")

        self.progress(100, "downloading")
        return filename

    def _yt_dlp_hook(self, d):
        if self.stop_event_set: raise InterruptedError("Cancelled")
        if d["status"] == "downloading":
            try:
                p = d.get("_percent_str", "0%").replace("%", "")
                self.progress(float(p), "downloading")
            except: pass

    def transcribe_and_diarize(self, audio_path, language="pl", model_size="medium", use_diarization=True):
        if self.stop_event_set: raise InterruptedError("Cancelled")

        # 1. Transcription (Whisper)
        self.log(f"Starting Whisper transcription ({model_size})...")
        segments = self._run_whisper(audio_path, language, model_size)

        # 2. Diarization (PyAnnote) - Optional
        speakers = {}
        if use_diarization and PYANNOTE_AVAILABLE:
            if ProjectConfig.HF_TOKEN:
                self.log("Starting Speaker Diarization (PyAnnote)...")
                speakers = self._run_diarization(audio_path)
            else:
                self.log("Skipping Diarization: HF_TOKEN not set in Config (.env).")
        elif use_diarization and not PYANNOTE_AVAILABLE:
            self.log("Skipping Diarization: pyannote.audio not installed.")

        # 3. Merge
        final_transcript = self._merge_transcript_speakers(segments, speakers)
        return final_transcript

    def _run_whisper(self, audio_path, language, model_size):
        self.progress(0, "transcribing")
        try:
            # Load model (cache in Project defined cache or default)
            model = WhisperModel(model_size, device=self.device, compute_type=self.compute_type)
            
            segments_generator, info = model.transcribe(
                audio_path,
                language=language if language != "auto" else None,
                beam_size=5,
                vad_filter=True
            )
            
            segments = []
            for segment in segments_generator:
                if self.stop_event_set: raise InterruptedError("Cancelled")
                segments.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip()
                })
                # Simple progress update (fake, as we don't know exact duration easily inside loop without pre-check)
                self.progress(50, "transcribing", details=f"{segment.end:.1f}s processed")
            
            self.progress(100, "transcribing")
            return segments
            
        except Exception as e:
            logger.error(f"Whisper Error: {e}")
            raise

    def _run_diarization(self, audio_path):
        self.progress(0, "diarizing")
        try:
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=ProjectConfig.HF_TOKEN
            )
            pipeline.to(torch.device(self.device))
            
            diarization = pipeline(audio_path)
            
            # Convert to list of {start, end, speaker}
            speaker_segments = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                if self.stop_event_set: raise InterruptedError("Cancelled")
                speaker_segments.append({
                    "start": turn.start,
                    "end": turn.end,
                    "speaker": speaker
                })
            
            self.progress(100, "diarizing")
            return speaker_segments
            
        except Exception as e:
            logger.error(f"Diarization Error: {e}")
            self.log(f"Diarization failed: {e}")
            return []

    def _merge_transcript_speakers(self, transcript_segments, speaker_segments):
        """
        Assigns a speaker to each transcript segment based on time overlap.
        """
        if not speaker_segments:
            return transcript_segments # Return plain transcript if no speakers

        for t_seg in transcript_segments:
            # Find speaker segment with max overlap
            best_speaker = "Unknown"
            max_overlap = 0
            
            t_start = t_seg["start"]
            t_end = t_seg["end"]
            t_dur = t_end - t_start
            
            for s_seg in speaker_segments:
                # Calculate overlap
                start = max(t_start, s_seg["start"])
                end = min(t_end, s_seg["end"])
                overlap = max(0, end - start)
                
                if overlap > max_overlap:
                    max_overlap = overlap
                    best_speaker = s_seg["speaker"]
            
            # Logic: If overlap is significant relative to segment duration, assign speaker
            if max_overlap > 0:
                t_seg["speaker"] = best_speaker
            else:
                t_seg["speaker"] = "Unknown"
                
        return transcript_segments

    def save_to_obsidian(self, segments, title, url=None):
        """
        Formats the processed segments into a Markdown note and saves it to the Vault.
        """
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        filename = f"{safe_title}.md"
        path = ProjectConfig.OBSIDIAN_VAULT / filename
        
        content = f"# {title}\n\n"
        if url:
            content += f"**Source:** {url}\n\n"
        
        content += "## Transcription\n\n"
        
        current_speaker = None
        
        for seg in segments:
            speaker = seg.get("speaker", None)
            start_fmt = str(timedelta(seconds=int(seg['start'])))
            
            if speaker and speaker != current_speaker:
                content += f"\n**{speaker}** ({start_fmt}):\n"
                current_speaker = speaker
            elif not speaker:
                 content += f"**[{start_fmt}]** "

            content += f"{seg['text']} "
            
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
            
        self.log(f"Saved note to: {path}")
        return path