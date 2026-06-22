import csv
import subprocess
import os

# Input files
VIDEO_FILE = "video.mp4"
CSV_FILE = "timestamps.csv"
OUTPUT_DIR = "clips"

# Make output folder
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Read timestamps
with open(CSV_FILE, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        clip_type = row["type"]
        start = row["start"]
        end = row["end"]
        label = row["label"].replace(" ", "_").replace("/", "-")  # safe filename

        output_file = os.path.join(OUTPUT_DIR, f"{clip_type}_{label}.mp4")

        # ffmpeg command
        cmd = [
            "ffmpeg", "-y",
            "-i", VIDEO_FILE,
            "-ss", start,
            "-to", end,
            "-c", "copy",
            output_file
        ]

        print("Running:", " ".join(cmd))
        subprocess.run(cmd)

