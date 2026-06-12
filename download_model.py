"""
Download a pre-trained playing cards YOLO model.

Uses the 'playing-cards-ow0bj' model from Roboflow Universe
trained on 52 card classes in YOLO format.

Run: python download_model.py
"""

import os
import urllib.request
import sys

# YOLOv8m trained on 52-class synthetic playing cards dataset
# Source: https://github.com/TeogopK/Playing-Cards-Object-Detection
MODEL_URL = (
    "https://raw.githubusercontent.com/TeogopK/Playing-Cards-Object-Detection/"
    "main/final_models/yolov8m_synthetic.pt"
)

FALLBACK_URLS = [
    # Backup: YOLOv8s trained on 52 classes, 99.5% mAP (Google Drive — manual download)
    # https://drive.google.com/file/d/1AqZnW6dI6flFZvGxAn6A9apDNSviXZ5f/view
]

DEST = os.path.join("models", "playing_cards.pt")


def download(url: str, dest: str):
    print(f"Downloading from:\n  {url}")
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    def _progress(block_count, block_size, total_size):
        if total_size > 0:
            pct = min(100, block_count * block_size * 100 // total_size)
            bar = "#" * (pct // 4)
            sys.stdout.write(f"\r  [{bar:<25}] {pct}%")
            sys.stdout.flush()

    urllib.request.urlretrieve(url, dest, reporthook=_progress)
    print(f"\nSaved to: {dest}")


def main():
    if os.path.exists(DEST):
        print(f"Model already exists at: {DEST}")
        return

    try:
        download(MODEL_URL, DEST)
    except Exception as e:
        print(f"\nDownload failed: {e}")
        print("\n--- Manual options ---")
        print("Option A: Train your own model")
        print("  1. Export dataset from Roboflow (playing-cards-ow0bj)")
        print("  2. Run: python training/train.py")
        print()
        print("Option B: Use Roboflow API")
        print("  pip install roboflow")
        print("  Then set ROBOFLOW_API_KEY and run: python training/download_roboflow.py")


if __name__ == "__main__":
    main()
