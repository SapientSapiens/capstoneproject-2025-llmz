from ingestion.content_catalog import load_existing_catalog, create_current_catalog
from ingestion.transcript_ingestion import process_video_transcript
from ingestion.asr_operation import process_videos_with_asr
import pandas as pd
import logging
import time
import sys
from pathlib import Path
from datetime import datetime
from prefect import flow, task

# Set up logging
# Create logs directory
PROJECT_ROOT = Path(__file__).parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Generate timestamp for log file
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = f"ingestion_pipeline_{timestamp}.log"
log_filepath = LOG_DIR / log_filename

# Get the root logger and configure it
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Clear any existing handlers to avoid duplication
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# Create formatter
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# File handler for timestamped log file
file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

print(f"📝 Logging initialized: {log_filepath}")

# Get module-specific logger
logger = logging.getLogger(__name__)

@task(name="find_new_videos")
def find_new_videos(existing_df, current_df):
    """
    Compare existing and current catalogs to find new videos.
    Returns DataFrame containing only new videos.
    """
    if existing_df is None or existing_df.empty:
        logger.info("🆕 First run - all videos are new")
        return current_df
    
    # Find videos in current catalog that aren't in existing catalog
    existing_ids = set(existing_df['video_id'].dropna())
    current_ids = set(current_df['video_id'].dropna())
    
    new_ids = current_ids - existing_ids
    
    if not new_ids:
        logger.info("✅ No new videos found")
        return pd.DataFrame()
    
    new_videos = current_df[current_df['video_id'].isin(new_ids)]
    logger.info(f"🆕 Found {len(new_videos)} new videos")
    
    return new_videos

@task(name="process_videos", retries=2, retry_delay_seconds=6)
def process_videos(videos_to_process):
    """
    Process videos using rotating proxies without complex retry logic.
    Maintains success/failure tracking for pipeline reporting.
    """
    successful_processing = []
    failed_processing = []
      
    for index, video in videos_to_process.iterrows():
        video_id = video['video_id']
        video_title = video['title']
        
        logger.info(f"🎬 Processing: {video_title} ({video_id})")
        
        try:
            # Process the video transcript WITH proxy session
            result = process_video_transcript(video)
            
            if result:
                logger.info(f"✅ Successfully processed: {video_title}")
                successful_processing.append(video_id)
            else:
                logger.warning(f"❌ Failed to process: {video_title}")
                failed_processing.append(video_id)
                
        except Exception as e:
            logger.error(f"💥 Error processing {video_title}: {e}")
            failed_processing.append(video_id)
        
        # Simple fixed delay between videos to be respectful
        if index < len(videos_to_process) - 1:
            logger.info(f"🔄 Waiting 2s before next video...")
            time.sleep(2)
    
    return successful_processing, failed_processing

@flow(name="orchestrated-youtube-playlist-content-ingestion-pipeline")
def content_ingestion_pipeline():
    """
    Main orchestration pipeline for content ingestion
    """
    logger.info("🚀 Starting Content Ingestion Pipeline")
    
    # Step 1: Load existing catalog (if any)
    logger.info("📥 Step 1: Loading existing content catalog...")
    existing_catalog = load_existing_catalog()
    
    # Step 2: Create current catalog
    logger.info("🔄 Step 2: Creating current content catalog...")
    #current_catalog, new_filename = create_current_catalog()
    current_catalog= create_current_catalog()
    
    # Step 3: Find new videos
    logger.info("🔍 Step 3: Comparing catalogs for new videos...")
    new_videos = find_new_videos(existing_catalog, current_catalog)
    
    # Step 4: Conditionally process new videos
    if not new_videos.empty:
        logger.info(f"🎯 Step 4: Processing {len(new_videos)} new videos...")
        
        # Separate videos with and without captions
        videos_with_captions = new_videos[new_videos['has_captions'] == True]
        videos_without_captions = new_videos[new_videos['has_captions'] == False]
        
        logger.info(f"📊 Initial Video Type Breakdown:")
        logger.info(f" Videos  🎯 With captions: {len(videos_with_captions)} videos")
        logger.info(f" Videos  🔇 Without captions: {len(videos_without_captions)} videos (ASR candidates)")
        
        # Process only videos with captions using transcript API with proxies
        if not videos_with_captions.empty:
            logger.info("🎬 Starting transcript processing for videos with captions...")
            successful, failed = process_videos(videos_with_captions)
            
            # Get the failed video details for ASR bucket
            failed_videos_for_asr = videos_with_captions[videos_with_captions['video_id'].isin(failed)]
            
            # Combine all ASR candidates: original without captions + failed processing + age-restricted
            asr_candidates = pd.concat([videos_without_captions, failed_videos_for_asr], ignore_index=True)
            
            # Summary report
            logger.info(f"📊 Processing Summary:")
            logger.info(f"✅ Successful transcript extraction: {len(successful)} videos")
            logger.info(f"🔇 ASR candidate : {len(asr_candidates)} videos")
            logger.info(f" - Originally without captions: {len(videos_without_captions)}")
            logger.info(f" - Failed/age-restricted: {len(failed_videos_for_asr)}")
            
            if len(failed) > 0:
                logger.info(f" 🚨 Failed/Age-restricted videos (also added to ASR bucket): {failed}")
            
            # Step 5: Process ASR candidates
            if not asr_candidates.empty:
                logger.info("🎤 Step 5: Starting ASR processing...")
                successful_asr, failed_asr = process_videos_with_asr(asr_candidates)
                
                # Final summary
                logger.info(f"📊 FINAL PIPELINE SUMMARY:")
                logger.info(f"🎯 Original new videos: {len(new_videos)}")
                logger.info(f"✅ Successful transcript API: {len(successful)}")
                logger.info(f"🔊 Successful ASR: {len(successful_asr)}")
                logger.info(f"❌ Total failed: {len(failed) + len(failed_asr)}")
                logger.info(f"📄 Total transcripts generated: {len(successful) + len(successful_asr)}")
                
        else:
            # No videos with captions, so all ASR candidates are the ones without captions
            asr_candidates = videos_without_captions
            logger.info("⏭️  No videos with captions to process")
            logger.info(f"🔇 All {len(asr_candidates)} videos are ASR candidates")
            
            # Process all videos with ASR
            if not asr_candidates.empty:
                logger.info("🎤 Step 5: Starting ASR processing for all videos...")
                successful_asr, failed_asr = process_videos_with_asr(asr_candidates)
                
                logger.info(f"📊 ASR Processing Summary:")
                logger.info(f"🔊 Successful ASR: {len(successful_asr)}")
                logger.info(f"❌ Failed ASR: {len(failed_asr)}")
            
    else:
        logger.info("⏭️  Step 4: No new videos to process")
    
    logger.info("🏁 Content Ingestion Pipeline Completed 🏁")

if __name__ == "__main__":
    import sys

    if "--run-now" in sys.argv:
        print("🔧 Running for development and test")
        content_ingestion_pipeline()  # Run immediately
    else:
        # For Prefect deployment      
        
        content_ingestion_pipeline.serve(
             name="youtube-playlist-content-ingestion-pipeline",
            cron="30 19 * * *",
             tags=["YT-playlist", "video-transcript", "RAG", "ingestion-pipeline"],
        )