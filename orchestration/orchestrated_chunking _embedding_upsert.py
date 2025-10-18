#!/usr/bin/env python3
"""
Orchestrated Pipeline for Transcripts chunking, embedding, and Qdrant upsert operations
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from prefect import flow

# Set up project structure for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import our task scripts
from ingestion.transcript_chunking import run_transcript_chunking, delete_processed_files
from ingestion.chunk_embedding_upserting import run_chunk_embedding_upserting

# Set up logging
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = f"chunk_embed_upsert_{timestamp}.log"
log_filepath = LOG_DIR / log_filename

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

for handler in logger.handlers[:]:
    logger.removeHandler(handler)

formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

print(f"📝 RAG Pipeline Logging initialized: {log_filepath}")
logger = logging.getLogger(__name__)

@flow(name="orchestrated-chunk-embed-upsert-pipeline")
def chunk_embed_upsert_pipeline():
    """
    Main orchestration pipeline for RAG operations
    Simply coordinates the execution of independent task scripts
    """
    logger.info("🚀 Starting Chunk->Embed->Upsert Pipeline")
    
    # Step 1: Execute chunking (script handles everything)
    logger.info("📋 Step 1: Executing transcript chunking...")
    chunking_files_count = run_transcript_chunking()
        
    if chunking_files_count == 0:
        logger.info("⏭️ No transcript chunked - stopping pipeline")
        return

    logger.info(f"✅ Chunking completed: {chunking_files_count} transcript chunked")


    # Step 2: Execute embedding and upsert (script handles everything)
    logger.info("📋 Step 2: Executing embedding and Qdrant upsert...")
    upsert_success = run_chunk_embedding_upserting()
    
    if not upsert_success:
        logger.error("💥 Embedding/upsert failed")
        return False
    
    logger.info("🎉 Chunk->Embed->Upsert Pipeline completed successfully!")
    return True

if __name__ == "__main__":
    import sys

    if "--run-now" in sys.argv:
        print("🔧 Running RAG pipeline for development and test")
        chunk_embed_upsert_pipeline()
    else:
        chunk_embed_upsert_pipeline.serve(
            name="rag-chunking-embedding-upsert-pipeline",
            cron="30 22 * * *",
            tags=["RAG", "chunking", "embedding", "qdrant", "survival-strategies"],
        )