import time
import json
import shutil
import logging
import sys
import os

# Ensure project root is in sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import ollama
from pathlib import Path
from typing import List, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from config import ProjectConfig
from video_transcriber import VideoTranscriber
from ai_notes import TranscriptProcessor
from obsidian_manager import ObsidianGardener

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("brain_guard.log")
    ]
)
logger = logging.getLogger("BrainGuard")

class BrainGuardHandler(FileSystemEventHandler):
    """
    Watches the '00_Inbox' folder for new media files.
    Triggers the ETL pipeline: Transcribe -> Summarize -> Save -> Log.
    """
    def __init__(self):
        self.transcriber = VideoTranscriber(model_size="medium") # Use medium for better accuracy
        self.processor = TranscriptProcessor()
        self.gardener = ObsidianGardener()
        self.supported_extensions = {'.mp3', '.wav', '.m4a', '.ogg', '.webm', '.mp4', '.md'}
        logger.info("BrainGuard initialized and ready to protect (Media + Notes).")

    def _extract_tasks(self, text: str) -> list[str]:
        """
        Uses the fast LLM to extract actionable tasks from the transcript.
        """
        try:
            prompt = """
            Jesteś asystentem. Przeanalizuj poniższy tekst i wyciągnij listę konkretnych zadań (ToDo) dla użytkownika.
            Zwróć TYLKO listę zadań, każde w nowej linii, zaczynając od myślnika "- ".
            Jeśli nie ma zadań, zwróć "BRAK".
            
            Tekst:
            """
            response = ollama.chat(
                model=ProjectConfig.OLLAMA_MODEL_FAST,
                messages=[{'role': 'user', 'content': f"{prompt}\n{text[:4000]}"}] # Limit context
            )
            content = response['message']['content'].strip()
            
            if "BRAK" in content:
                return []
            
            tasks = []
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('- '):
                    tasks.append(line[2:])
                elif line.startswith('* '):
                    tasks.append(line[2:])
            return tasks
        except Exception as e:
            logger.error(f"Task extraction failed: {e}")
            return []

    def on_created(self, event):
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        
        # Ignore temp files or hidden files
        if file_path.name.startswith('.') or file_path.suffix == '.tmp':
            return

        if file_path.suffix.lower() in self.supported_extensions:
            logger.info(f"detected new file: {file_path}")
            # Wait for file to be fully written (important for MD files)
            time.sleep(1)
            
            if file_path.suffix.lower() == '.md':
                self.process_markdown_file(file_path)
            else:
                self.process_file(file_path)

    def process_markdown_file(self, file_path: Path):
        """Processes a markdown file looking for audio attachments."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            import re
            # Pattern for ![[Recording 2026... .m4a]]
            audio_pattern = r'!\[\[(.*?\.(mp3|wav|m4a|ogg|mp4))\]\]'
            matches = re.findall(audio_pattern, content)

            if not matches:
                logger.info(f"No audio attachments in {file_path.name}. Processing as text note.")
                # Treat as text note to be refined
                self._refine_text_note(file_path, content)
                return

            for match in matches:
                audio_filename = match[0]
                
                # Check if already transcribed
                if f"Transkrypcja Nagrania: {audio_filename}" in content:
                    logger.info(f"Skipping {audio_filename} - already transcribed in note.")
                    continue
                
                logger.info(f"Found audio link: {audio_filename}")

                # Search for the audio file in the vault
                audio_path = self._find_file_in_vault(audio_filename)
                
                if audio_path:
                    logger.info(f"Processing attached audio: {audio_path}")
                    # 1. Transcribe
                    json_path = self.transcriber.process_local_file(str(audio_path))
                    with open(json_path, 'r', encoding='utf-8') as f:
                        payload = json.load(f)
                    
                    raw_text = payload['content']
                    
                    # 2. Generate Note Snippet
                    note_data = self.processor.generate_note_content_from_text(raw_text, meta={"title": audio_filename})
                    
                    # 3. Update the original Markdown file
                    update_content = f"\n\n---\n## 🎤 Transkrypcja Nagrania: {audio_filename}\n\n"
                    update_content += f"### 📝 Podsumowanie\n{note_data['summary']}\n\n"
                    update_content += f"### 📜 Tekst\n{raw_text}\n"
                    
                    with open(file_path, 'a', encoding='utf-8') as f:
                        f.write(update_content)
                    
                    logger.info(f"Updated note {file_path.name} with transcription.")

                    # 3.5 Smart Move based on new content
                    with open(file_path, 'r', encoding='utf-8') as f:
                        full_content = f.read()
                    
                    category = self.gardener.smart_categorize(full_content)
                    target_dir = ProjectConfig.OBSIDIAN_VAULT / category
                    target_dir.mkdir(parents=True, exist_ok=True)
                    
                    if target_dir != file_path.parent:
                        new_note_path = target_dir / file_path.name
                        shutil.move(file_path, new_note_path)
                        logger.info(f"Categorized and moved MD file to: {new_note_path}")

                    # 4. Move audio to archive
                    archive_dir = ProjectConfig.OBSIDIAN_VAULT / "00_Inbox" / "Archive"
                    archive_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Move carefully in case it's in use
                    try:
                        shutil.move(audio_path, archive_dir / audio_filename)
                        logger.info(f"Archived audio file to: {archive_dir / audio_filename}")
                    except Exception as e:
                        logger.warning(f"Could not move audio file (may be in use): {e}")
                else:
                    logger.warning(f"Could not find audio file: {audio_filename}")

        except Exception as e:
            logger.error(f"Failed to process MD file {file_path}: {e}")

    def _refine_text_note(self, file_path: Path, content: str):
        """Refines a raw text note: Links -> Tags -> Categorizes -> Moves."""
        try:
            # 1. Auto-Link (FlashText) & Semantic Links
            linked_content = self.gardener.auto_link(content)
            linked_content = self.gardener.suggest_semantic_links(linked_content)
            
            # 2. Generate Tags (LLM)
            # We use the fast processor just to get tags, or re-use TranscriptProcessor logic?
            # Let's use TranscriptProcessor to 'generate_note_content' but treating input as the text.
            # But that might overwrite structure. We just want tags.
            
            # Let's ask LLM for tags for this content.
            prompt = f"Proszę wygenerować 3-5 tagów (słowa kluczowe) dla poniższego tekstu. Zwróć tylko listę po przecinku.\n\n{content[:2000]}"
            response = ollama.chat(
                model=ProjectConfig.OLLAMA_MODEL_FAST,
                messages=[{'role': 'user', 'content': prompt}]
            )
            tags_str = response['message']['content']
            tags = [t.strip() for t in tags_str.split(',') if t.strip()]
            
            # 3. Save with YAML (This adds title, date, tags)
            # We need to overwrite the file or save to a new location?
            # Save uses `save_note` which writes to Vault Root. We want to categorize.
            
            # Let's construct the final content manually to preserve original text structure but add YAML.
            # Check if YAML already exists?
            if content.startswith('---'):
                # Already has YAML, just append links if changed
                final_content = linked_content
            else:
                # Add YAML
                import datetime
                frontmatter = "---\n"
                frontmatter += f"title: {file_path.stem}\n"
                frontmatter += f"date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                frontmatter += "tags:\n"
                for t in tags:
                    t = t.replace("#", "").strip().lower()
                    frontmatter += f"  - {t}\n"
                frontmatter += "---\n\n"
                final_content = frontmatter + linked_content

            # 4. Smart Categorize
            category = self.gardener.smart_categorize(final_content)
            target_dir = ProjectConfig.OBSIDIAN_VAULT / category
            target_dir.mkdir(parents=True, exist_ok=True)
            
            target_path = target_dir / file_path.name
            
            # Write to target
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(final_content)
                
            # Remove original if moved
            if target_path != file_path:
                file_path.unlink()
                
            logger.info(f"Refined and moved text note to: {target_path} (Category: {category})")
            
        except Exception as e:
            logger.error(f"Failed to refine text note: {e}")

    def _find_file_in_vault(self, filename: str) -> Optional[Path]:
        """Deep search for a file in the vault."""
        # Check current dir first
        inbox_dir = ProjectConfig.OBSIDIAN_VAULT / "00_Inbox"
        for p in inbox_dir.glob(filename):
            return p
            
        # Then check vault root
        for p in ProjectConfig.OBSIDIAN_VAULT.glob(filename):
            return p
            
        # Then deep search
        for p in ProjectConfig.OBSIDIAN_VAULT.rglob(filename):
            return p
        return None

    def process_file(self, file_path: Path):
        """
        Orchestrates the processing pipeline.
        """
        try:
            # Wait a bit for file copy to finish
            time.sleep(2) 
            
            logger.info(f"Starting processing for: {file_path.name}")

            # 1. Transcribe
            json_path = self.transcriber.process_local_file(str(file_path))
            
            # Load the transcript payload
            with open(json_path, 'r', encoding='utf-8') as f:
                payload = json.load(f)
            
            raw_text = payload['content']
            meta = payload['meta']

            if not raw_text:
                logger.warning("Empty transcript generated.")
                return

            # 2. Generate Note Content (Summary & Body)
            note_data = self.processor.generate_note_content_from_text(raw_text, meta=meta)
            
            # 3. Extract Tasks
            tasks = self._extract_tasks(raw_text)

            # 4. Save to Obsidian (With Smart Categorization)
            category = self.gardener.smart_categorize(note_data['content'])
            target_dir = ProjectConfig.OBSIDIAN_VAULT / category
            target_dir.mkdir(parents=True, exist_ok=True)
            
            note_filename = f"{note_data['title']}.md"
            target_path = target_dir / note_filename
            
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(note_data['content'])
            
            logger.info(f"Saved and categorized note to: {target_path} (Category: {category})")

            # 5. Archive Source Audio in 00_Inbox/Archive (regardless of target category)
            inbox_dir = ProjectConfig.OBSIDIAN_VAULT / "00_Inbox"
            archive_dir = inbox_dir / "Archive"
            archive_dir.mkdir(parents=True, exist_ok=True)
            
            source_archive_path = archive_dir / file_path.name
            shutil.move(file_path, source_archive_path)
            logger.info(f"Archived source audio to: {source_archive_path}")

            # 6. Update Daily Log (Optional - keeping it for history)
            try:
                self.gardener.update_daily_log(
                    title=note_data['title'],
                    summary=note_data['summary'],
                    tasks=tasks,
                    note_path=str(target_path)
                )
            except Exception as log_err:
                logger.warning(f"Could not update daily log: {log_err}")

        except Exception as e:
            logger.error(f"Processing failed for {file_path}: {e}", exc_info=True)


if __name__ == "__main__":
    # Ensure Inbox exists
    inbox_path = ProjectConfig.OBSIDIAN_VAULT / "00_Inbox"
    inbox_path.mkdir(parents=True, exist_ok=True)
    
    event_handler = BrainGuardHandler()
    
    # 0. Initial Scan of the Inbox
    logger.info("Performing initial scan of 00_Inbox...")
    for existing_file in inbox_path.iterdir():
        if existing_file.is_file() and existing_file.suffix.lower() in event_handler.supported_extensions:
            logger.info(f"Processing existing file: {existing_file.name}")
            if existing_file.suffix.lower() == '.md':
                event_handler.process_markdown_file(existing_file)
            else:
                event_handler.process_file(existing_file)

    observer = Observer()
    observer.schedule(event_handler, str(inbox_path), recursive=False)
    
    logger.info(f"Monitoring {inbox_path} ... Press Ctrl+C to stop.")
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
