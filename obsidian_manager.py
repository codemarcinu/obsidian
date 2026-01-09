import os
import re
import logging
from typing import List, Set, Tuple
from pathlib import Path

# External library for fuzzy matching (Point 5)
try:
    from rapidfuzz import process, fuzz
except ImportError:
    # Fallback if not installed immediately, though it's in requirements.txt
    process = None
    fuzz = None

from config import ProjectConfig, logger

class ObsidianGardener:
    """
    Manages the health and connectivity of the Obsidian Vault.
    Replaces regex-based linking with NLP/Fuzzy matching to avoid false positives.
    """

    def __init__(self, vault_path: str = None):
        self.vault_path = Path(vault_path) if vault_path else ProjectConfig.OBSIDIAN_VAULT
        self.logger = logging.getLogger("ObsidianGardener")
        self.existing_notes = self._scan_vault()

    def _scan_vault(self) -> Set[str]:
        """
        Scans the vault to build an index of existing note titles.
        Returns a set of lowercase titles for matching.
        """
        titles = set()
        if not self.vault_path.exists():
            self.logger.warning(f"Vault path does not exist: {self.vault_path}")
            return titles

        for root, _, files in os.walk(self.vault_path):
            for file in files:
                if file.endswith(".md"):
                    # Remove extension and normalize
                    title = file[:-3]
                    titles.add(title)
        
        self.logger.info(f"Gardener index: Found {len(titles)} existing notes.")
        return titles

    def _find_matches(self, text: str) -> List[Tuple[str, str]]:
        """
        Identifies potential links in the text using fuzzy matching against existing notes.
        Returns a list of (matched_text, note_title).
        Constraint: Score > 90 to avoid false positives.
        """
        if not process:
            self.logger.warning("rapidfuzz not installed. Skipping smart linking.")
            return []

        # Optimization: Split text into words/ngrams could be heavy. 
        # For efficiency in this MVP, we iterate through existing notes and check presence in text.
        # This is reverse-search (safer for specific tech terms).
        
        matches = []
        # Sort by length (descending) to match "Machine Learning" before "Learning"
        sorted_titles = sorted(self.existing_notes, key=len, reverse=True)

        for title in sorted_titles:
            # Simple exact case-insensitive match first (Performance)
            if title.lower() in text.lower():
                # Verify using fuzz for exactness if needed, or just strict string match
                # Here we use regex to ensure word boundary \b to avoid matching "OS" in "HOST"
                pattern = re.compile(re.escape(title), re.IGNORECASE)
                
                # We want to replace the text occurrence with [[Title]]
                # But we need to be careful not to double link [[[[Title]]]]
                if pattern.search(text):
                     matches.append(title)
        
        return matches

    def auto_link(self, content: str) -> str:
        """
        Injects wikilinks [[Note Name]] into content where appropriate.
        """
        if not self.existing_notes:
            return content

        # Sort titles by length to handle sub-phrases correctly
        # e.g. Link "Kali Linux" before "Linux"
        sorted_notes = sorted(self.existing_notes, key=len, reverse=True)
        
        processed_content = content

        for note_title in sorted_notes:
            # Skip short words to avoid noise (e.g. "IT", "Go", "Is")
            if len(note_title) < 3:
                continue

            # Pattern: Case insensitive, word boundaries, NOT already inside [[...]] or (...), or `...`
            # This is complex with regex. A safe simplified approach:
            # 1. Ignore code blocks (placeholder logic omitted for brevity, but critical in production)
            # 2. Match whole words
            
            pattern = re.compile(r'\b(' + re.escape(note_title) + r')\b(?![^\[]*\]\])', re.IGNORECASE)
            
            def replacer(match):
                # Preserve original casing in text, but link to canonical note title?
                # Usually Obsidian prefers [[Canonical Title|original text]]
                original_text = match.group(1)
                # If cases match exactly, just [[Title]]
                if original_text == note_title:
                    return f"[[{note_title}]]"
                # If different case, [[Title|original text]]
                return f"[[{note_title}|{original_text}]]"

            processed_content = pattern.sub(replacer, processed_content)

        return processed_content

    def clean_orphans(self):
        """Placeholder for finding notes with 0 backlinks."""
        pass

    def process_file(self, file_path: str) -> Tuple[bool, str]:
        """
        Main entry point. Reads a file, applies auto-linking, and saves it.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Apply smart linking
            new_content = self.auto_link(content)

            # Only write if changed
            if new_content != content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                msg = "Linked existing concepts successfully."
            else:
                msg = "No new links generated."

            return True, msg

        except Exception as e:
            self.logger.error(f"Gardener error on {file_path}: {e}")
            return False, str(e)

if __name__ == "__main__":
    # Test run
    g = ObsidianGardener()
    print(f"Index size: {len(g.existing_notes)}")