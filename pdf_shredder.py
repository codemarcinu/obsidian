import os
import io
import logging
import pdfplumber
import ollama
import json
import shutil
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
from datetime import datetime
from google.cloud import vision

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
        "RODO": ["RODO", "GDPR", "dane osobowe", "przetwarzanie", "osób fizycznych", "poufność"],
        "FINANSE": ["faktura", "rachunek", "płatność", "kwota", "brutto", "netto", "vat", "przelew", "termin płatności"],
        "ZDROWIE": ["badanie", "wynik", "pacjent", "lekarz", "skierowanie", "recepta", "laboratorium"]
    }

    def __init__(self, vault_path: Optional[str] = None):
        self.vault_path = Path(vault_path) if vault_path else ProjectConfig.OBSIDIAN_VAULT
        self.output_dir = self.vault_path / "Compliance"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("PDFShredder")

        # Google Vision Setup
        if ProjectConfig.GOOGLE_APPLICATION_CREDENTIALS and ProjectConfig.GOOGLE_APPLICATION_CREDENTIALS.exists():
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(ProjectConfig.GOOGLE_APPLICATION_CREDENTIALS)
            self.vision_client = vision.ImageAnnotatorClient()
        else:
            self.vision_client = None
            self.logger.warning("Google Vision credentials not found. OCR will be disabled.")

    def detect_compliance_tags(self, text: str) -> List[str]:
        """Automated Compliance Tagging (Point 6 of Audit)."""
        tags = []
        text_lower = text.lower()
        for tag, keywords in self.COMPLIANCE_MAP.items():
            if any(kw.lower() in text_lower for kw in keywords):
                tags.append(tag)
        return tags if tags else ["General"]

    def ocr_pdf_fallback(self, pdf_path: str) -> str:
        """OCR fallback using Google Vision for PDF files with no text layer."""
        if not self.vision_client:
            return ""
        
        self.logger.info(f"PDF has no text layer or very little text. Attempting Google Vision OCR: {pdf_path}")
        try:
            with open(pdf_path, 'rb') as f:
                content = f.read()
            
            input_config = vision.InputConfig(content=content, mime_type='application/pdf')
            feature = vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)
            
            # Process the first few pages
            request = vision.AnnotateFileRequest(
                input_config=input_config,
                features=[feature],
                pages=[1, 2, 3] 
            )
            
            response = self.vision_client.batch_annotate_files(requests=[request])
            
            texts = []
            for page_response in response.responses[0].responses:
                if page_response.full_text_annotation.text:
                    texts.append(page_response.full_text_annotation.text)
            
            return "\n".join(texts)
        except Exception as e:
            self.logger.error(f"OCR Fallback failed: {e}")
            return ""

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

        combined_text = "\n".join(full_text).strip()
        
        # Fallback to Google Vision if no text was extracted or content is too short (possible scan)
        if not combined_text or len(combined_text) < 100:
            ocr_text = self.ocr_pdf_fallback(pdf_path)
            if ocr_text:
                combined_text = ocr_text
                self.logger.info("Successfully recovered text via Google Vision OCR.")

        tags = self.detect_compliance_tags(combined_text)
        return combined_text, tags

    def suggest_filename(self, text: str) -> str:
        """Uses LLM to suggest a standardized filename."""
        prompt = """
        Na podstawie treści dokumentu zaproponuj nazwę pliku w formacie: YYYY-MM-DD_Typ_Podmiot_Opis.
        Typ: Faktura, Umowa, Wynik, Pismo, Inne.
        Podmiot: Nazwa firmy/osoby (np. Orange, UPC, LuxMed).
        Opis: Krótko (np. Internet, Krew, Prad).
        
        Jeśli nie znajdziesz daty w dokumencie, użyj dzisiejszej.
        Zwróć TYLKO nazwę pliku, bez rozszerzenia.
        """
        try:
            response = ollama.chat(
                model=ProjectConfig.OLLAMA_MODEL_FAST,
                messages=[{'role': 'user', 'content': f"{prompt}\n\nTekst: {text[:2000]}"}]
            )
            filename = response['message']['content'].strip()
            # Sanitize
            filename = "".join(c for c in filename if c.isalnum() or c in ('-', '_')).strip()
            return filename
        except Exception as e:
            self.logger.error(f"Filename suggestion failed: {e}")
            return f"Doc_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def extract_home_data(self, text: str) -> Dict[str, Any]:
        """Extracts structured data for Life Admin (invoices, etc.)."""
        prompt = """
        Przeanalizuj ten dokument. Jeśli to faktura lub dokument płatniczy, wyciągnij:
        - date (termin płatności YYYY-MM-DD)
        - amount (kwota z walutą)
        - account (numer konta)
        - subject (czego dotyczy)
        
        Zwróć JSON. Jeśli nie znaleziono, zwróć pusty JSON {}.
        """
        try:
            response = ollama.chat(
                model=ProjectConfig.OLLAMA_MODEL_FAST,
                messages=[{'role': 'user', 'content': f"{prompt}\n\nTekst: {text[:3000]}"}],
                format='json'
            )
            return json.loads(response['message']['content'])
        except Exception:
            return {}

    def process_pdf(self, pdf_path: str) -> Tuple[bool, str]:
        """Main pipeline for PDF ingestion."""
        self.logger.info(f"Shredding PDF: {pdf_path}")
        
        content, tags = self.extract_content(pdf_path)
        if not content:
            return False, "Failed to extract content."

        # 1. Smart Renaming
        new_filename = self.suggest_filename(content)
        original_path = Path(pdf_path)
        
        # Rename the source file if possible (and if it's in Inbox/Temp)
        # Assuming we are working on a copy or it's safe to rename in place if it's in a watched dir.
        # But pdf_path might be in temp. Let's define safe_title for the Note based on this.
        safe_title = new_filename
        
        # 2. Extract Home Data if applicable
        home_data = {}
        if "FINANSE" in tags or "ZDROWIE" in tags:
            home_data = self.extract_home_data(content)

        # 3. Save structured note
        final_path = self.save_as_note(safe_title, content, tags, home_data)
        
        # 4. Auto-linking via Gardener
        gardener = ObsidianGardener(str(self.vault_path))
        gardener.process_file(final_path)
        
        return True, str(final_path)

    def process_image(self, image_path: str) -> Tuple[bool, str]:
        """Pipeline for Image ingestion (OCR + Labeling)."""
        self.logger.info(f"Processing Image: {image_path}")
        
        if not self.vision_client:
            return False, "Google Vision not configured."

        try:
            with open(image_path, 'rb') as f:
                content = f.read()

            image = vision.Image(content=content)
            
            # Perform Label Detection and Text Detection
            features = [
                vision.Feature(type_=vision.Feature.Type.LABEL_DETECTION),
                vision.Feature(type_=vision.Feature.Type.TEXT_DETECTION),
            ]
            request = vision.AnnotateImageRequest(image=image, features=features)
            response = self.vision_client.batch_annotate_images(requests=[request])
            
            result = response.responses[0]
            
            # Extract Text
            text_content = result.full_text_annotation.text if result.full_text_annotation else ""
            
            # Extract Labels
            labels = [label.description for label in result.label_annotations]
            
            # Combine for analysis
            analysis_content = f"Labels: {', '.join(labels)}\n\nText Content:\n{text_content}"
            
            # 1. Smart Renaming & Categorization
            tags = self.detect_compliance_tags(text_content)
            tags.append("VisualNote")
            
            new_filename = self.suggest_filename(analysis_content)
            
            # 2. Extract Home Data if applicable
            home_data = {}
            if "FINANSE" in tags or "ZDROWIE" in tags:
                home_data = self.extract_home_data(text_content)

            # 3. Copy image to Vault Assets
            assets_dir = self.vault_path / "Assets"
            assets_dir.mkdir(exist_ok=True)
            image_ext = Path(image_path).suffix
            saved_image_name = f"{new_filename}{image_ext}"
            shutil.copy2(image_path, assets_dir / saved_image_name)
            
            # 4. Save structured note
            final_path = self.save_as_note(new_filename, text_content, tags, home_data)
            
            # Embed image in note
            with open(final_path, 'r+') as f:
                content = f.read()
                f.seek(0, 0)
                f.write(f"![[{saved_image_name}]]\n\n" + content)
                
                # Append Image Analysis info
                f.seek(0, 2) # End of file
                f.write(f"\n\n## Visual Analysis\n**Detected Objects:** {', '.join(labels)}\n")

            # 5. Auto-linking via Gardener
            gardener = ObsidianGardener(str(self.vault_path))
            gardener.process_file(final_path)
            
            return True, str(final_path)

        except Exception as e:
            self.logger.error(f"Image processing failed: {e}")
            return False, str(e)

    def save_as_note(self, title: str, content: str, tags: List[str], home_data: Dict[str, Any] = None) -> Path:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # Determine subdir based on tags
        subdir = "Compliance"
        if "FINANSE" in tags: subdir = "Finanse"
        elif "ZDROWIE" in tags: subdir = "Zdrowie"
        
        output_dir = self.vault_path / subdir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = output_dir / f"{title}.md"
        
        tag_string = "\n  - ".join(tags)
        
        # Construct Callout for Home Data
        callout = ""
        if home_data:
            callout = f"""
> [!money] Podsumowanie Dokumentu
> **Kwota:** {home_data.get('amount', 'N/A')}
> **Termin:** {home_data.get('date', 'N/A')} 📅 {home_data.get('date', 'N/A')}
> **Konto:** {home_data.get('account', 'N/A')}
> **Dotyczy:** {home_data.get('subject', 'N/A')}
"""

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
{callout}

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