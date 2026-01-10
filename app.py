import streamlit as st
import os
import json
import time
import logging
from pathlib import Path
from typing import List

# --- CONFIG ---
from config import ProjectConfig, logger

# --- MODULES ---
# Ingest Modules
from video_transcriber import VideoTranscriber
# Refinery Modules
from ai_notes import TranscriptProcessor
from obsidian_manager import ObsidianGardener

# Initialize Page
st.set_page_config(page_title="Obsidian AI Bridge v4.0 (ETL)", layout="wide", page_icon="⚡")

# --- UTILS ---

def load_inbox_items() -> List[Path]:
    """Scans INBOX_DIR for ready JSON files."""
    if not ProjectConfig.INBOX_DIR.exists():
        return []
    # Sort by modification time (newest first)
    files = list(ProjectConfig.INBOX_DIR.glob("*.json"))
    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return files

def get_file_summary(path: Path) -> dict:
    """Reads metadata from JSON safely."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        meta = data.get('meta', {})
        return {
            "title": meta.get('title', path.stem),
            "date": time.strftime('%Y-%m-%d %H:%M', time.localtime(data.get('processed_at', 0))),
            "path": path,
            "data": data
        }
    except Exception:
        return {"title": "Uszkodzony Plik", "path": path, "data": None}

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚡ AI Second Brain")
    st.caption("v4.0 • Architektura Async ETL")
    st.info("System optymalizuje użycie VRAM poprzez oddzielenie pobierania (Whisper) od przetwarzania (LLM).")
    
    st.divider()
    st.markdown("### 📊 Stan Kolejki")
    inbox_files = load_inbox_items()
    st.metric("Oczekujące w Inbox", len(inbox_files))

# --- TABS ---
tab_ingest, tab_refinery, tab_rag, tab_debug = st.tabs([
    "📥 Pobieranie (Ingest)", 
    "🏭 Przetwarzanie (Refinery)",
    "🔎 Baza Wiedzy",
    "⚙️ System"
])

# ==============================================================================
# TAB 1: INGEST (Extract)
# Goal: Download -> Transcribe -> Save JSON to Inbox -> Release VRAM
# ==============================================================================
with tab_ingest:
    st.header("1. Pobieranie Mediów")
    st.markdown("Pobierz i przetwórz audio na tekst. Wynik trafi do `Inbox`.")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        video_url = st.text_input("YouTube URL:", placeholder="https://youtube.com/watch?v=...")
    with col2:
        model_size = st.selectbox("Model Whisper", ["base", "small", "medium", "large-v3"], index=2)

    if st.button("🚀 Rozpocznij Proces", type="primary", use_container_width=True):
        if not video_url:
            st.error("Podaj URL!")
            st.stop()

        status = st.status("Inicjalizacja potoku...", expanded=True)
        progress = status.empty()
        
        try:
            # Initialize Transcriber (Stateless)
            transcriber = VideoTranscriber(model_size=model_size)
            
            def update_progress(msg):
                status.write(f"🔄 {msg}")
            
            # Run Process
            json_path = transcriber.process_to_inbox(video_url, progress_callback=update_progress)
            
            status.update(label="✅ Zakończono!", state="complete", expanded=False)
            st.success(f"Zapisano dane w Inbox: `{Path(json_path).name}`")
            st.balloons()
            time.sleep(2)
            st.rerun()
            
        except Exception as e:
            status.update(label="❌ Błąd Krytyczny", state="error")
            st.error(str(e))
            logger.error(f"Ingest Error: {e}")

# ==============================================================================
# TAB 2: REFINERY (Transform & Load)
# Goal: Load JSON -> Generate Note (LLM) -> Link (FlashText) -> Save to Vault
# ==============================================================================
with tab_refinery:
    st.header("2. Rafineria Wiedzy")
    
    if not inbox_files:
        st.info("Inbox jest pusty. Przejdź do zakładki Pobieranie, aby dodać materiały.")
    else:
        # Selection Logic
        file_options = {f.name: f for f in inbox_files}
        selected_file_name = st.selectbox(
            "Wybierz element z Inbox:", 
            options=list(file_options.keys()),
            format_func=lambda x: f"📄 {x}"
        )
        
        selected_path = file_options[selected_file_name]
        summary = get_file_summary(selected_path)
        data = summary['data']

        if data:
            st.divider()
            c1, c2 = st.columns([1, 1])
            with c1:
                st.subheader(summary['title'])
                st.caption(f"Przetworzono: {summary['date']}")
                st.text_area("Surowy Transkrypt (Podgląd)", data.get('content', '')[:1000]+"...", height=200, disabled=True)
            
            with c2:
                st.markdown("### Konfiguracja AI")
                prompt_style = st.selectbox("Styl Notatki", ["Akademicki", "Blog Post", "Wypunktowanie", "Podsumowanie"])
                
                # Mapping style names for backend compatibility if needed, 
                # but currently ai_notes.py handles strings. 
                # Let's adjust mapping to match ai_notes expectations or update ai_notes.
                # Since I can't see ai_notes logic for these exact strings, I will map them.
                style_map = {
                    "Akademicki": "Academic",
                    "Blog Post": "Blog Post",
                    "Wypunktowanie": "Bullet Points",
                    "Podsumowanie": "Summary"
                }
                
                if st.button("🧠 Generuj Notatkę Obsidian", type="primary"):
                    with st.spinner("Ładowanie LLM i Generowanie..."):
                        try:
                            # 1. Generate Content (LLM)
                            processor = TranscriptProcessor()
                            note_content = processor.generate_note_content_from_text(
                                text=data.get('content', ''), 
                                meta=data.get('meta', {}),
                                style=style_map.get(prompt_style, "Academic")
                            )
                            
                            # 2. Smart Linking & Tagging (FlashText)
                            gardener = ObsidianGardener()
                            final_note = gardener.auto_link(note_content['content'])
                            final_tags = gardener.smart_tagging(note_content.get('tags', []))
                            
                            # 3. Save to Vault
                            saved_path = gardener.save_note(
                                title=note_content.get('title', summary['title']),
                                content=final_note,
                                tags=final_tags
                            )
                            
                            # 4. Archive Inbox Item
                            archive_dir = ProjectConfig.INBOX_DIR / "archive"
                            archive_dir.mkdir(exist_ok=True)
                            selected_path.rename(archive_dir / selected_path.name)
                            
                            st.success(f"Utworzono notatkę: `{saved_path.name}`")
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"Błąd Rafinerii: {e}")

# ==============================================================================
# TAB 3 & 4: Placeholders for RAG & Config (Simplified for Phase 3)
# ==============================================================================
with tab_rag:
    st.info("Silnik RAG zostanie podłączony w przyszłych aktualizacjach.")

with tab_debug:
    st.write("Konfiguracja Systemu:")
    st.json(ProjectConfig.model_dump())