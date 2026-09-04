# Dataset Builder Automation

A simple tool to turn timestamped YouTube links into organized MP4 clips for model training.

## What it does
- Reads Excel/CSV with video URL, start time, end time, and optional label/subfolder
- Downloads each source video once (cache), then cuts clips fast with FFmpeg
- Saves clips with clean, consistent names
- Includes a lightweight Flask UI for non-CLI use

## Project structure
- `dataset_builder.py` — core pipeline (parse sheet, cache videos, cut clips)
- `app.py` — Flask web app
- `generate_sample_excel.py` — generates a sample input file
- `verify_dataset.py` — inspects generated MP4 files with `ffprobe`

## Requirements
- Python 3.9+
- FFmpeg + FFprobe available in PATH
- Python packages:
  - `flask`
  - `pandas`
  - `yt-dlp`
  - `openpyxl`

Install:
```bash
pip install flask pandas yt-dlp openpyxl
```

## Input format
Expected columns (flexible naming is supported):
- URL
- Start time
- End time
- Subfolder/Label (optional)

Time format can be:
- `HH:MM:SS`
- `MM:SS`
- seconds as number

## Run (CLI)
```bash
python dataset_builder.py --excel cricket_clips_input.xlsx --out dataset_clips --workers 4 --max-res 720
```

Useful flags:
- `--overwrite` overwrite existing clips
- `--no-subfolders` save all clips in one folder

## Run (Web UI)
```bash
python app.py
```
Then open `http://127.0.0.1:5000`.

## Verify output clips
```bash
python verify_dataset.py --dir dataset_clips
```

## Notes
- Keep `max-res` at 720p for speed unless quality needs are higher.
- Reused source videos are cached in `raw_videos/`.
