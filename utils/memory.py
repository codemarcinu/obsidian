import torch
import gc
import logging

logger = logging.getLogger("MemoryManager")

def release_vram():
    """
    Aggressively releases VRAM by invoking garbage collection and emptying the CUDA cache.
    Crucial for swapping between large models (e.g., Whisper -> Ollama) on consumer GPUs.
    """
    if torch.cuda.is_available():
        logger.info("Releasing VRAM...", extra={"tags": "RESOURCE-MGT"})
        
        # 1. Force Python Garbage Collection
        gc.collect()
        
        # 2. Empty PyTorch CUDA Cache
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()
        
        # Optional: Print stats
        allocated = torch.cuda.memory_allocated() / 1024**3
        reserved = torch.cuda.memory_reserved() / 1024**3
        logger.info(f"VRAM after cleanup - Allocated: {allocated:.2f}GB, Reserved: {reserved:.2f}GB", 
                    extra={"tags": "RESOURCE-STATS"})
    else:
        logger.info("CUDA not available, skipping VRAM release.", extra={"tags": "RESOURCE-MGT"})
