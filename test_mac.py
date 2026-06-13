"""macOS crash 隔離測試 — 逐步 import 找出哪個炸"""
import sys, os
if sys.platform == 'darwin':
    os.environ.setdefault('OBJC_DISABLE_INITIALIZE_FORK_SAFETY', 'YES')
    os.environ.setdefault('PYTORCH_ENABLE_MPS_FALLBACK', '1')
    os.environ.setdefault('CUDA_VISIBLE_DEVICES', '')
    os.environ.setdefault('OMP_NUM_THREADS', '1')
    os.environ.setdefault('MKL_NUM_THREADS', '1')
print(f"Python {sys.version}")
print(f"Platform: {sys.platform}")

print("\n[1] numpy...")
import numpy as np
print(f"    numpy {np.__version__} OK")

print("[2] cv2...")
import cv2
print(f"    cv2 {cv2.__version__} OK")

print("[3] torch...")
import torch
print(f"    torch {torch.__version__}  MPS={torch.backends.mps.is_available()}  OK")

print("[4] tkinter...")
import tkinter as tk
root = tk.Tk()
root.withdraw()
print(f"    tkinter OK  DPI={root.winfo_fpixels('1i'):.0f}")
root.destroy()

print("[5] mss...")
import mss
with mss.mss() as sct:
    print(f"    mss OK  monitors={len(sct.monitors)}")

print("[6] ultralytics YOLO import...")
from ultralytics import YOLO
print(f"    ultralytics OK")

print("\n=== 全部通過，crash 在 main.py 的邏輯裡 ===")
