import os
import pandas as pd
import requests
import time
import re
import logging
from datetime import datetime
from pathlib import Path
from prefect import task


# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent
PROPERTIES_FILE = PROJECT_ROOT / "playlists.properties"

# YouTube Data API configuration
CLIENT_ID = os.getenv("YT_DATA_API_CLIENT_ID")
CLIENT_SECRET = os.getenv("YT_DATA_API_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("YT_DATA_API_REFRESH_TOKEN")
YT_API = "https://www.googleapis.com/youtube/v3"

# Get module-specific logger
logger = logging.getLogger(__name__)

@task(name="read_playlists_from_properties")
def read_playlists_from_properties(file_path=PROPERTIES_FILE):
    """
    Read playlist URLs from properties file.
    Expected format: playlist_urls=https://youtube.com/playlist?list=...
    """
    playlist_urls = []
    
    try:
        logger.info(f"📁 Looking for properties file: {file_path}")
        logger.info(f"📁 File exists: {file_path.exists()}")
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if line.startswith('#') or not line:
                    continue
                # Parse key=value pairs
                if '=' in line:
                    key, value = line.split('=', 1)
                    if key.strip() == 'playlist_urls':
                        playlist_urls.append(value.strip())
        
        logger.info(f"📋 Read {len(playlist_urls)} playlist URLs from {file_path}")
        return playlist_urls
        
    except FileNotFoundError:
        logger.error(f"❌ Properties file not found: {file_path}")
        logger.error(f"❌ Current working directory: {os.getcwd()}")
        return []
    except Exception as e:
        logger.error(f"❌ Error reading properties file: {e}")
        return []
    
@task(name="get_access_token")
def get_access_token():
    """Get access token using refresh token"""
    try:
        r = requests.post("https://oauth2.googleapis.com/token", data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": REFRESH_TOKEN,
        })
        r.raise_for_status()
        logger.info("✅ Successfully obtained access token")
        return r.json()["access_token"]
    except Exception as e:
        logger.error(f"❌ Failed to get access token: {e}")
        raise

def iso8601_to_seconds(s):
    """Convert ISO 8601 duration to seconds"""
    if not s:
        return None
    m = re.findall(r'(\d+)([HMS])', s)
    sec = 0
    for v, u in m:
        v = int(v)
        sec += v * (3600 if u=='H' else 60 if u=='M' else 1)
    return sec

@task(name="fetch_playlist_items", retries=2, retry_delay_seconds=20)
def fetch_playlist_items(token, pid):
    """Fetch all items from a playlist"""
    out = []
    token_hdr = {"Authorization": f"Bearer {token}"}
    next_tok = None

    logger.info(f"Fetching playlist items for playlist ID: {pid}")

    while True:
        p = {"part": "snippet,contentDetails", "playlistId": pid, "maxResults": 50}
        if next_tok: 
            p["pageToken"] = next_tok
        r = requests.get(f"{YT_API}/playlistItems", params=p, headers=token_hdr, timeout=20)
        r.raise_for_status()
        d = r.json()
        out += d.get("items", [])
        next_tok = d.get("nextPageToken")
        if not next_tok:
            break
        time.sleep(0.1)

    logger.info(f"Completed fetching {len(out)} items from playlist {pid}")    
    return out

@task(name="fetch_videos_info", retries=2, retry_delay_seconds=20)
def fetch_videos_info(token, vids):
    """Fetch video metadata including duration and caption availability"""
    token_hdr = {"Authorization": f"Bearer {token}"}
    info = {}

    logger.info(f"Fetching metadata for {len(vids)} videos")
    
    for i in range(0, len(vids), 50):
        batch = vids[i:i+50]
        ids = ",".join(batch)
        resp = requests.get(
            f"{YT_API}/videos",
            params={"part": "contentDetails,snippet", "id": ids},
            headers=token_hdr,
            timeout=20,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        returned = {it["id"] for it in items}
        
        for it in items:
            vid = it["id"]
            dur_iso = it.get("contentDetails", {}).get("duration")
            dur = iso8601_to_seconds(dur_iso) if dur_iso else None
            has_cc = it.get("contentDetails", {}).get("caption", "false").lower() == "true"
            info[vid] = {"duration_seconds": dur, "has_captions": has_cc}
        
        missing = [v for v in batch if v not in returned]
        if missing:
            logger.warning(f"Missing metadata for videos: {missing}")
        time.sleep(0.1)

    logger.info(f"Completed metadata fetch for {len(info)} videos")    
    return info

@task(name="load_existing_catalog")
def load_existing_catalog():
    """
    Load the most recent content_catalog_<timestamp>.csv file if exists,
    then delete it to prevent file accumulation.
    Returns DataFrame if found, None if no catalog exists.
    """
    # Use absolute path based on PROJECT_ROOT
    catalog_dir = PROJECT_ROOT / "data" / "content_catalog"
    catalog_files = list(catalog_dir.glob("content_catalog_*.csv"))
    
    if not catalog_files:
        logger.info("📭 No existing content catalog found - first run scenario")
        return None
    
    try:
        # Find the most recent file by timestamp in filename
        latest_file = max(catalog_files, key=lambda x: Path(x).stat().st_mtime)
        logger.info(f"📂 Loading existing catalog: {latest_file}")
        
        # Load the CSV
        df = pd.read_csv(latest_file)
        logger.info(f"✅ Successfully loaded {len(df)} videos from existing catalog")
        
        # Delete the file after reading to prevent accumulation
        latest_file.unlink()  # This is Path's equivalent of os.remove
        logger.info(f"🗑️  Deleted previous catalog file: {latest_file}")
        
        return df
        
    except Exception as e:
        logger.error(f"❌ Error loading/deleting existing catalog: {e}")
        # Return None on error to ensure clean state
        return None
    
@task(name="create_current_catalog")
def create_current_catalog():
    """
    Create a new content catalog by scanning YouTube playlists from properties file.
    Returns DataFrame and the filename it was saved to.
    """
    # Read playlist URLs from properties file
    playlist_urls = read_playlists_from_properties()
    
    if not playlist_urls:
        logger.info("❌ No playlist URLs found. Cannot create catalog.")
        return pd.DataFrame()
    
    token = get_access_token()
    rows = []

    for purl in playlist_urls:
        pid = purl.split("list=")[-1]
        logger.info(f"🔍 Scanning playlist: {purl}")
        
        items = fetch_playlist_items(token, pid)
        vids = [i["contentDetails"]["videoId"] for i in items if "contentDetails" in i]
        infos = fetch_videos_info(token, vids)

        for i in items:
            snip = i.get("snippet", {})
            cd = i.get("contentDetails", {})
            vid = cd.get("videoId")
            if not vid:
                continue
            
            title = (snip.get("title") or "").strip()
            is_short_tag = title.lower().endswith("#shorts")
            meta = infos.get(vid, {})
            dur = meta.get("duration_seconds")
            has_cc = meta.get("has_captions", False)
            
            # Skip shorts and ultra-short videos
            if is_short_tag or (dur is not None and dur < 60):
                continue
                
            rows.append({
                "playlist_url": purl,
                "video_id": vid,
                "title": title,
                "url": f"https://www.youtube.com/watch?v={vid}",
                "duration_seconds": dur,
                "is_short_tag": is_short_tag,
                "has_captions": has_cc
            })

    df = pd.DataFrame(rows)
    
    # Generate timestamp for filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Use absolute path based on PROJECT_ROOT
    output_dir = PROJECT_ROOT / "data" / "content_catalog"
    #output_dir.mkdir(parents=True, exist_ok=True)  # Create directory if it doesn't exist
    
    filename = output_dir / f"content_catalog_{timestamp}.csv"
    
    # Save to CSV
    df.to_csv(filename, index=False)
    logger.info(f"✅ Created new content catalog: {filename} with {len(df)} videos")
    
    #return df, str(filename)
    return df


# Module initialization for script testing
if __name__ == "__main__":
    # Test the functions
    print("Testing content_catalog.py...")
    print(f"📁 Project root: {PROJECT_ROOT}")
    print(f"📁 Properties file: {PROPERTIES_FILE}")
    # Load existing catalog (if any)
    existing_df = load_existing_catalog()
    
    # Create new catalog
    current_df, filename = create_current_catalog()
    
    print(f"📊 Existing catalog: {len(existing_df) if existing_df is not None else 0} videos")
    print(f"📊 Current catalog: {len(current_df)} videos")
    print(f"💾 Saved to: {filename}")