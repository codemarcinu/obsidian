import sys
import os
import logging
from pathlib import Path
import time

# Add project root to path so we can import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(message)s')
logger = logging.getLogger("IntegrationTest")

def run_tests():
    print("🚀 ROZPOCZYNAM TEST INTEGRACYJNY ARCHITEKTURY\n")

    # 1. TEST CONFIG
    print("[1/5] Weryfikacja Konfiguracji (Pydantic)... ", end="", flush=True)
    try:
        from config import ProjectConfig
        if not ProjectConfig.OBSIDIAN_VAULT.exists():
            print("FAIL")
            print(f"   ❌ Vault path does not exist: {ProjectConfig.OBSIDIAN_VAULT}")
            return
        print("✅ PASS")
        print(f"   📂 Vault: {ProjectConfig.OBSIDIAN_VAULT}")
        print(f"   🤖 Model: {ProjectConfig.OLLAMA_MODEL}")
    except Exception as e:
        print("FAIL")
        print(f"   ❌ Error: {e}")
        return

    # 2. TEST RAG ENGINE
    print("\n[2/5] Inicjalizacja RAG Engine (ChromaDB)... ", end="", flush=True)
    try:
        from rag_engine import ObsidianRAG
        start = time.time()
        rag = ObsidianRAG()
        # Wykonaj proste zapytanie o metadane (nie obciąża LLM)
        meta = rag._get_indexed_metadata()
        elapsed = time.time() - start
        print("✅ PASS")
        print(f"   ⏱️ Czas inicjalizacji: {elapsed:.2f}s")
        print(f"   📚 Zindeksowane pliki: {len(meta)}")
    except Exception as e:
        print("FAIL")
        print(f"   ❌ Error: {e}")

    # 3. TEST RESEARCHER
    print("\n[3/5] Inicjalizacja WebResearcher... ", end="", flush=True)
    try:
        from ai_research import WebResearcher
        res = WebResearcher()
        print("✅ PASS")
    except Exception as e:
        print("FAIL")
        print(f"   ❌ Error: {e}")

    # 4. TEST TRANSCRIBER (GPU/VRAM CHECK)
    print("\n[4/5] Ładowanie Modeli Whisper (Simulation)... ", end="", flush=True)
    try:
        from video_transcriber import VideoTranscriber
        import torch
        
        if torch.cuda.is_available():
            vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
            print(f"\n   🖥️ GPU Wykryte: {torch.cuda.get_device_name(0)} ({vram:.2f} GB VRAM)")
        else:
            print("\n   ⚠️ GPU Niewykryte - Test CPU.")

        # Używamy 'tiny', żeby nie blokować testu na długie ładowanie 'medium'
        # Ale weryfikujemy, czy architektura Singletona działa
        start = time.time()
        vt = VideoTranscriber(model_size="tiny") 
        elapsed = time.time() - start
        print(f"✅ PASS")
        print(f"   ⏱️ Czas ładowania modelu: {elapsed:.2f}s")
    except Exception as e:
        print("FAIL")
        print(f"   ❌ Error: {e}")

    # 5. TEST TRANSCRIPT PROCESSOR
    print("\n[5/5] Inicjalizacja TranscriptProcessor... ", end="", flush=True)
    try:
        from ai_notes import TranscriptProcessor
        tp = TranscriptProcessor()
        print("✅ PASS")
    except Exception as e:
        print("FAIL")
        print(f"   ❌ Error: {e}")

    print("\n🏁 TEST ZAKOŃCZONY. System gotowy do uruchomienia przez Streamlit.")

if __name__ == "__main__":
    run_tests()
