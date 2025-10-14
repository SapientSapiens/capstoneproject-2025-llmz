import yt_dlp
import json
from datetime import datetime
from pathlib import Path
from faster_whisper import WhisperModel
import logging
import time
from prefect import task

# Set up logging
logger = logging.getLogger(__name__)

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
AUDIO_DIR = PROJECT_ROOT / "data" / "ingested_audio_files"
TRANSCRIPTS_DIR = PROJECT_ROOT / "data" / "raw_asr_transcripts"

def sanitize_filename(title):
    """Remove invalid characters from filename"""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        title = title.replace(char, '-')
    return title[:100]  # Lfor file name constraint

@task(name="download_audio", retries=2, retry_delay_seconds=5)
def download_audio(video_url, video_title, output_dir=AUDIO_DIR):
    """Download audio from YouTube video"""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Sanitize title for filename
    safe_title = sanitize_filename(video_title)
    timestamp = datetime.now().strftime("%y-%m-%d %I:%M %p")
    audio_filename = f"{safe_title}_{timestamp}"
    audio_path = output_dir / audio_filename
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': str(audio_path),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            # No quality setting for WAV - it's uncompressed
        }],
        'quiet': False,
    }
    
    try:
        logger.info(f"📥 Downloading audio for: {video_title}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        
        # Return the path to the WAV file
        wav_path = audio_path.with_suffix('.wav')
        logger.info(f"✅ Audio downloaded: {wav_path}")
        return str(wav_path)
        
    except Exception as e:
        logger.error(f"❌ Audio download failed for {video_title}: {e}")
        return None

@task(name="extract_chapters_yt_dlp", retries=2, retry_delay_seconds=5)
def extract_chapters_yt_dlp(video_url):
    """
    Extract chapters from YouTube video (same as transcript_ingestion.py)
    Returns chapters with start_sec and title
    """
    ydl_opts = {
        'skip_download': True,
        'writesubtitles': False,
        'getchapters': True,
        'force_generic_extractor': True,
        'quiet': True,
        'extract_flat': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            chapters = info.get('chapters')

            if chapters:
                formatted_chapters = []
                for chapter in chapters:
                    start_sec = chapter['start_time']
                    total_seconds = int(start_sec)
                    minutes, seconds = divmod(total_seconds, 60)
                    timestamp = f"{minutes:02d}:{seconds:02d}"

                    formatted_chapters.append({
                        "start_sec": total_seconds,
                        "timestamp": timestamp,
                        "title": chapter['title']
                    })

                logger.info(f"Extracted {len(formatted_chapters)} chapters from video")
                return formatted_chapters
            else:
                logger.info("No chapters found in video")
                return []

    except Exception as e:
        logger.warning(f"Could not extract chapters: {e}")
        return []

@task(name="segment_transcript_by_chapters")
def segment_transcript_by_chapters(transcript_segments, chapters):
    """
    Segment ASR transcript by chapter boundaries
    Returns same format as transcript_ingestion.py
    """
    if not chapters:
        # No chapters found, return entire transcript as one segment
        full_text = " ".join([segment.text for segment in transcript_segments])
        logger.info("No chapters found, using full video as single segment")
        return [{
            "chapter_title": "Full Video",
            "text": full_text,
            "start_time": 0
        }]

    segmented_content = []

    # Add segments for each chapter
    for i, chapter in enumerate(chapters):
        chapter_start = chapter["start_sec"]

        # Determine chapter end time (next chapter's start or end of video)
        if i + 1 < len(chapters):
            chapter_end = chapters[i + 1]["start_sec"]
        else:
            # Last chapter goes until end of video
            chapter_end = transcript_segments[-1].end if transcript_segments else chapter_start

        # Get all transcript segments within this chapter
        chapter_segments = [
            segment for segment in transcript_segments
            if chapter_start <= segment.start < chapter_end
        ]

        # Combine text for this chapter
        chapter_text = " ".join([segment.text for segment in chapter_segments])

        segmented_content.append({
            "chapter_title": chapter["title"],
            "text": chapter_text,
            "start_time": chapter_start
        })
    
    logger.info(f"Segmented transcript into {len(segmented_content)} chapters")
    return segmented_content

@task(name="transcribe_audio")
def transcribe_audio(audio_path, model_size="base"):
    """Transcribe audio using Fast Whisper with CUDA"""
    try:
        logger.info(f"🔊 Starting ASR transcription: {audio_path}")
        #model = WhisperModel(model_size, device="cuda", compute_type="float16")
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        
        # Transcribe with beam search for better accuracy
        segments, info = model.transcribe(
            audio_path,
            beam_size=5,
            best_of=5,
            temperature=0.0,
            vad_filter=True  # Voice Activity Detection for better segmentation
        )
        
        # Convert to list to reuse the segments
        segments_list = list(segments)
        logger.info(f"✅ ASR completed: {len(segments_list)} segments, language: {info.language}")
        
        return segments_list
        
    except Exception as e:
        logger.error(f"❌ ASR transcription failed: {e}")
        return None

@task(name="save_asr_transcript")
def save_asr_transcript(video_data, segmented_content, output_dir=TRANSCRIPTS_DIR):
    """
    Save ASR transcript in same format as existing JSON files
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Sanitize title for filename
    safe_title = sanitize_filename(video_data['title'])
    
    # Generate timestamp for filename (matches existing format)
    timestamp = datetime.now().strftime("%y-%m-%d %I:%M %p")
    
    # Create filename (same pattern as transcript_ingestion.py)
    filename = f"{safe_title}_{timestamp}.json"
    filepath = output_dir / filename
    
    # Same data structure as transcript_ingestion.py
    output_data = {
        "video_title": video_data['title'],
        "segments": [
            {
                "segment_title": segment["chapter_title"],
                "text": segment["text"],
                "start_time": segment["start_time"]
            }
            for segment in segmented_content
        ]
    }
    
    # Save to JSON file
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"💾 ASR transcript saved: {filepath}")
    return str(filepath)

@task(name="process_single_video_with_asr")
def process_single_video_with_asr(video_row):
    """
    Process a single video with ASR pipeline
    Returns filepath if successful, None if failed
    """
    video_id = video_row['video_id']
    video_url = video_row['url']
    video_title = video_row['title']
    
    logger.info(f"🎤 Starting ASR pipeline for: {video_title}")
    
    try:
        # Step 1: Download audio
        audio_path = download_audio(video_url, video_title)
        if not audio_path:
            return None
        
        # Step 2: Extract chapters
        chapters = extract_chapters_yt_dlp(video_url)
        logger.info(f"📖 Chapters found: {len(chapters)}" if chapters else "ℹ️ No chapters found")
        
        # Step 3: Transcribe with Fast Whisper
        transcript_segments = transcribe_audio(audio_path, model_size="base")
        if not transcript_segments:
            return None
        
        # Step 4: Segment by chapters
        segmented_content = segment_transcript_by_chapters(transcript_segments, chapters)
        
        # Step 5: Save in same format as existing transcripts
        filepath = save_asr_transcript(video_row, segmented_content)
        
        logger.info(f"✅ ASR pipeline completed for: {video_title}")
        return filepath
        
    except Exception as e:
        logger.error(f"❌ ASR pipeline failed for {video_title}: {e}")
        return None

@task(name="process_videos_with_asr")
def process_videos_with_asr(videos_df):
    """
    Main function to process multiple videos with ASR
    Takes DataFrame of video rows and processes each one
    Returns list of successful and failed video IDs
    """
    successful_processing = []
    failed_processing = []
    
    if videos_df.empty:
        logger.info("📭 No videos to process with ASR")
        return successful_processing, failed_processing
    
    logger.info(f"🎯 Starting ASR processing for {len(videos_df)} videos")
    
    for index, video_row in videos_df.iterrows():
        video_id = video_row['video_id']
        video_title = video_row['title']
        
        logger.info(f"🔊 Processing {index + 1}/{len(videos_df)}: {video_title}")
        
        result = process_single_video_with_asr(video_row)
        
        if result:
            successful_processing.append(video_id)
            logger.info(f"✅ ASR success for : {video_title}")
        else:
            failed_processing.append(video_id)
            logger.error(f"❌ ASR failed for: {video_title}")

        # ✅ ADDING DELAY HERE - between ASR video processing
        if index < len(videos_df) - 1:
            logger.info("🔄 Waiting 5s before next ASR video...")
            time.sleep(5) 
    
    logger.info(f"🏁 ASR batch completed: {len(successful_processing)} success, {len(failed_processing)} failed")
    return successful_processing, failed_processing


# Module initialization for script testing
if __name__ == "__main__":
    """
    Test the ASR processing individually
    """
    print("🧪 Testing ASR Processing Pipeline Individually...")
    print("=" * 60)
    
    # Test with a sample video (choose a short one for quick testing)
    test_video = {
        'video_id': 'yjDrpVvpJMM',  # Replace with a real video ID for testing
        'title': 'How to Escape Quicksand',
        'url': 'https://www.youtube.com/watch?v=yjDrpVvpJMM',  # Replace with real URL
        'duration_seconds': 347,
        'has_captions': True
    }
    
    print(f"🎬 Testing with video: {test_video['title']}")
    print(f"🔗 URL: {test_video['url']}")
    
    # Test single video processing
    result = process_single_video_with_asr(test_video)
    
    if result:
        print(f"🎉 ASR Test SUCCESS! Transcript saved to: {result}")
        
        # Read and display the generated transcript
        try:
            with open(result, 'r', encoding='utf-8') as f:
                transcript_data = json.load(f)
            
            print(f"\n📄 Generated Transcript Preview:")
            print(f"Video Title: {transcript_data['video_title']}")
            print(f"Number of segments: {len(transcript_data['segments'])}")
            
            for i, segment in enumerate(transcript_data['segments'][:3]):  # Show first 3 segments
                print(f"\nSegment {i+1}: {segment['segment_title']}")
                print(f"Start Time: {segment['start_time']}s")
                print(f"Text Preview: {segment['text'][:100]}...")
                
        except Exception as e:
            print(f"⚠️ Could not read generated transcript: {e}")
            
    else:
        print("💥 ASR Test FAILED!")
        print("💡 Check the error messages above for troubleshooting.")
    
    print("=" * 60)
    print("🧪 ASR Individual Test Completed!")