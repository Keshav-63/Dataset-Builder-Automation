import os
import re
import sys
import time
import argparse
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import yt_dlp

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Lock mechanism for thread-safe raw video downloading
_download_locks = {}
_download_locks_global = threading.Lock()

def get_video_lock(video_id: str) -> threading.Lock:
    with _download_locks_global:
        if video_id not in _download_locks:
            _download_locks[video_id] = threading.Lock()
        return _download_locks[video_id]

def time_to_seconds(time_val) -> float:
    """Converts HH:MM:SS, MM:SS, decimal seconds, or float/int to total seconds."""
    if pd.isna(time_val) or time_val is None:
        return 0.0
    
    if isinstance(time_val, (int, float)):
        return float(time_val)
    
    time_str = str(time_val).strip()
    if not time_str:
        return 0.0
        
    parts = time_str.split(':')
    try:
        if len(parts) == 3:
            h, m, s = parts
            return float(h) * 3600 + float(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return float(m) * 60 + float(s)
        elif len(parts) == 1:
            return float(parts[0])
    except ValueError:
        raise ValueError(f"Invalid timestamp format: '{time_val}'")
    return 0.0

def sanitize_filename(filename: str) -> str:
    """Removes unsafe characters for file paths."""
    return re.sub(r'[\\/*?:"<>|]', "_", str(filename)).strip()

def extract_youtube_id(url: str) -> str:
    """Extracts 11-character YouTube video ID from various URL formats."""
    url_str = str(url).strip()
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11})',
        r'youtu\.be\/([0-9A-Za-z_-]{11})',
        r'embed\/([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url_str)
        if match:
            return match.group(1)
    return sanitize_filename(url_str)

def get_format_selector(max_res: int = 720) -> str:
    """
    Returns a yt-dlp format selector capped at max_res (e.g. 720 for 720p).
    Prevents downloading multi-gigabyte streams for short clip extraction.
    """
    return f'bestvideo[height<={max_res}][ext=mp4]/bestvideo[height<={max_res}]/best[height<={max_res}][ext=mp4]/best[height<={max_res}]/best'

def identify_columns(df: pd.DataFrame):
    """Dynamically matches column names for URL, start_time, end_time, and subfolder/label."""
    col_map = {}
    
    url_names = {'url', 'yt_link', 'youtube_url', 'link', 'video_url', 'youtube'}
    start_names = {'start', 'start_time', 'start_timestamp', 'from', 'start_sec', 'begin'}
    end_names = {'end', 'end_time', 'end_timestamp', 'to', 'end_sec', 'stop'}
    subfolder_names = {'subfolder', 'folder', 'category', 'class', 'label', 'clip_name', 'name', 'output_name', 'action', 'title', 'id', 'clip_id'}
    
    lower_cols = {str(col).strip().lower(): col for col in df.columns}
    
    for key in lower_cols:
        cleaned_key = key.replace(' ', '_').replace('-', '_')
        if not col_map.get('url') and any(syn in cleaned_key for syn in url_names):
            col_map['url'] = lower_cols[key]
        if not col_map.get('start') and any(syn in cleaned_key for syn in start_names):
            col_map['start'] = lower_cols[key]
        if not col_map.get('end') and any(syn in cleaned_key for syn in end_names):
            col_map['end'] = lower_cols[key]
        if not col_map.get('subfolder') and any(syn in cleaned_key for syn in subfolder_names):
            col_map['subfolder'] = lower_cols[key]

    if 'url' not in col_map and len(df.columns) > 0:
        col_map['url'] = df.columns[0]
    if 'start' not in col_map and len(df.columns) > 1:
        col_map['start'] = df.columns[1]
    if 'end' not in col_map and len(df.columns) > 2:
        col_map['end'] = df.columns[2]
        
    return col_map

def download_raw_video(url: str, cache_dir: str = "raw_videos", max_res: int = 720) -> str:
    """
    Downloads full source YouTube video once into local cache_dir, capped at max_res (default 720p).
    Returns path to cached video MP4 file.
    """
    os.makedirs(cache_dir, exist_ok=True)
    video_id = extract_youtube_id(url)
    target_mp4 = os.path.abspath(os.path.join(cache_dir, f"{video_id}.mp4"))
    
    # Thread-safe lock so multiple threads don't download same video simultaneously
    lock = get_video_lock(video_id)
    with lock:
        if os.path.exists(target_mp4) and os.path.getsize(target_mp4) > 0:
            return target_mp4

        print(f"[CACHE MISS] Downloading source YouTube video once (Capped at {max_res}p): {video_id} ({url})")
        temp_template = os.path.join(cache_dir, f"temp_{video_id}.%(ext)s")
        format_selector = get_format_selector(max_res)

        ydl_opts = {
            'format': format_selector,
            'outtmpl': temp_template,
            'quiet': False,
            'no_warnings': True,
            'nocheckcertificate': True,
            'overwrites': True,
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
            'postprocessor_args': {
                'ffmpeg': [
                    '-threads', '2',
                    '-c:v', 'libx264',
                    '-preset', 'ultrafast',
                    '-crf', '22',
                    '-an',
                    '-pix_fmt', 'yuv420p',
                    '-movflags', '+faststart'
                ]
            }
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        temp_mp4 = os.path.join(cache_dir, f"temp_{video_id}.mp4")
        if os.path.exists(temp_mp4):
            if os.path.exists(target_mp4):
                os.remove(target_mp4)
            os.rename(temp_mp4, target_mp4)
        elif not os.path.exists(target_mp4):
            for f in os.listdir(cache_dir):
                if f.startswith(f"temp_{video_id}"):
                    full_temp = os.path.join(cache_dir, f)
                    if os.path.exists(target_mp4):
                        os.remove(target_mp4)
                    os.rename(full_temp, target_mp4)
                    break

        if os.path.exists(target_mp4):
            print(f"[CACHE SAVED] Source video cached successfully: {video_id}.mp4 ({round(os.path.getsize(target_mp4)/(1024*1024), 2)} MB)")
            return target_mp4
        else:
            raise RuntimeError(f"Failed to save cached video for {video_id}")

def cut_clip_from_raw(raw_video_path: str, start_sec: float, end_sec: float, output_path: str) -> bool:
    """Cuts timestamp section from a cached local MP4 file using FFmpeg."""
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_sec),
        "-to", str(end_sec),
        "-i", raw_video_path,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "22",
        "-an",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output_path
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        return True
    return False

def download_single_clip(clip_info: dict, output_dir: str, target_fps: int = 60, max_res: int = 720, create_subfolders: bool = True, raw_video_map: dict = None, overwrite: bool = False) -> dict:
    """
    Downloads or extracts a single video section directly without audio, formatted as subfolder_video000.mp4.
    If raw source video is cached, cuts clip locally in milliseconds.
    If clip already exists, skips downloading.
    """
    row_id = clip_info['row_id']
    url = clip_info['url']
    start_sec = clip_info['start_sec']
    end_sec = clip_info['end_sec']
    subfolder_name = clip_info.get('subfolder', 'dataset_clips')
    clip_index = clip_info.get('clip_index', 0)
    
    if end_sec <= start_sec:
        return {
            'row_id': row_id,
            'status': 'error',
            'error': f"End time ({end_sec}s) must be greater than start time ({start_sec}s)"
        }
        
    clean_subfolder = sanitize_filename(subfolder_name)
    filename_base = f"{clean_subfolder}_video{clip_index:03d}"
    
    if create_subfolders:
        target_directory = os.path.join(output_dir, clean_subfolder)
    else:
        target_directory = output_dir
        
    os.makedirs(target_directory, exist_ok=True)
    final_output_path = os.path.join(target_directory, f"{filename_base}.mp4")
    
    # 1. Skip logic if clip already exists
    if not overwrite and os.path.exists(final_output_path) and os.path.getsize(final_output_path) > 0:
        file_size_mb = os.path.getsize(final_output_path) / (1024 * 1024)
        return {
            'row_id': row_id,
            'status': 'skipped',
            'file_path': final_output_path,
            'filename': f"{filename_base}.mp4",
            'subfolder': clean_subfolder,
            'duration_sec': round(end_sec - start_sec, 2),
            'file_size_mb': round(file_size_mb, 2),
            'elapsed_sec': 0.0,
            'note': 'Clip already exists (Skipped re-download)'
        }
        
    start_time_mark = time.time()
    video_id = extract_youtube_id(url)
    
    # 2. Local FFmpeg cutting if raw video is cached
    raw_video_path = raw_video_map.get(video_id) if raw_video_map else None
    if not raw_video_path or not os.path.exists(raw_video_path):
        default_raw = os.path.abspath(os.path.join("raw_videos", f"{video_id}.mp4"))
        if os.path.exists(default_raw) and os.path.getsize(default_raw) > 0:
            raw_video_path = default_raw

    if raw_video_path and os.path.exists(raw_video_path):
        success = cut_clip_from_raw(raw_video_path, start_sec, end_sec, final_output_path)
        if success:
            elapsed = time.time() - start_time_mark
            file_size_mb = os.path.getsize(final_output_path) / (1024 * 1024)
            return {
                'row_id': row_id,
                'status': 'success',
                'file_path': final_output_path,
                'filename': f"{filename_base}.mp4",
                'subfolder': clean_subfolder,
                'duration_sec': round(end_sec - start_sec, 2),
                'file_size_mb': round(file_size_mb, 2),
                'elapsed_sec': round(elapsed, 2),
                'source': 'local_cache'
            }

    # 3. Direct yt-dlp Range Download (Fallback)
    temp_template = os.path.join(target_directory, f"temp_{filename_base}.%(ext)s")
    format_selector = get_format_selector(max_res)
        
    ydl_opts = {
        'format': format_selector,
        'outtmpl': temp_template,
        'download_ranges': yt_dlp.utils.download_range_func(None, [(start_sec, end_sec)]),
        'force_keyframes_at_cuts': True,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'overwrites': True,
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
        'postprocessor_args': {
            'ffmpeg': [
                '-threads', '2',
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-crf', '22',
                '-an',
                '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart'
            ]
        }
    }
    
    for attempt in range(2):
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
            temp_mp4 = os.path.join(target_directory, f"temp_{filename_base}.mp4")
            if os.path.exists(temp_mp4):
                if os.path.exists(final_output_path):
                    os.remove(final_output_path)
                os.rename(temp_mp4, final_output_path)
            elif not os.path.exists(final_output_path):
                for f in os.listdir(target_directory):
                    if f.startswith(f"temp_{filename_base}"):
                        full_temp = os.path.join(target_directory, f)
                        if os.path.exists(final_output_path):
                            os.remove(final_output_path)
                        os.rename(full_temp, final_output_path)
                        break

            elapsed = time.time() - start_time_mark
            file_size_mb = os.path.getsize(final_output_path) / (1024 * 1024) if os.path.exists(final_output_path) else 0
            
            return {
                'row_id': row_id,
                'status': 'success',
                'file_path': final_output_path,
                'filename': f"{filename_base}.mp4",
                'subfolder': clean_subfolder,
                'duration_sec': round(end_sec - start_sec, 2),
                'file_size_mb': round(file_size_mb, 2),
                'elapsed_sec': round(elapsed, 2),
                'source': 'direct_download'
            }
            
        except Exception as e:
            if attempt == 0:
                time.sleep(1)
                continue
            return {
                'row_id': row_id,
                'status': 'error',
                'error': str(e)
            }

def process_excel_dataset(file_path: str, output_dir: str = "dataset_clips", max_workers: int = 2, target_fps: int = 60, max_res: int = 720, create_subfolders: bool = True, overwrite: bool = False, progress_callback=None):
    """
    Reads dataset spreadsheet, caches source videos once per unique URL (capped at 720p default), and extracts clips concurrently.
    """
    os.makedirs(output_dir, exist_ok=True)
    raw_cache_dir = os.path.join(os.path.dirname(os.path.abspath(output_dir)), "raw_videos")
    os.makedirs(raw_cache_dir, exist_ok=True)
    
    print(f"\n=======================================================")
    print(f" Cricket Model Dataset Extractor (Smart Caching MP4)")
    print(f"=======================================================")
    print(f"Reading input file: {file_path}")
    
    if file_path.endswith('.csv'):
        df = pd.read_csv(file_path)
    else:
        df = pd.read_excel(file_path)
        
    print(f"Total rows found: {len(df)}")
    
    col_map = identify_columns(df)
    print(f"Detected columns -> URL: '{col_map.get('url')}', Start: '{col_map.get('start')}', End: '{col_map.get('end')}', Subfolder: '{col_map.get('subfolder')}'")
    
    if not col_map.get('url') or not col_map.get('start') or not col_map.get('end'):
        raise ValueError("Failed to locate required columns (URL, Start Time, End Time) in the dataset file.")
        
    subfolder_counters = {}
    clip_tasks = []
    unique_urls = set()
    
    for idx, row in df.iterrows():
        try:
            url = str(row[col_map['url']]).strip()
            start_val = row[col_map['start']]
            end_val = row[col_map['end']]
            
            subfolder_val = str(row[col_map['subfolder']]).strip() if col_map.get('subfolder') and pd.notna(row[col_map['subfolder']]) else "bowling_clip"
            
            if not url or url.lower() == 'nan':
                continue
                
            start_sec = time_to_seconds(start_val)
            end_sec = time_to_seconds(end_val)
            
            clean_sub = sanitize_filename(subfolder_val)
            if clean_sub not in subfolder_counters:
                subfolder_counters[clean_sub] = 0
                
            clip_idx = subfolder_counters[clean_sub]
            subfolder_counters[clean_sub] += 1
            
            unique_urls.add(url)
            
            clip_tasks.append({
                'row_id': idx + 1,
                'url': url,
                'start_sec': start_sec,
                'end_sec': end_sec,
                'subfolder': clean_sub,
                'clip_index': clip_idx
            })
        except Exception as err:
            print(f"[Warning] Row {idx + 1} skipped due to parsing error: {err}")

    print(f"Found {len(unique_urls)} unique YouTube source video link(s) across {len(clip_tasks)} total clips.")

    # Phase 1: Ensure/Cache full source videos once per unique URL (capped resolution)
    raw_video_map = {}
    print(f"\n--- Phase 1: Checking & Caching Source Videos (Max {max_res}p) ---")
    for u in unique_urls:
        vid_id = extract_youtube_id(u)
        try:
            raw_path = download_raw_video(u, cache_dir=raw_cache_dir, max_res=max_res)
            raw_video_map[vid_id] = raw_path
        except Exception as err:
            print(f"[Warning] Failed to cache full video for '{vid_id}' ({err}). Will fallback to direct range download.")

    # Phase 2: Cut / Extract clips
    print(f"\n--- Phase 2: Extracting {len(clip_tasks)} Clips Across {max_workers} Workers ---")
    success_count = 0
    skipped_count = 0
    fail_count = 0
    results = []
    
    start_total_time = time.time()
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_clip = {
            executor.submit(download_single_clip, clip, output_dir, target_fps, max_res, create_subfolders, raw_video_map, overwrite): clip 
            for clip in clip_tasks
        }
        
        for future in as_completed(future_to_clip):
            res = future.result()
            results.append(res)
            if res['status'] == 'success':
                success_count += 1
                rel_path = os.path.relpath(res['file_path'], output_dir)
                source_lbl = " [Cached source]" if res.get('source') == 'local_cache' else ""
                print(f"[SUCCESS] [Row {res['row_id']}] Saved: {rel_path} ({res['file_size_mb']} MB in {res['elapsed_sec']}s){source_lbl}")
            elif res['status'] == 'skipped':
                skipped_count += 1
                rel_path = os.path.relpath(res['file_path'], output_dir)
                print(f"[SKIPPED] [Row {res['row_id']}] Existing clip: {rel_path} ({res['file_size_mb']} MB)")
            else:
                fail_count += 1
                print(f"[ERROR] [Row {res['row_id']}] Failure: {res['error']}")
                
            if progress_callback:
                progress_callback({
                    'completed': len(results),
                    'total': len(clip_tasks),
                    'success_count': success_count,
                    'skipped_count': skipped_count,
                    'fail_count': fail_count,
                    'latest': res
                })
                
    total_elapsed = round(time.time() - start_total_time, 2)
    print(f"\n=======================================================")
    print(f" DOWNLOAD SUMMARY")
    print(f"=======================================================")
    print(f"Total Clips Processed : {len(clip_tasks)}")
    print(f"Successful Downloads  : {success_count}")
    print(f"Skipped (Already Exists): {skipped_count}")
    print(f"Failed Downloads      : {fail_count}")
    print(f"Total Execution Time  : {total_elapsed} seconds")
    print(f"Output Directory      : {os.path.abspath(output_dir)}")
    print(f"=======================================================\n")
    
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ultra-Fast YouTube Clip Extractor for Cricket Dataset")
    parser.add_argument("--excel", "-e", type=str, default="cricket_clips.xlsx", help="Path to Excel (.xlsx) or CSV file")
    parser.add_argument("--out", "-o", type=str, default="dataset_clips", help="Output directory for MP4 clips")
    parser.add_argument("--workers", "-w", type=int, default=2, help="Number of concurrent worker threads (default 2)")
    parser.add_argument("--fps", type=int, default=60, help="Target frame rate (e.g. 60)")
    parser.add_argument("--max-res", type=int, default=720, help="Max resolution height limit (default 720p for fast/lightweight downloads)")
    parser.add_argument("--no-subfolders", action="store_true", help="Save all clips directly in output folder instead of creating subfolders")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing clip files instead of skipping")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.excel):
        print(f"Error: Specified dataset file '{args.excel}' not found.")
        print(f"Run 'python generate_sample_excel.py' to generate a sample Excel sheet first.")
        sys.exit(1)
        
    process_excel_dataset(args.excel, args.out, args.workers, args.fps, max_res=args.max_res, create_subfolders=not args.no_subfolders, overwrite=args.overwrite)
