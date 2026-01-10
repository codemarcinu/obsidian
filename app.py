import streamlit as st
import os
import time
import logging
from pathlib import Path
import ollama

# --- CONFIG ---
from config import ProjectConfig, logger

# --- MODULES ---
from ai_notes import TranscriptProcessor
from rag_engine import ObsidianRAG
from video_transcriber import VideoTranscriber
from news_agent import NewsAgent
from ai_research import WebResearcher
from pdf_shredder import PDFShredder

st.set_page_config(page_title="Obsidian AI Bridge v3.0", layout="wide", page_icon="🧠")

# --- RESOURCE CACHING (The "Anti-Shell-Hell" Layer) ---

@st.cache_resource(show_spinner="Ładowanie silnika RAG...")
def get_rag_engine():
    """Singleton for Vector DB connection."""
    return ObsidianRAG()

@st.cache_resource(show_spinner="Ładowanie modeli AI do VRAM (Whisper+Pyannote)...")
def get_transcriber():
    """Singleton for GPU-heavy models. Loaded ONCE."""
    return VideoTranscriber(model_size="medium")

@st.cache_data(ttl=300)
def get_vault_stats():
    """Cached vault statistics."""
    vault = ProjectConfig.OBSIDIAN_VAULT
    md_files = list(vault.rglob("*.md"))
    return len(md_files)

def check_system_health():
    health = {"ollama": False, "gpu": False}
    try:
        ollama.list()
        health["ollama"] = True
    except: pass
    try:
        import torch
        if torch.cuda.is_available(): health["gpu"] = True
    except: pass
    return health

# --- SESSION STATE INIT ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- SIDEBAR ---
with st.sidebar:
    st.title("🧠 Second Brain")
    st.caption("v3.0 • Module-Based Architecture")
    st.divider()
    
    mode = st.radio(
        "Nawigacja:",
        [
            "🏠 Dashboard",
            "📥 Import: Wideo/Audio",
            "🌐 Research & News",
            "📄 Import: PDF Compliance",
            "🔎 RAG Chat (Baza Wiedzy)",
            "⚙️ Debug / Config"
        ]
    )
    
    st.divider()
    st.info(f"Vault: `{ProjectConfig.OBSIDIAN_VAULT.name}`")
    st.info(f"Model: `{ProjectConfig.OLLAMA_MODEL}`")

# --- MAIN PAGES ---

if mode == "🏠 Dashboard":
    st.title("Centrum Dowodzenia")
    
    health = check_system_health()
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Notatki w Bazie", get_vault_stats())
    with c2:
        st.metric("AI Model", "Online" if health["ollama"] else "Offline", delta_color="normal")
    with c3:
        st.metric("GPU Status", "RTX 3060 Ready" if health["gpu"] else "CPU Only")

    st.markdown("### ⚡ Quick Actions")
    if st.button("🧹 Wyczyść Cache (Reload Models)"):
        st.cache_resource.clear()
        st.rerun()

elif mode == "📥 Import: Wideo/Audio":
    st.header("🎥 Media Ingestion (GPU Optimized)")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        video_url = st.text_input("YouTube URL:")
        uploaded_file = st.file_uploader("Lub plik lokalny (MP3/MP4/WAV):")
    with col2:
        st.markdown("**Konfiguracja:**")
        do_diarization = st.checkbox("Rozpoznawanie mówców (Pyannote)", value=True)
        # Note: Model size is fixed in singleton for performance, but could be parameterised with different singletons

    if st.button("🚀 Przetwórz Media", type="primary"):
        status_container = st.status("Inicjalizacja...", expanded=True)
        progress_bar = status_container.empty()
        
        with status_container:
            try:
                # 1. Get Singleton
                transcriber = get_transcriber()
                
                # 2. Acquire File
                target_file = None
                
                def download_callback(msg):
                    status_container.update(label=f"📥 {msg}", state="running")
                
                if video_url:
                    target_file = transcriber.download_video(video_url, progress_callback=download_callback)
                elif uploaded_file:
                    status_container.write("📥 Wczytywanie pliku lokalnego...")
                    target_file = ProjectConfig.TEMP_DIR / uploaded_file.name
                    with open(target_file, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    target_file = str(target_file)
                
                if target_file:
                    st.audio(target_file)
                    
                    # 3. Transcribe
                    status_container.update(label="📝 Transkrypcja (Whisper)...", state="running")
                    
                    def transcribe_callback(percent):
                        progress_bar.progress(percent, text=f"Transkrypcja: {percent}%")
                    
                    segments = transcriber.transcribe_and_diarize(target_file, progress_callback=transcribe_callback)
                    progress_bar.empty() # Clear progress bar
                    
                    # 4. Format
                    full_text = ""
                    for seg in segments:
                        speaker = f"[{seg.get('speaker', '?')}]: " if 'speaker' in seg else ""
                        full_text += f"{speaker}{seg['text']}\n"
                    
                    # 5. Save Raw
                    raw_path = str(target_file) + ".txt"
                    with open(raw_path, "w", encoding='utf-8') as f:
                        f.write(full_text)
                        
                    # 6. Generate Note
                    status_container.update(label="🧠 Analiza treści (Ollama)...", state="running")
                    processor = TranscriptProcessor() # Lightweight, no caching needed
                    note_data = processor.generate_note_content(raw_path)
                    
                    st.session_state['draft_note'] = note_data
                    status_container.update(label="✅ Gotowe!", state="complete")
                    
            except Exception as e:
                status_container.update(label="❌ Błąd krytyczny!", state="error")
                st.error(f"Error: {e}")
                logger.error(f"Ingestion Error: {e}")

    # Editor UI
    if 'draft_note' in st.session_state:
        draft = st.session_state['draft_note']
        st.divider()
        st.subheader(f"Edycja: {draft.get('title', 'Untitled')}")
        edited_content = st.text_area("Treść", draft.get('content', ''), height=400)
        
        if st.button("💾 Zapisz Notatkę"):
            processor = TranscriptProcessor()
            # Note: We need to parse title from content or input, simple way:
            final_path = processor.save_note_to_disk(draft.get('title', 'note'), edited_content)
            st.success(f"Zapisano: {final_path}")
            del st.session_state['draft_note']
            time.sleep(1)
            st.rerun()

elif mode == "🌐 Research & News":
    st.header("🌐 AI Researcher")
    tab1, tab2 = st.tabs(["Web Analyzer", "RSS News Agent"])
    
    with tab1:
        url = st.text_input("URL artykułu:")
        if st.button("Analizuj"):
            researcher = WebResearcher()
            with st.spinner("Czytanie i analiza..."):
                if researcher.process_url(url):
                    st.success("Notatka dodana do Research!")
                else:
                    st.error("Błąd pobierania.")
    
    with tab2:
        if st.button("Pobierz Newsy"):
            agent = NewsAgent()
            with st.spinner("Skanowanie feedów..."):
                count = agent.run()
            st.success(f"Dodano {count} nowych newsów.")

elif mode == "📄 Import: PDF Compliance":
    st.header("📄 PDF Shredder")
    uploaded = st.file_uploader("Wybierz PDF", type="pdf")
    if uploaded and st.button("Przetwórz"):
        temp_path = ProjectConfig.TEMP_DIR / uploaded.name
        with open(temp_path, "wb") as f:
            f.write(uploaded.getbuffer())
        
        shredder = PDFShredder()
        success, msg = shredder.process_pdf(str(temp_path))
        if success:
            st.success(f"Raport gotowy: {Path(msg).name}")
        else:
            st.error(msg)

elif mode == "🔎 RAG Chat (Baza Wiedzy)":
    st.header("🔎 Chat z Dokumentacją")
    
    # Singleton RAG Engine
    rag = get_rag_engine()
    
    c1, c2 = st.columns([3, 1])
    with c2:
        if st.button("🔄 Re-indeksacja"):
            with st.status("Indeksowanie..."):
                count = rag.index_vault(ProjectConfig.OBSIDIAN_VAULT)
                st.write(f"Zindeksowano: {count} nowych chunków.")
    
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
    if prompt := st.chat_input():
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
            
        with st.chat_message("assistant"):
            response_container = st.empty()
            full_response = ""
            for chunk in rag.query(prompt, history=st.session_state.messages):
                full_response += chunk
                response_container.markdown(full_response + "▌")
            response_container.markdown(full_response)
        
        st.session_state.messages.append({"role": "assistant", "content": full_response})

elif mode == "⚙️ Debug / Config":
    st.header("Konfiguracja i Logi")
    
    tab_cfg, tab_log = st.tabs(["⚙️ Konfiguracja", "📝 Logi Systemowe"])
    
    with tab_cfg:
        st.json(ProjectConfig.model_dump())
    
    with tab_log:
        log_file = ProjectConfig.BASE_DIR / "system.log"
        col1, col2 = st.columns([4, 1])
        with col2:
            if st.button("🔄 Odśwież"):
                st.rerun()
            if st.button("🗑️ Wyczyść Logi"):
                if log_file.exists():
                    log_file.write_text("")
                    st.success("Logi wyczyszczone.")
                    st.rerun()
        
        if log_file.exists():
            with open(log_file, "r", encoding='utf-8') as f:
                lines = f.readlines()
                # Odwracamy kolejność, żeby najnowsze były na górze
                last_logs = "".join(reversed(lines[-500:]))
                st.code(last_logs, language="log")
        else:
            st.warning("Plik system.log nie istnieje.")
