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
        return {"title": "Corrupted File", "path": path, "data": None}

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚡ AI Second Brain")
    st.caption("v4.0 • Async ETL Architecture")
    st.info("System optimizes VRAM usage by separating Ingestion (Whisper) from Refinery (LLM).")
    
    st.divider()
    st.markdown("### 📊 Queue Status")
    inbox_files = load_inbox_items()
    st.metric("Inbox Queue", len(inbox_files))

# --- TABS ---
tab_ingest, tab_refinery, tab_rag, tab_debug = st.tabs([
    "📥 Ingest (Download & Transcribe)", 
    "🏭 Refinery (LLM & Obsidian)",
    "🔎 Knowledge Base",
    "⚙️ System"
])

# ==============================================================================
# TAB 1: INGEST (Extract)
# Goal: Download -> Transcribe -> Save JSON to Inbox -> Release VRAM
# ==============================================================================
with tab_ingest:
    st.header("1. Media Ingestion")
    st.markdown("Pobierz i przetwórz audio na tekst. Wynik trafi do `Inbox`.")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        video_url = st.text_input("YouTube URL:", placeholder="https://youtube.com/watch?v=...")
    with col2:
        model_size = st.selectbox("Model Whisper", ["base", "small", "medium", "large-v3"], index=2)

    if st.button("🚀 Start Extraction Process", type="primary", use_container_width=True):
        if not video_url:
            st.error("Podaj URL!")
            st.stop()

        status = st.status("Initializing Ingestion Pipeline...", expanded=True)
        progress = status.empty()
        
        try:
            # Initialize Transcriber (Stateless)
            transcriber = VideoTranscriber(model_size=model_size)
            
            def update_progress(msg):
                status.write(f"🔄 {msg}")
            
            # Run Process
            json_path = transcriber.process_to_inbox(video_url, progress_callback=update_progress)
            
            status.update(label="✅ Extraction Complete!", state="complete", expanded=False)
            st.success(f"Saved payload to Inbox: `{Path(json_path).name}`")
            st.balloons()
            time.sleep(2)
            st.rerun()
            
        except Exception as e:
            status.update(label="❌ Critical Error", state="error")
            st.error(str(e))
            logger.error(f"Ingest Error: {e}")

# ==============================================================================
# TAB 2: REFINERY (Transform & Load)
# Goal: Load JSON -> Generate Note (LLM) -> Link (FlashText) -> Save to Vault
# ==============================================================================
with tab_refinery:
    st.header("2. Knowledge Refinery")
    
    if not inbox_files:
        st.info("Inbox is empty. Go to Ingest tab to add content.")
    else:
        # Selection Logic
        file_options = {f.name: f for f in inbox_files}
        selected_file_name = st.selectbox(
            "Select Item from Inbox:", 
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
                st.caption(f"Processed: {summary['date']}")
                st.text_area("Raw Transcript (Preview)", data.get('content', '')[:1000]+"...", height=200, disabled=True)
            
            with c2:
                st.markdown("### AI Configuration")
                prompt_style = st.selectbox("Note Style", ["Academic", "Blog Post", "Bullet Points", "Summary"])
                
                if st.button("🧠 Generate Obsidian Note", type="primary"):
                    with st.spinner("Loading LLM & Generating..."):
                        try:
                            # 1. Generate Content (LLM)
                            processor = TranscriptProcessor()
                            note_content = processor.generate_note_content_from_text(
                                text=data.get('content', ''), 
                                meta=data.get('meta', {}),
                                style=prompt_style
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
                            
                            st.success(f"Note created: `{saved_path.name}`")
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"Refinery Error: {e}")

# ==============================================================================
# TAB 3 & 4: Placeholders for RAG & Config (Simplified for Phase 3)
# ==============================================================================
with tab_rag:
    st.info("RAG Engine will be re-connected in future updates.")

with tab_debug:
    st.write("System Config:")
    st.json(ProjectConfig.model_dump())