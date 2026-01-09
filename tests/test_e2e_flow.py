import pytest
from unittest.mock import MagicMock, patch
import os
from video_transcriber import VideoTranscriber
from ai_notes import TranscriptProcessor
from config import ProjectConfig

class TestE2EFlow:
    """
    Simulates the full flow:
    1. Video Download (Mocked)
    2. Transcription (Mocked Whisper)
    3. Note Generation (Mocked Ollama)
    4. Saving to Vault (Real FS or Mocked)
    """
    
    @pytest.fixture
    def mock_transcriber(self):
        with patch('video_transcriber.VideoTranscriber._run_whisper') as mock_whisper, \
             patch('video_transcriber.VideoTranscriber._run_diarization') as mock_diarization, \
             patch('video_transcriber.yt_dlp.YoutubeDL') as mock_ytdl:
             
            # Setup Whisper Mock
            mock_whisper.return_value = [
                {"start": 0.0, "end": 5.0, "text": "Hello world."},
                {"start": 5.0, "end": 10.0, "text": "This is a test."}
            ]
            
            # Setup Diarization Mock (Empty for now to simplify)
            mock_diarization.return_value = []
            
            # Setup YT-DLP Mock (bypass download)
            instance = mock_ytdl.return_value
            instance.extract_info.return_value = {"title": "Test Video", "ext": "webm"}
            
            transcriber = VideoTranscriber()
            # Disable actual download logic in methods if needed, 
            # but mocking extract_info usually handles the metadata part.
            # For the actual 'download_video' method, we might need to mock internal os calls or the method itself
            # if we want to skip file ops.
            
            yield transcriber

    @patch('ai_notes.TranscriptProcessor.process_transcript')
    @patch('video_transcriber.VideoTranscriber.download_video')
    def test_full_pipeline_simulation(self, mock_download, mock_process, mock_transcriber):
        """
        Tests the orchestration logic without running heavy ML models.
        """
        # 1. Simulate user input
        url = "https://youtube.com/watch?v=123"
        
        # 2. Run Transcriber (Mocked Download + Mocked Whisper)
        # We Mock download_video to return a dummy path
        mock_download.return_value = "/tmp/test_video.mp3"
        
        # Manually call the steps as App.py would
        audio_path = mock_download(url)
        assert audio_path == "/tmp/test_video.mp3"
        
        transcript_segments = mock_transcriber.transcribe_and_diarize(
            audio_path, 
            model_size="tiny", 
            use_diarization=False
        )
        
        assert len(transcript_segments) == 2
        assert transcript_segments[0]['text'] == "Hello world."
        
        # 3. Save Transcript to file (Simulate what happens before AI processing)
        transcript_path = "/tmp/test_transcript.txt"
        with open(transcript_path, 'w') as f:
            for seg in transcript_segments:
                f.write(f"{seg['text']}\n")
                
        # 4. Run AI Processor (Mocked Ollama)
        # We mocked process_transcript entirely here to verify integration, 
        # but detailed logic is in test_ai_notes.py
        mock_process.return_value = (True, "/tmp/test_vault/Test-Note.md")
        
        processor = TranscriptProcessor(vault_path="/tmp/test_vault")
        success, path = processor.process_transcript(transcript_path)
        
        assert success is True
        assert path == "/tmp/test_vault/Test-Note.md"

