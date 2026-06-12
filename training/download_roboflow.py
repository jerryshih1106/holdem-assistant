"""
Download playing cards dataset from Roboflow.

Set ROBOFLOW_API_KEY env var before running:
    $env:ROBOFLOW_API_KEY = "your_key"
    python training/download_roboflow.py
"""

import os


def main():
    api_key = os.environ.get("ROBOFLOW_API_KEY")
    if not api_key:
        print("Error: set ROBOFLOW_API_KEY environment variable first.")
        return

    try:
        from roboflow import Roboflow
    except ImportError:
        print("Install roboflow: pip install roboflow")
        return

    rf = Roboflow(api_key=api_key)
    project = rf.workspace("augmented-startups").project("playing-cards-ow0bj")
    dataset = project.version(4).download("yolov8", location="training/dataset")
    print(f"Dataset downloaded to: {dataset.location}")
    print("\nNow run:")
    print("  python training/train.py --data training/dataset/data.yaml")


if __name__ == "__main__":
    main()
