"""截圖除錯工具 — 列出視窗 / 存截圖 / 顯示預覽。

用法（在 holdem-assistant 目錄下執行）：
  python debug_capture.py              # 列出所有視窗
  python debug_capture.py save         # 截全螢幕存成 debug_capture.png
  python debug_capture.py preview      # 開視窗即時預覽（按 q 離開）
  python debug_capture.py window N8    # 截標題含 "N8" 的視窗並存圖 + 預覽
"""

import sys
import cv2
import numpy as np
from detection.screen_capture import ScreenCapture, list_windows, capture_window


def cmd_list():
    wins = list_windows()
    print(f"{'HWND':>10}  {'Title'}")
    print("-" * 60)
    for hwnd, title in wins:
        print(f"{hwnd:>10}  {title}")
    print(f"\n共 {len(wins)} 個視窗")


def cmd_save(region=None):
    sc = ScreenCapture(region=region)
    frame = sc.grab()
    path = "debug_capture.png"
    cv2.imwrite(path, frame)
    print(f"已存至 {path}  ({frame.shape[1]}x{frame.shape[0]})")
    sc.close()


def cmd_preview(region=None):
    sc = ScreenCapture(region=region)
    import time
    print("截圖中，存成 _preview_latest.png（每 0.5 秒更新一次），Ctrl+C 停止...")
    try:
        while True:
            frame = sc.grab()
            preview = cv2.resize(frame, (960, 540))
            cv2.imwrite("_preview_latest.png", preview)
            print(f"\r[{time.strftime('%H:%M:%S')}] 已存 _preview_latest.png  {frame.shape[1]}x{frame.shape[0]}", end="")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n停止")
    sc.close()


def cmd_window(keyword):
    wins = list_windows()
    matched = [(h, t) for h, t in wins if keyword.lower() in t.lower()]
    if not matched:
        print(f"找不到標題含 '{keyword}' 的視窗。目前視窗清單：")
        cmd_list()
        return
    hwnd, title = matched[0]
    print(f"找到視窗：[{hwnd}] {title!r}")
    frame = capture_window(hwnd)
    if frame is None:
        print("截圖失敗（PrintWindow 回傳 None）")
        return
    path = "debug_capture.png"
    cv2.imwrite(path, frame)
    print(f"已存至 {path}  ({frame.shape[1]}x{frame.shape[0]})")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        cmd_list()
    elif args[0] == "save":
        cmd_save()
    elif args[0] == "preview":
        cmd_preview()
    elif args[0] == "window" and len(args) >= 2:
        cmd_window(args[1])
    else:
        print(__doc__)
