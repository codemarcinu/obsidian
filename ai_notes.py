import os
import re
import ollama
import logging
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from tqdm import tqdm
from pathlib import Path

from config import ProjectConfig, logger

class TranscriptProcessor:
    """
    Refactored Note Generator: Converts raw transcripts into structured technical documentation.
    Adapted for ETL: Can process text directly from memory.
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
        self.fast_model = ProjectConfig.OLLAMA_MODEL_FAST
        self.logger = logging.getLogger("TranscriptProcessor")

    def _generate_metadata(self, text: str) -> Tuple[str, str]:
        """Uses lightweight LLM (Fast Model) to generate title and short summary."""
        prompt = "Na podstawie tekstu podaj: 1. Krótki tytuł techniczny (bez znaków specjalnych), 2. Jednozdaniowe podsumowanie."
        try:
            # Use faster, smaller model for metadata generation to save time/compute
            resp = ollama.chat(
                model=self.fast_model,
                messages=[{'role': 'user', 'content': f"{prompt}\n\nTekst: {text[:2000]}"}]
            )
            content = resp['message']['content']
            lines = content.split('\n')
            title = lines[0].strip().replace("1. ", "").replace("Tytuł: ", "")
            summary = lines[1].strip().replace("2. ", "").replace("Podsumowanie: ", "") if len(lines) > 1 else "Brak podsumowania."
            # Sanitize title
            title = "".join(c for c in title if c.isalnum() or c in " -_").strip()
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
            "SECURITY": ["exploit", "podatność", "cve", "pentest", "hacker"],
            "AI": ["llm", "ai", "model", "sztuczna inteligencja", "machine learning"],
            "PYTHON": ["python", "pip", "django", "flask", "fastapi"]
        }
        for tag, keywords in patterns.items():
            if any(kw in text_lower for kw in keywords):
                tags.append(tag)
        return tags or ["GENERAL"]

    def generate_note_content_from_text(self, text: str, meta: Dict[str, Any] = None, style: str = "Academic") -> Dict[str, Any]:
        """
        Direct generation from text string (Refinery Phase).
        """
        if not text:
            return {"title": "Empty Note", "content": "", "tags": []}

        # 1. Metadata
        title, summary = self._generate_metadata(text)
        if meta and meta.get('title') and meta.get('title') != "Unknown Title":
             # Prefer metadata title but sanitize it
             title = "".join(c for c in meta['title'] if c.isalnum() or c in " -_").strip()

        # 2. Context Chunking
        chunks = [text[i:i+6000] for i in range(0, len(text), 5000)]
        full_body = []

        # Adjust system prompt based on style
        style_instruction = ""
        if style == "Bullet Points": style_instruction = "Używaj głównie list wypunktowanych."
        if style == "Summary": style_instruction = "Skup się tylko na najważniejszych wnioskach."
        
        system_prompt = self.SYSTEM_PROMPT + f"\nSTYL: {style_instruction}"

        for i, chunk in enumerate(tqdm(chunks, desc="Refining Content")):
            try:
                resp = ollama.chat(
                    model=self.model,
                    messages=[
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': f"Przetwórz fragment {i+1} (zachowaj ciągłość):\n{chunk}"}
                    ]
                )
                full_body.append(resp['message']['content'])
            except Exception as e:
                self.logger.error(f"Chunk error: {e}")

        combined_body = "\n\n".join(full_body)
        
        # 3. Tagging
        tags = self._detect_compliance_tags(combined_body)
        if meta:
            tags.append(f"source/{meta.get('uploader', 'unknown').lower().replace(' ', '_')}")

        return {
            "title": title,
            "content": combined_body, # Raw markdown body, header will be added by Gardener
            "summary": summary,
            "tags": tags
        }

    # Legacy wrapper for compatibility if needed, but App uses the method above now
    def generate_note_content(self, transcript_file: str) -> Dict[str, Any]:
        path = Path(transcript_file)
        if not path.exists(): return {"error": "File not found"}
        return self.generate_note_content_from_text(path.read_text(encoding='utf-8'))
