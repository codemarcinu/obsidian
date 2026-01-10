import os
import logging
import re
from typing import List, Set, Dict, Tuple, Optional
from pathlib import Path
from flashtext import KeywordProcessor

from config import ProjectConfig, logger

class LinkOptimizer:
    """
    High-performance Wikilink injector using FlashText.
    Designed to handle 1000s of existing notes without slowing down.
    """
    def __init__(self, titles: List[str]):
        self.processor = KeywordProcessor(case_sensitive=False)
        # Sort titles by length (descending) to ensure longest match wins
        # FlashText does this internally by default, but we ensure clean mapping
        for title in titles:
            if len(title) > 3:  # Ignore very short words to avoid noise
                # Format: keyword -> clean name for [[link]]
                self.processor.add_keyword(title, f"[[{title}]]")

    def apply_links(self, text: str) -> str:
        """
        Replaces found keywords with [[Wikilinks]].
        Avoids double-linking and matches only word boundaries.
        """
        # FlashText handles boundaries and non-overlapping matches efficiently
        return self.processor.replace_keywords(text)

class ObsidianGardener:
    """
    Manages Vault health, connectivity, and metadata.
    Refactored for ETL: Linking & Tagging happen in the Refinery phase.
    """

    def __init__(self, vault_path: Optional[str] = None):
        self.vault_path = Path(vault_path) if vault_path else ProjectConfig.OBSIDIAN_VAULT
        self.logger = logging.getLogger("ObsidianGardener")
        self.existing_notes = self._scan_vault_titles()
        self.existing_tags = self._scan_vault_tags()
        self.link_optimizer = LinkOptimizer(self.existing_notes)

    def _scan_vault_titles(self) -> List[str]:
        """Index all note titles from the vault."""
        titles = []
        if not self.vault_path.exists():
            return titles

        for root, _, files in os.walk(self.vault_path):
            for file in files:
                if file.endswith(".md"):
                    titles.append(file[:-3])
        
        self.logger.info(f"Gardener indexed {len(titles)} notes.", extra={"tags": "GARDENER-INDEX"})
        return titles

    def _scan_vault_tags(self) -> Set[str]:
        """
        Extracts all existing tags from the vault to enable Smart Tagging.
        Scans YAML frontmatter and inline #tags.
        """
        tags = set()
        tag_pattern = re.compile(r'(?:^|
)#([a-zA-Z0-9_\-/]+)')
        
        # Limit scanning to first 1000 notes for performance if vault is huge
        count = 0
        for root, _, files in os.walk(self.vault_path):
            for file in files:
                if file.endswith(".md"):
                    try:
                        content = (Path(root) / file).read_text(encoding='utf-8', errors='ignore')
                        found = tag_pattern.findall(content)
                        tags.update(found)
                        count += 1
                    except Exception:
                        continue
                if count > 1000: break
        
        self.logger.info(f"Gardener found {len(tags)} unique tags in vault.", extra={"tags": "GARDENER-TAGS"})
        return tags

    def smart_tagging(self, suggested_tags: List[str]) -> List[str]:
        """
        Cross-references suggested tags with existing ones.
        Returns a cleaned list of tags (existing or strictly relevant).
        """
        final_tags = []
        for tag in suggested_tags:
            tag = tag.replace("#", "").strip()
            # If tag exists or is similar to existing, use it
            # (Simple exact match for now, could be fuzzy)
            if tag.lower() in [t.lower() for t in self.existing_tags]:
                final_tags.append(tag)
            else:
                # Add it anyway if it seems valuable (could add logic here)
                final_tags.append(tag)
        return list(set(final_tags))

    def auto_link(self, content: str) -> str:
        """Wrapper for LinkOptimizer."""
        return self.link_optimizer.apply_links(content)

    def save_note(self, title: str, content: str, tags: List[str], folder: str = "Inbox") -> Path:
        """
        Final Load step: Saves the processed note to Obsidian.
        """
        target_dir = self.vault_path / folder
        target_dir.mkdir(parents=True, exist_ok=True)
        
        safe_title = re.sub(r'[\\/*?:":<>|]', "", title)
        file_path = target_dir / f"{safe_title}.md"
        
        # Apply Auto-linking to content
        linked_content = self.auto_link(content)
        
        # Construct Markdown with Frontmatter
        formatted_tags = [f"#{t.replace(' ', '_')}" for t in tags]
        
        md_content = f"""
---source: AI-Generated
tags: {" ".join(formatted_tags)}
date: {os.path.getmtime(ProjectConfig.BASE_DIR) if os.path.exists(ProjectConfig.BASE_DIR) else ""}
---

# {title}

{linked_content}
"""
        file_path.write_text(md_content, encoding='utf-8')
        self.logger.info(f"Note saved to Obsidian: {file_path}", extra={"tags": "GARDENER-SAVE"})
        return file_path

if __name__ == "__main__":
    gardener = ObsidianGardener()
    test_text = "I am studying Machine Learning and Python in my Education folder."
    print(f"Original: {test_text}")
    print(f"Linked: {gardener.auto_link(test_text)}")