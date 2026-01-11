# 🧠 Twój Osobisty Asystent Wiedzy (AI Second Brain)

**Przewodnik Użytkownika**

## 1. Czym jest ten system?

Wyobraź sobie, że masz bardzo pracowitego, niewidzialnego asystenta, który pracuje 24 godziny na dobę. Ten asystent potrafi:

*   Słuchać Twoich nagrań głosowych i robić z nich notatki.
*   Oglądać za Ciebie filmy na YouTube i streszczać je.
*   Czytać artykuły w Internecie i wyciągać z nich to, co najważniejsze.
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

2.  **Kolejka YouTube:** W folderze `00_Inbox` masz plik `youtube_queue.md`. Wklejasz tam linki do filmów, które chcesz przetworzyć.
    *   *Co robi system:* W nocy (lub w tle) pobiera treść filmów i tworzy z nich materiały edukacyjne.

3.  **Kolejka Artykułów:** W pliku `reading_list.md` wklejasz linki do ciekawych artykułów.
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

1.  **Poranek:** Otwierasz Obsidiana. Wita Cię **Dashboard**, gdzie widzisz podsumowanie nowych notatek przetworzonych w nocy (np. 3 filmy z YouTube i raport newsowy).
2.  **W pracy:** Znajdujesz ciekawy artykuł, ale nie masz czasu czytać. Wklejasz link do pliku `reading_list.md` w folderze Inbox.
3.  **W drodze do domu:** Nagrywasz notatkę głosową: *"Pamiętaj o przeglądzie samochodu w przyszłym tygodniu i kup mleko"*. Plik automatycznie synchronizuje się do folderu `00_Inbox`.
4.  **Wieczorem:** System automatycznie przetwarza Twoje nagranie. "Przegląd samochodu" trafia na listę zadań z datą, a artykuł z pracy czeka jako streszczenie w folderze "Research".

---

## 5. Rozwiązywanie problemów (W skrócie)

*   **"System nie widzi pliku!"** – Upewnij się, że wrzuciłeś go do folderu `00_Inbox`. Daj mu chwilę (system czeka 1-2 sekundy, aż plik się skopiuje).
*   **"Gdzie jest moja notatka?"** – System mógł ją automatycznie przenieść. Sprawdź Dashboard lub folder `Zasoby`, jeśli system nie był pewien kategorii.
*   **"Kolejka YouTube nie działa"** – Sprawdź w pliku `youtube_queue.md`, czy przy linku pojawił się symbol ⏳ (w trakcie) lub ✅ (gotowe). Jeśli jest ❌, coś poszło nie tak z linkiem.

---

*Dokumentacja oparta na wersji systemu v4.5 (BrainGuard + UI + RAG).*

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