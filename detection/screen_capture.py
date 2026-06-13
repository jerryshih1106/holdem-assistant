"""Screen capture — PrintWindow（Windows）/ mss（跨平台）雙模式。

macOS 修正：
- mss.MSS() 物件改為 thread-local，避免跨執行緒 SIGBUS
- win32gui / dxcam 全部用 platform guard 保護
- 新增 macOS Screen Recording 權限提示
"""

import sys
import threading
import numpy as np
import cv2
from typing import Optional, Tuple

_IS_WIN = sys.platform == 'win32'
_IS_MAC = sys.platform == 'darwin'

# Thread-local mss 實例：每個執行緒各自持有，避免 macOS Quartz SIGBUS
_tls = threading.local()


def _get_mss_sct():
    """回傳目前執行緒的 mss.MSS() 實例（不存在就建立）。"""
    if not hasattr(_tls, 'sct') or _tls.sct is None:
        import mss as _mss
        _tls.sct = _mss.mss()
    return _tls.sct


def list_windows() -> list:
    """回傳所有可見視窗的 (hwnd, title) 清單（Windows only）。"""
    if not _IS_WIN:
        return []
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
    """用 PrintWindow 擷取指定視窗（Windows only），回傳 BGR ndarray 或 None。"""
    if not _IS_WIN:
        return None
    import win32gui, win32ui, win32con, ctypes
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
            return None

        if region:
            rx, ry, rw, rh = region
            frame = frame[ry:ry+rh, rx:rx+rw]

        return frame
    except Exception as e:
        print(f'[PrintWindow] {e}')
        return None


def check_mac_screen_permission() -> bool:
    """macOS：用 CGPreflightScreenCaptureAccess 確認螢幕錄製權限。
    回傳 True=已授權，False=未授權。
    沒授權時同時觸發系統請求彈窗讓使用者授權。
    """
    if not _IS_MAC:
        return True
    try:
        import ctypes, ctypes.util
        cg = ctypes.CDLL(ctypes.util.find_library('CoreGraphics'))
        # CGPreflightScreenCaptureAccess：macOS 11+ 才有；回傳 bool
        cg.CGPreflightScreenCaptureAccess.restype = ctypes.c_bool
        has_perm = cg.CGPreflightScreenCaptureAccess()
        if not has_perm:
            # 觸發系統授權彈窗（使用者點允許後需重啟 Terminal）
            cg.CGRequestScreenCaptureAccess.restype = ctypes.c_bool
            cg.CGRequestScreenCaptureAccess()
            print('[Capture] ⚠️  macOS 螢幕錄製權限未開啟！')
            print('  → 系統設定 → 隱私權與安全性 → 螢幕錄製')
            print('  → 勾選 Terminal（或 iTerm2）→ 重新啟動 Terminal 再執行')
        return has_perm
    except Exception:
        # CGPreflightScreenCaptureAccess 在 macOS 10.x 不存在，直接略過
        return True


def _check_mac_screen_permission():
    check_mac_screen_permission()


class ScreenCapture:
    def __init__(self, region: Optional[Tuple[int, int, int, int]] = None):
        self._region  = region
        self._hwnd    = None
        self._dxcam   = None
        self._monitor_mss: Optional[dict] = None
        self._lock = threading.Lock()  # dxcam 非 thread-safe

        if _IS_MAC:
            _check_mac_screen_permission()
        self._init_capture()

    def _init_capture(self):
        if self._hwnd is not None:
            return

        if _IS_WIN:
            try:
                import dxcam
                region = self._region
                left, top, w, h = region if region else (0, 0, 0, 0)
                rect = (left, top, left + w, top + h) if region else None
                self._dxcam = dxcam.create(output_color="BGR", region=rect)
                print(f'[Capture] dxcam 初始化（region={rect}）')
                return
            except Exception as e:
                print(f'[Capture] dxcam 失敗 ({e})，改用 mss')

        # mss fallback（Windows + macOS 通用）
        self._update_mss_monitor(self._region)
        print(f'[Capture] mss 模式（region={self._region}）')

    def _update_mss_monitor(self, region):
        """更新 mss monitor dict（實際 sct 物件在 grab 時 thread-local 建立）。"""
        if region is None:
            # 全螢幕：defer to grab time（各 thread 拿各自的 monitors[1]）
            self._monitor_mss = None
        else:
            left, top, w, h = region
            self._monitor_mss = {"left": left, "top": top, "width": w, "height": h}

    # ── 切換模式 ──────────────────────────────────────────────

    def set_window(self, hwnd: int):
        if not _IS_WIN:
            print('[Capture] set_window 只支援 Windows')
            return
        self._hwnd = hwnd
        import win32gui
        title = win32gui.GetWindowText(hwnd)
        print(f'[Capture] 視窗模式：{title!r} (hwnd={hwnd})')

    def set_screen_mode(self):
        self._hwnd = None

    def set_region(self, region: Optional[Tuple[int, int, int, int]]):
        self._region = region
        if self._hwnd is not None:
            return
        if self._dxcam is not None:
            try: del self._dxcam
            except Exception: pass
            self._dxcam = None
        # 讓各執行緒的 thread-local sct 在下次 grab 時重建
        _tls.sct = None
        self._init_capture()

    # ── 擷取 ──────────────────────────────────────────────────

    def grab(self) -> np.ndarray:
        if self._hwnd is not None and _IS_WIN:
            frame = capture_window(self._hwnd, self._region)
            if frame is not None:
                return frame
            print('[Capture] PrintWindow 回傳空，fallback 到螢幕擷取')

        if self._dxcam is not None:
            with self._lock:
                frame = self._dxcam.grab()
            if frame is not None:
                return frame

        return self._grab_mss()

    def _grab_mss(self) -> np.ndarray:
        """使用 thread-local mss 實例截圖（macOS thread-safe）。"""
        sct = _get_mss_sct()
        monitor = self._monitor_mss
        if monitor is None:
            monitor = sct.monitors[1]  # 主螢幕
        raw = sct.grab(monitor)
        frame = np.array(raw)
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

    def grab_with_preview(self) -> np.ndarray:
        # cv2.imshow() 在 macOS 上與 tkinter 共存會 segfault，改儲存成檔案
        frame = self.grab()
        try:
            cv2.imwrite("_preview_latest.png", cv2.resize(frame, (960, 540)))
        except Exception:
            pass
        return frame

    @staticmethod
    def list_monitors() -> list:
        import mss as _mss
        with _mss.mss() as sct:
            return sct.monitors

    def close(self):
        if self._dxcam is not None:
            try: del self._dxcam
            except Exception: pass
        # thread-local sct 由各執行緒自行 GC，不需要統一關閉
