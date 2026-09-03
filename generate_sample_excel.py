import os
import sys
import pandas as pd

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def create_sample_excel(file_path: str = "cricket_clips_input.xlsx"):
    """
    Creates an example Excel file with YouTube links, timestamp markers, and Subfolder names
    specifically formatted for cricket bowling clip dataset building.
    Files will be named: <subfolder>_video000.mp4, <subfolder>_video001.mp4, etc.
    """
    data = [
        {
            "Subfolder": "fast_bowling",
            "YouTube_URL": "https://www.youtube.com/watch?v=xPE0VH2cyK4",
            "Start_Time": "00:00:03",
            "End_Time": "00:00:10"
        },
        {
            "Subfolder": "spin_bowling",
            "YouTube_URL": "https://www.youtube.com/watch?v=xPE0VH2cyK4",
            "Start_Time": "00:00:11",
            "End_Time": "00:00:18"
        },
        {
            "Subfolder": "fast_bowling",
            "YouTube_URL": "https://www.youtube.com/watch?v=xPE0VH2cyK4",
            "Start_Time": "00:00:05",
            "End_Time": "00:00:12"
        }
    ]
    
    df = pd.DataFrame(data)
    
    # Save to Excel format
    df.to_excel(file_path, index=False, engine="openpyxl")
    print(f"Sample Excel sheet created successfully at: {os.path.abspath(file_path)}")
    print(f"\nColumns included:")
    for col in df.columns:
        print(f" - {col}")
    print(f"\nClips will be saved as: subfolder_video000.mp4, subfolder_video001.mp4, etc.!")

if __name__ == "__main__":
    create_sample_excel()
