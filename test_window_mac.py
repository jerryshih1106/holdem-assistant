"""最小視窗測試 — 確認 macOS 能顯示 tkinter 視窗"""
import sys, os

# 必須在 Tk() 之前
if sys.platform == 'darwin':
    try:
        import AppKit
        app = AppKit.NSApplication.sharedApplication()
        app.setActivationPolicy_(0)
        app.activateIgnoringOtherApps_(True)
        print('[AppKit] setActivationPolicy OK')
    except Exception as e:
        print(f'[AppKit] 失敗: {e}')
        try:
            import ctypes, ctypes.util
            carbon = ctypes.CDLL(ctypes.util.find_library('Carbon'))
            class PSN(ctypes.Structure):
                _fields_ = [('lo', ctypes.c_ulong), ('hi', ctypes.c_ulong)]
            psn = PSN(0, 0)
            carbon.GetCurrentProcess(ctypes.byref(psn))
            r = carbon.TransformProcessType(ctypes.byref(psn), 1)
            print(f'[Carbon] TransformProcessType result={r}')
        except Exception as e2:
            print(f'[Carbon] 失敗: {e2}')

import tkinter as tk

root = tk.Tk()
root.title('視窗測試 — 你看得到這個嗎？')
root.geometry('400x150+300+300')
root.configure(bg='#1A1A2E')
root.attributes('-topmost', True)

tk.Label(root, text='✓ 視窗正常顯示！', bg='#1A1A2E',
         fg='#00FF88', font=('Courier', 20, 'bold')).pack(expand=True)
tk.Label(root, text='5 秒後自動關閉', bg='#1A1A2E',
         fg='#888888', font=('Courier', 11)).pack()

root.update_idletasks()
root.lift()
root.focus_force()

root.after(5000, root.destroy)
root.mainloop()
print('測試結束')
