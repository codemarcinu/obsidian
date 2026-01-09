import pytest
from unittest.mock import MagicMock, patch, mock_open
import os
from ai_notes import TranscriptProcessor
from config import ProjectConfig

@pytest.fixture
def mock_config():
    with patch('config.ProjectConfig') as MockConfig:
        MockConfig.OBSIDIAN_VAULT = "/tmp/test_vault"
        MockConfig.OLLAMA_MODEL = "bielik:latest"
        yield MockConfig

@pytest.fixture
def processor(mock_config):
    return TranscriptProcessor(vault_path="/tmp/test_vault", model="bielik:latest")

def test_clean_filename(processor):
    assert processor.clean_filename("Test Title 123!") == "test-title-123"
    assert processor.clean_filename("  bad   spacing  ") == "bad-spacing"

def test_create_chunks(processor):
    text = "a" * 10000
    chunks = processor.create_chunks(text, chunk_size=6000, overlap=500)
    assert len(chunks) == 2
    assert len(chunks[0]) == 6000
    assert len(chunks[1]) == 4500 # 10000 - (6000-500)

@patch('ollama.chat')
def test_generate_metadata_success(mock_chat, processor):
    # Mock Ollama response
    mock_chat.return_value = {
        'message': {'content': '1. Test Title\n2. This is a summary.'}
    }
    
    title, summary = processor.generate_metadata("Sample text content")
    
    assert title == "Test Title"
    assert summary == "This is a summary."
    mock_chat.assert_called_once()

@patch('ollama.chat')
def test_generate_metadata_failure(mock_chat, processor):
    # Simulate an exception (e.g., model not found)
    mock_chat.side_effect = Exception("Model not found")
    
    title, summary = processor.generate_metadata("Sample text content")
    
    # Should fallback to defaults
    assert title == "Szkolenie Cybersec AutoNote"
    assert summary == "Automatycznie wygenerowana notatka."

@patch('ai_notes.open', new_callable=mock_open, read_data="Sample transcript content")
@patch('ai_notes.ObsidianGardener')
@patch('ollama.chat')
def test_process_transcript_flow(mock_chat, mock_gardener, mock_file, processor):
    # Setup mocks
    mock_chat.return_value = {
        'message': {'content': 'AI Generated Note Content'}
    }
    
    # Mock gardener success
    mock_gardener_instance = mock_gardener.return_value
    mock_gardener_instance.process_file.return_value = (True, "Linked")
    
    # Run
    success, msg = processor.process_transcript("dummy_path.txt")
    
    assert success is True
    assert "Linked" in msg
    
    # Verify file was opened to read
    mock_file.assert_any_call("dummy_path.txt", 'r', encoding='utf-8')
    
    # Verify note was saved (checking write calls)
    # We expect at least one write call for the new note
    handle = mock_file()
    handle.write.assert_called()