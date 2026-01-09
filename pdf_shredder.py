import os
import logging
import pdfplumber
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from datetime import datetime

from config import ProjectConfig, logger
from obsidian_manager import ObsidianGardener

class PDFShredder:
    """
    Advanced PDF Processor: Extracts text and tables, detects compliance patterns,
    and generates structured Obsidian notes.
    """

    COMPLIANCE_MAP = {
        "DORA": ["DORA", "ICT", "rezyliencja", "operacyjna", "incydent", "finansowe"],
        "NIS2": ["NIS2", "dyrektywa", "cyberbezpieczeństwo", "bezpieczeństwo sieci", "podmiot kluczowy"],
        "RODO": ["RODO", "GDPR", "dane osobowe", "przetwarzanie", "osób fizycznych", "poufność"]
    }

    def __init__(self, vault_path: Optional[str] = None):
        self.vault_path = Path(vault_path) if vault_path else ProjectConfig.OBSIDIAN_VAULT
        self.output_dir = self.vault_path / "Compliance"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("PDFShredder")

    def detect_compliance_tags(self, text: str) -> List[str]:
        """Automated Compliance Tagging (Point 6 of Audit)."""
        tags = []
        text_lower = text.lower()
        for tag, keywords in self.COMPLIANCE_MAP.items():
            if any(kw.lower() in text_lower for kw in keywords):
                tags.append(tag)
        return tags if tags else ["General"]

    def extract_content(self, pdf_path: str) -> Tuple[str, List[str]]:
        """Extracts text and identifies compliance scope."""
        full_text = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    # Extract text
                    page_text = page.extract_text()
                    if page_text:
                        full_text.append(page_text)
                    
                    # Optional: Table extraction logic (simplified for MVP)
                    tables = page.extract_tables()
                    for table in tables:
                        if table:
                            full_text.append("| " + " | ".join([str(cell or "") for cell in table[0]]) + " |")
                            full_text.append("|" + "---|" * len(table[0]))
        except Exception as e:
            self.logger.error(f"Error reading PDF {pdf_path}: {e}")
            return "", []

        combined_text = "\n".join(full_text)
        tags = self.detect_compliance_tags(combined_text)
        return combined_text, tags

    def process_pdf(self, pdf_path: str) -> Tuple[bool, str]:
        """Main pipeline for PDF ingestion."""
        self.logger.info(f"Shredding PDF: {pdf_path}")
        
        content, tags = self.extract_content(pdf_path)
        if not content:
            return False, "Failed to extract content."

        # Metadata generation
        title = Path(pdf_path).stem
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        
        # Save structured note
        final_path = self.save_as_note(safe_title, content, tags)
        
        # Auto-linking via Gardener
        gardener = ObsidianGardener(str(self.vault_path))
        gardener.process_file(final_path)
        
        return True, str(final_path)

    def save_as_note(self, title: str, content: str, tags: List[str]) -> Path:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        filepath = self.output_dir / f"PDF-{title}.md"
        
        tag_string = "\n  - ".join(tags)
        
        note_content = f"""
---
created: {timestamp}
tags:
  - {tag_string}
  - pdf-shredder
type: audit-document
status: processed
---

# {title}

> [!INFO] Dokument przeanalizowany przez PDF Shredder (Refactored v2.0)
> Wykryte obszary zgodności: {', '.join(tags)}

## Treść Wyciągnięta

{content[:20000]} # Limit to 20k chars for Obsidian performance

---
*End of document extract.*
"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(note_content)
        return filepath