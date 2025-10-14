import json
import logging
from datetime import datetime
from pathlib import Path
from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent
TRANSCRIPTS_DIR = PROJECT_ROOT / "data" / "raw_ingested_transcripts"

# Get module-specific logger
logger = logging.getLogger(__name__)


def get_english_transcript(video_id):
    """
    Simple function to get English transcript for a YouTube video.
    Prefers manual transcripts, falls back to auto-generated if needed.
    """
    try:
        # Get available transcripts
        transcript_list = YouTubeTranscriptApi().list(video_id)

        # Find all English variants
        english_codes = []
        for transcript in transcript_list:
            if transcript.language_code.startswith('en'):
                english_codes.append(transcript.language_code)
                logger.info(f"Found: {transcript.language} ({transcript.language_code}) - {'Auto' if transcript.is_generated else 'Manual'}")

        if not english_codes:
            logger.warning("No English transcripts found")
            return None

        # Try to get manual transcript first
        try:
            transcript = transcript_list.find_manually_created_transcript(english_codes)
            logger.info(f"✓ Using MANUAL transcript: {transcript.language_code}")
        except:
            # Fallback to any English transcript
            transcript = transcript_list.find_transcript(english_codes)
            logger.info(f"○ Using English transcript: {transcript.language_code}")

        # Fetch and return the data
        return transcript.fetch()

    except Exception as e:
        if "age-restricted" in str(e):
            logger.warning("⛔ Video is age-restricted. Skipping as authentication is currently unsupported.")
            return "AGE_RESTRICTED"
        else:
            logger.error(f"Error getting transcript : {e}")
            return None

def extract_chapters_yt_dlp(video_url):
    """
    Extracts chapters and their time ranges from a YouTube video using yt-dlp,
    with explicit type casting to prevent float/int formatting errors.
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
        logger.error(f"An error occurred during chapter extraction: {e}")
        return []

def segment_transcript_by_chapters(transcript, chapters):
    """
    Segment the transcript by chapter boundaries - KEEP START_TIME for temporal context
    """
    if not chapters:
        # No chapters found, return entire transcript as one segment
        full_text = " ".join([line.text for line in transcript])
        logger.info("No chapters found, using full video as single segment")
        return [{
            "chapter_title": "Full Video",
            "text": full_text,
            "start_time": 0  # Keep for temporal reference
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
            chapter_end = transcript[-1].start + transcript[-1].duration if transcript else chapter_start

        # Get all transcript lines within this chapter
        chapter_lines = [
            line for line in transcript
            if chapter_start <= line.start < chapter_end
        ]

        # Combine text for this chapter
        chapter_text = " ".join([line.text for line in chapter_lines])

        segmented_content.append({
            "chapter_title": chapter["title"],
            "text": chapter_text,
            "start_time": chapter_start  # KEEP THIS - valuable for retrieval
        })

    logger.info(f"Segmented transcript into {len(segmented_content)} chapters")
    return segmented_content

def sanitize_filename(title):
    """
    Remove invalid characters from filename
    """
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        title = title.replace(char, '-')
    return title[:100]  # Limit length for file name constraint

def save_transcript_to_file(video_data, segmented_content, output_dir=TRANSCRIPTS_DIR):
    """
    Save optimized transcript data with temporal context
    """
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Sanitize title for filename
    safe_title = sanitize_filename(video_data['title'])
    
    # Generate timestamp for filename
    timestamp = datetime.now().strftime("%y-%m-%d %I:%M %p")
    
    # Create filename
    filename = f"{safe_title}_{timestamp}.json"
    filepath = output_dir / filename
    
    # OPTIMIZED DATA STRUCTURE with temporal context
    output_data = {
        "video_title": video_data['title'],
        "segments": [
            {
                "segment_title": segment["chapter_title"],
                "text": segment["text"],
                "start_time": segment["start_time"]  # Include temporal metadata
            }
            for segment in segmented_content
        ]
    }
    
    # Save to JSON file
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"💾 Transcript with temporal context saved: {filepath}")
    return str(filepath)

def process_video_transcript(video_row):
    """
    Main function to process a single video's transcript
    Takes a video row from the catalog DataFrame and returns the filepath
    """
    video_id = video_row['video_id']
    video_url = video_row['url']
    
    logger.info(f"\n🎬 Processing Video: {video_row['title']} ({video_id})")
    print("=" * 60)
    
    # Step 1: Get transcript
    logger.info("📝 Step 1: Extracting Transcript...")
    transcript = get_english_transcript(video_id)
    
    # Check for age-restricted FIRST
    if transcript == "AGE_RESTRICTED":
        logger.warning("⛔ Age-restricted video - cannot process with transcript API")
        return None
    elif not transcript:  # Then check for other failures
        logger.error("❌ Failed to extract transcript")
        return None
    
    logger.info(f"✅ Transcript extracted: {len(transcript)} lines")
    
    # Step 2: Get chapters
    logger.info("📖 Step 2: Extracting Chapters...")
    chapters = extract_chapters_yt_dlp(video_url)
    
    if chapters:
        logger.info(f"✅ Chapters found: {len(chapters)} chapters")
        for chapter in chapters[:3]:  # Show first 3 chapters
            logger.info(f"[{chapter['timestamp']}] {chapter['title']}")
        if len(chapters) > 3:
            logger.info(f"... and {len(chapters) - 3} more chapters")
    else:
        logger.info("ℹ️  No chapters found in video")
    
    # Step 3: Combine transcript and chapters
    logger.info("🔗 Step 3: Combining Transcript with Chapters...")
    segmented_content = segment_transcript_by_chapters(transcript, chapters)
    
    # Step 4: Save to file
    logger.info("💾 Step 4: Saving Transcript...")
    filepath = save_transcript_to_file(video_row, segmented_content)
    
    logger.info(f"✅ Successfully processed: {video_row['title']}")
    return filepath

# For testing individual videos
if __name__ == "__main__":
    # Test with a sample video
    test_video = {
        'video_id': 'CAjkJ2kSMmE',
        'title': 'TERRIFYING Tornado Scenarios: What You Should Do',
        'url': 'https://www.youtube.com/watch?v=CAjkJ2kSMmE',
        'duration_seconds': 1029,
        'has_captions': True
    }
    
    result = process_video_transcript(test_video)
    if result:
        print(f"\n🎉 Test completed successfully! File saved: {result}")
    else:
        print("\n💥 Test failed!")