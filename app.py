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

# --- CUSTOM CSS ---
st.markdown("""
<style>
    /* Ukrycie domyślnego menu i stopki */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Stylizacja Sidebaru */
    [data-testid="stSidebar"] {
        background-color: #2d2d2d;
        border-right: 1px solid #3d3d3d;
    }
    
    /* Przyciski */
    .stButton > button {
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

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

def process_single_file(file_path: Path, style="Academic", gardener_instance=None):
    """Logic extracted for batch processing."""
    summary = get_file_summary(file_path)
    data = summary['data']
    if not data: return False
    
    style_map = {
        "Akademicki": "Academic",
        "Blog Post": "Blog Post",
        "Wypunktowanie": "Bullet Points",
        "Podsumowanie": "Summary"
    }
    selected_style = style_map.get(style, "Academic")

    # 1. Generate Content (LLM)
    processor = TranscriptProcessor()
    note_content = processor.generate_note_content_from_text(
        text=data.get('content', ''), 
        meta=data.get('meta', {}),
        style=selected_style
    )
    
    # 2. Smart Linking & Tagging (FlashText)
    gardener = gardener_instance or ObsidianGardener()
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
    file_path.rename(archive_dir / file_path.name)
    
    return saved_path

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚡ AI Second Brain")
    st.caption("v4.1 • UX Enhanced")
    
    # Navigation
    st.markdown("### 🧭 Nawigacja")
    selected_page = st.radio(
        "Idź do:",
        [
            "📥 Pobieranie (Ingest)", 
            "🏭 Przetwarzanie (Refinery)",
            "🔎 Baza Wiedzy (RAG)",
            "📰 Research & News",
            "⚙️ System"
        ],
        label_visibility="collapsed"
    )
    
    st.divider()
    
    # Inbox Status
    inbox_files = load_inbox_items()
    st.markdown("### 📊 Stan Kolejki")
    col_met, col_ref = st.columns([2, 1])
    with col_met:
        st.metric("Inbox", len(inbox_files))
    with col_ref:
        st.write("") # wyrównanie do linii metryki
        if st.button("🔄", help="Odśwież listę plików"):
            st.rerun()
    
    if len(inbox_files) > 0:
        st.info(f"Najnowszy: {inbox_files[0].name[:20]}...")
    
    # [UX] Live Logs
    with st.expander("🤖 Status BrainGuard", expanded=False):
        log_file = Path("brain_guard.log")
        if log_file.exists():
            # Czytamy ostatnie linie
            lines = log_file.read_text(encoding='utf-8').splitlines()[-10:]
            st.code("\n".join(lines), language="bash")
            if st.button("Odśwież log"):
                st.rerun()
        else:
            st.warning("Brak pliku logów.")

    st.divider()
    st.info("System optymalizuje użycie VRAM poprzez oddzielenie pobierania (Whisper) od przetwarzania (LLM).")

# ==============================================================================
# PAGE 1: INGEST (Extract)
# ==============================================================================
if selected_page == "📥 Pobieranie (Ingest)":
    st.header("1. Pobieranie Mediów")
    st.caption("Pobierz audio z YouTube lub pliku, wykonaj transkrypcję i zapisz do Inbox.")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        source_type = st.radio("Źródło:", ["YouTube URL", "Plik Lokalny (mp3, wav, m4a)"])
        model_size = st.selectbox("Model Whisper", ["base", "small", "medium", "large-v3"], index=2)
    
    with col2:
        if source_type == "YouTube URL":
            video_url = st.text_input("YouTube URL:", placeholder="https://youtube.com/watch?v=...")
            uploaded_file = None
        else:
            video_url = None
            uploaded_file = st.file_uploader("Wrzuć nagranie", type=['mp3', 'wav', 'm4a', 'ogg'])

    st.divider()

    if st.button("🚀 Rozpocznij Proces", type="primary", use_container_width=True):
        if source_type == "YouTube URL":
            if not video_url:
                st.error("Podaj URL!")
                st.stop()

            status = st.status("Inicjalizacja potoku...", expanded=True)
            progress = status.empty()
            
            try:
                transcriber = VideoTranscriber(model_size=model_size)
                def update_progress(msg): status.write(f"🔄 {msg}")
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
            if not uploaded_file:
                st.error("Wybierz plik!")
                st.stop()
            status = st.status("Przetwarzanie pliku lokalnego...", expanded=True)
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
                transcript_data = transcriber._run_transcription_isolated(str(save_path))
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

# ==============================================================================
# PAGE 2: REFINERY (Transform & Load)
# ==============================================================================
elif selected_page == "🏭 Przetwarzanie (Refinery)":
    st.header("2. Rafineria Wiedzy")
    
    if not inbox_files:
        st.info("Inbox jest pusty. Przejdź do zakładki Pobieranie, aby dodać materiały.")
    else:
        # [UX] Batch Processing
        if st.button("🚀 Przetwórz całą kolejkę automatycznie", type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Initialize gardener once for the whole batch
            batch_gardener = ObsidianGardener()
            
            for i, file_path in enumerate(inbox_files):
                status_text.text(f"Przetwarzanie: {file_path.name}...")
                try:
                    process_single_file(file_path, style="Summary", gardener_instance=batch_gardener)
                except Exception as e:
                    st.error(f"Błąd przy {file_path.name}: {e}")
                
                progress_bar.progress((i + 1) / len(inbox_files))
            
            st.success("Kolejka przetworzona!")
            st.balloons()
            time.sleep(2)
            st.rerun()
            
        st.divider()

        # Single Selection Logic
        file_options = {f.name: f for f in inbox_files}
        
        col_sel, col_act = st.columns([3, 1])
        with col_sel:
            selected_file_name = st.selectbox(
                "Wybierz element z Inbox:", 
                options=list(file_options.keys()),
                format_func=lambda x: f"📄 {x}"
            )
        
        selected_path = file_options[selected_file_name]
        summary = get_file_summary(selected_path)
        data = summary['data']

        with col_act:
            st.write("") 
            st.write("") 
            if st.button("🗑️ Usuń plik", type="secondary", use_container_width=True):
                try:
                    selected_path.unlink()
                    st.toast(f"Usunięto plik: {selected_path.name}")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Nie udało się usunąć: {e}")

        if data:
            st.divider()
            c1, c2 = st.columns([1, 1])
            with c1:
                st.subheader(summary['title'])
                st.caption(f"Przetworzono: {summary['date']}")
                st.text_area("Surowy Transkrypt (Podgląd)", data.get('content', '')[:1000]+"...", height=400, disabled=True)
            
            with c2:
                st.markdown("### Konfiguracja AI")
                prompt_style = st.selectbox("Styl Notatki", ["Akademicki", "Blog Post", "Wypunktowanie", "Podsumowanie"])
                
                if st.button("🧠 Generuj Notatkę Obsidian", type="primary", use_container_width=True):
                    with st.spinner("Ładowanie LLM i Generowanie..."):
                        try:
                            saved_path = process_single_file(selected_path, style=prompt_style)
                            st.success(f"Utworzono notatkę: `{saved_path.name}`")
                            st.balloons()
                            time.sleep(2)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Błąd Rafinerii: {e}")
                            logger.error(f"Refinery Error: {e}")

# ==============================================================================
# PAGE 3: RAG (Knowledge Base Chat)
# ==============================================================================
elif selected_page == "🔎 Baza Wiedzy (RAG)":
    st.header("🔎 Czat z Bazą Wiedzy (RAG)")
    
    if "rag_engine" not in st.session_state:
        try:
            from rag_engine import ObsidianRAG
            with st.spinner("Ładowanie silnika wektorowego (ChromaDB)..."):
                st.session_state.rag_engine = ObsidianRAG()
                st.toast("Silnik RAG załadowany pomyślnie.")
        except Exception as e:
            st.error(f"Nie udało się załadować RAG: {e}")
            st.stop()

    rag = st.session_state.rag_engine

    col_idx, col_clear = st.columns([3, 1])
    with col_idx:
        with st.expander("⚙️ Zarządzanie Indeksem"):
            st.caption("Uruchom, gdy dodasz nowe notatki do Obsidiana.")
            if st.button("🔄 Przeindeksuj Skarbiec (Incremental)"):
                with st.spinner("Aktualizacja wektorów..."):
                    added = rag.index_vault(ProjectConfig.OBSIDIAN_VAULT)
                    st.success(f"Zindeksowano nowych fragmentów: {added}")
    
    with col_clear:
        st.write("") 
        if st.button("🧹 Wyczyść Czat", type="secondary"):
            st.session_state.messages = []
            st.rerun()

    st.divider()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("O co chcesz zapytać swojego Drugiego Mózgu?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            try:
                # [UX] Unpacking stream and sources
                stream, sources = rag.query(
                    question=prompt, 
                    history=st.session_state.messages[:-1],
                    n_results=5,
                    stream=True
                )
                
                # Display Sources with Obsidian URI
                if sources:
                    st.markdown("### 📚 Źródła:")
                    source_links = []
                    for src in sources:
                        # Assuming 'Obsidian Vault' is the vault name from config or general
                        # Ideally we read the folder name from ProjectConfig.OBSIDIAN_VAULT.name
                        vault_name = ProjectConfig.OBSIDIAN_VAULT.name or "Obsidian Vault"
                        link = f"obsidian://open?vault={vault_name}&file={src.replace(' ', '%20')}"
                        source_links.append(f"[{src}]({link})")
                    
                    st.markdown(" | ".join(source_links))
                    st.divider()

                for chunk in stream:
                    content = chunk.get('message', {}).get('content', '')
                    full_response += content
                    message_placeholder.markdown(full_response + "▌")
                
                message_placeholder.markdown(full_response)
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
            except Exception as e:
                st.error(f"Błąd generowania: {e}")

# ==============================================================================
# PAGE 4 & 5
# ==============================================================================
elif selected_page == "📰 Research & News":
    st.header("📰 Agent Newsowy i Research")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Daily Cybersec Briefing")
        st.caption("Pobiera newsy z zdefiniowanych kanałów RSS.")
        if st.button("Uruchom NewsAgenta"):
            from news_agent import NewsAgent
            agent = NewsAgent()
            with st.status("Analiza RSS...", expanded=True) as status:
                count = agent.run(limit=3) 
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
                    if success: st.success("Notatka badawcza utworzona w folderze Research!")
                    else: st.error("Błąd pobierania.")

elif selected_page == "⚙️ System":
    st.header("⚙️ Konfiguracja Systemu")
    st.json(ProjectConfig.model_dump())