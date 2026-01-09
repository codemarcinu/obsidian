import streamlit as st
import os
import shutil
import warnings
import time
from pathlib import Path
import ollama

# SILENCE TORCH AUDIO WARNINGS
warnings.filterwarnings("ignore", category=UserWarning, message=".*Torchaudio's I/O functions.*")

# Imports
from config import ProjectConfig, logger
from ai_notes import TranscriptProcessor
from rag_engine import ObsidianRAG
from video_transcriber import VideoTranscriber
from news_agent import NewsAgent
from ai_research import WebResearcher
from pdf_shredder import PDFShredder

# --- CONFIG & INIT ---
st.set_page_config(page_title="Obsidian AI Bridge v2.2", layout="wide", page_icon="🧠")

# Ensure directories exist via Config
ProjectConfig.validate_paths()

if "messages" not in st.session_state:
    st.session_state.messages = []

# --- UTILS ---
def count_vault_stats():
    """Helper for Dashboard stats."""
    vault = ProjectConfig.OBSIDIAN_VAULT
    md_files = list(vault.rglob("*.md"))
    return len(md_files)

def check_system_health():
    """Checks Ollama and GPU."""
    health = {"ollama": False, "gpu": False}
    try:
        ollama.list()
        health["ollama"] = True
    except:
        pass
    
    # Simple check if import torch worked (VideoTranscriber checks CUDA on init)
    try:
        import torch
        if torch.cuda.is_available():
            health["gpu"] = True
    except:
        pass
    return health

# --- SIDEBAR ---
with st.sidebar:
    st.title("🧠 Second Brain")
    st.caption("v2.2 • UX Upgrade")
    st.markdown("---")
    
    mode = st.radio(
        "Nawigacja:",
        [
            "🏠 Dashboard",
            "📥 Import: Wideo/Audio",
            "🌐 Research & News",
            "📄 Import: PDF Compliance",
            "🏭 Inbox (Przetwarzanie)",
            "🔎 RAG Chat (Baza Wiedzy)",
            "⚙️ Ustawienia"
        ]
    )
    
    st.markdown("---")
    st.info(f"Vault: `{ProjectConfig.OBSIDIAN_VAULT.name}`")
    st.info(f"Model: `{ProjectConfig.OLLAMA_MODEL}`")

# --- MAIN LOGIC ---

# 0. DASHBOARD (NEW UX #3)
if mode == "🏠 Dashboard":
    st.title("Centrum Dowodzenia")
    
    # Health Check
    health = check_system_health()
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Notatki w Bazie", count_vault_stats())
    with c2:
        status = "🟢 Online" if health["ollama"] else "🔴 Offline"
        st.metric("AI Model (Ollama)", status, delta="Ready" if health["ollama"] else "-Error")
    with c3:
        gpu_status = "🟢 RTX 3060" if health["gpu"] else "🟡 CPU Mode"
        st.metric("Akceleracja GPU", gpu_status)

    st.markdown("### 🕒 Szybkie Akcje")
    col1, col2 = st.columns(2)
    with col1:
        st.info("💡 **Masz nowy pomysł?** Przejdź do *Import Wideo* lub *Research*, aby dodać wiedzę do swojego cyfrowego mózgu.")
    with col2:
        st.success("🔎 **Szukasz czegoś?** Skorzystaj z *RAG Chat*, aby przeszukać swoje lokalne pliki przy pomocy AI.")

# 1. IMPORT VIDEO (NEW UX #1, #2, #4)
elif mode == "📥 Import: Wideo/Audio":
    st.header("🎥 Media Ingestion Pipeline")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        video_url = st.text_input("YouTube URL:")
        uploaded_file = st.file_uploader("Lub wgraj plik (MP3/MP4/WAV):")
    with col2:
        model_size = st.selectbox("Model Whisper", ["base", "small", "medium", "large-v3"], index=1)
        do_diarization = st.checkbox("Rozpoznawanie mówców", value=True)

    if st.button("🚀 Uruchom Proces", type="primary"):
        # UX #2: Collapsible Status
        with st.status("Przetwarzanie mediów...", expanded=True) as status:
            target_file = None
            generated_data = None
            
            try:
                # 1. Acquire Media
                status.write("📥 Pobieranie materiału...")
                transcriber = VideoTranscriber()
                
                if video_url:
                    target_file = transcriber.download_video(video_url)
                elif uploaded_file:
                    target_file = ProjectConfig.TEMP_DIR / uploaded_file.name
                    with open(target_file, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    target_file = str(target_file)
                
                if target_file:
                    # UX #4: Media Player
                    st.audio(target_file)
                    
                    # 2. Transcribe & Diarize
                    status.write("📝 Transkrypcja i Diaryzacja (Whisper + Pyannote)...")
                    segments = transcriber.transcribe_and_diarize(
                        target_file, 
                        model_size=model_size,
                        use_diarization=do_diarization
                    )
                    
                    # Save raw transcript for Processor
                    base_name = os.path.splitext(target_file)[0]
                    txt_path = base_name + "_full_transcript.txt"
                    
                    full_text = ""
                    for seg in segments:
                        speaker_prefix = f"[{seg.get('speaker', 'Unknown')}]: " if 'speaker' in seg else ""
                        full_text += f"{speaker_prefix}{seg['text']}\n"
                    
                    with open(txt_path, "w", encoding="utf-8") as f:
                        f.write(full_text)
                    
                    # 3. AI Processing (Generation only)
                    status.write("🧠 Generowanie notatki AI (Llama/Bielik)...")
                    processor = TranscriptProcessor()
                    generated_data = processor.generate_note_content(txt_path)
                    
                    status.update(label="Gotowe! Sprawdź wynik poniżej i zatwierdź zapis.", state="complete", expanded=False)
                    
                    # Store in session state for editing
                    st.session_state['draft_note'] = generated_data
                    st.session_state['draft_file_path'] = target_file
                    
            except Exception as e:
                status.update(label="Błąd podczas przetwarzania!", state="error")
                st.error(f"Critical Error: {e}")
                logger.error(f"Ingestion failed: {e}", exc_info=True)

    # UX #1: Human in the Loop (Editor)
    if 'draft_note' in st.session_state:
        st.divider()
        st.subheader("📝 Weryfikacja i Edycja Notatki")
        
        draft = st.session_state['draft_note']
        if "error" in draft:
            st.error(draft["error"])
        else:
            col_meta1, col_meta2 = st.columns([3, 1])
            with col_meta1:
                new_title = st.text_input("Tytuł notatki (nazwa pliku):", value=draft['title'])
            with col_meta2:
                st.info(f"Wykryte tagi: {', '.join(draft['tags'])}")
                
            edited_content = st.text_area("Treść Markdown:", value=draft['content'], height=500)
            
            c1, c2 = st.columns([1, 4])
            with c1:
                if st.button("💾 Zapisz do Obsidian"):
                    processor = TranscriptProcessor()
                    final_path = processor.save_note_to_disk(new_title, edited_content)
                    
                    # UX #2: Toast Notification
                    st.toast(f"Zapisano pomyślnie: {os.path.basename(final_path)}", icon="✅")
                    st.success(f"Notatka dodana do Vaulta: `{final_path}`")
                    
                    # Cleanup session
                    del st.session_state['draft_note']
                    if 'draft_file_path' in st.session_state:
                        path_to_del = st.session_state['draft_file_path']
                        if os.path.exists(path_to_del):
                            os.remove(path_to_del)
                            logger.info(f"Cleaned up: {path_to_del}")
                    
                    time.sleep(1.5)
                    st.rerun()
            with c2:
                if st.button("🗑️ Odrzuć"):
                    del st.session_state['draft_note']
                    st.rerun()

# 2. RESEARCH & NEWS
elif mode == "🌐 Research & News":
    st.header("🌐 AI Research & News")
    
    tab1, tab2 = st.tabs(["🔎 Web Researcher", "📰 News Agent"])
    
    with tab1:
        st.subheader("Analiza Artykułu Technicznego")
        url = st.text_input("Wklej link do artykułu:")
        if st.button("Analizuj Artykuł"):
            with st.status("Pobieranie i analizowanie...", expanded=True) as status:
                researcher = WebResearcher()
                success = researcher.process_url(url)
                if success:
                    status.update(label="Analiza zakończona!", state="complete")
                    st.toast("Notatka researchowa dodana!", icon="🧠")
                else:
                    status.update(label="Błąd", state="error")
                    st.error("Błąd podczas analizy strony.")
                    
    with tab2:
        st.subheader("Agregator Cyber Newsów")
        if st.button("Uruchom Agenta Newsowego"):
            with st.status("Przetwarzanie newsów...", expanded=True) as status:
                agent = NewsAgent()
                count = agent.run()
                status.update(label=f"Gotowe! Przetworzono {count} newsów.", state="complete")
            if count > 0:
                st.toast(f"Dodano {count} nowych wpisów!", icon="📰")
                st.balloons()

# 3. PDF COMPLIANCE
elif mode == "📄 Import: PDF Compliance":
    st.header("📄 PDF Shredder (DORA/NIS2)")
    st.caption("Automatyczna ekstrakcja tabel i tagowanie regulacyjne.")
    
    uploaded_pdf = st.file_uploader("Wgraj dokument (PDF):", type="pdf")
    if uploaded_pdf and st.button("Analizuj Dokument"):
        temp_path = ProjectConfig.TEMP_DIR / uploaded_pdf.name
        with open(temp_path, "wb") as f:
            f.write(uploaded_pdf.getbuffer())
        
        with st.status("Szatkowanie dokumentu...", expanded=True) as status:
            shredder = PDFShredder()
            success, msg = shredder.process_pdf(str(temp_path))
            
            if success:
                status.update(label="Zakończono!", state="complete")
                st.toast("Dokument przetworzony!", icon="✅")
                st.success(f"Raport wygenerowany: {Path(msg).name}")
            else:
                status.update(label="Błąd PDF", state="error")
                st.error(f"Błąd: {msg}")
        
        # Cleanup
        if temp_path.exists():
            temp_path.unlink()

# 4. INBOX
elif mode == "🏭 Inbox (Przetwarzanie)":
    st.header("🏭 Fabryka Wiedzy (Inbox)")
    st.info("Sekcja w trakcie przebudowy na system Human-in-the-Loop.")
    
    txt_files = list(ProjectConfig.TEMP_DIR.glob("*.txt"))
    if not txt_files:
        st.info("Brak surowych transkrypcji do przetworzenia.")
    else:
        for txt_file in txt_files:
            if "processed" in txt_file.name: continue
            col1, col2 = st.columns([4, 1])
            with col1: st.text(f"📄 {txt_file.name}")
            with col2:
                if st.button("Wczytaj", key=str(txt_file)):
                    processor = TranscriptProcessor()
                    st.session_state['draft_note'] = processor.generate_note_content(str(txt_file))
                    st.rerun()

# 5. RAG CHAT
elif mode == "🔎 RAG Chat (Baza Wiedzy)":
    st.header("🔎 Rozmowa z Bazą Wiedzy")
    
    if st.button("🔄 Aktualizuj Indeks"):
        with st.status("Indeksowanie przyrostowe...", expanded=True) as status:
            rag = ObsidianRAG()
            count = rag.index_vault(ProjectConfig.OBSIDIAN_VAULT)
            status.update(label=f"Zaktualizowano {count} fragmentów.", state="complete")
            st.toast("Baza wiedzy jest aktualna!", icon="🧠")
    
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

# 6. SETTINGS
elif mode == "⚙️ Ustawienia":
    st.header("Konfiguracja")
    st.code(f"""
    BASE_DIR: {ProjectConfig.BASE_DIR}
    VAULT: {ProjectConfig.OBSIDIAN_VAULT}
    OLLAMA: {ProjectConfig.OLLAMA_MODEL}
    """, language="yaml")
    
    if st.button("Wyczyść Cache"):
        st.cache_data.clear()
        st.toast("Cache wyczyszczony", icon="🧹")