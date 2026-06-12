"""
Fine-tune or train a YOLO model on your custom poker card dataset.

Usage:
    python training/train.py --data dataset/data.yaml --epochs 50

Prerequisites:
    - ultralytics installed
    - Dataset in YOLO format under training/dataset/
      (images/ and labels/ subdirs with train/val splits)
"""

import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Train YOLO for poker card detection")
    parser.add_argument("--data", default="training/dataset/data.yaml",
                        help="Path to dataset YAML")
    parser.add_argument("--model", default="yolov8n.pt",
                        help="Base model (yolov8n/s/m/l/x.pt)")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--output", default="models/playing_cards.pt",
                        help="Where to copy best weights after training")
    args = parser.parse_args()

    from ultralytics import YOLO

    model = YOLO(args.model)
    results = model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        project="training/runs",
        name="poker_cards",
        save=True,
    )

    # Copy best weights to models/
    best = Path(results.save_dir) / "weights" / "best.pt"
    if best.exists():
        import shutil
        shutil.copy(best, args.output)
        print(f"\nBest weights copied to: {args.output}")
    else:
        print(f"\nTraining complete. Best weights at: {best}")


if __name__ == "__main__":
    main()
