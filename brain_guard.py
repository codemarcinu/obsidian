import time
import json
import shutil
import logging
import sys
import os
import re

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
from utils.life_admin import process_voice_note_for_life

def send_windows_notification(title, message):
    """Sends a toast notification to Windows via WSL PowerShell."""
    try:
        safe_title = title.replace("'", "").replace('"', '')
        safe_msg = message.replace("'", "").replace('"', '')
        cmd = f"powershell.exe -NoProfile -Command \"New-BurntToastNotification -Text '{safe_title}', '{safe_msg}'\""
        os.system(cmd)
    except Exception as e:
        logger.warning(f"Notification failed: {e}")

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
        self.queue_filename = "youtube_queue.md"
        self.processing_queue = False
        logger.info("BrainGuard initialized and ready to protect (Media + Notes).")

    def _extract_tasks(self, text: str) -> list[str]:
        """
        Wrapper to extract tasks using Life Admin logic.
        Formats for Obsidian Tasks plugin: '- [ ] Task 📅 YYYY-MM-DD 🔺high'
        """
        try:
            life_items = process_voice_note_for_life(text)
            tasks = []
            for item in life_items:
                # Basic Task
                action = item.get('action_item', 'Task')
                category = item.get('category', 'General')
                
                # Check for priority keywords
                priority = ""
                lower_action = action.lower()
                if "pilne" in lower_action or "na cito" in lower_action or "ważne" in lower_action:
                    priority = " 🔺" # High priority for Tasks plugin
                elif "kiedyś" in lower_action:
                    priority = " 🔽" # Low priority

                # Date
                date_str = ""
                if item.get('due_date'):
                    date_str = f" 📅 {item['due_date']}"

                # Construct: - [ ] #Category Task 📅 2026-01-01 🔺
                task_str = f"#{category} {action}{date_str}{priority}"
                tasks.append(task_str)
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

        # Check for Queue File
        if file_path.name == self.queue_filename:
            logger.info(f"Queue file created: {file_path}")
            self.process_youtube_queue(file_path)
            return

        if file_path.suffix.lower() in self.supported_extensions:
            logger.info(f"detected new file: {file_path}")
            # Wait for file to be fully written (important for MD files)
            time.sleep(1)
            
            if file_path.suffix.lower() == '.md':
                self.process_markdown_file(file_path)
            else:
                self.process_file(file_path)

    def on_modified(self, event):
        if event.is_directory: return
        file_path = Path(event.src_path)
        
        if file_path.name == self.queue_filename:
            self.process_youtube_queue(file_path)

    def process_youtube_queue(self, file_path: Path):
        """
        Reads the queue file, processes new links, and marks them as done.
        """
        if self.processing_queue:
            return

        self.processing_queue = True
        logger.info(f"Checking queue file: {file_path}")
        
        try:
            # Read all lines
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Identify work
            for i, line in enumerate(lines):
                line_stripped = line.strip()
                
                # Check for YouTube links that are NOT done/in-progress/error
                if ("youtube.com" in line_stripped or "youtu.be" in line_stripped) and \
                   "✅" not in line_stripped and \
                   "⏳" not in line_stripped and \
                   "❌" not in line_stripped:
                         
                    # 1. Mark as In Progress immediately
                    lines[i] = line.rstrip() + " ⏳ [W trakcie...]\n"
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.writelines(lines)
                    
                    # Extract URL
                    url_match = re.search(r'(https?://(?:www\.|m\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]+))', line_stripped)
                    if not url_match:
                        lines[i] = line.rstrip() + " ❌ [Błąd: Niepoprawny URL]\n"
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.writelines(lines)
                        continue

                    full_url = url_match.group(0)
                    logger.info(f"Queue processing: {full_url}")

                    try:
                        # PROCESS
                        # 1. Transcribe (Download -> Inbox JSON)
                        json_path = self.transcriber.process_to_inbox(full_url)
                        
                        # 2. Read JSON payload
                        with open(json_path, 'r', encoding='utf-8') as jf:
                            payload = json.load(jf)
                        
                        # 3. Generate Note Content
                        note_data = self.processor.generate_note_content_from_text(
                            payload['content'], 
                            meta=payload['meta']
                        )
                        
                        # 4. Save to Vault (Smart Categorize)
                        category = self.gardener.smart_categorize(note_data['content'])
                        target_dir = ProjectConfig.OBSIDIAN_VAULT / category
                        target_dir.mkdir(parents=True, exist_ok=True)
                        target_path = target_dir / f"{note_data['title']}.md"
                        
                        with open(target_path, 'w', encoding='utf-8') as nf:
                            nf.write(note_data['content'])
                            
                        # 5. Update Daily Log
                        self.gardener.update_daily_log(
                            title=note_data['title'],
                            summary=note_data['summary'],
                            tasks=[],
                            note_path=str(target_path)
                        )

                        # Mark Done
                        lines[i] = line.rstrip() + " ✅ [Gotowe]\n"
                        logger.info(f"Queue Task Completed: {full_url}")
                        send_windows_notification("BrainGuard Queue", f"Przetworzono: {note_data['title']}")

                    except Exception as e:
                        logger.error(f"Queue Task Failed {full_url}: {e}")
                        lines[i] = line.rstrip() + f" ❌ [Błąd: {str(e)[:50]}]\n"
                    
                    # Write update after processing this item
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.writelines(lines)

        except Exception as e:
            logger.error(f"Error processing queue file: {e}")
        finally:
            self.processing_queue = False

    def process_markdown_file(self, file_path: Path):
        """Processes a markdown file looking for audio attachments OR URLs."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Pattern for ![[Recording 2026... .m4a]]
            audio_pattern = r'!\[\[(.*?\.(mp3|wav|m4a|ogg|mp4))\]\]'
            # Pattern for YouTube URLs
            url_pattern = r'(https?://(?:www\.|m\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]+))'
            
            audio_matches = re.findall(audio_pattern, content)
            url_matches = re.findall(url_pattern, content)

            if not audio_matches and not url_matches:
                logger.info(f"No audio/video attachments in {file_path.name}. Processing as text note.")
                # Treat as text note to be refined
                self._refine_text_note(file_path, content)
                return

            # Process Audio Files
            for match in audio_matches:
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
                    
                    # 3. Life Admin Extraction
                    tasks = self._extract_tasks(raw_text)
                    life_section = ""
                    if tasks:
                        life_section = "\n### 🏠 Life Admin & Tasks\n" + "\n".join([f"- [ ] {t}" for t in tasks]) + "\n"

                    # 4. Update the original Markdown file
                    update_content = f"\n\n---\n## 🎤 Transkrypcja Nagrania: {audio_filename}\n\n"
                    update_content += f"### 📝 Podsumowanie\n{note_data['summary']}\n\n"
                    update_content += f"### 📜 Tekst\n{raw_text}\n"
                    update_content += life_section
                    
                    with open(file_path, 'a', encoding='utf-8') as f:
                        f.write(update_content)
                    
                    logger.info(f"Updated note {file_path.name} with transcription.")

                    # 3.5 Smart Move based on new content
                    # Reload content
                    with open(file_path, 'r', encoding='utf-8') as f:
                        full_content = f.read()
                    
                    category = self.gardener.smart_categorize(full_content)
                    target_dir = ProjectConfig.OBSIDIAN_VAULT / category
                    target_dir.mkdir(parents=True, exist_ok=True)
                    
                    if target_dir != file_path.parent:
                        new_note_path = target_dir / file_path.name
                        shutil.move(file_path, new_note_path)
                        logger.info(f"Categorized and moved MD file to: {new_note_path}")
                        # Update file_path for subsequent loops if needed (though we only process once per event generally)
                        file_path = new_note_path

                    # 4. Move audio to archive
                    archive_dir = ProjectConfig.OBSIDIAN_VAULT / "00_Inbox" / "Archive"
                    archive_dir.mkdir(parents=True, exist_ok=True)
                    
                    try:
                        shutil.move(audio_path, archive_dir / audio_filename)
                        logger.info(f"Archived audio file to: {archive_dir / audio_filename}")
                    except Exception as e:
                        logger.warning(f"Could not move audio file (may be in use): {e}")
                else:
                    logger.warning(f"Could not find audio file: {audio_filename}")

            # Process YouTube URLs
            for match in url_matches:
                full_url = match[0]
                video_id = match[1]
                
                if f"Transkrypcja Wideo" in content and video_id in content:
                     # Simple avoidance check
                     continue

                logger.info(f"Found YouTube URL: {full_url}")
                
                try:
                    # 1. Transcribe (Download -> Inbox JSON)
                    json_path = self.transcriber.process_to_inbox(full_url)
                    with open(json_path, 'r', encoding='utf-8') as f:
                        payload = json.load(f)
                    
                    raw_text = payload['content']
                    meta = payload['meta']
                    
                    # 2. Generate Note Snippet
                    note_data = self.processor.generate_note_content_from_text(raw_text, meta=meta)
                    
                    # 3. Update Note
                    update_content = f"\n\n---\n## 🎬 Transkrypcja Wideo: {meta['title']}\n"
                    update_content += f"URL: {full_url}\n\n"
                    update_content += f"### 📝 Podsumowanie\n{note_data['summary']}\n\n"
                    update_content += f"### 📜 Tekst\n{raw_text}\n"
                    
                    with open(file_path, 'a', encoding='utf-8') as f:
                        f.write(update_content)
                        
                    logger.info(f"Updated note {file_path.name} with video transcript.")
                except Exception as e:
                    logger.error(f"Failed to process video URL {full_url}: {e}")


        except Exception as e:
            logger.error(f"Failed to process MD file {file_path}: {e}")

    def _refine_text_note(self, file_path: Path, content: str):
        """Refines a raw text note: Links -> Tags -> Categorizes -> Moves."""
        try:
            # 1. Auto-Link (FlashText) & Semantic Links
            linked_content = self.gardener.auto_link(content)
            linked_content = self.gardener.suggest_semantic_links(linked_content)
            
            # 2. Generate Tags (LLM)
            prompt = f"Proszę wygenerować 3-5 tagów (słowa kluczowe) dla poniższego tekstu. Zwróć tylko listę po przecinku.\n\n{content[:2000]}"
            response = ollama.chat(
                model=ProjectConfig.OLLAMA_MODEL_FAST,
                messages=[{'role': 'user', 'content': prompt}]
            )
            tags_str = response['message']['content']
            tags = [t.strip() for t in tags_str.split(',') if t.strip()]
            
            # 3. Save with YAML (This adds title, date, tags)
            if content.startswith('---'):
                final_content = linked_content
            else:
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
            
            # 3. Extract Tasks (Life Admin)
            tasks = self._extract_tasks(raw_text)

            # Append Life Admin section to content
            if tasks:
                life_section = "\n\n## 🏠 Life Admin & Tasks\n" + "\n".join([f"- [ ] {t}" for t in tasks])
                note_data['content'] += life_section

            # 4. Save to Obsidian (With Smart Categorization)
            category = self.gardener.smart_categorize(note_data['content'])
            target_dir = ProjectConfig.OBSIDIAN_VAULT / category
            target_dir.mkdir(parents=True, exist_ok=True)
            
            note_filename = f"{note_data['title']}.md"
            target_path = target_dir / note_filename
            
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(note_data['content'])
            
            logger.info(f"Saved and categorized note to: {target_path} (Category: {category})")

            # [UX] Notification
            send_windows_notification("BrainGuard", f"Gotowe: {note_data['title']}")

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
