import os
import chromadb
import ollama
from typing import List, Dict
import hashlib
from tqdm import tqdm
import glob

# Konfiguracja domyślna
DEFAULT_DB_PATH = os.path.join(os.getcwd(), "obsidian_db")
EMBEDDING_MODEL = "mxbai-embed-large"  # Używamy modelu, który już masz
CHAT_MODEL = "bielik"                 # Twój główny model do rozmowy

class ObsidianRAG:
    def __init__(self, db_path=DEFAULT_DB_PATH):
        """Inicjalizacja klienta bazy wektorowej."""
        self.client = chromadb.PersistentClient(path=db_path)
        # Tworzymy kolekcję lub pobieramy istniejącą
        self.collection = self.client.get_or_create_collection(name="obsidian_notes")

    def get_embeddings(self, text_list: List[str]) -> List[List[float]]:
        """Generuje embeddingi przy użyciu Ollama."""
        embeddings = []
        for text in text_list:
            try:
                response = ollama.embeddings(model=EMBEDDING_MODEL, prompt=text)
                embeddings.append(response["embedding"])
            except Exception as e:
                print(f"[!] Błąd generowania embeddingu: {e}")
                # W przypadku błędu (np. brak modelu) zwracamy pustą listę lub rzucamy błąd
                # Tutaj dla bezpieczeństwa rzucę błąd, by użytkownik wiedział, że coś jest nie tak
                raise e
        return embeddings

    def index_vault(self, vault_path: str, chunk_size=1000, overlap=100):
        """Indeksuje cały vault Obsidianu."""
        print(f"[*] Rozpoczynam indeksowanie: {vault_path}")
        
        # Znajdź wszystkie pliki .md
        files = glob.glob(os.path.join(vault_path, "**/*.md"), recursive=True)
        print(f"[*] Znaleziono {len(files)} plików markdown.")

        count = 0
        for file_path in tqdm(files, desc="Indeksowanie plików"):
            # Pomiń pliki systemowe/ukryte
            if "/." in file_path:
                continue
                
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            
            if not content.strip():
                continue

            # Podział na chunki
            chunks = self._chunk_text(content, chunk_size, overlap)
            
            # Przygotowanie danych do ChromaDB
            ids = []
            documents = []
            metadatas = []
            
            for i, chunk in enumerate(chunks):
                # Unikalne ID dla chunka
                chunk_id = hashlib.md5(f"{file_path}_{i}".encode()).hexdigest()
                
                ids.append(chunk_id)
                documents.append(chunk)
                metadatas.append({
                    "source": file_path,
                    "filename": os.path.basename(file_path),
                    "chunk_index": i
                })

            # Dodawanie do bazy (batchami - tutaj uproszczone per plik)
            if documents:
                try:
                    embeddings = self.get_embeddings(documents)
                    self.collection.upsert(
                        ids=ids,
                        embeddings=embeddings,
                        documents=documents,
                        metadatas=metadatas
                    )
                    count += len(documents)
                except Exception as e:
                    print(f"[!] Błąd indeksowania pliku {file_path}: {e}")

        print(f"[SUCCESS] Zindeksowano {count} fragmentów.")
        return count

    def query(self, question: str, history: List[Dict[str, str]] = None, n_results=5, model_name=CHAT_MODEL, stream=False):
        """Zadaje pytanie do bazy wiedzy z opcjonalnym strumieniowaniem."""
        if history is None:
            history = []

        # 1. Wygeneruj embedding pytania
        try:
            query_embedding = ollama.embeddings(model=EMBEDDING_MODEL, prompt=question)["embedding"]
        except Exception as e:
            error_msg = f"Błąd modelu embeddingów ({EMBEDDING_MODEL}). Czy jest zainstalowany? ({e})"
            if stream: yield error_msg
            return error_msg

        # 2. Przeszukaj bazę
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )

        context_text = ""
        unique_sources = []
        
        if results['documents'][0]:
            context_text = "\n\n---\n\n".join(results['documents'][0])
            sources = [meta['filename'] for meta in results['metadatas'][0]]
            unique_sources = list(set(sources))
        else:
            context_text = "Brak bezpośrednich informacji w notatkach na ten temat."

        # 3. Zapytaj LLM
        system_prompt = f"""
Jesteś asystentem, który odpowiada na pytania na podstawie podanych notatek użytkownika.
Twoja wiedza pochodzi TYLKO z poniższego kontekstu. Jeśli nie znasz odpowiedzi na podstawie kontekstu, powiedz to.
Nie wymyślaj faktów.

KONTEKST Z NOTATEK:
{context_text}
"""
        messages = [{'role': 'system', 'content': system_prompt}]
        for msg in history:
            if msg['role'] in ['user', 'assistant']:
                messages.append(msg)
        messages.append({'role': 'user', 'content': question})

        try:
            if stream:
                # Tryb strumieniowy
                response_stream = ollama.chat(model=model_name, messages=messages, stream=True)
                for chunk in response_stream:
                    yield chunk['message']['content']
                
                # Na końcu strumienia możemy dodać źródła
                if unique_sources:
                    yield "\n\n**Źródła:**\n" + "\n".join([f"- `{s}`" for s in unique_sources])
            else:
                # Tryb standardowy
                response = ollama.chat(model=model_name, messages=messages)
                answer = response['message']['content']
                if unique_sources:
                    answer += "\n\n**Źródła:**\n" + "\n".join([f"- `{s}`" for s in unique_sources])
                return answer

        except Exception as e:
            error_msg = f"Błąd generowania odpowiedzi: {e}"
            if stream: yield error_msg
            return error_msg

    def _chunk_text(self, text, chunk_size, overlap):
        """Prosta funkcja dzieląca tekst na kawałki."""
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start += chunk_size - overlap
            
        return chunks

if __name__ == "__main__":
    # Test manualny
    rag = ObsidianRAG()
    # rag.index_vault("/ścieżka/do/testu")
    # print(rag.query("O czym jest ten projekt?"))
    print("Moduł RAG gotowy. Zaimportuj go w app.py.")
