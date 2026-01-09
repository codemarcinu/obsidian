import os
import shutil
import subprocess
from pathlib import Path

# --- KONFIGURACJA ---
# Ścieżka do folderu z transkrypcjami (Windows D:\...)
INPUT_DIR = "/mnt/d/transkrypcje"

# Ścieżka do Twojego Obsidiana (Windows)
OBSIDIAN_DIR = "/mnt/c/Users/marci/Documents/Obsidian Vault/Education" 

# Folder na przetworzone pliki (utworzy się sam wewnątrz folderu wejściowego)
ARCHIVE_DIR = os.path.join(INPUT_DIR, "processed")

def process_all():
    # Upewnij się, że foldery istnieją (INPUT_DIR musi istnieć, resztę stworzymy)
    if not os.path.exists(INPUT_DIR):
        print(f"[!] Błąd: Folder wejściowy nie istnieje: {INPUT_DIR}")
        return

    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    os.makedirs(OBSIDIAN_DIR, exist_ok=True)

    # Znajdź wszystkie pliki .txt
    files = [f for f in os.listdir(INPUT_DIR) if f.endswith('.txt')]
    
    if not files:
        print("[i] Brak nowych plików do przetworzenia.")
        return

    print(f"[*] Znaleziono {len(files)} nowych transkrypcji.")

    for filename in files:
        file_path = os.path.join(INPUT_DIR, filename)
        
        print(f"\n>>> Rozpoczynam pracę nad: {filename}")
        
        # Uruchomienie ai_notes.py jako podprocesu
        # Zakładamy, że jesteśmy w katalogu z ai_notes.py
        cmd = [
            "./venv/bin/python", 
            "ai_notes.py", 
            file_path, 
            "--output", OBSIDIAN_DIR
        ]
        
        try:
            subprocess.run(cmd, check=True)
            
            # Po sukcesie przenieś plik do archiwum
            shutil.move(file_path, os.path.join(ARCHIVE_DIR, filename))
            print(f"[+] Przeniesiono {filename} do archiwum.")
            
        except subprocess.CalledProcessError as e:
            print(f"[!] Błąd podczas przetwarzania {filename} (skrypt zwrócił błąd): {e}")
        except Exception as e:
            print(f"[!] Nieoczekiwany błąd przy pliku {filename}: {e}")

if __name__ == "__main__":
    process_all()
