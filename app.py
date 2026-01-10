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
tab_ingest, tab_refinery, tab_rag, tab_research, tab_debug = st.tabs([
    "📥 Pobieranie (Ingest)", 
    "🏭 Przetwarzanie (Refinery)",
    "🔎 Baza Wiedzy",
    "📰 Research & News",
    "⚙️ System"
])

# ==============================================================================
# TAB 1: INGEST (Extract)
# Goal: Download -> Transcribe -> Save JSON to Inbox -> Release VRAM
# ==============================================================================
with tab_ingest:
    st.header("1. Pobieranie Mediów")
    
    # Wybór źródła
    source_type = st.radio("Źródło:", ["YouTube URL", "Plik Lokalny (mp3, wav, m4a)"], horizontal=True)
    model_size = st.selectbox("Model Whisper", ["base", "small", "medium", "large-v3"], index=2)

    if source_type == "YouTube URL":
        video_url = st.text_input("YouTube URL:", placeholder="https://youtube.com/watch?v=...")
    else:
        uploaded_file = st.file_uploader("Wrzuć nagranie", type=['mp3', 'wav', 'm4a', 'ogg'])

    if st.button("🚀 Rozpocznij Proces", type="primary", use_container_width=True):
        if source_type == "YouTube URL":
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
        else:
            # Logika dla pliku lokalnego
            if not uploaded_file:
                st.error("Wybierz plik!")
                st.stop()
                
            status = st.status("Przetwarzanie pliku lokalnego...", expanded=True)
            
            # Zapisz plik tymczasowo
            save_path = ProjectConfig.TEMP_DIR / uploaded_file.name
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            try:
                status.write("🎧 Inicjalizacja Whisper...")
                transcriber = VideoTranscriber(model_size=model_size)
                
                meta = {
                    "id": f"local-{int(time.time())}",
                    "title": uploaded_file.name,
                    "uploader": "Marcin (Voice Memo)",
                    "duration": 0,
                    "local_path": str(save_path),
                    "url": "local_file"
                }
                
                status.write("🎧 Transkrypcja (Whisper)...")
                # Wywołujemy transkrypcję (zakładamy że _run_transcription_isolated istnieje i jest dostępna)
                # Jeśli nie, używamy process_to_inbox ale on ściąga z URL. 
                # Zgodnie z planem użytkownika, używamy _run_transcription_isolated.
                transcript_data = transcriber._run_transcription_isolated(str(save_path))
                
                # Zapis do Inbox
                payload = {
                    "meta": meta,
                    "content": transcript_data['text'],
                    "segments": transcript_data['segments'],
                    "processed_at": time.time(),
                    "status": "ready_for_refinery"
                }
                
                out_name = f"memo-{int(time.time())}.json"
                out_path = ProjectConfig.INBOX_DIR / out_name
                with open(out_path, 'w', encoding='utf-8') as f:
                    json.dump(payload, f, indent=2, ensure_ascii=False)
                
                status.update(label="✅ Gotowe! Plik w Inbox.", state="complete")
                st.success(f"Zapisano dane w Inbox: `{out_name}`")
                st.balloons()
                time.sleep(2)
                st.rerun()

            except Exception as e:
                status.update(label="❌ Błąd Krytyczny", state="error")
                st.error(f"Błąd: {e}")
                logger.error(f"Local Ingest Error: {e}")

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
# TAB 3: RAG (Knowledge Base Chat)
# ==============================================================================
with tab_rag:
    st.header("🔎 Czat z Bazą Wiedzy (RAG)")
    
    # 1. Inicjalizacja RAG (Lazy loading)
    if "rag_engine" not in st.session_state:
        try:
            from rag_engine import ObsidianRAG
            with st.spinner("Ładowanie silnika wektorowego (ChromaDB)..."):
                st.session_state.rag_engine = ObsidianRAG()
                st.success("Silnik RAG gotowy.")
        except Exception as e:
            st.error(f"Nie udało się załadować RAG: {e}")
            st.stop()

    rag = st.session_state.rag_engine

    # 2. Panel boczny - Indeksowanie
    with st.expander("⚙️ Zarządzanie Indeksem"):
        st.caption("Uruchom, gdy dodasz nowe notatki do Obsidiana.")
        if st.button("🔄 Przeindeksuj Skarbiec (Incremental)"):
            with st.spinner("Aktualizacja wektorów..."):
                added = rag.index_vault(ProjectConfig.OBSIDIAN_VAULT)
                st.success(f"Zindeksowano nowych fragmentów: {added}")

    # 3. Interfejs Czatu
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Wyświetlanie historii
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Obsługa pytania użytkownika
    if prompt := st.chat_input("O co chcesz zapytać swojego Drugiego Mózgu?"):
        # Dodaj pytanie do historii
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generowanie odpowiedzi
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            try:
                # Przekazujemy historię rozmowy dla kontekstu
                stream = rag.query(
                    question=prompt, 
                    history=st.session_state.messages[:-1], # Bez ostatniego pytania
                    n_results=5
                )
                
                for chunk in stream:
                    # Obsługa struktury odpowiedzi Ollamy
                    content = chunk.get('message', {}).get('content', '')
                    full_response += content
                    message_placeholder.markdown(full_response + "▌")
                
                message_placeholder.markdown(full_response)
                
                # Dodaj odpowiedź do historii
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
            except Exception as e:
                st.error(f"Błąd generowania: {e}")

# ==============================================================================
# TAB 4: RESEARCH & NEWS
# ==============================================================================
with tab_research:
    st.header("📰 Agent Newsowy i Research")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Daily Cybersec Briefing")
        st.caption("Pobiera newsy z Sekuraka, Zaufanej Trzeciej Strony itp.")
        if st.button("uruchom NewsAgenta"):
            from news_agent import NewsAgent
            agent = NewsAgent()
            with st.status("Analiza RSS...", expanded=True) as status:
                count = agent.run(limit=3) # Limit 3 na źródło dla szybkości
                status.update(label=f"Zakończono! Dodano {count} nowych notatek.", state="complete")
    
    with col2:
        st.subheader("Web Research (URL)")
        target_url = st.text_input("Wklej link do artykułu/dokumentacji:")
        if st.button("Analizuj Artykuł"):
            if target_url:
                from ai_research import WebResearcher
                researcher = WebResearcher()
                with st.spinner("Pobieranie i analiza AI..."):
                    success = researcher.process_url(target_url)
                    if success:
                        st.success("Notatka badawcza utworzona w folderze Research!")
                    else:
                        st.error("Błąd pobierania.")

# ==============================================================================
# TAB 5: SYSTEM DEBUG
# ==============================================================================
with tab_debug:
    st.write("Konfiguracja Systemu:")
    st.json(ProjectConfig.model_dump())