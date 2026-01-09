import os
import glob
import hashlib
import logging
import time
from typing import List, Dict, Generator, Set
from pathlib import Path

import chromadb
from chromadb.config import Settings
import ollama
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import ProjectConfig, logger

class ObsidianRAG:
    """
    Advanced RAG Engine with Smart Indexing and Incremental Updates.
    Optimized for local LLMs (Ollama) and Markdown knowledge bases.
    """

    def __init__(self, db_path: Path = None):
        self.db_path = db_path if db_path else ProjectConfig.DB_DIR
        self.embedding_model = "mxbai-embed-large"  # High-performance local embedding
        
        # Initialize Vector DB
        self.client = chromadb.PersistentClient(path=str(self.db_path))
        self.collection = self.client.get_or_create_collection(
            name="obsidian_knowledge",
            metadata={"hnsw:space": "cosine"}
        )
        
        self.logger = logging.getLogger("RAG-Engine")
        
        # Text splitter optimized for Code & Markdown
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=ProjectConfig.CHUNK_SIZE,
            chunk_overlap=ProjectConfig.CHUNK_OVERLAP,
            separators=["\n## ", "\n### ", "\n#### ", "\n", " ", ""],
            keep_separator=True
        )

    def calculate_file_hash(self, file_path: str) -> str:
        """Calculates MD5 hash of file content for change detection."""
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            buf = f.read()
            hasher.update(buf)
        return hasher.hexdigest()

    def get_indexed_hashes(self) -> Dict[str, str]:
        """Retrieves a map of {filename: hash} currently in DB."""
        # This can be slow for huge DBs, but fine for personal <100k notes
        # Optimized: Fetch only metadata
        existing_data = self.collection.get(include=['metadatas'])
        
        file_hashes = {}
        if existing_data and existing_data['metadatas']:
            for meta in existing_data['metadatas']:
                if 'filename' in meta and 'file_hash' in meta:
                    file_hashes[meta['filename']] = meta['file_hash']
        return file_hashes

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Batch generation of embeddings via Ollama."""
        embeddings = []
        for text in texts:
            # TODO: Implement batching API if Ollama supports it in future
            try:
                resp = ollama.embeddings(model=self.embedding_model, prompt=text)
                embeddings.append(resp["embedding"])
            except Exception as e:
                self.logger.error(f"Embedding failed: {e}")
                # Return zero-vector fallback or re-raise? Re-raising to avoid bad data.
                raise e
        return embeddings

    def clean_stale_records(self, current_files: Set[str]):
        """Removes vectors for files that no longer exist on disk."""
        indexed_files = set(self.get_indexed_hashes().keys())
        stale_files = indexed_files - current_files
        
        if stale_files:
            self.logger.info(f"Cleaning up {len(stale_files)} deleted files from DB...")
            for file in stale_files:
                self.collection.delete(where={"filename": file})

    def index_vault(self, vault_path: str) -> int:
        """
        Smart Incremental Indexing.
        Returns number of newly indexed chunks.
        """
        vault_path = Path(vault_path)
        if not vault_path.exists():
            self.logger.error(f"Vault not found: {vault_path}")
            return 0

        self.logger.info("Scanning vault for changes...")
        all_md_files = list(vault_path.rglob("*.md"))
        
        # Get current state of DB
        indexed_map = self.get_indexed_hashes()
        current_filenames = set()
        
        new_chunks_count = 0
        files_processed = 0

        for file_path in all_md_files:
            file_name = file_path.name
            current_filenames.add(file_name)
            
            # Skip hidden files
            if file_path.name.startswith('.'):
                continue

            try:
                current_hash = self.calculate_file_hash(str(file_path))
                
                # CHECK: Skip if hash matches DB
                if file_name in indexed_map and indexed_map[file_name] == current_hash:
                    continue
                
                # If we are here, file is new or changed.
                # First, remove old version if exists
                if file_name in indexed_map:
                    self.collection.delete(where={"filename": file_name})
                    self.logger.info(f"Updating modified file: {file_name}")
                else:
                    self.logger.info(f"Indexing new file: {file_name}")

                # Read and Split
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                chunks = self.splitter.split_text(content)
                if not chunks: 
                    continue

                # Prepare Data
                ids = []
                documents = []
                metadatas = []
                
                embeddings = self.get_embeddings(chunks)

                for i, chunk in enumerate(chunks):
                    chunk_id = f"{file_name}_{i}_{current_hash[:6]}"
                    ids.append(chunk_id)
                    documents.append(chunk)
                    metadatas.append({
                        "source": str(file_path),
                        "filename": file_name,
                        "file_hash": current_hash,
                        "chunk_index": i
                    })

                # Upsert
                self.collection.upsert(
                    ids=ids,
                    embeddings=embeddings,
                    documents=documents,
                    metadatas=metadatas
                )
                
                new_chunks_count += len(chunks)
                files_processed += 1

            except Exception as e:
                self.logger.error(f"Failed to index {file_name}: {e}")

        # Garbage Collection
        self.clean_stale_records(current_filenames)

        self.logger.info(f"Indexing complete. Processed {files_processed} files, added {new_chunks_count} chunks.")
        return new_chunks_count

    def query(self, question: str, history: List[Dict] = None, n_results=5, model_name="mistral", stream=False):
        """
        Retrieves context and queries LLM. 
        Supports streaming generator.
        """
        # 1. Embed Query
        try:
            q_embed = ollama.embeddings(model=self.embedding_model, prompt=question)["embedding"]
        except Exception as e:
            yield f"Error: Embedding model {self.embedding_model} not reachable."
            return

        # 2. Retrieve
        results = self.collection.query(
            query_embeddings=[q_embed],
            n_results=n_results
        )

        # 3. Format Context
        if not results['documents'] or not results['documents'][0]:
            context = "No relevant notes found."
            sources = []
        else:
            docs = results['documents'][0]
            metas = results['metadatas'][0]
            
            context_parts = []
            sources = set()
            
            for doc, meta in zip(docs, metas):
                context_parts.append(f"--- NOTE: {meta['filename']} ---\n{doc}")
                sources.add(meta['filename'])
            
            context = "\n".join(context_parts)

        # 4. LLM Generation
        system_prompt = f"""
        You are a Second Brain Assistant. Use the following Context from user notes to answer the Question.
        If the answer is not in the context, say so. Do not hallucinate.
        
        CONTEXT:
        {context}
        """

        messages = [{'role': 'system', 'content': system_prompt}]
        if history:
            # Filter history to keep only user/assistant turns
            valid_roles = {'user', 'assistant'}
            messages.extend([m for m in history if m.get('role') in valid_roles])
        
        messages.append({'role': 'user', 'content': question})

        try:
            stream_resp = ollama.chat(model=model_name, messages=messages, stream=True)
            
            for chunk in stream_resp:
                content = chunk['message']['content']
                if content:
                    yield content
            
            # Append sources at the end
            if sources:
                yield "\n\n**Sources:**\n" + "\n".join([f"- `{s}`" for s in sources])

        except Exception as e:
            yield f"\n[System Error]: {e}"

if __name__ == "__main__":
    # Smoke Test
    print("Testing RAG Engine...")
    rag = ObsidianRAG()
    # rag.index_vault(ProjectConfig.OBSIDIAN_VAULT)
    print("RAG initialized.")