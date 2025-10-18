# Cell 1: Setup and Configuration
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any
import hashlib
import psutil
import gc
from prefect import task
import logging

# Add this at the top with other imports
logger = logging.getLogger(__name__)

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from qdrant_client import QdrantClient, models
from qdrant_client.models import Distance, VectorParams, PointStruct
from fastembed import TextEmbedding

# Configuration
CHUNKED_DATA_DIR = PROJECT_ROOT / "data" / "chunked_data"
QDRANT_URL = "https://5ef7d200-3b5c-4874-8f95-e621d3d5d429.eu-central-1-0.aws.cloud.qdrant.io"
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = "survival_strategies"
EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"
EMBEDDING_DIMENSION = 768

logger.info("🎯 Configuration loaded for EMBEDDING-->UPSERTION")

# Initialize Clients
@task(name="initialize_clients", retries=2, retry_delay_seconds=5)
def initialize_clients():
    """Initialize Qdrant client and embedding model"""
    # Initialize Qdrant Cloud client
    qdrant_client = QdrantClient(
        url=QDRANT_URL,
        api_key=QDRANT_API_KEY,
        timeout=60
    )
    
    # Initialize FastEmbed model
    embedding_model = TextEmbedding(model_name=EMBEDDING_MODEL)
    
    logger.info("✅ Clients initialized successfully")
    return qdrant_client, embedding_model


# Setup Collection (Following the example pattern)
@task(name="setup_collection", retries=2, retry_delay_seconds=5)
def setup_collection():
    """Setup Qdrant collection following the example pattern"""
    # Delete existing collection if needed (good for testing)
    try:
        qdrant_client.delete_collection(collection_name=COLLECTION_NAME)
        logger.info(f"🗑️ Deleted existing collection: {COLLECTION_NAME}")
    except Exception:
       logger.info(f"📚 No existing collection to delete: {COLLECTION_NAME}")
    
    # Create new collection
    qdrant_client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=EMBEDDING_DIMENSION,
            distance=Distance.COSINE
        )
    )
    logger.info(f"📖 Created new collection: {COLLECTION_NAME} (dimension: {EMBEDDING_DIMENSION})")
      
    logger.info("✅ Collection setup completed with indexes")


# Generate Points for Upsert (Adapted from example)
def generate_points_with_embeddings(chunks: List[Dict[str, Any]]) -> List[PointStruct]:
    """Generate points with embeddings for Qdrant upsert"""
    points = []
    
    # Extract texts for batch embedding
    texts = [chunk["text"] for chunk in chunks]
    
    logger.info(f"🔢 Generating embeddings for {len(texts)} chunks...")
    
    # Generate embeddings in batch (much faster)
    embeddings = list(embedding_model.embed(texts))
    
    logger.info(f"✅ Generated {len(embeddings)} embeddings")
    
    # Create points (similar to example but with our chunk structure)
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        # Create unique ID using hash of content (similar to example's incremental ID)
        content_str = f"{chunk['video_title']}{chunk['chapter_title']}{chunk['start_time']}{chunk['text']}"
        point_id = int(hashlib.sha256(content_str.encode()).hexdigest()[:16], 16)
        
        point = PointStruct(
            id=point_id,
            vector=embedding.tolist(),  # Convert numpy array to list
            payload={
                "video_title": chunk["video_title"],
                "chapter_title": chunk["chapter_title"], 
                "start_time": chunk["start_time"],
                "text": chunk["text"]
            }
        )
        points.append(point)
    
    return points

def print_memory_usage():
    process = psutil.Process()
    memory_mb = process.memory_info().rss / 1024 / 1024
    logger.info(f"🧠 Memory usage: {memory_mb:.1f} MB")


def load_chunks_from_file(file_path: Path) -> List[Dict[str, Any]]:
    """Load chunks from a single JSON file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
        logger.info(f"   📄 Loaded {len(chunks)} chunks from {file_path.name}")
        return chunks
    except Exception as e:
        logger.error(f"   ❌ Error loading {file_path}: {e}")
        return []


@task(name="process_all_files")
def process_all_files():
    """Process one chunk file at a time to minimize memory usage"""
    chunk_files = list(CHUNKED_DATA_DIR.glob("*.json"))
    
    if not chunk_files:
        logger.error("❌ No chunk files found")
        return 0, []  # Return tuple with empty list
    
    logger.info(f"📁 Found {len(chunk_files)} chunk files to process")
    total_upserted = 0
    processed_files = [] 
    
    for file_index, file_path in enumerate(chunk_files, 1):
        logger.info(f"\n📄 [{file_index}/{len(chunk_files)}] Processing {file_path.name}...")
        print_memory_usage()
        
        try:
            # Load only one file's chunks
            chunks = load_chunks_from_file(file_path)
            if not chunks:
                logger.info(f"⏭️ No chunks in {file_path.name}, skipping")
                continue
            
            logger.info(f"   📊 {len(chunks)} chunks loaded from file")
            
            # Process this file's chunks in small batches
            file_upserted = upsert_all_chunks_in_batches(chunks, batch_size=10)
            total_upserted += file_upserted
            
            # Track successfully processed files
            if file_upserted > 0:
                processed_files.append(file_path)
                logger.info(f"✅ {file_path.name}: {file_upserted}/{len(chunks)} chunks upserted")
            else:
                logger.info(f"⚠️ {file_path.name}: No chunks upserted")
            
        except Exception as e:
            logger.error(f"❌ Error processing {file_path.name}: {e}")
            continue  # Continue with next file even if one fails
        
        finally:
            # Always clean up memory
            if 'chunks' in locals():
                del chunks
            gc.collect()
            print_memory_usage()
    
    logger.info(f"\n🎉 Sequential processing completed!")
    logger.info(f"📊 Total chunks upserted: {total_upserted}")
    return total_upserted, processed_files 


@task(name="upsert_all_chunks_in_batches", retries=2, retry_delay_seconds=5)
def upsert_all_chunks_in_batches(chunks: List[Dict[str, Any]], batch_size: int = 10):
    """Upsert chunks in small batches with memory management"""
    total_upserted = 0
    total_batches = (len(chunks) + batch_size - 1) // batch_size
    
    for i in range(0, len(chunks), batch_size):
        batch_chunks = chunks[i:i + batch_size]
        batch_number = (i // batch_size) + 1
        
        logger.info(f"   🔄 Batch {batch_number}/{total_batches} ({len(batch_chunks)} chunks)...")
        
        try:
            # Generate points with embeddings for this batch
            points = generate_points_with_embeddings(batch_chunks)
            
            # Upsert to Qdrant
            operation_info = qdrant_client.upsert(
                collection_name=COLLECTION_NAME,
                wait=True,
                points=points
            )
            
            if operation_info.status == models.UpdateStatus.COMPLETED:
                total_upserted += len(points)
                logger.info(f"   ✅ Batch {batch_number} upserted successfully")
            else:
                logger.warning(f"   ⚠️ Batch {batch_number} upsert status: {operation_info.status}")
                
        except Exception as e:
            logger.error(f"   ❌ Batch {batch_number} failed: {e}")
        
        finally:
            # Clean up batch memory
            if 'points' in locals():
                del points
            gc.collect()
    
    return total_upserted


def delete_processed_files(file_paths: List[Path]) -> None:
    """Delete files that were successfully processed."""
    for file_path in file_paths:
        try:
            file_path.unlink()
            logger.info(f"🗑️ Deleted processed file: {file_path.name}")
        except OSError as e:
            logger.error(f"❌ Error deleting {file_path}: {e}")


@task(name="run_chunk_embedding_upserting")
def run_chunk_embedding_upserting():
    """Main execution function for embedding and upserting chunks"""
    logger.info("🎯 Starting Survival Strategies Chunk Embedding & Upsert Process")
    
    # Validate environment
    if not QDRANT_API_KEY:
        logger.error("❌ QDRANT_API_KEY environment variable not set")
        return False
    
    if not CHUNKED_DATA_DIR.exists():
        logger.error(f"❌ Chunked data directory not found: {CHUNKED_DATA_DIR}")
        return False
    
    # Initialize using your exact functions
    global qdrant_client, embedding_model
    qdrant_client, embedding_model = initialize_clients()
    setup_collection()

    # Process files using your exact function
    total_upserted, processed_files = process_all_files()
    
    # Clean up processed files
    if processed_files:
        logger.info(f"\n🧹 Cleaning up {len(processed_files)} processed files...")
        # delete_processed_files(processed_files)
   
    # Report results
    if total_upserted > 0:
        logger.info(f"\n🎉 SUCCESS: {total_upserted} chunks upserted to Qdrant Cloud")
        logger.info(f"📊 Collection: {COLLECTION_NAME}")
        return True
    else:
        logger.error("\n❌ FAILED: No chunks were processed")
        return False


if __name__ == "__main__":
    run_chunk_embedding_upserting()