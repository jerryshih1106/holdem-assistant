"""macOS crash 隔離測試 v2"""
import sys, os
if sys.platform == 'darwin':
    os.environ.setdefault('OBJC_DISABLE_INITIALIZE_FORK_SAFETY', 'YES')
    os.environ.setdefault('PYTORCH_ENABLE_MPS_FALLBACK', '1')
    os.environ.setdefault('OMP_NUM_THREADS', '1')
    os.environ.setdefault('MKL_NUM_THREADS', '1')

print(f"Python {sys.version}\nPlatform: {sys.platform}\n")

print("[1] numpy..."); import numpy as np; print(f"    {np.__version__} OK")
print("[2] cv2...");   import cv2;          print(f"    {cv2.__version__} OK")
print("[3] torch...")
import torch
print(f"    {torch.__version__}  MPS={torch.backends.mps.is_available()}")

print("[4] tkinter...")
import tkinter as tk
root = tk.Tk(); root.withdraw()
print(f"    OK  DPI={root.winfo_fpixels('1i'):.0f}")
root.destroy()

print("[5] mss...")
import mss
with mss.MSS() as sct:
    print(f"    OK  monitors={len(sct.monitors)}")

print("[6] YOLO import...")
from ultralytics import YOLO
print("    import OK")

print("[7] keyboard (macOS 應跳過)...")
if sys.platform == 'darwin':
    print("    跳過（CGEventTap → SIGBUS 風險）")
else:
    try:
        import keyboard
        print("    OK")
    except Exception as e:
        print(f"    {e}")

print("[8] YOLO 載入模型（若有 .pt 檔）...")
import os as _os
model_path = _os.path.join(_os.path.dirname(__file__), "models", "playing_cards.pt")
if _os.path.exists(model_path):
    m = YOLO(model_path)
    if sys.platform == 'darwin':
        m.to('cpu')
    print(f"    載入成功，強制 CPU")
    dummy = np.zeros((640, 640, 3), dtype=np.uint8)
    results = m.predict(source=dummy, conf=0.6, iou=0.45, verbose=False, device='cpu')
    print(f"    predict OK  detections={sum(len(r.boxes) for r in results)}")
else:
    print(f"    跳過（{model_path} 不存在）")

print("\n=== 全部通過 ===")
