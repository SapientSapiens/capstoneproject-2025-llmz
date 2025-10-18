#!/usr/bin/env python3
"""
Transcript Chunking Script for Survival Strategy Videos
Processes JSON transcripts and outputs chunks in single-file-per-video format
"""

import json
import re
from math import ceil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple
from prefect import task
import logging

# Add this after imports
logger = logging.getLogger(__name__)


# Configuration - Using relative paths from script location
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
RAW_INGESTED_DIR = PROJECT_ROOT / "data" / "raw_ingested_transcripts"
RAW_ASR_DIR = PROJECT_ROOT / "data" / "raw_asr_transcripts" 
CHUNKED_OUTPUT_DIR = PROJECT_ROOT / "data" / "chunked_data"

# Chunking parameters
BASE_THRESHOLD = 1000  # words
STEP_SIZE = 500        # words
OVERLAP = 200          # words
MIN_TEXT_LENGTH = 10   # minimum words to consider a chapter


def compute_parts(num_words: int, base_threshold: int = BASE_THRESHOLD, step: int = STEP_SIZE) -> int:
    """Compute number of parts according to the user's pattern."""
    if num_words <= base_threshold:
        return 1
    return ceil((num_words - base_threshold) / step) + 1


def chunk_chapter_by_words(text: str, overlap: int = OVERLAP, 
                          base_threshold: int = BASE_THRESHOLD, 
                          step: int = STEP_SIZE) -> List[Dict[str, Any]]:
    """Chunk the given text (by words) according to the user's rules."""
    # Normalize whitespace and split into words
    words = text.strip().split()
    L = len(words)
    parts = compute_parts(L, base_threshold=base_threshold, step=step)
    
    # If only one part, return the single chunk
    if parts == 1:
        return [{
            "part_index": 1,
            "start_word": 0,
            "end_word": L,
            "word_count": L,
            "text": " ".join(words)
        }]
    
    n = parts
    o = overlap
    
    # Compute chunk size s so that n*s - (n-1)*o >= L
    s = ceil((L + (n - 1) * o) / n)
    stride = s - o
    
    if stride <= 0:
        o = max(0, s - 1)
        stride = s - o
        
    chunks = []
    
    for i in range(n):
        start = i * stride
        end = start + s
        
        # Adjust bounds if they run past the end
        if end >= L:
            end = L
            start = max(0, end - s)
            
        start = max(0, start)
        if end <= start:
            end = min(L, start + s)
        
        chunk_words = words[start:end]
        chunks.append({
            "part_index": i + 1,
            "start_word": start,
            "end_word": end,
            "word_count": len(chunk_words),
            "text": " ".join(chunk_words)
        })
    
    # Fallback if we didn't get exactly n chunks
    if len(chunks) != n:
        chunks = []
        stride = max(1, (L - s) // (n - 1) if n > 1 else L)
        for i in range(n):
            start = i * stride
            end = start + s
            if i == n - 1:
                end = L
            if end > L:
                end = L
                start = max(0, end - s)
            chunk_words = words[start:end]
            chunks.append({
                "part_index": i + 1,
                "start_word": start,
                "end_word": end,
                "word_count": len(chunk_words),
                "text": " ".join(chunk_words)
            })
    
    return chunks


def clean_chapter_title(chapter_title: str, video_title: str) -> str:
    """Clean chapter title according to rules."""
    # Check for untitled chapters (like "<Untitled Chapter 1>")
    if re.match(r'^(<)?Untitled Chapter \d+(>)?$', chapter_title.strip(), re.IGNORECASE):
        return video_title
    
    # Remove leading numbers and colons/dots (e.g., "5: Battery Radio" -> "Battery Radio", "1. Don't run" -> "Don't run")
    cleaned = re.sub(r'^\d+[.:]\s*', '', chapter_title.strip())
    
    return cleaned if cleaned else video_title


def should_skip_chapter(text: str) -> bool:
    """Determine if a chapter should be skipped due to minimal content."""
    if not text or not text.strip():
        return True
    
    word_count = len(text.strip().split())
    return word_count < MIN_TEXT_LENGTH


def process_segment(segment: Dict[str, Any], video_title: str, total_segments: int) -> List[Dict[str, Any]]:
    """Process a single segment/chapter and return chunk(s)."""
    segment_title = segment.get('segment_title', '')
    text = segment.get('text', '')
    start_time = segment.get('start_time', 0)
    
    # Skip chapters with minimal text
    if should_skip_chapter(text):
        return []
    
    # If this is a single chapter video OR untitled chapter, use video title
    if total_segments == 1 or re.match(r'^(<)?Untitled Chapter \d+(>)?$', segment_title.strip(), re.IGNORECASE):
        clean_title = video_title
    else:
        clean_title = clean_chapter_title(segment_title, video_title) # Clean chapter title

    # Check if we need to chunk this segment
    chunks = chunk_chapter_by_words(text)
    
    results = []
    for chunk in chunks:
        chunk_data = {
            "video_title": video_title,
            "chapter_title": clean_title,
            "start_time": start_time,
            "text": chunk['text']
        }
        
        # If this was chunked from a long segment, modify chapter title
        if len(chunks) > 1:
            chunk_data["chapter_title"] = f"{clean_title} - Part {chunk['part_index']}"
            
        results.append(chunk_data)
    
    return results


def create_safe_filename(video_title: str) -> str:
    """Create a safe filename from video title with timestamp."""
    # Remove special characters and normalize
    safe_title = re.sub(r'[^\w\s-]', '', video_title).strip().lower()
    safe_title = re.sub(r'[-\s]+', '_', safe_title)
    
    # Add timestamp for uniqueness
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    return f"{safe_title}_{timestamp}.json"


@task(name="process_transcript_file")
def process_transcript_file(file_path: Path) -> Tuple[List[Dict[str, Any]], str]:
    """Process a single transcript JSON file and return all chunks and video title."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, KeyError, UnicodeDecodeError) as e:
        logger.error(f"Error reading {file_path}: {e}")
        return [], ""
    
    video_title = data.get('video_title', 'Unknown Video')
    segments = data.get('segments', [])
    
    all_chunks = []
    total_segments = len(segments)  # Get total segments count
    
    for segment in segments:
        chunks = process_segment(segment, video_title, total_segments)  # Pass total_segments
        all_chunks.extend(chunks)
    
    logger.info(f"Processed {file_path}: {len(all_chunks)} chunks created")
    return all_chunks, video_title


@task(name="save_video_chunks")
def save_video_chunks(chunks: List[Dict[str, Any]], video_title: str) -> Path:
    """Save all chunks for a video as a single JSON array file."""
    CHUNKED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create safe filename with timestamp
    filename = create_safe_filename(video_title)
    output_path = CHUNKED_OUTPUT_DIR / filename
    
    # Save as direct JSON array (no wrapper)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved {len(chunks)} chunks for '{video_title}' to {output_path}")
    return output_path


@task(name="get_all_transcript_files")
def get_all_transcript_files() -> List[Path]:
    """Get all JSON files from both source directories."""
    files = []
    
    for source_dir in [RAW_INGESTED_DIR, RAW_ASR_DIR]:
        if source_dir.exists():
            json_files = list(source_dir.glob("*.json"))
            files.extend(json_files)
            logger.info(f"Found {len(json_files)} files in {source_dir}")
        else:
            logger.warning(f"Warning: Directory {source_dir} does not exist")
    
    return files


def delete_processed_files(file_paths: List[Path]) -> None:
    """Delete files that were successfully processed."""
    for file_path in file_paths:
        try:
            file_path.unlink()
            logger.info(f"Deleted processed file: {file_path}")
        except OSError as e:
            logger.error(f"Error deleting {file_path}: {e}")


@task(name="run_transcript_chunking")
def run_transcript_chunking():
    """Main chunking process."""
    logger.info("Starting transcript chunking process...")
    
    # Get all transcript files
    transcript_files = get_all_transcript_files()
    
    if not transcript_files:
        logger.warning("No transcript files found to process")
        return 0  # Return 0 when no files to process
    
    processed_files = []
    total_chunks_created = 0
    
    # Process each file
    for file_path in transcript_files:
        logger.info(f"\nProcessing: {file_path.name}")
        
        chunks, video_title = process_transcript_file(file_path)
        
        if chunks:
            save_video_chunks(chunks, video_title)
            processed_files.append(file_path)
            total_chunks_created += len(chunks)
        else:
            logger.warning(f"No chunks created for {file_path.name}")
    
    # Summary
    logger.info(f"\nChunking process completed!")
    logger.info(f"Files processed: {len(processed_files)}")
    logger.info(f"Total chunks created: {total_chunks_created}")
    logger.info(f"Chunks saved to: {CHUNKED_OUTPUT_DIR}")

    if processed_files:
        logger.info(f"\nDeleting {len(processed_files)} processed source files...")
        # delete_processed_files(processed_files) 
    
    return len(processed_files)  # Return count of successfully processed files


if __name__ == "__main__":
   run_transcript_chunking()