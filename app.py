import streamlit as st
import os
import subprocess
import shutil
import feedparser
from rag_engine import ObsidianRAG
from video_transcriber import VideoTranscriber

# --- KONFIGURACJA ---
# Domyślne ścieżki (można nadpisać w UI)
DEFAULT_INPUT_DIR = "/mnt/d/transkrypcje"
DEFAULT_VAULT_PATH = "/mnt/c/Users/marci/Documents/Obsidian Vault/Education"

# Fallback jeśli dysk D: nie istnieje (np. inne środowisko)
if not os.path.exists(DEFAULT_INPUT_DIR):
    DEFAULT_INPUT_DIR = os.path.join(os.getcwd(), "downloads")
    os.makedirs(DEFAULT_INPUT_DIR, exist_ok=True)

RSS_FEEDS = {
    "Sekurak": "https://feeds.feedburner.com/sekurak",
    "Niebezpiecznik": "https://feeds.feedburner.com/niebezpiecznik",
    "Zaufana Trzecia Strona": "https://zaufanatrzeciastrona.pl/feed/",
    "ZTS - Weekendowa Lektura": "https://zaufanatrzeciastrona.pl/tag/weekendowa-lektura/feed/"
}

# --- INIT ---
st.set_page_config(page_title="Obsidian AI Bridge", layout="wide", page_icon="🧠")

# Inicjalizacja Session State
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- SIDEBAR: NAWIGACJA ---
with st.sidebar:
    st.title("🧠 Drugi Mózg")
    st.markdown("---")
    
    mode = st.radio(
        "Wybierz tryb pracy:",
        [
            "📥 Import: Wideo & Audio",
            "🌍 Import: Web & News",
            "📄 Import: Dokumenty PDF",
            "🏭 Przetwarzanie (Inbox)",
            "🔎 Eksploracja (RAG Chat)"
        ]
    )
    
    st.markdown("---")
    st.markdown("### ⚙️ Ustawienia Globalne")
    
    # Globalne ustawienia dostępne zawsze pod ręką
    vault_path = st.text_input("Ścieżka do Obsidiana:", value=DEFAULT_VAULT_PATH)
    input_dir = st.text_input("Folder Roboczy (Inbox):", value=DEFAULT_INPUT_DIR)
    
    selected_model = st.selectbox(
        "Model AI (Ollama):",
        ["bielik", "llama3.2", "deepseek-r1"],
        index=0
    )

# --- FUNKCJE POMOCNICZE ---

def run_ai_notes(file_path):
    """Uruchamia generator notatek dla podanego pliku."""
    try:
        cmd = ["./venv/bin/python", "ai_notes.py", file_path, "--output", vault_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

# --- GŁÓWNA LOGIKA APLIKACJI ---

# 1. IMPORT WIDEO
if mode == "📥 Import: Wideo & Audio":
    st.header("🎥 Pobieranie i Transkrypcja")
    st.markdown("Pobierz materiał z YouTube, dokonaj transkrypcji i (opcjonalnie) od razu utwórz notatkę.")

    col1, col2 = st.columns([2, 1])
    with col1:
        video_url = st.text_input("YouTube URL:")
        local_file = st.text_input("Lub ścieżka do pliku lokalnego:")
    with col2:
        whisper_model = st.selectbox("Dokładność (Whisper)", ["base", "small", "medium", "large-v3"], index=2)
    
    st.markdown("#### Opcje Pipeline'u")
    c1, c2, c3 = st.columns(3)
    with c1:
        do_transcribe = st.checkbox("1. Transkrybuj (Whisper)", value=True)
    with c2:
        do_summarize = st.checkbox("2. Szybkie Podsumowanie", value=True)
    with c3:
        do_obsidian = st.checkbox("3. Auto-Notatka Obsidian", value=False, help="Od razu uruchamia generator notatek po transkrypcji.")

    if st.button("🚀 Uruchom Proces", type="primary"):
        if not video_url and not local_file:
            st.error("Podaj źródło (URL lub plik)!")
        else:
            # Kontener statusu
            status_container = st.container()
            progress_bar = status_container.progress(0)
            status_text = status_container.empty()
            
            def update_progress(percent, stage, details=None):
                progress_bar.progress(int(percent))
                status_text.text(f"{stage.upper()}: {percent:.1f}% {details or ''}")
            
            transcriber = VideoTranscriber(log_callback=lambda x: None, progress_callback=update_progress)
            
            try:
                # KROK 1: POBIERANIE
                if video_url:
                    status_text.text("Pobieranie wideo...")
                    target_file = transcriber.download_video(video_url, save_path=input_dir)
                else:
                    target_file = local_file
                
                status_text.text(f"Gotowy do pracy: {os.path.basename(target_file)}")
                
                # KROK 2: TRANSKRYPCJA
                txt_path = None
                if do_transcribe:
                    segments, info = transcriber.transcribe_video(target_file, language="pl", model_size=whisper_model) # Hardcoded PL for simplicity, or add selector back
                    txt_path, full_text = transcriber.save_transcription(segments, info, os.path.splitext(target_file)[0])
                    st.success(f"Transkrypcja gotowa: `{os.path.basename(txt_path)}`")

                    # KROK 3: PODSUMOWANIE (TXT)
                    if do_summarize and full_text:
                        status_text.text("Generowanie podsumowania...")
                        summary = transcriber.summarize_text(full_text)
                        if summary:
                            sum_path = os.path.splitext(target_file)[0] + "_podsumowanie.txt"
                            with open(sum_path, "w", encoding="utf-8") as f:
                                f.write(summary)
                            st.info("Podsumowanie zapisane.")

                    # KROK 4: OBSIDIAN (AUTO)
                    if do_obsidian and txt_path:
                        status_text.text("Generowanie notatki Obsidian...")
                        success, out, err = run_ai_notes(txt_path)
                        if success:
                            st.balloons()
                            st.success("✅ Notatka utworzona w Obsidianie!")
                            with st.expander("Szczegóły notatki"):
                                st.text(out)
                        else:
                            st.error("Błąd generowania notatki.")
                            st.text(err)
                
                status_text.text("Proces zakończony.")
                progress_bar.progress(100)

            except Exception as e:
                st.error(f"Wystąpił błąd: {e}")

# 2. IMPORT WEB & NEWS
elif mode == "🌍 Import: Web & News":
    st.header("🌍 Internet Research & News")
    
    tab_news1, tab_news2 = st.tabs(["Pojedynczy Artykuł", "Centrum RSS"])
    
    with tab_news1:
        url = st.text_input("Wklej adres URL artykułu do analizy:")
        if st.button("Analizuj i Notuj"):
            if url:
                with st.spinner(f"Agent czyta: {url}..."):
                    try:
                        cmd = ["./venv/bin/python", "ai_research.py", url]
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        if result.returncode == 0:
                            st.success("Notatka dodana do Obsidiana!")
                            st.expander("Logi").text(result.stdout)
                        else:
                            st.error("Błąd.")
                            st.text(result.stderr)
                    except Exception as e:
                        st.error(str(e))

    with tab_news2:
        st.info("Agent RSS automatycznie pobiera nowości, filtruje je i tworzy prasówkę.")
        if st.button("Uruchom Agenta Newsowego"):
            with st.status("Przeglądam internet...", expanded=True):
                cmd = ["./venv/bin/python", "news_agent.py"]
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                stdout, stderr = process.communicate()
                st.write(stdout)
                if stderr:
                    st.error(stderr)
            st.success("Gotowe.")

# 3. IMPORT PDF
elif mode == "📄 Import: Dokumenty PDF":
    st.header("📄 Przetwarzanie Dokumentów PDF")
    uploaded_file = st.file_uploader("Wrzuć plik PDF", type="pdf")
    
    if uploaded_file and st.button("Analizuj PDF"):
        with st.spinner("Przetwarzanie..."):
            temp_path = os.path.join("/tmp", uploaded_file.name)
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            try:
                # PDF Shredder logic
                cmd = ["./venv/bin/python", "pdf_shredder.py", temp_path]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    st.success("Treść wyciągnięta i przeanalizowana!")
                    st.text(result.stdout)
                else:
                    st.error("Błąd PDF Shreddera.")
                    st.text(result.stderr)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

# 4. PRZETWARZANIE (INBOX)
elif mode == "🏭 Przetwarzanie (Inbox)":
    st.header("🏭 Fabryka Wiedzy")
    st.markdown(f"Pliki oczekujące w: `{input_dir}`")
    
    if not os.path.exists(input_dir):
        st.warning("Folder Inbox nie istnieje.")
    else:
        # Filtrujemy tylko txt, które nie są systemowe
        files = [f for f in os.listdir(input_dir) if f.endswith('.txt') and "_podsumowanie" not in f and "processed" not in f]
        
        if not files:
            st.info("Skrzynka odbiorcza jest pusta. Dobra robota! 🎉")
        else:
            st.write(f"Oczekujące transkrypcje: {len(files)}")
            
            for f in files:
                with st.expander(f"📄 {f}", expanded=False):
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        st.caption("Podgląd (pierwsze 500 znaków):")
                        try:
                            with open(os.path.join(input_dir, f), 'r', encoding='utf-8') as file_obj:
                                content = file_obj.read(500)
                                st.text(content + "...")
                        except:
                            st.text("Nie można odczytać podglądu.")
                    
                    with col_b:
                        if st.button(f"Generuj Notatkę", key=f"gen_{f}"):
                            with st.spinner("Przetwarzanie..."):
                                full_path = os.path.join(input_dir, f)
                                success, out, err = run_ai_notes(full_path)
                                if success:
                                    st.success("Gotowe!")
                                    # Opcjonalnie: przenieś do processed
                                    processed_dir = os.path.join(input_dir, "processed")
                                    os.makedirs(processed_dir, exist_ok=True)
                                    shutil.move(full_path, os.path.join(processed_dir, f))
                                    st.rerun()
                                else:
                                    st.error(err)

# 5. EKSPLORACJA (RAG)
elif mode == "🔎 Eksploracja (RAG Chat)":
    st.header("🔎 Rozmowa z Bazą Wiedzy")
    
    c1, c2 = st.columns([3, 1])
    with c2:
        if st.button("🔄 Przeindeksuj Vault"):
            with st.spinner("Indeksowanie..."):
                rag = ObsidianRAG()
                c = rag.index_vault(vault_path)
                st.success(f"Zaktualizowano: {c} fragmentów.")
    
    # Chat UI
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
    if prompt := st.chat_input("Zadaj pytanie swoim notatkom..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
            
        with st.chat_message("assistant"):
            rag = ObsidianRAG()
            response_placeholder = st.empty()
            full_response = ""
            
            # Prosty streaming (bez obsługi <think> dla uproszczenia kodu, można dodać)
            for chunk in rag.query(prompt, history=st.session_state.messages[:-1], model_name=selected_model, stream=True):
                 # Usuwanie tagów myślenia jeśli się pojawią (dla estetyki)
                clean_chunk = chunk.replace("<think>", "**Myślę:**\n").replace("</think>", "\n---\n")
                full_response += clean_chunk
                response_placeholder.markdown(full_response + "▌")
            
            response_placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})

st.sidebar.markdown("---")
st.sidebar.caption("v2.0 • Unified Knowledge System")