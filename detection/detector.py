"""YOLO-based card detector wrapping ultralytics."""

import os
from typing import List, Optional
import numpy as np

from detection.card_mapper import Detection


class CardDetector:
    def __init__(self, model_path: str, conf: float = 0.60, iou: float = 0.45):
        self._conf = conf
        self._iou = iou
        self._model = None
        self._model_path = model_path
        self._load_model()

    def _load_model(self):
        if not os.path.exists(self._model_path):
            print(f"[Detector] Model not found at '{self._model_path}'.")
            print("[Detector] Run: python download_model.py  to fetch the default model.")
            return
        try:
            from ultralytics import YOLO
            self._model = YOLO(self._model_path)
            print(f"[Detector] Loaded model: {self._model_path}")
        except Exception as e:
            print(f"[Detector] Failed to load model: {e}")

    def is_ready(self) -> bool:
        return self._model is not None

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """Run inference and return Detection list."""
        if self._model is None:
            return []

        results = self._model.predict(
            source=frame,
            conf=self._conf,
            iou=self._iou,
            verbose=False,
        )

        detections: List[Detection] = []
        h, w = frame.shape[:2]

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                cls_id = int(box.cls[0])
                label = result.names[cls_id]
                conf = float(box.conf[0])
                # xyxy absolute → normalized xywh
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                xc = ((x1 + x2) / 2) / w
                yc = ((y1 + y2) / 2) / h
                bw = (x2 - x1) / w
                bh = (y2 - y1) / h
                detections.append(Detection(label, conf, (xc, yc, bw, bh)))

        return detections

    def annotate(self, frame: np.ndarray, detections: List[Detection]) -> np.ndarray:
        """Draw bounding boxes and labels onto frame copy."""
        import cv2
        out = frame.copy()
        h, w = frame.shape[:2]
        for det in detections:
            xc, yc, bw, bh = det.bbox
            x1 = int((xc - bw / 2) * w)
            y1 = int((yc - bh / 2) * h)
            x2 = int((xc + bw / 2) * w)
            y2 = int((yc + bh / 2) * h)
            color = (0, 255, 0) if det.card else (0, 100, 255)
            cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
            label = f"{det.card or det.label} {det.confidence:.2f}"
            cv2.putText(out, label, (x1, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX,
                        0.55, color, 2, cv2.LINE_AA)
        return out
