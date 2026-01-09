# 🧠 AI Second Brain (Obsidian Pipeline)

Osobisty asystent wiedzy, który automatyzuje proces zbierania, przetwarzania i wyszukiwania informacji. System integruje się z Obsidianem, tworząc "Drugi Mózg" zasilany sztuczną inteligencją.

## 🚀 Główne Funkcje

1.  **Wideo do Notatki (Video Pipeline):**
    *   Pobiera wideo z YouTube/URL.
    *   Transkrybuje dźwięk (Whisper).
    *   Generuje techniczną notatkę Markdown (Ollama/LLM).
    *   **Auto-Ogrodnik:** Automatycznie formatuje notatkę i linkuje kluczowe pojęcia do istniejącej bazy wiedzy.

2.  **RAG Chat (Retrieval-Augmented Generation):**
    *   Czatuj ze swoim Obsidianem.
    *   System wektoryzuje Twoje notatki i pozwala zadawać pytania typu: *"Co mam w notatkach na temat Linuxa?"*.

3.  **Inteligentny Interfejs (Streamlit):**
    *   Wygodny panel boczny do nawigacji.
    *   Zarządzanie procesami w tle.

## 🛠️ Wymagania

*   System: Linux (zalecane) / Windows / macOS
*   Python 3.10+
*   [Ollama](https://ollama.com/) (uruchomiona lokalnie)
*   [FFmpeg](https://ffmpeg.org/) (do przetwarzania audio)

## 📦 Instalacja

1.  **Sklonuj repozytorium:**
    ```bash
    git clone https://github.com/TWOJA_NAZWA_UZYTKOWNIKA/obsidian.git
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
    *   Upewnij się, że masz zainstalowany model w Ollama (domyślnie `bielik` lub inny zdefiniowany w skryptach):
        ```bash
        ollama pull bielik
        ```
    *   Stwórz plik `.env` (opcjonalnie, jeśli używasz zewnętrznych API).

## ▶️ Uruchomienie

Aby uruchomić główny interfejs:

```bash
streamlit run app.py
```

## 📂 Struktura Projektu

*   `app.py` - Główny interfejs użytkownika (Streamlit).
*   `ai_notes.py` - Silnik generowania notatek z transkrypcji.
*   `obsidian_manager.py` - "Ogrodnik": czyści formatowanie i auto-linkuje notatki.
*   `video_transcriber.py` - Pobieranie wideo i transkrypcja (Whisper).
*   `rag_engine.py` - Obsługa bazy wektorowej i wyszukiwania (RAG).
*   `ai_research.py` / `news_agent.py` - Moduły eksperymentalne do researchu.

## 🤖 Modele AI

Domyślna konfiguracja używa lokalnych modeli przez Ollama:
*   **Transkrypcja:** Whisper (via `video_transcriber.py`)
*   **Generowanie Notatek:** `bielik` (lub `llama3` - edytuj `ai_notes.py`)
*   **Chat RAG:** `bielik` (edytuj `rag_engine.py`)

## 📝 Licencja

Projekt prywatny / MIT.