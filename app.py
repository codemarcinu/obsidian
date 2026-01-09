import streamlit as st
import os
import shutil
from pathlib import Path

# Imports
from config import ProjectConfig
from ai_notes import TranscriptProcessor
from rag_engine import ObsidianRAG
from video_transcriber import VideoTranscriber
from news_agent import NewsAgent
from ai_research import WebResearcher

# --- CONFIG & INIT ---
st.set_page_config(page_title="Obsidian AI Bridge v2", layout="wide", page_icon="🧠")

# Ensure directories exist via Config
ProjectConfig.validate_paths()

if "messages" not in st.session_state:
    st.session_state.messages = []

# --- SIDEBAR ---
with st.sidebar:
    st.title("🧠 Second Brain v2")
    st.caption("Secure • Modular • Local")
    st.markdown("---")
    
    mode = st.radio(
        "Tryb pracy:",
        [
            "📥 Import: Wideo/Audio",
            "🌐 Research & News",
            "🏭 Inbox (Przetwarzanie)",
            "🔎 RAG Chat (Baza Wiedzy)",
            "⚙️ Ustawienia"
        ]
    )
    
    st.markdown("---")
    st.info(f"Vault: `{ProjectConfig.OBSIDIAN_VAULT.name}`")
    st.info(f"Model: `{ProjectConfig.OLLAMA_MODEL}`")

# --- UTILS ---
def get_transcriber_callback(progress_bar, status_text):
    def update_progress(percent, stage, details=None):
        progress_bar.progress(int(percent))
        status_text.text(f"{stage.upper()}: {percent:.1f}% {details or ''}")
    return update_progress

# --- MAIN LOGIC ---

# 1. IMPORT VIDEO
if mode == "📥 Import: Wideo/Audio":
    st.header("🎥 Media Ingestion Pipeline")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        video_url = st.text_input("YouTube URL:")
        uploaded_file = st.file_uploader("Lub wgraj plik (MP3/MP4/WAV):")
    with col2:
        model_size = st.selectbox("Model Whisper", ["base", "small", "medium", "large-v3"], index=1)
        do_obsidian = st.checkbox("Auto-Notatka (Obsidian)", value=True)

    if st.button("🚀 Uruchom Proces", type="primary"):
        status_container = st.container()
        p_bar = status_container.progress(0)
        s_text = status_container.empty()
        
        try:
            transcriber = VideoTranscriber(
                log_callback=lambda x: None, 
                progress_callback=get_transcriber_callback(p_bar, s_text)
            )
            
            target_file = None
            
            # 1. Acquire Media
            if video_url:
                s_text.text("Pobieranie wideo...")
                target_file = transcriber.download_video(video_url, save_path=str(ProjectConfig.TEMP_DIR))
            elif uploaded_file:
                target_file = ProjectConfig.TEMP_DIR / uploaded_file.name
                with open(target_file, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                target_file = str(target_file)
            
            if target_file:
                # 2. Transcribe & Diarize
                s_text.text("Transkrypcja i Diaryzacja (może potrwać)...")
                segments = transcriber.transcribe_and_diarize(
                    target_file, 
                    language="pl", 
                    model_size=model_size,
                    use_diarization=True
                )
                
                # Save raw transcript for Processor
                base_name = os.path.splitext(target_file)[0]
                txt_path = base_name + "_full_transcript.txt"
                
                # Format text for LLM (include speaker info)
                full_text = ""
                for seg in segments:
                    speaker_prefix = f"[{seg.get('speaker', 'Unknown')}]: " if 'speaker' in seg else ""
                    full_text += f"{speaker_prefix}{seg['text']}\n"
                
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(full_text)
                
                st.success(f"Transkrypcja gotowa: `{os.path.basename(txt_path)}`")

                # 3. AI Processing
                if do_obsidian:
                    s_text.text("Generowanie notatki AI...")
                    processor = TranscriptProcessor()
                    success, msg = processor.process_transcript(txt_path)
                    
                    if success:
                        st.balloons()
                        st.success(f"✅ Notatka utworzona: {os.path.basename(msg)}")
                        with st.expander("Podgląd ścieżki"):
                            st.code(msg)
                    else:
                        st.error(f"Błąd generatora: {msg}")

        except Exception as e:
            st.error(f"Critical Error: {e}")

# 2. RESEARCH & NEWS
elif mode == "🌐 Research & News":
    st.header("🌐 AI Research & News")
    
    tab1, tab2 = st.tabs(["🔎 Web Researcher", "📰 News Agent"])
    
    with tab1:
        st.subheader("Analiza Artykułu Technicznego")
        url = st.text_input("Wklej link do artykułu/dokumentacji:")
        if st.button("Analizuj Artykuł"):
            with st.spinner("Pobieranie i analizowanie..."):
                researcher = WebResearcher()
                success = researcher.process_url(url)
                if success:
                    st.success("Analiza zakończona! Notatka zapisana w folderze 'Research'.")
                else:
                    st.error("Błąd podczas analizy.")
                    
    with tab2:
        st.subheader("Agregator Cyber Newsów")
        st.write("Automatycznie pobiera i streszcza newsy z zaufanych źródeł (Sekurak, ZTS, etc.)")
        if st.button("Uruchom Agenta Newsowego"):
            with st.status("Przetwarzanie newsów...", expanded=True) as status:
                agent = NewsAgent()
                count = agent.run()
                status.update(label=f"Gotowe! Przetworzono {count} nowych artykułów.", state="complete")
            if count > 0:
                st.balloons()

# 3. INBOX PROCESSING
elif mode == "🏭 Inbox (Przetwarzanie)":
    st.header("🏭 Fabryka Wiedzy (Inbox)")
    
    # Scan Temp Dir for .txt files
    txt_files = list(ProjectConfig.TEMP_DIR.glob("*.txt"))
    
    if not txt_files:
        st.info("Skrzynka odbiorcza pusta.")
    else:
        st.write(f"Znaleziono {len(txt_files)} plików do przetworzenia.")
        
        for txt_file in txt_files:
            if "processed" in txt_file.name: continue

            col1, col2 = st.columns([4, 1])
            with col1:
                st.text(f"📄 {txt_file.name}")
            with col2:
                if st.button("Przetwórz", key=str(txt_file)):
                    with st.spinner("Analizuję..."):
                        processor = TranscriptProcessor()
                        success, msg = processor.process_transcript(str(txt_file))
                        if success:
                            st.success("Gotowe!")
                            processed_dir = ProjectConfig.TEMP_DIR / "processed"
                            processed_dir.mkdir(exist_ok=True)
                            shutil.move(str(txt_file), processed_dir / txt_file.name)
                            st.rerun()
                        else:
                            st.error(f"Błąd: {msg}")

# 4. RAG CHAT
elif mode == "🔎 RAG Chat (Baza Wiedzy)":
    st.header("🔎 Rozmowa z Bazą Wiedzy")
    
    c1, c2 = st.columns([3, 1])
    with c2:
        if st.button("🔄 Aktualizuj Indeks"):
            with st.status("Indeksowanie przyrostowe...", expanded=True) as status:
                rag = ObsidianRAG()
                count = rag.index_vault(ProjectConfig.OBSIDIAN_VAULT)
                status.update(label=f"Zakończono! Dodano/Zmieniono {count} fragmentów.", state="complete")
    
    # Chat Interface
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
    if prompt := st.chat_input("O co chcesz zapytać?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
            
        with st.chat_message("assistant"):
            rag = ObsidianRAG()
            response_placeholder = st.empty()
            full_response = ""
            
            # Streaming generator
            gen = rag.query(
                prompt, 
                history=st.session_state.messages[:-1], 
                model_name=ProjectConfig.OLLAMA_MODEL, 
                stream=True
            )
            
            for chunk in gen:
                chunk = chunk.replace("<think>", "**Myślenie:**\n").replace("</think>", "\n---\n")
                full_response += chunk
                response_placeholder.markdown(full_response + "▌")
            
            response_placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})

# 5. SETTINGS
elif mode == "⚙️ Ustawienia":
    st.header("Konfiguracja")
    st.code(f"""
    BASE_DIR: {ProjectConfig.BASE_DIR}
    VAULT: {ProjectConfig.OBSIDIAN_VAULT}
    DB_DIR: {ProjectConfig.DB_DIR}
    LOG_FILE: {ProjectConfig.BASE_DIR / 'system.log'}
    """, language="yaml")
    
    if st.button("Wyczyść Cache Streamlit"):
        st.cache_data.clear()
        st.success("Wyczyszczono.")