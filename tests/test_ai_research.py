import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Dodajemy katalog nadrzędny do ścieżki, aby zaimportować moduły
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import ai_research

def test_clean_filename():
    assert ai_research.clean_filename("To Jest Tytuł!") == "to-jest-tytuł"
    assert ai_research.clean_filename("DORA: Regulacje 2025") == "dora-regulacje-2025"

def test_create_chunks():
    text = "A" * 1000
    chunks = ai_research.create_chunks(text, chunk_size=100, overlap=10)
    assert len(chunks) > 0
    assert len(chunks[0]) == 100

@patch('ai_research.requests.get')
def test_fetch_article_content_success(mock_get):
    # Mockujemy odpowiedź HTML
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"<html><head><title>Test Title</title></head><body><p>Test content.</p></body></html>"
    mock_get.return_value = mock_response

    title, text = ai_research.fetch_article_content("http://fake.url")
    
    assert title == "Test Title"
    assert "Test content." in text

@patch('ai_research.requests.get')
def test_fetch_article_content_failure(mock_get):
    mock_get.side_effect = Exception("Connection error")
    title, text = ai_research.fetch_article_content("http://fake.url")
    assert title is None
    assert text is None
