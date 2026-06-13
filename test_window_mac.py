"""最小視窗測試 v2 — Tk() 先建立，之後再用 NSApp 激活"""
import sys

import tkinter as tk

root = tk.Tk()
root.title('視窗測試 — 你看得到嗎？')
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

# Tk() 建立後才能安全呼叫 NSApp
if sys.platform == 'darwin':
    try:
        import AppKit
        AppKit.NSApp.activateIgnoringOtherApps_(True)
        print('[NSApp] activateIgnoringOtherApps OK')
    except Exception as e:
        print(f'[NSApp] 失敗: {e}')

root.after(5000, root.destroy)
root.mainloop()
print('測試結束')
