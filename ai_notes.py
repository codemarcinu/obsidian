import os
import argparse
import re
import ollama
import logging
from datetime import datetime
from tqdm import tqdm
from typing import List, Optional, Tuple, Dict, Any

# Use centralized config
from config import ProjectConfig, logger
from obsidian_manager import ObsidianGardener

class TranscriptProcessor:
    """
    Handles the processing of raw transcripts into structured Obsidian technical notes.
    Refactored to support 'Human-in-the-Loop' (Edit before Save).
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

    def generate_note_content(self, file_path: str) -> Dict[str, Any]:
        """
        Generates the note content BUT DOES NOT SAVE IT.
        Returns a dictionary with 'title', 'content', 'tags'.
        """
        self.logger.info(f"Generating content for: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                full_text = f.read()
        except FileNotFoundError:
            return {"error": f"File not found: {file_path}"}

        # Step 1: Metadata
        raw_title, summary = self.generate_metadata(full_text)
        safe_title = self.clean_filename(raw_title)[:60] or "unknown-training"
        
        # Step 2: Chunking
        chunks = self.create_chunks(full_text)
        full_notes = []
        
        # Step 3: AI Processing
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
                full_notes.append(f"\n> [!ERROR] Chunk {i+1} failed: {e}")

        all_text = " ".join(full_notes)
        compliance_tags = self.detect_compliance(all_text)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # Assemble Markdown
        markdown_content = f"""
--- 
created: {timestamp}
tags:
  - auto-generated
  - education
  - transcript
status: to-review
compliance: {compliance_tags}
---

# {raw_title}

> **Meta:** {summary}

---
{chr(10).join(full_notes)}

---
*Generated by AI Bridge v2.2*
"""
        return {
            "title": safe_title,
            "content": markdown_content,
            "tags": compliance_tags
        }

    def save_note_to_disk(self, title: str, content: str) -> str:
        """Saves the provided content to disk and runs the Gardener."""
        date_prefix = datetime.now().strftime("%Y-%m-%d")
        filename = f"{date_prefix}-{title}.md"
        filepath = os.path.join(self.vault_path, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
            
        self.logger.info(f"Note saved: {filepath}")
        
        # Step 5: Gardener (Auto-linking)
        gardener = ObsidianGardener(self.vault_path)
        gardener.process_file(filepath)
        
        return filepath

    # Legacy wrapper for CLI compatibility
    def process_transcript(self, file_path: str) -> Tuple[bool, str]:
        result = self.generate_note_content(file_path)
        if "error" in result:
            return False, result["error"]
        
        final_path = self.save_note_to_disk(result["title"], result["content"])
        return True, final_path

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