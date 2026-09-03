"""
Cricket Video Dataset Builder - High Speed YouTube Clip Extractor
Supports single clip extraction or batch Excel (.xlsx / .csv) downloading.
"""

from dataset_builder import download_single_clip, process_excel_dataset, time_to_seconds

def download_youtube_clip(url: str, start_time: str, end_time: str, output_filename: str = None, target_fps: int = 60):
    """
    Downloads a specific timestamp section from a YouTube video as an MP4 file (no audio, maximum FPS).
    """
    start_sec = time_to_seconds(start_time)
    end_sec = time_to_seconds(end_time)
    
    clip_info = {
        'row_id': 1,
        'url': url,
        'start_sec': start_sec,
        'end_sec': end_sec,
        'label': 'cricket_bowling_clip'
    }
    
    print(f"Downloading clip from {start_time} ({start_sec}s) to {end_time} ({end_sec}s) at up to {target_fps} FPS...")
    result = download_single_clip(clip_info, output_dir=".", target_fps=target_fps)
    
    if result['status'] == 'success':
        print(f"\n✨ Success! Clip saved as: {result['file_path']} ({result['file_size_mb']} MB)")
    else:
        print(f"\n❌ Error downloading clip: {result['error']}")

if __name__ == "__main__":
    import os
    
    # Check if a sample excel exists, or run single clip example
    sample_excel = "cricket_clips_input.xlsx"
    if os.path.exists(sample_excel):
        print(f"Found batch file '{sample_excel}', starting batch extraction...")
        process_excel_dataset(sample_excel, output_dir="dataset_clips", max_workers=4)
    else:
        # Example Single Clip Usage
        video_url = "https://www.youtube.com/watch?v=xPE0VH2cyK4"
        start = "00:00:03" 
        end = "00:00:10"   
        
        download_youtube_clip(video_url, start, end)