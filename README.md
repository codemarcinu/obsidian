# 🧠 AI Second Brain (Obsidian Pipeline) v4.0

Osobisty asystent wiedzy, który automatyzuje proces zbierania, przetwarzania i wyszukiwania informacji. System integruje się z Obsidianem, tworząc "Drugi Mózg" zasilany sztuczną inteligencją.

> **Wersja 4.0 (ETL):** Architektura została przebudowana na asynchroniczny potok ETL (Extract-Transform-Load), aby zapobiegać błędom OOM (Out Of Memory) na kartach GPU z ograniczoną pamięcią (np. RTX 3060 12GB).

## 🚀 Główne Funkcje

1.  **ETL Pipeline (Nowość!):**
    *   **Krok 1: Ingest (Pobieranie):** Pobiera wideo i transkrybuje dźwięk (Faster-Whisper), zapisując surowe dane do "Poczekalni" (`_INBOX`). Po zakończeniu natychmiast zwalnia pamięć VRAM.
    *   **Krok 2: Refinery (Rafineria):** Przetwarza dane z Poczekalni. Używa LLM (Ollama) do generowania notatek, a następnie FlashText do błyskawicznego linkowania pojęć.
2.  **Inteligentny Interfejs (Streamlit):**
    *   Pełne spolszczenie interfejsu.
    *   Zakładki oddzielające procesy obciążające GPU (Ingest) od procesów logicznych (Refinery).
3.  **Zarządzanie Pamięcią:**
    *   Agresywne zwalnianie modeli z VRAM (Load-Run-Unload).
    *   Dedykowany moduł Garbage Collector.

## 🛠️ Wymagania

*   System: Linux (zalecane) / Windows / macOS
*   **GPU:** NVIDIA z obsługą CUDA (zalecane min. 8GB VRAM dla dużych modeli Whisper).
*   Python 3.10+
*   [Ollama](https://ollama.com/) (uruchomiona lokalnie)
*   [FFmpeg](https://ffmpeg.org/) (do przetwarzania audio)

## 📦 Instalacja

1.  **Sklonuj repozytorium:**
    ```bash
    git clone https://github.com/codemarcinu/obsidian.git
    cd obsidian
    ```

2.  **Stwórz środowisko wirtualne:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Zainstaluj zależności:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Konfiguracja:**
    *   Upewnij się, że masz zainstalowany model w Ollama (np. `bielik`, `mistral`):
        ```bash
        ollama pull bielik
        ```
    *   Edytuj `config.py` lub `.env`, aby wskazać ścieżkę do swojego skarbca Obsidian (`OBSIDIAN_VAULT_PATH`).

## ▶️ Uruchomienie

Aby uruchomić aplikację:

```bash
./run_brain.sh
```
*Skrypt automatycznie czyści pliki tymczasowe przed startem.*

## 📂 Struktura Projektu

*   `app.py` - Interfejs użytkownika (Streamlit) z podziałem na zakładki Ingest/Refinery.
*   `video_transcriber.py` - Bezstanowy moduł transkrypcji (Whisper). Ładuje model tylko na czas pracy.
*   `ai_notes.py` - Silnik generowania notatek (LLM -> Markdown).
*   `obsidian_manager.py` - "Ogrodnik": Linkuje notatki (FlashText) i zarządza tagami.
*   `utils/memory.py` - Narzędzia do czyszczenia VRAM i Cache.
*   `obsidian_db/_INBOX` - Strefa buforowa dla przetworzonych transkrypcji (JSON).

## 🤖 Modele AI

*   **Transkrypcja:** `faster-whisper` (modele: base, small, medium, large-v3).
*   **LLM:** Domyślnie `bielik` (konfigurowalne w `.env` lub `config.py`).

## 📝 Licencja

Projekt prywatny / MIT.