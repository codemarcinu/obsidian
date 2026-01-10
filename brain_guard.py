import time
import json
import shutil
import logging
import sys
import ollama
from pathlib import Path
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
        self.supported_extensions = {'.mp3', '.wav', '.m4a', '.ogg', '.webm', '.mp4'}
        logger.info("BrainGuard initialized and ready to protect.")

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
            self.process_file(file_path)

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

            # 4. Save to Obsidian (Zasoby/Wiedza)
            # Use 'Zasoby/Wiedza' as the destination folder, need to handle path in save_note?
            # ObsidianGardener.save_note uses self.vault_path (root). 
            # I should modify save_note to accept a subfolder or prepend it to title?
            # No, save_note uses `self.vault_path / filename`.
            # I will modify save_note call to handle subdirectories?
            # Actually, `ObsidianGardener.save_note` takes `title`, `content`, `tags`.
            # It saves to `self.vault_path`.
            # I want to save to `Zasoby/Wiedza`.
            # I will manually construct the path or move it after saving.
            # OR, I can instantiate a Gardener with a specific path?
            # Gardener init: `vault_path`.
            # I can create a temporary gardener for `Zasoby/Wiedza`?
            # Or just hack it: save, then move.
            
            # Let's check `save_note` implementation in `obsidian_manager.py`.
            # It joins `self.vault_path / filename`.
            # I'll modify `BrainGuard` to move the file after saving if needed, or just let it save in root for now (Inbox approach).
            # But the plan said "tworzy notatkę merytoryczną w Zasoby/Wiedza".
            
            # Let's try to save directly to `Zasoby/Wiedza` by passing a modified title? No, title becomes filename.
            # I will instantiate a specific gardener for the target folder?
            # No, `ObsidianGardener` is designed for the whole vault.
            # I will modify `save_note` in `obsidian_manager.py` to accept `subfolder` argument in a future iteration.
            # For now, I'll use the default save (Vault Root) and then move it, or just accept it lands in root (or Education/ which is root).
            
            # ACTUALLY: The user has `obsidian_db` and `Education`. `Education` is the Vault.
            # I want it in `Education/Zasoby/Wiedza`.
            
            saved_path = self.gardener.save_note(note_data['title'], note_data['content'], note_data['tags'])
            
            # Move to Zasoby/Wiedza
            target_dir = ProjectConfig.OBSIDIAN_VAULT / "Zasoby" / "Wiedza"
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / saved_path.name
            shutil.move(saved_path, target_path)
            logger.info(f"Moved note to: {target_path}")

            # 5. Update Daily Log
            self.gardener.update_daily_log(
                title=note_data['title'],
                summary=note_data['summary'],
                tasks=tasks,
                note_path=str(target_path)
            )

            # 6. Archive Source Audio
            self.gardener.archive_source_file(str(file_path), subfolder="Audio")

        except Exception as e:
            logger.error(f"Processing failed for {file_path}: {e}", exc_info=True)


if __name__ == "__main__":
    # Ensure Inbox exists
    inbox_path = ProjectConfig.OBSIDIAN_VAULT / "00_Inbox"
    inbox_path.mkdir(parents=True, exist_ok=True)
    
    event_handler = BrainGuardHandler()
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
