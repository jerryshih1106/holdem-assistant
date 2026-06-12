"""Screen capture — PrintWindow（視窗擷取）/ dxcam / mss 三種模式。"""

import numpy as np
import cv2
from typing import Optional, Tuple


def list_windows() -> list:
    """回傳所有可見視窗的 (hwnd, title) 清單。"""
    import win32gui
    result = []
    def _cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title.strip():
                result.append((hwnd, title))
    win32gui.EnumWindows(_cb, None)
    return result


def capture_window(hwnd: int, region: Optional[Tuple[int,int,int,int]] = None) -> Optional[np.ndarray]:
    """用 PrintWindow 擷取指定視窗，回傳 BGR ndarray 或 None。"""
    import win32gui, win32ui, win32con
    try:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        w, h = right - left, bottom - top
        if w <= 0 or h <= 0:
            return None

        hwnd_dc  = win32gui.GetWindowDC(hwnd)
        mfc_dc   = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc  = mfc_dc.CreateCompatibleDC()
        bmp      = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(mfc_dc, w, h)
        save_dc.SelectObject(bmp)

        # PW_RENDERFULLCONTENT=2 可抓到硬體加速內容
        import ctypes
        result = ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)

        bmp_info = bmp.GetInfo()
        raw = bmp.GetBitmapBits(True)
        frame = np.frombuffer(raw, dtype=np.uint8).reshape(
            bmp_info['bmHeight'], bmp_info['bmWidth'], 4)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)
        win32gui.DeleteObject(bmp.GetHandle())

        if result == 0:
            return None  # PrintWindow 失敗

        if region:
            rx, ry, rw, rh = region
            frame = frame[ry:ry+rh, rx:rx+rw]

        return frame
    except Exception as e:
        print(f'[PrintWindow] {e}')
        return None


class ScreenCapture:
    def __init__(self, region: Optional[Tuple[int, int, int, int]] = None):
        self._region  = region
        self._hwnd    = None   # 視窗擷取模式時設定
        self._dxcam   = None
        self._sct     = None
        self._monitor_mss = None
        self._init_capture()

    # ── 初始化 ────────────────────────────────────────────────

    def _init_capture(self):
        if self._hwnd is not None:
            return  # 視窗模式，不需要初始化螢幕擷取
        try:
            import dxcam
            region = self._region
            left, top, w, h = region if region else (0, 0, 0, 0)
            rect = (left, top, left + w, top + h) if region else None
            self._dxcam = dxcam.create(output_color="BGR", region=rect)
            print(f'[Capture] dxcam 初始化（region={rect}）')
        except Exception as e:
            print(f'[Capture] dxcam 失敗 ({e})，改用 mss')
            self._init_mss(self._region)

    def _init_mss(self, region):
        import mss as _mss
        self._sct = _mss.MSS()
        if region is None:
            self._monitor_mss = self._sct.monitors[1]
        else:
            left, top, w, h = region
            self._monitor_mss = {"left": left, "top": top, "width": w, "height": h}

    # ── 切換模式 ──────────────────────────────────────────────

    def set_window(self, hwnd: int):
        """切換為視窗擷取模式（PrintWindow）。"""
        self._hwnd = hwnd
        import win32gui
        title = win32gui.GetWindowText(hwnd)
        print(f'[Capture] 視窗模式：{title!r} (hwnd={hwnd})')

    def set_screen_mode(self):
        """切換回螢幕擷取模式。"""
        self._hwnd = None

    def set_region(self, region: Optional[Tuple[int, int, int, int]]):
        self._region = region
        if self._hwnd is not None:
            return  # 視窗模式下 region 是視窗內的裁切範圍，不需重初始化
        if self._dxcam is not None:
            try: del self._dxcam
            except Exception: pass
            self._dxcam = None
        if self._sct is not None:
            try: self._sct.close()
            except Exception: pass
            self._sct = None
        self._init_capture()

    # ── 擷取 ──────────────────────────────────────────────────

    def grab(self) -> np.ndarray:
        if self._hwnd is not None:
            frame = capture_window(self._hwnd, self._region)
            if frame is not None:
                return frame
            print('[Capture] PrintWindow 回傳空，fallback 到螢幕擷取')

        if self._dxcam is not None:
            frame = self._dxcam.grab()
            if frame is not None:
                return frame

        return self._grab_mss()

    def _grab_mss(self) -> np.ndarray:
        if self._sct is None:
            self._init_mss(self._region)
        raw = self._sct.grab(self._monitor_mss)
        frame = np.array(raw)
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

    def grab_with_preview(self) -> np.ndarray:
        frame = self.grab()
        preview = cv2.resize(frame, (960, 540))
        cv2.imshow("Screen Preview", preview)
        cv2.waitKey(1)
        return frame

    @staticmethod
    def list_monitors() -> list:
        import mss as _mss
        with _mss.MSS() as sct:
            return sct.monitors

    def close(self):
        if self._dxcam is not None:
            try: del self._dxcam
            except Exception: pass
        if self._sct is not None:
            try: self._sct.close()
            except Exception: pass
