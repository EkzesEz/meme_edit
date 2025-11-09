# Video Watermark Processor

A Python script that adds rotated/scaled watermarks to videos and converts them to 9:16 aspect ratio.

## Features

- Processes all videos in a specified folder
- Converts videos to 9:16 aspect ratio
- Adds black padding if needed
- Applies watermark with:
    - Random rotation (±8°)
    - Random scaling (±15%)
    - Adjustable opacity
    - Random position (left/right bottom corner)

## Requirements

- ffmpeg and ffprobe in system PATH
- Python 3.x
- Pillow library (`pip install pillow`)

## Setup

1. Create folders:
     - `videos/` - put your input videos here
     - `watermark/` - put your watermark image as `white.jpg`
     - `output/` - processed videos will appear here

## Configuration

Key parameters in the script:

```python
WM_REL_WIDTH = 0.25    # Watermark width relative to video width
WM_OPACITY = 0.1       # Watermark opacity (0-1)
ROTATE_DEG_RANGE = 8   # Random rotation range in degrees
MARGIN_X = 0.05        # Horizontal margin (5%)
MARGIN_Y = 0.5         # Vertical margin from bottom (50%)
```

## Usage

Simply run the script:

```bash
python3 video_processor.py
```

Processed videos will be saved in the `output/` folder with "_wm" suffix.

## Supported Formats

Input video formats: .mp4, .mov, .mkv, .avi, .webm, .mpeg, .mpg, .flv