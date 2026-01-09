import os
import argparse
import re
import ollama
import logging
from datetime import datetime
from tqdm import tqdm
from typing import List, Optional, Tuple

# Use centralized config
from config import ProjectConfig, logger
from obsidian_manager import ObsidianGardener

class TranscriptProcessor:
    """
    Handles the processing of raw transcripts into structured Obsidian technical notes.
    Refactored to be importable and state-aware.
    """
    
    SYSTEM_PROMPT = """
    Jesteś Ekspertem Technicznym i Analitykiem Cyberbezpieczeństwa. Tworzysz precyzyjną dokumentację techniczną w formacie Obsidian Markdown.

    Twoje zadanie: Przeanalizuj podany transkrypt wideo/szkolenia i stwórz zwięzłą, techniczną notatkę.

    WYMAGANIA FORMATOWANIA:
    1. Używaj TYLKO nagłówków H2 (##) dla głównych sekcji. Nie używaj H1 (tytuł jest w metadanych).
    2. Kluczowe pojęcia, narzędzia i technologie pogrubiaj (np. **nmap**, **SQL Injection**).
    3. WSZYSTKIE komendy, ścieżki plików, fragmenty kodu i logi umieszczaj w blokach kodu:
       ```bash
       nmap -sV 192.168.1.1
       ```
    4. Ignoruj całkowicie dygresje, żarty, powitania ("Cześć", "Dajcie suba") i lanie wody.
    5. Pisz w stylu bezosobowym, technicznym (np. "Należy wykonać skan...", "Podatność polega na...").
    6. Jeśli fragment nie zawiera konkretnej wiedzy, pomiń go.

    CELEM JEST DOKŁADNOŚĆ. Nie zmyślaj. Opieraj się tylko na tekście.
    """

    def __init__(self, vault_path: Optional[str] = None, model: str = None):
        """
        Initialize the processor with configurable vault path and model.
        """
        self.vault_path = vault_path if vault_path else str(ProjectConfig.OBSIDIAN_VAULT)
        self.model = model if model else ProjectConfig.OLLAMA_MODEL
        self.logger = logging.getLogger("TranscriptProcessor")
        
        # Ensure vault exists
        os.makedirs(self.vault_path, exist_ok=True)

    def clean_filename(self, title: str) -> str:
        """Sanitizes the title for filesystem safety."""
        title = title.lower()
        title = re.sub(r'[^\w\s-]', '', title)
        return re.sub(r'[\s_-]+', '-', title).strip('-')

    def create_chunks(self, text: str, chunk_size: int = 6000, overlap: int = 500) -> List[str]:
        """Splits text into overlapping chunks for context preservation."""
        chunks = []
        start = 0
        text_len = len(text)
        while start < text_len:
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start += chunk_size - overlap
        return chunks

    def generate_metadata(self, text_sample: str) -> Tuple[str, str]:
        """Generates a technical title and one-sentence summary."""
        prompt = (
            "Jesteś bibliotekarzem. Na podstawie tego fragmentu stwórz: "
            "1. Krótki techniczny tytuł (max 6 słów, bez znaków specjalnych). "
            "2. Jedno zdanie streszczenia."
        )
        try:
            response = ollama.chat(
                model=self.model, 
                messages=[{'role': 'system', 'content': prompt}, 
                          {'role': 'user', 'content': text_sample[:2000]}],
                options={'temperature': 0.3} # Precision mode
            )
            content = response['message']['content']
            
            # Simple parsing
            lines = content.split('\n')
            raw_title = lines[0].replace('Tytuł:', '').replace('1.', '').strip()
            summary = lines[1].replace('Streszczenie:', '').replace('2.', '').strip() if len(lines) > 1 else "Brak podsumowania"
            
            return raw_title, summary
        except Exception as e:
            self.logger.error(f"Error generating metadata: {e}")
            return "Szkolenie Cybersec AutoNote", "Automatycznie wygenerowana notatka."

    def detect_compliance(self, text: str) -> List[str]:
        """Helper to identify DORA/RODO/NIS2 contexts in transcripts."""
        found = []
        text_lower = text.lower()
        if any(kw in text_lower for kw in ["rodo", "gdpr", "osobowe"]): found.append("RODO")
        if any(kw in text_lower for kw in ["dora", "rezyliencja", "ict"]): found.append("DORA")
        if any(kw in text_lower for kw in ["nis2", "dyrektywa", "cyberbezpieczeństwo"]): found.append("NIS2")
        return found if found else ["TBC"]

    def process_transcript(self, file_path: str) -> Tuple[bool, str]:
        """
        Main logic to process a transcript file.
        Returns: (Success (bool), Message/Path (str))
        """
        self.logger.info(f"Processing transcript: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                full_text = f.read()
        except FileNotFoundError:
            msg = f"File not found: {file_path}"
            self.logger.error(msg)
            return False, msg

        # Step 1: Metadata
        raw_title, summary = self.generate_metadata(full_text)
        safe_title = self.clean_filename(raw_title)[:60] or "unknown-training"
        
        # Step 2: Chunking
        chunks = self.create_chunks(full_text)
        self.logger.info(f"Generated {len(chunks)} chunks using model {self.model}")

        # Step 3: AI Processing
        full_notes = []
        for i, chunk in enumerate(tqdm(chunks, desc="AI Analysis", unit="chunk")):
            try:
                response = ollama.chat(
                    model=self.model, 
                    messages=[{'role': 'system', 'content': self.SYSTEM_PROMPT}, 
                              {'role': 'user', 'content': chunk}],
                    options={'temperature': 0.2} 
                )
                note_part = response['message']['content']
                full_notes.append(f"\n## Część {i+1}\n{note_part}")
            except Exception as e:
                err_msg = f"\n> [!ERROR] Chunk {i+1} processing failed: {e}"
                self.logger.error(err_msg)
                full_notes.append(err_msg)

        # Step 4: Save
        final_path = self.save_note(safe_title, summary, full_notes)
        
        # Step 5: Gardener (Auto-linking)
        if final_path:
            self.logger.info(f"Running Gardener on: {final_path}")
            gardener = ObsidianGardener(self.vault_path)
            success, msg = gardener.process_file(final_path)
            return success, msg
        
        return False, "Failed to save note."

    def save_note(self, title: str, intro: str, notes_list: List[str]) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        date_prefix = datetime.now().strftime("%Y-%m-%d")
        filename = f"{date_prefix}-{title}.md"
        filepath = os.path.join(self.vault_path, filename)
        
        all_text = " ".join(notes_list)
        compliance_tags = self.detect_compliance(all_text)
        
        content = f"""
---
created: {timestamp}
tags:
  - auto-generated
  - education
  - transcript
status: to-review
compliance: {compliance_tags}
---

# {title}

> **Meta:** {intro}

---
{chr(10).join(notes_list)}

---
*Generated by AI Bridge (Refactored Pipeline)*
"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

        self.logger.info(f"Note saved: {filepath}")
        return filepath

# CLI Compatibility Wrapper
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="Path to transcript file")
    parser.add_argument("--output", help="Target Obsidian folder")
    parser.add_argument("--model", help="Ollama model to use")
    
    args = parser.parse_args()
    
    processor = TranscriptProcessor(
        vault_path=args.output,
        model=args.model
    )
    
    success, msg = processor.process_transcript(args.file)
    if success:
        print(f"SUCCESS: {msg}")
    else:
        print(f"ERROR: {msg}")
