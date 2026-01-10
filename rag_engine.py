import hashlib
import logging
import time
from typing import List, Dict, Set, Optional, Any
from pathlib import Path

import chromadb
import ollama
from langchain_text_splitters import RecursiveCharacterTextSplitter
from tqdm import tqdm

from config import ProjectConfig, logger

class ObsidianRAG:
    """
    RAG Engine 2.0: Optimized for Incremental Indexing and local LLMs.
    Features: MD5 change detection, Recursive splitting, and metadata enrichment.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path if db_path else ProjectConfig.CHROMA_DB_DIR
        self.embedding_model = ProjectConfig.EMBEDDING_MODEL
        
        # Initialize Vector DB
        self.client = chromadb.PersistentClient(path=str(self.db_path))
        self.collection = self.client.get_or_create_collection(
            name="obsidian_knowledge",
            metadata={"hnsw:space": "cosine"}
        )
        
        self.logger = logging.getLogger("RAG-Engine")
        
        # Text splitter optimized for Markdown and Code
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=ProjectConfig.RAG_CHUNK_SIZE,
            chunk_overlap=ProjectConfig.RAG_CHUNK_OVERLAP,
            separators=["\n## ", "\n### ", "\n#### ", "\n", " ", ""],
            keep_separator=True
        )

    def _get_file_hash(self, file_path: Path) -> str:
        """Generates MD5 hash for content validation."""
        return hashlib.md5(file_path.read_bytes()).hexdigest()

    def _get_indexed_metadata(self) -> Dict[str, Dict[str, str]]:
        """
        Builds a map of indexed files: {filename: {hash, mtime}}.
        Used for incremental update logic.
        """
        results = self.collection.get(include=['metadatas'])
        indexed = {}
        if results and results['metadatas']:
            for meta in results['metadatas']:
                fname = meta.get('filename')
                if fname:
                    # We only need one entry per file to check hash/mtime
                    indexed[fname] = {
                        "hash": meta.get("file_hash"),
                        "mtime": str(meta.get("mtime", ""))
                    }
        return indexed

    def _get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generates embeddings using local Ollama model."""
        embeddings = []
        for text in texts:
            try:
                resp = ollama.embeddings(model=self.embedding_model, prompt=text)
                embeddings.append(resp["embedding"])
            except Exception as e:
                self.logger.error(f"Embedding failed for text fragment: {e}", extra={"tags": "RAG-ERROR"})
                raise e
        return embeddings

    def index_vault(self, vault_path: Path) -> int:
        """
        Performs Incremental Indexing of the Obsidian Vault.
        Only processes new or modified files.
        """
        if not vault_path.exists():
            self.logger.error(f"Vault path not found: {vault_path}")
            return 0

        self.logger.info(f"Starting Incremental Indexing: {vault_path}", extra={"tags": "RAG-INDEX"})
        all_files = list(vault_path.rglob("*.md"))
        indexed_map = self._get_indexed_metadata()
        
        new_chunks = 0
        current_filenames = set()

        for file_path in tqdm(all_files, desc="Indexing Vault"):
            if file_path.name.startswith('.'): continue
            
            file_name = file_path.name
            current_filenames.add(file_name)
            
            try:
                mtime = str(file_path.stat().st_mtime)
                file_hash = self._get_file_hash(file_path)

                # Skip if already indexed and unchanged
                if file_name in indexed_map:
                    if indexed_map[file_name]["hash"] == file_hash:
                        continue
                    
                    # File changed -> Remove old vectors
                    self.collection.delete(where={"filename": file_name})
                    self.logger.info(f"Updating changed file: {file_name}")

                # Read and Chunk
                content = file_path.read_text(encoding='utf-8')
                chunks = self.splitter.split_text(content)
                if not chunks: continue

                # Batch Upsert
                ids = [f"{file_name}_{i}_{file_hash[:6]}" for i in range(len(chunks))]
                embeddings = self._get_embeddings(chunks)
                metadatas = [{
                    "filename": file_name,
                    "file_hash": file_hash,
                    "mtime": mtime,
                    "chunk_index": i,
                    "source": str(file_path)
                } for i in range(len(chunks))]

                self.collection.upsert(
                    ids=ids,
                    embeddings=embeddings,
                    documents=chunks,
                    metadatas=metadatas
                )
                new_chunks += len(chunks)

            except Exception as e:
                self.logger.error(f"Failed to process {file_name}: {e}")

        # Cleanup deleted files
        stale_files = set(indexed_map.keys()) - current_filenames
        if stale_files:
            self.logger.info(f"Removing {len(stale_files)} stale files from index.")
            for sf in stale_files:
                self.collection.delete(where={"filename": sf})

        return new_chunks

    def query(self, question: str, history: List[Dict] = None, n_results=5, model_name=None, stream=False):
        """
        Retrieves context and generates response using Ollama.
        """
        model = model_name or ProjectConfig.OLLAMA_MODEL
        
        # 1. Embed Question
        try:
            q_embed = ollama.embeddings(model=self.embedding_model, prompt=question)["embedding"]
        except Exception as e:
            yield f"Error: Embedding model {self.embedding_model} not reachable."
            return

        # 2. Retrieve Context
        results = self.collection.query(query_embeddings=[q_embed], n_results=n_results)
        
        if not results['documents'] or not results['documents'][0]:
            context = "Brak odpowiednich notatek w bazie wiedzy."
            sources = []
        else:
            docs = results['documents'][0]
            metas = results['metadatas'][0]
            context = "\n".join([f"--- DOKUMENT: {m['filename']} ---\n{d}" for d, m in zip(docs, metas)])
            sources = {m['filename'] for m in metas}

        # 3. Prompt Engineering
        system_msg = f"""
        Jesteś Asystentem Drugiego Mózgu. Odpowiadaj na pytania użytkownika, opierając się WYŁĄCZNIE na dostarczonym KONTEKŚCIE.
        Jeśli odpowiedzi nie ma w kontekście, powiedz otwarcie, że nie wiesz. Nie zmyślaj faktów.
        
        KONTEKST:
        {context}
        """

        messages = [{'role': 'system', 'content': system_msg}]
        if history:
            messages.extend([m for m in history if m.get('role') in ['user', 'assistant']])
        messages.append({'role': 'user', 'content': question})

        # 4. LLM Call
        try:
            response = ollama.chat(model=model, messages=messages, stream=stream)
            if stream:
                for chunk in response:
                    content = chunk['message']['content']
                    if content: yield content
                if sources:
                    yield "\n\n**Źródła:**\n" + "\n".join([f"- [[{s}]]" for s in sources])
            else:
                yield response['message']['content']
        except Exception as e:
            self.logger.error(f"LLM Query failed: {e}", extra={"tags": "RAG-ERROR"})
            yield f"Błąd systemowy: {e}"

if __name__ == "__main__":
    # Quick test
    rag = ObsidianRAG()
    print("RAG Engine 2.0 Ready.")
