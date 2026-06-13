"""macOS 螢幕錄製權限診斷工具"""
import sys, subprocess
print(f'Platform: {sys.platform}')

# ── 1. CoreGraphics API 確認 ──────────────────────────────────────
import ctypes, ctypes.util
lib = ctypes.util.find_library('CoreGraphics')
print(f'CoreGraphics lib: {lib}')

cg = ctypes.CDLL(lib)

try:
    cg.CGPreflightScreenCaptureAccess.restype = ctypes.c_bool
    r1 = cg.CGPreflightScreenCaptureAccess()
    print(f'CGPreflightScreenCaptureAccess  = {r1}')
except Exception as e:
    print(f'CGPreflightScreenCaptureAccess  ERROR: {e}')
    r1 = None

try:
    cg.CGRequestScreenCaptureAccess.restype = ctypes.c_bool
    r2 = cg.CGRequestScreenCaptureAccess()
    print(f'CGRequestScreenCaptureAccess    = {r2}')
except Exception as e:
    print(f'CGRequestScreenCaptureAccess    ERROR: {e}')
    r2 = None

# ── 2. mss 截圖基本資訊 ───────────────────────────────────────────
import mss, numpy as np
with mss.mss() as sct:
    monitors = sct.monitors
    print(f'mss monitors: {len(monitors)}  →  {monitors}')
    img = np.array(sct.grab(sct.monitors[1]))
    print(f'截圖 shape={img.shape}  max={img.max()}  mean={img.mean():.1f}')

# ── 3. 可見視窗數量（無權限時只會看到自己的視窗）──────────────────
try:
    import Quartz
    opts = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
    wins = Quartz.CGWindowListCopyWindowInfo(opts, Quartz.kCGNullWindowID)
    print(f'可見視窗數: {len(wins) if wins else 0}（< 5 表示螢幕錄製權限未開）')
    if wins:
        for w in list(wins)[:8]:
            print(f'  {w.get("kCGWindowOwnerName","?"):30s}  {w.get("kCGWindowName","")}')
except Exception as e:
    print(f'Quartz CGWindowListCopyWindowInfo: {e}')

# ── 4. 直接打開系統設定到螢幕錄製頁面 ────────────────────────────
print()
print('=== 正在開啟 系統設定 → 螢幕錄製 ===')
subprocess.run([
    'open',
    'x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture'
])
print('請在系統設定中勾選 Terminal（或 Python），然後重新啟動 Terminal')
