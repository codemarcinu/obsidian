import pytest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pdf_shredder

def test_clean_filename():
    # clean_filename removes non-alphanumeric chars. It does NOT remove extension logic (that's in shred_pdf).
    assert pdf_shredder.clean_filename("Raport 2025 (Final).pdf") == "raport-2025-finalpdf"
    assert pdf_shredder.clean_filename("Nagłówek: Rozdział 1") == "nagłówek-rozdział-1"

@patch('pdf_shredder.fitz.open')
def test_extract_chapters_from_pdf(mock_open):
    # Mockujemy dokument PDF
    mock_doc = MagicMock()
    mock_page = MagicMock()
    
    # Symulujemy tekst na stronie z nagłówkiem "Rozdział 1"
    mock_page.get_text.return_value = "Wstęp\nBla bla bla.\nRozdział 1.\nTreść rozdziału 1."
    
    # Iterator po stronach
    mock_doc.__iter__.return_value = [mock_page]
    mock_open.return_value = mock_doc

    chapters = pdf_shredder.extract_chapters_from_pdf("dummy.pdf")
    
    # Oczekujemy co najmniej 2 sekcji (Wstęp i Rozdział 1)
    assert len(chapters) >= 2
    assert chapters[0]['title'] == "Wstęp"
    assert "Bla bla bla" in chapters[0]['content']
    assert "Treść rozdziału 1" in chapters[1]['content']

@patch('pdf_shredder.ollama.chat')
def test_process_chapter_with_ai(mock_chat):
    mock_chat.return_value = {'message': {'content': '---\ntags: [test]\n---\nSummary'}}
    result = pdf_shredder.process_chapter_with_ai("Some text")
    assert "tags: [test]" in result
