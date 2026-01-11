#!/bin/bash

# Ustalenie katalogu skryptu
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Kolory
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}   🧠 OBSIDIAN AI SECOND BRAIN V2.0      ${NC}"
echo -e "${BLUE}==========================================${NC}"

# 1. Sprawdzenie venv
if [ -d "venv" ]; then
    echo -e "${GREEN}[1/6]${NC} Aktywacja wirtualnego środowiska..."
    source venv/bin/activate
else
    echo -e "${YELLOW}[1/6]${NC} Nie znaleziono venv. Tworzenie nowego środowiska..."
    python3 -m venv venv
    source venv/bin/activate
    echo -e "${GREEN}      Gotowe.${NC}"
fi

# 2. Sprawdzenie narzędzi systemowych (FFmpeg)
echo -e "${BLUE}[2/6]${NC} Sprawdzanie narzędzi systemowych..."
if ! command -v ffmpeg &> /dev/null; then
    echo -e "${RED}❌ BŁĄD: Nie znaleziono ffmpeg!${NC}"
    echo -e "Jest on wymagany do przetwarzania audio/wideo."
    echo -e "Zainstaluj go komendą: ${YELLOW}sudo apt install -y ffmpeg${NC}"
    exit 1
else
    echo -e "${GREEN}      FFmpeg jest zainstalowany.${NC}"
fi

# 3. Aktualizacja zależności
echo -e "${BLUE}[3/6]${NC} Weryfikacja bibliotek (może to chwilę potrwać)..."
# Pokazujemy postęp instalacji, ale filtrujemy komunikaty "Requirement already satisfied" dla czytelności
pip install -r requirements.txt | grep -v "already satisfied" || true
echo -e "${GREEN}      Biblioteki sprawdzone.${NC}"

# 4. Sprawdzenie konfiguracji i czyszczenie
echo -e "${BLUE}[4/6]${NC} Przygotowanie środowiska (czyszczenie temp)..."
mkdir -p obsidian_db/_INBOX
mkdir -p temp_processing
# Usuwanie plików starszych niż 24h z temp
find temp_processing -type f -mmin +1440 -delete 2>/dev/null || true

if [ ! -f ".env" ]; then
    echo -e "${YELLOW}      UWAGA: Brak pliku .env. Uruchamiam z domyślnymi ustawieniami.${NC}"
else
    echo -e "${GREEN}      Plik .env wczytany.${NC}"
fi

# 5. Sprawdzenie Ollama (AI)
echo -e "${BLUE}[5/6]${NC} Sprawdzanie modelu AI (Ollama)..."
python3 check_ollama.py
echo -e "${GREEN}      Gotowe.${NC}"

# --- URUCHOMIENIE BRAIN GUARD W TLE ---
echo -e "${BLUE}[+]${NC} Uruchamianie Strażnika (BrainGuard)..."

# Funkcja czyszcząca - zabija procesy w tle przy wyjściu (Ctrl+C)
cleanup() {
    echo -e "\n${YELLOW}Zamykanie systemu...${NC}"
    if [ ! -z "$GUARD_PID" ]; then
        echo "Zabijanie procesu Strażnika (PID: $GUARD_PID)..."
        kill $GUARD_PID
    fi
    exit
}

# Rejestracja sygnału wyjścia
trap cleanup SIGINT SIGTERM

# Start Strażnika w tle, logi idą do pliku
python3 -u brain_guard.py > brain_guard_runtime.log 2>&1 &
GUARD_PID=$!
echo -e "${GREEN}      Strażnik działa w tle (PID: $GUARD_PID).${NC}"

# 6. Start aplikacji
echo -e "${BLUE}[6/6]${NC} Uruchamianie interfejsu Streamlit..."
echo -e "${YELLOW}----------------------------------------------------------${NC}"
echo -e "${GREEN}  👉 SKOPIUJ TEN LINK DO PRZEGLĄDARKI W WINDOWS: ${NC}"
echo -e "${GREEN}     http://localhost:8501 ${NC}"
echo -e "${YELLOW}----------------------------------------------------------${NC}"

streamlit run app.py --server.address=0.0.0.0 --server.port=8501 --server.headless=true --server.enableCORS=false --server.enableXsrfProtection=false