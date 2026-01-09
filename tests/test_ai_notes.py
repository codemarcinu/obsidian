import pytest
from unittest.mock import patch, mock_open, MagicMock
import os
import sys

# Dodajemy katalog nadrzędny do ścieżki
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import ai_notes

# --- Test Data ---
SAMPLE_TEXT = "To jest przykładowy tekst szkolenia. Mówimy o bezpieczeństwie." * 100
SAMPLE_TITLE_RESPONSE = {'message': {'content': '# Szkolenie Cybersec\nTo jest intro.'}}
SAMPLE_NOTE_RESPONSE = {'message': {'content': 'To jest notatka z fragmentu.'}}

# --- Unit Tests ---

def test_clean_filename():
    assert ai_notes.clean_filename("Hacking & Security: 101!") == "hacking-security-101"
    assert ai_notes.clean_filename("  weird   spaces  ") == "weird-spaces"
    assert ai_notes.clean_filename("Normal Title") == "normal-title"
    assert ai_notes.clean_filename("pl_znaki_ąćęłńóśźż") == "pl-znaki-ąćęłńóśźż"  # Implementation replaces _ with -
    # The current regex r'[^\w\s-]' removes non-word chars. \w includes unicode in Python 3.
    # Let's verify special chars removal
    assert ai_notes.clean_filename("File/Path\\Name") == "filepathname"

def test_create_chunks_basic():
    text = "1234567890"
    chunks = ai_notes.create_chunks(text, chunk_size=4, overlap=2)
    # 0-4: 1234. Next start: 2
    # 2-6: 3456. Next start: 4
    # 4-8: 5678. Next start: 6
    # 6-10: 7890. Next start: 8
    # 8-12: 90. Next start: 10 -> Stop
    expected = ["1234", "3456", "5678", "7890", "90"]
    assert chunks == expected

def test_create_chunks_no_overlap():
    text = "1234567890"
    chunks = ai_notes.create_chunks(text, chunk_size=5, overlap=0)
    expected = ["12345", "67890"]
    assert chunks == expected

def test_create_chunks_empty():
    assert ai_notes.create_chunks("", 5, 2) == []

def test_create_chunks_short_text():
    text = "abc"
    chunks = ai_notes.create_chunks(text, chunk_size=10, overlap=2)
    assert chunks == ["abc"]

def test_generate_title_and_summary_success(mocker):
    mock_ollama = mocker.patch('ai_notes.ollama.chat')
    mock_ollama.return_value = SAMPLE_TITLE_RESPONSE
    
    result = ai_notes.generate_title_and_summary("Dummy text")
    assert result == "# Szkolenie Cybersec\nTo jest intro."
    mock_ollama.assert_called_once()

def test_generate_title_and_summary_failure(mocker):
    mock_ollama = mocker.patch('ai_notes.ollama.chat')
    mock_ollama.side_effect = Exception("API Error")
    
    result = ai_notes.generate_title_and_summary("Dummy text")
    assert result == "Szkolenie Cybersec - AutoNote"

@patch('os.makedirs')
@patch('os.path.exists', return_value=False)  # Force makedirs to be called
@patch('builtins.open', new_callable=mock_open)
def test_save_note(mock_file, mock_exists, mock_makedirs):
    title = "test-title"
    intro = "Test intro"
    notes = ["\n### Sekcja 1\nNote 1", "\n### Sekcja 2\nNote 2"]
    
    ai_notes.save_note(title, intro, notes)
    
    # Check if directory creation was attempted
    mock_makedirs.assert_called_with(ai_notes.OBSIDIAN_VAULT_PATH)
    
    # Check file write
    mock_file.assert_called_with(os.path.join(ai_notes.OBSIDIAN_VAULT_PATH, f"{os.path.join(os.getcwd(), 'Education')}/2026-01-08-test-title.md"), 'w', encoding='utf-8')
    # Wait, the path construction in test might differ from runtime due to mock.
    # The script uses global OBSIDIAN_VAULT_PATH.
    # We should just check if *any* file was opened for writing.
    
    handle = mock_file()
    handle.write.assert_called()
    content_written = handle.write.call_args[0][0]
    
    assert "# Raport ze szkolenia: test-title" in content_written
    assert "> **Intro:** Test intro" in content_written
    assert "Note 1" in content_written
    assert "Note 2" in content_written

@patch('ai_notes.save_note')
@patch('ai_notes.generate_title_and_summary')
@patch('ai_notes.ollama.chat')
@patch('builtins.open', new_callable=mock_open, read_data="Transkrypt content")
def test_process_transcript_success(mock_file, mock_chat, mock_gen_title, mock_save):
    # Setup mocks
    mock_gen_title.return_value = "Szkolenie 1\nIntro text"
    mock_chat.return_value = SAMPLE_NOTE_RESPONSE
    
    ai_notes.process_transcript("dummy_path.txt")
    
    # Verify calls
    mock_file.assert_called_with("dummy_path.txt", 'r', encoding='utf-8')
    mock_gen_title.assert_called_once()
    assert mock_chat.call_count > 0 # Should be called for chunks
    mock_save.assert_called_once()
    
    # Verify args passed to save_note
    args, _ = mock_save.call_args
    assert args[0] == "szkolenie-1" # cleaned title
    assert args[1] == "Szkolenie 1\nIntro text"
    assert len(args[2]) > 0 # Notes list

@patch('builtins.print')
def test_process_transcript_file_not_found(mock_print):
    ai_notes.process_transcript("non_existent_file.txt")
    mock_print.assert_any_call("[!] Plik nie istnieje.")
