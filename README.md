# 🧠 Twój Osobisty Asystent Wiedzy (AI Second Brain)

**Przewodnik Użytkownika**

## 1. Czym jest ten system?

Wyobraź sobie, że masz bardzo pracowitego, niewidzialnego asystenta, który pracuje 24 godziny na dobę. Ten asystent potrafi:

*   Słuchać Twoich nagrań głosowych i robić z nich notatki.
*   Oglądać za Ciebie filmy na YouTube i streszczać je.
*   Czytać artykuły w Internecie i wyciągać z nich to, co najważniejsze.
*   Czytać Twoje dokumenty (PDF, Skany) i zdjęcia, zamieniając je na tekst.
*   Pamiętać wszystko, co kiedykolwiek zapisałeś, i odpowiadać na pytania na podstawie tej wiedzy.

System ten łączy Twoje notatki (w aplikacji Obsidian) ze Sztuczną Inteligencją, tworząc Twój "Drugi Mózg".

---

## 2. Jak to działa? (Dwa tryby pracy)

System posiada dwa oblicza. Możesz korzystać z jednego lub obu, w zależności od potrzeb.

### A. "Niewidzialny Strażnik" (BrainGuard) 🤖

To tryb automatyczny ("Wrzuć i Zapomnij"). Działa w tle i obserwuje jeden konkretny folder w Twoim komputerze: **`00_Inbox`**.

**Jak z tego korzystać?**

1.  **Nagrania głosowe:** Wrzucasz plik audio (np. z dyktafonu w telefonie) do folderu `00_Inbox`.
    *   *Co robi system:* Zamienia mowę na tekst, tworzy ładną notatkę, wyciąga listę zadań (np. "Kupić mleko", "Wysłać przelew") i segreguje notatkę do odpowiedniego folderu.

2.  **Dokumenty i Zdjęcia (NOWOŚĆ):** Wrzucasz plik PDF, skan lub zdjęcie (JPG/PNG).
    *   *Co robi system:* Używa Google Vision ("oczu" AI) do odczytania tekstu ze zdjęć/skanów. Rozpoznaje, czy to faktura, recepta czy notatka wizualna, i kataloguje ją odpowiednio (np. do folderu `Finanse` lub `Zdrowie`). Zdjęcia są przenoszone do folderu `Assets` i wklejane bezpośrednio do notatki.

3.  **Kolejka YouTube:** W folderze `00_Inbox` masz plik `youtube_queue.md`. Wklejasz tam linki do filmów, które chcesz przetworzyć.
    *   *Co robi system:* W nocy (lub w tle) pobiera treść filmów i tworzy z nich materiały edukacyjne.

4.  **Kolejka Artykułów:** W pliku `reading_list.md` wklejasz linki do ciekawych artykułów.
    *   *Co robi system:* Czyta je za Ciebie i tworzy streszczenia "tl;dr" (za długie; nie czytałem).

### B. "Centrum Dowodzenia" (Aplikacja w przeglądarce) 🖥️

To panel sterowania, który otwierasz w przeglądarce internetowej, gdy chcesz ręcznie zarządzać systemem lub z nim "porozmawiać".

**Do czego służy?**

*   **Czat z Wiedzą (RAG):** Możesz zapytać: *"Co mówiłem w zeszłym miesiącu o projekcie X?"* lub *"Jakie mam notatki na temat bezpieczeństwa?"*. System przeszuka Twoje pliki i udzieli odpowiedzi.
*   **Ręczne Pobieranie:** Jeśli chcesz "na już" przetworzyć film z YouTube i widzieć postęp na pasku ładowania.
*   **Przegląd Newsów:** Klikasz jeden przycisk, a system pobiera najnowsze wiadomości z cyberbezpieczeństwa i tworzy dla Ciebie "poranną gazetę".

---

## 3. Co system robi za Ciebie? (Główne Funkcje)

### 🎙️ Notatki ze Spotkań i Audio (Transkrypcja)

Nie musisz już ręcznie notować podczas spotkań czy spacerów. Nagraj się, wrzuć plik do systemu.

*   **Rezultat:** Otrzymasz dokument z podziałem na tematy, podsumowaniem i listą zadań.
*   **Inteligentne Zadania:** Jeśli powiesz "Muszę zapłacić fakturę do piątku", system wykryje to jako zadanie z datą i priorytetem.

### 📄 Inteligentne Dokumenty (OCR & Wizja) - NOWOŚĆ

Masz skan faktury, zdjęcie paragonu lub odręczną notatkę?

*   **Działanie:** Wrzucasz plik (PDF, JPG, PNG) do Inbox.
*   **Technologia:** Wykorzystuje Google Vision API do precyzyjnego odczytu tekstu (OCR) i rozpoznawania obiektów.
*   **Rezultat:**
    *   **PDF/Dokumenty:** Przekonwertowane na tekst, otagowane (np. RODO, DORA) i zapisane w folderze `Compliance` lub `Finanse`.
    *   **Zdjęcia:** Stworzona notatka wizualna z opisem tego, co jest na zdjęciu, oraz pełnym odczytanym tekstem.

### 🎬 Oglądanie YouTube (Edukacja)

Chcesz wiedzy z godzinnego wykładu, ale masz tylko 5 minut?

*   **Działanie:** Wklejasz link. System "ogląda" wideo.
*   **Rezultat:** Notatka w stylu akademickim lub wpis na bloga, zawierająca kluczowe punkty wiedzy bez "lania wody".

### 📰 Twój Osobisty Prasówka (News Agent)

Zamiast przeglądać 10 stron internetowych codziennie rano:

*   **Działanie:** System skanuje zaufane źródła (np. Sekurak, Niebezpiecznik).
*   **Filtr:** Odrzuca reklamy i mało istotne treści.
*   **Rezultat:** Tworzy jeden raport dzienny ("Daily Digest") z najważniejszymi informacjami. Może nawet wygenerować plik MP3, żebyś mógł posłuchać newsów w drodze do pracy!

### 🔍 Inteligentne Badania (Web Research)

Widzisz długi, skomplikowany artykuł techniczny?

*   **Działanie:** Dajesz systemowi link.
*   **Rezultat:** Otrzymasz analizę zawierającą fakty, konfiguracje i konkrety, z pominięciem marketingowego wstępu.

### 🧹 Porządkowanie (Ogrodnik / Gardener)

Nie martw się, gdzie zapisać notatkę.

*   **Działanie:** System sam analizuje treść. Jeśli to faktura – trafi do "Finanse". Jeśli to artykuł o Pythonie – trafi do "Edukacja".
*   **Linkowanie:** System sam połączy nową notatkę z innymi, które już masz, tworząc sieć powiązań.

---

## 4. Twój Dzień z Systemem (Przykładowy Scenariusz)

1.  **Poranek:** Otwierasz Obsidiana. Wita Cię **Dashboard**, gdzie widzisz podsumowanie nowych notatek przetworzonych w nocy.
2.  **W pracy:** Robisz zdjęcie tablicy po spotkaniu i wrzucasz do Inbox. Po chwili masz w Obsidianie notatkę z przepisanym tekstem z tablicy.
3.  **W drodze do domu:** Nagrywasz notatkę głosową: *"Zapłacić fakturę za prąd, którą wrzuciłem wcześniej"*.
4.  **Wieczorem:** System połączył fakty – masz notatkę ze zdjęcia faktury w folderze Finanse oraz zadanie w liście zadań.

---

## 5. Rozwiązywanie problemów (W skrócie)

*   **"System nie widzi pliku!"** – Upewnij się, że wrzuciłeś go do folderu `00_Inbox`. Daj mu chwilę (system czeka 1-2 sekundy, aż plik się skopiuje).
*   **"Gdzie jest moja notatka?"** – System mógł ją automatycznie przenieść. Sprawdź Dashboard lub folder `Zasoby`, jeśli system nie był pewien kategorii.
*   **"OCR nie działa"** – Upewnij się, że plik `gcp_key.json` jest poprawny i znajduje się w głównym katalogu projektu.

---

*Dokumentacja oparta na wersji systemu v5.0 (BrainGuard + Vision + RAG).*

---
---

# 🔧 Sekcja Techniczna (Administrator)

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
    Służy do ciągłej automatyzacji folderu `00_Inbox`. Obsługuje teraz PDF i Obrazy!
    ```bash
    ./start_guard.sh
    ```
    *Logi działania strażnika znajdują się w pliku `brain_guard.log`.*

## 📂 Struktura Folderów

*   `00_Inbox/` - Tutaj wrzucasz pliki (mp3, md, pdf, jpg, png). System stąd je zabiera.
    *   `Archive/` - Tutaj lądują przetworzone pliki źródłowe.
*   `Assets/` - Tutaj trafiają obrazy wyciągnięte z notatek lub przeniesione z Inbox.
*   `Daily/` - Dzienniki.
*   `Education/` - Notatki edukacyjne.
*   `Newsy/` - Wiadomości i artykuły.
*   `Compliance/` - Dokumenty prawne/audytowe.
*   `Finanse/` - Faktury i dokumenty finansowe.
*   `Zdrowie/` - Dokumentacja medyczna.

## 🤖 Modele AI (Ollama & Google)

*   **Ollama (Lokalnie):** Bielik-11b (Mózg), Llama 3.2 (Worker), Mxbai (Embed).
*   **Google Cloud Vision (Chmura):** Zaawansowany OCR i rozpoznawanie obrazu dla dokumentów i zdjęć. (Wymaga `gcp_key.json`).
