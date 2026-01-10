import os
import logging
from typing import List, Tuple, Optional
from pathlib import Path
from flashtext import KeywordProcessor

from config import ProjectConfig, logger
# Import RAG ONLY if needed to avoid circular imports during init
from rag_engine import ObsidianRAG

class LinkOptimizer:
    """
    High-performance keyword replacement using FlashText (Aho-Corasick algorithm).
    Replaces O(N*M) regex searches with O(N) single-pass scan.
    """
    def __init__(self, vault_titles: List[str]):
        self.processor = KeywordProcessor(case_sensitive=False)
        self.titles_set = set(vault_titles)
        
        # Build dictionary: "Linux" -> "[[Linux]]"
        for title in vault_titles:
            # Skip very short generic names
            if len(title) < 3: continue 
            
            clean_title = title.replace(".md", "")
            self.processor.add_keyword(clean_title, f"[[{clean_title}]]")

    def process_text(self, text: str) -> str:
        """Injects wikilinks into text in a single pass."""
        return self.processor.replace_keywords(text)

class ObsidianGardener:
    """
    Manager for Vault operations: Auto-linking, Tagging, and Cleaning.
    Refactored to use LinkOptimizer (FlashText) and Semantic Search.
    """

    def __init__(self, vault_path: Optional[str] = None):
        self.vault_path = Path(vault_path) if vault_path else ProjectConfig.OBSIDIAN_VAULT
        self.logger = logging.getLogger("ObsidianGardener")
        self.rag = None # Lazy load RAG to avoid heavy startup if not needed
        
        # Initialize LinkOptimizer with current vault state
        self.existing_notes = self._scan_vault()
        self.optimizer = LinkOptimizer(self.existing_notes)

    def _scan_vault(self) -> List[str]:
        """Index all note titles from the vault."""
        titles = []
        if not self.vault_path.exists():
            return titles
        for root, _, files in os.walk(self.vault_path):
            for file in files:
                if file.endswith(".md"):
                    titles.append(file[:-3]) # Remove .md
        self.logger.info(f"Gardener indexed {len(titles)} notes for auto-linking.", extra={"tags": "GARDENER-INDEX"})
        return titles

    def _get_rag(self):
        """Lazy loader for RAG engine."""
        if not self.rag:
            self.rag = ObsidianRAG()
        return self.rag

    def suggest_semantic_links(self, text: str) -> str:
        """
        Uses Vector DB to find related concepts that don't match keywords exactly.
        Appends a 'Related' section.
        """
        try:
            rag = self._get_rag()
            # We only query using the first chunk or summary to save time
            query_text = text[:1000] 
            related = rag.find_related_notes(query_text, threshold=0.45)
            
            if not related:
                return text

            # Filter out notes that are already linked in text
            existing_links = set(self.optimizer.processor.extract_keywords(text))
            
            append_text = "\n\n## 🧠 Powiązane semantycznie (AI)\n"
            added = False
            for note in related:
                clean_name = note['filename'].replace(".md", "")
                # Only add if not already linked keyword
                if clean_name not in existing_links:
                    append_text += f"- [[{clean_name}]] (zbieżność: {note['score']:.2f})\n"
                    added = True
            
            return text + append_text if added else text

        except Exception as e:
            self.logger.warning(f"Semantic linking skipped: {e}")
            return text

    def process_file(self, file_path: str) -> Tuple[bool, str]:
        """Reads, links and saves a specific note."""
        try:
            path = Path(file_path)
            if not path.exists(): return False, "File not found."
            
            content = path.read_text(encoding='utf-8')
            
            # 1. FlashText Auto-linking (Fast)
            new_content = self.optimizer.process_text(content)
            
            # 2. Semantic Linking (Smart - Optional/Slower)
            # new_content = self.suggest_semantic_links(new_content) # Uncomment to enable RAG linking

            if new_content != content:
                path.write_text(new_content, encoding='utf-8')
                return True, "Auto-linking applied (FlashText)."
            
            return True, "No changes needed."
        except Exception as e:
            self.logger.error(f"Gardener failed for {file_path}: {e}")
            return False, str(e)

    # --- Compatibility Methods for app.py ---

    def auto_link(self, text: str) -> str:
        """Wrapper for FlashText optimizer to support app.py."""
        return self.optimizer.process_text(text)

    def smart_tagging(self, tags: List[str]) -> List[str]:
        """
        Deduplicates and normalizes tags. 
        Could be expanded to use RAG for tag suggestions in future.
        """
        # Simple normalization: lowercase, remove # if present, remove duplicates
        clean_tags = set()
        for t in tags:
            t = t.strip().lower()
            if t.startswith('#'):
                t = t[1:]
            if t:
                clean_tags.add(t)
        return list(clean_tags)

    def save_note(self, title: str, content: str, tags: List[str]) -> Path:
        """Saves a new note to the vault with proper formatting."""
        safe_title = "".join([c for c in title if c.isalnum() or c in (' ', '-', '_')]).strip()
        filename = f"{safe_title}.md"
        file_path = self.vault_path / filename
        
        # Format tags
        tag_line = " ".join([f"#{t}" for t in tags])
        
        # Assemble content
        final_content = f"""# {title}

{tag_line}

{content}
"""
        file_path.write_text(final_content, encoding='utf-8')
        self.logger.info(f"Saved new note: {file_path}", extra={"tags": "GARDENER-SAVE"})
        
        # Update optimizer with new title so it's linkable immediately
        self.optimizer.processor.add_keyword(safe_title, f"[[{safe_title}]]")
        
        return file_path


if __name__ == "__main__":
    gardener = ObsidianGardener()
    print("Gardener initialized with FlashText Optimizer.")
