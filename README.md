# 🧠 AI Second Brain (Obsidian Hybrid WSL Pipeline) v4.5

Osobisty asystent wiedzy, który automatyzuje proces zbierania, przetwarzania i wyszukiwania informacji. System integruje się z Obsidianem, tworząc "Drugi Mózg" zasilany sztuczną inteligencją, działający w architekturze hybrydowej (WSL 2 + Windows).

> **Wersja 4.5 (Auto-Gardener):** Dodano funkcję "BrainGuard" – automatycznego strażnika, który monitoruje folder Inbox, przetwarza pliki w tle i inteligentnie kategoryzuje notatki do odpowiednich folderów w Skarbcu.

## 🚀 Główne Funkcje

### 1. 🤖 BrainGuard (Automatyzacja "Drop & Forget")
*   **Monitorowanie:** Skrypt nasłuchuje zmian w folderze `00_Inbox` na Windowsie.
*   **Audio/Wideo:** Automatycznie wykrywa nowe pliki nagrań, wykonuje transkrypcję, generuje notatkę i archiwizuje plik źródłowy.
*   **Notatki Tekstowe:** Przetwarza luźne notatki `.md` – dodaje tagi, linkuje pojęcia i formatuje YAML.
*   **Inteligentna Kategoryzacja:** AI analizuje treść i automatycznie przenosi notatkę do jednego z folderów: `Education`, `Newsy`, `Research`, `Zasoby`, `Daily`, `Prywatne`.

### 2. ⚡ ETL Pipeline (Interfejs UI)
*   **Ingest:** Pobieranie i transkrypcja z YouTube URL.
*   **Refinery:** Ręczne przetwarzanie i edycja transkryptów przed zapisaniem.
*   **Optymalizacja VRAM:** Agresywne zwalnianie modeli z pamięci GPU po każdym zadaniu.

### 3. 🔎 RAG & Chat (Baza Wiedzy)
*   **Chat:** Możliwość rozmowy z własną bazą notatek (Retrieval Augmented Generation).
*   **Indeksacja:** Wektorowa baza danych (ChromaDB) trzymana w szybkim systemie plików WSL.

### 4. 🎨 UI & UX
*   Ciemny motyw "Obsidian Dark" w interfejsie webowym.
*   Pasek boczny nawigacji.
*   Automatyczne linkowanie słów kluczowych (FlashText).

## 🛠️ Architektura Hybrydowa (WSL + Windows)

System jest zaprojektowany do działania na **WSL 2 (Ubuntu)**, ale operuje na plikach znajdujących się na dysku **Windows**.

*   **Obsidian Vault:** `/mnt/c/Users/marci/Documents/Obsidian Vault` (Windows)
*   **Silnik AI & DB:** `/home/marcin/obsidian` (WSL - dla wydajności I/O)
*   **Inbox:** Notatki trafiają do Windowsowego folderu `00_Inbox`, skąd są podejmowane przez system.

## 📦 Instalacja i Uruchomienie

1.  **Uruchomienie Interfejsu (UI):**
    Służy do ręcznego pobierania filmów z YT, czatowania z bazą i zarządzania systemem.
    ```bash
    streamlit run app.py
    ```

2.  **Uruchomienie Strażnika (Tło):**
    Służy do ciągłej automatyzacji folderu `00_Inbox`.
    ```bash
    ./start_guard.sh
    ```
    *Logi działania strażnika znajdują się w pliku `brain_guard.log`.*

## 📂 Struktura Folderów

*   `00_Inbox/` - Tutaj wrzucasz pliki (mp3, md). System stąd je zabiera.
    *   `Archive/` - Tutaj lądują przetworzone pliki audio.
*   `Daily/` - Dzienniki.
*   `Education/` - Notatki edukacyjne.
*   `Newsy/` - Wiadomości i artykuły.
*   `Prywatne/` - Notatki osobiste.
*   `Research/` - Pogłębione analizy.
*   `Zasoby/` - Inne materiały i wiedza ogólna.

## 🤖 Modele AI (Ollama)

System wykorzystuje lokalną instancję Ollama:
*   **Bielik-11b-v2.3:** Główny "mózg" do generowania treści i analizy (wysoka jakość, język polski).
*   **Llama 3.2:** Szybki model do tagowania i kategoryzacji (niskie opóźnienie).
*   **Mxbai-embed-large:** Model embeddingów do wyszukiwania semantycznego.

## 📝 Licencja

Projekt prywatny.
