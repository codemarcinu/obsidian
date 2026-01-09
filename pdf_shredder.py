import os
import argparse
import fitz  # PyMuPDF
import ollama
from tqdm import tqdm
import re

# --- KONFIGURACJA ---
OBSIDIAN_VAULT_PATH = "/mnt/c/Users/marci/Documents/Obsidian Vault/Education"
OLLAMA_MODEL = "bielik"

SYSTEM_PROMPT = """
Jesteś ekspertem Compliance/IT. Masz przed sobą fragment raportu/audytu.
Twoim zadaniem jest wygenerowanie metadanych do notatki Obsidian.

Zwróć TYLKO blok YAML frontmatter i jedno zdanie podsumowania.
Format:
---
tags: [tag1, tag2]
risk_level: high/medium/low
---
# Podsumowanie
[Jedno zdanie o czym to jest]
"""

def clean_filename(text):
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'[\s_-]+', '-', text).strip('-')[:50]

def extract_chapters_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    chapters = []
    
    current_chapter_title = "Wstęp"
    current_text = []
    
    print(f"[*] Analiza struktury PDF: {pdf_path}")
    
    # Prosta heurystyka: czytamy strona po stronie
    # W wersji PRO można by analizować rozmiar czcionki (font size) żeby wykrywać nagłówki
    for page_num, page in enumerate(doc):
        text = page.get_text()
        
        # Szukamy potencjalnych nagłówków (np. "Rozdział 1", "2. Metodologia")
        # To jest uproszczone - w prawdziwym życiu PDFy to piekło formatowania
        lines = text.split('\n')
        for line in lines:
            # Jeśli linia wygląda na nagłówek (krótka, zaczyna się od cyfry lub słowa kluczowego)
            if len(line) < 50 and (re.match(r'^\d+\.', line) or "Rozdział" in line or "Sekcja" in line):
                # Zapisz poprzedni rozdział
                if current_text:
                    chapters.append({
                        "title": current_chapter_title,
                        "content": "\n".join(current_text)
                    })
                
                current_chapter_title = line.strip()
                current_text = []
            else:
                current_text.append(line)
                
    # Dodaj ostatni rozdział
    if current_text:
        chapters.append({"title": current_chapter_title, "content": "\n".join(current_text)})
        
    return chapters

def process_chapter_with_ai(text):
    # Skracamy tekst jeśli za długi dla modelu
    sample = text[:4000] 
    
    try:
        response = ollama.chat(model=OLLAMA_MODEL, messages=[
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': f"Oto fragment tekstu:\n{sample}"}
        ])
        return response['message']['content']
    except:
        return "---\ntags: [auto-generated]\n---\n# Podsumowanie\nBłąd analizy AI."

def shred_pdf(pdf_path):
    pdf_name = os.path.basename(pdf_path).replace('.pdf', '')
    safe_pdf_name = clean_filename(pdf_name)
    
    # Tworzymy folder na ten konkretny raport w Obsidianie
    output_dir = os.path.join(OBSIDIAN_VAULT_PATH, safe_pdf_name)
    os.makedirs(output_dir, exist_ok=True)
    
    chapters = extract_chapters_from_pdf(pdf_path)
    print(f"[*] Znaleziono {len(chapters)} sekcji. Przetwarzanie...")

    # Plik główny (MOC - Map of Content)
    moc_content = [f"# Raport: {pdf_name}\n\n## Spis treści"]
    
    for i, chapter in enumerate(tqdm(chapters)):
        # Jeśli sekcja jest pusta/za krótka, pomijamy
        if len(chapter['content']) < 100:
            continue
            
        safe_title = f"{i+1:02d}-{clean_filename(chapter['title'])}"
        filename = f"{safe_title}.md"
        
        # Analiza AI
        ai_metadata = process_chapter_with_ai(chapter['content'])
        
        # Składanie notatki
        full_note = f"{ai_metadata}\n\n## Treść\n{chapter['content']}\n\n---\n[[00-MOC-{safe_pdf_name}|Wróć do spisu treści]]"
        
        with open(os.path.join(output_dir, filename), 'w', encoding='utf-8') as f:
            f.write(full_note)
            
        # Dodaj do MOC
        moc_content.append(f"- [[{safe_title}|{chapter['title']}]]")

    # Zapisz MOC
    moc_filename = f"00-MOC-{safe_pdf_name}.md"
    with open(os.path.join(output_dir, moc_filename), 'w', encoding='utf-8') as f:
        f.write("\n".join(moc_content))

    print(f"\n[SUCCESS] Raport pocięty! Sprawdź folder: {output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PDF Shredder for Obsidian")
    parser.add_argument("pdf", help="Ścieżka do pliku PDF")
    args = parser.parse_args()
    
    shred_pdf(args.pdf)
