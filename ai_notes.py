import os
import re
import ollama
import logging
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from tqdm import tqdm
from pathlib import Path

from config import ProjectConfig, logger
from obsidian_manager import ObsidianGardener

class TranscriptProcessor:
    """
    Refactored Note Generator: Converts raw transcripts into structured technical documentation.
    Implements Point 6 (Compliance Tagging) and Point 1 (Direct Imports).
    """
    
    SYSTEM_PROMPT = """
    Jesteś Senior Python Architect i Security Engineer. Twoim zadaniem jest stworzenie profesjonalnej dokumentacji technicznej w formacie Markdown dla Obsidian.

    ZASADY:
    1. Nagłówki: ## dla sekcji, ### dla podsekcji.
    2. Kod: Zawsze używaj bloków kodu z określeniem języka (bash, python, yaml).
    3. Styl: Techniczny, zwięzły, bezosobowy.
    4. Compliance: Jeśli temat dotyczy bezpieczeństwa, infrastruktury krytycznej lub danych, wyróżnij aspekty DORA, NIS2 lub RODO.
    
    WYJŚCIE: Tylko czysty Markdown.
    """

    def __init__(self, model: Optional[str] = None):
        self.model = model or ProjectConfig.OLLAMA_MODEL
        self.vault_path = ProjectConfig.OBSIDIAN_VAULT
        self.logger = logging.getLogger("TranscriptProcessor")

    def _generate_metadata(self, text: str) -> Tuple[str, str]:
        """Uses LLM to generate title and short summary."""
        prompt = "Na podstawie tekstu podaj: 1. Krótki tytuł techniczny (bez znaków specjalnych), 2. Jednozdaniowe podsumowanie."
        try:
            resp = ollama.chat(
                model=self.model,
                messages=[{'role': 'user', 'content': f"{prompt}\n\nTekst: {text[:2000]}"}]
            )
            content = resp['message']['content']
            lines = content.split('\n')
            title = lines[0].strip().replace("1. ", "").replace("Tytuł: ", "")
            summary = lines[1].strip().replace("2. ", "").replace("Podsumowanie: ", "") if len(lines) > 1 else "Brak podsumowania."
            return title, summary
        except Exception:
            return "Note-" + datetime.now().strftime("%Y%m%d-%H%M"), "Automatyczna notatka."

    def _detect_compliance_tags(self, text: str) -> List[str]:
        """Advanced Compliance Tagging (DORA/NIS2/RODO)."""
        tags = []
        text_lower = text.lower()
        patterns = {
            "DORA": ["dora", "rezyliencja", "incydent", "ciągłość działania", "ict risk"],
            "NIS2": ["nis2", "infrastruktura krytyczna", "dyrektywa", "bezpieczeństwo sieci"],
            "RODO": ["rodo", "gdpr", "dane osobowe", "prywatność", "przetwarzanie"],
            "SECURITY": ["exploit", "podatność", "cve", "pentest", "hacker"]
        }
        for tag, keywords in patterns.items():
            if any(kw in text_lower for kw in keywords):
                tags.append(tag)
        return tags or ["GENERAL"]

    def generate_note_content(self, transcript_file: str) -> Dict[str, Any]:
        """Main pipeline to generate note structure."""
        path = Path(transcript_file)
        if not path.exists(): return {"error": "File not found"}

        raw_text = path.read_text(encoding='utf-8')
        title, summary = self._generate_metadata(raw_text)
        
        # Simple chunking for LLM context window
        chunks = [raw_text[i:i+5000] for i in range(0, len(raw_text), 4500)]
        full_markdown = []

        for i, chunk in enumerate(tqdm(chunks, desc="Generating Note Content")):
            try:
                resp = ollama.chat(
                    model=self.model,
                    messages=[
                        {'role': 'system', 'content': self.SYSTEM_PROMPT},
                        {'role': 'user', 'content': f"Przetwórz fragment {i+1}:\n{chunk}"}
                    ]
                )
                full_markdown.append(resp['message']['content'])
            except Exception as e:
                self.logger.error(f"Chunk processing failed: {e}")

        combined_content = "\n\n".join(full_markdown)
        compliance = self._detect_compliance_tags(combined_content)
        
        # Metadata construction
        header = f"""
---
created: {datetime.now().strftime("%Y-%m-%d %H:%M")}
tags: [auto-generated, {", ".join(compliance).lower()}]
compliance: {compliance}
status: to-review
---

# {title}

> **Summary:** {summary}

---
"""
        return {
            "title": "".join(c for c in title if c.isalnum() or c in " -_").strip(),
            "content": header + combined_content,
            "tags": compliance # Compatibility with app.py UI
        }

    def save_note_to_disk(self, title: str, content: str) -> str:
        """Saves note and triggers Gardener for auto-linking."""
        safe_title = title.replace(" ", "-").lower()
        filename = f"{datetime.now().strftime('%Y-%m-%d')}-{safe_title}.md"
        file_path = self.vault_path / filename
        
        file_path.write_text(content, encoding='utf-8')
        self.logger.info(f"Saved note: {file_path}", extra={"tags": "NOTE-SAVE"})
        
        # Trigger Gardener
        gardener = ObsidianGardener()
        gardener.process_file(str(file_path))
        
        return str(file_path)