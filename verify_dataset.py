import os
import sys
import json
import subprocess
import argparse

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def inspect_mp4(file_path: str) -> dict:
    """Uses ffprobe to inspect video clip metadata (resolution, fps, frame count, codec)."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        file_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        video_stream = None
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                video_stream = stream
                break
                
        if not video_stream:
            return {"error": "No video stream found"}
            
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        codec = video_stream.get("codec_name", "unknown")
        
        # Calculate FPS
        fps_str = video_stream.get("r_frame_rate", "0/1")
        if "/" in fps_str:
            num, den = fps_str.split("/")
            fps = round(float(num) / float(den), 2) if float(den) != 0 else 0
        else:
            fps = float(fps_str)
            
        nb_frames = video_stream.get("nb_frames")
        duration = float(data.get("format", {}).get("duration", 0))
        
        if not nb_frames and duration > 0 and fps > 0:
            nb_frames = int(duration * fps)
            
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        
        return {
            "filename": os.path.basename(file_path),
            "rel_path": os.path.normpath(file_path),
            "resolution": f"{width}x{height}",
            "fps": fps,
            "duration_sec": round(duration, 2),
            "frames": nb_frames,
            "codec": codec,
            "size_mb": round(file_size_mb, 2)
        }
        
    except Exception as e:
        return {"filename": os.path.basename(file_path), "rel_path": file_path, "error": str(e)}

def verify_output_directory(dir_path: str = "dataset_clips"):
    """Scans and verifies all MP4 clips in the dataset directory (including subdirectories)."""
    if not os.path.exists(dir_path):
        print(f"Directory '{dir_path}' does not exist.")
        return
        
    mp4_files = []
    for root, _, files in os.walk(dir_path):
        for f in files:
            if f.endswith(".mp4"):
                mp4_files.append(os.path.join(root, f))
                
    if not mp4_files:
        print(f"No .mp4 files found in '{dir_path}'.")
        return
        
    print(f"\n=======================================================")
    print(f" DATASET CLIPS QUALITY INSPECTOR")
    print(f"=======================================================")
    print(f"Inspecting {len(mp4_files)} clips in '{dir_path}':\n")
    
    table_data = []
    high_fps_count = 0
    
    for full_path in mp4_files:
        info = inspect_mp4(full_path)
        rel = os.path.relpath(full_path, dir_path)
        if "error" not in info:
            table_data.append(info)
            if info["fps"] >= 50:
                high_fps_count += 1
            print(f"[CLIP] {rel}")
            print(f"   Resolution: {info['resolution']} | FPS: {info['fps']} | Duration: {info['duration_sec']}s | Frames: {info['frames']} | Codec: {info['codec']} | Size: {info['size_mb']} MB")
        else:
            print(f"[WARNING] {rel}: {info['error']}")
            
    print(f"\nSummary:")
    print(f" Total verified MP4s : {len(table_data)}")
    print(f" High-FPS Clips (>=50): {high_fps_count} / {len(table_data)}")
    print(f"=======================================================\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify extracted dataset video clips")
    parser.add_argument("--dir", "-d", type=str, default="dataset_clips", help="Directory containing MP4 clips")
    args = parser.parse_args()
    
    verify_output_directory(args.dir)
