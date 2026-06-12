"""
Session EV 漏洞視覺化面板 (F7)

即時顯示 session_tracker 的決策數據：
  - 正確率、總 EV 損失、每100手損失
  - 各漏洞類別的條形圖（按損失大小排序）
  - 最差街道 / 最差位置
  - 建議改進行動

使用方式：
    from ui.session_panel import SessionPanel
    panel = SessionPanel(root)
    panel.toggle()        # F7 熱鍵
"""

import tkinter as tk
from tkinter import ttk
import time
from typing import Optional
from poker.session_tracker import get_tracker, reset_tracker, SessionReport, LeakSummary


# ── 色彩常數（與其他面板一致）────────────────────────────────────────────────
BG     = '#0D1117'
BG2    = '#161B22'
BG3    = '#21262D'
FG     = '#E6EDF3'
DIM    = '#8B949E'
ACCENT = '#58A6FF'
GREEN  = '#56D364'
YELLOW = '#E3B341'
RED    = '#FF7B54'
BORDER = '#30363D'

FONT_TITLE  = ('Consolas', 13, 'bold')
FONT_HEADER = ('Consolas', 10, 'bold')
FONT_BODY   = ('Consolas', 9)
FONT_LARGE  = ('Consolas', 18, 'bold')
FONT_SMALL  = ('Consolas', 8)


class SessionPanel:
    """Session EV 漏洞視覺化面板（Toplevel 視窗）。"""

    def __init__(self, master: tk.Misc):
        self.master  = master
        self._win:   Optional[tk.Toplevel] = None
        self._after_id = None

    # ── 視窗生命週期 ─────────────────────────────────────────────────────────

    def toggle(self):
        if self._win and self._win.winfo_exists():
            self._win.destroy()
            self._win = None
            if self._after_id:
                self.master.after_cancel(self._after_id)
        else:
            self._build()

    def _build(self):
        win = tk.Toplevel(self.master)
        win.title('Session EV 漏洞面板')
        win.configure(bg=BG)
        win.geometry('640x560')
        win.resizable(True, True)
        win.protocol('WM_DELETE_WINDOW', self.toggle)
        self._win = win

        self._build_ui(win)
        self._refresh()

    def _build_ui(self, win: tk.Toplevel):
        """建立靜態 UI 骨架。"""
        # ── 標題列 ───────────────────────────────────────────────────────────
        hdr = tk.Frame(win, bg=BG2, pady=6)
        hdr.pack(fill='x', padx=1, pady=(1, 0))

        tk.Label(hdr, text='Session EV 漏洞追蹤', font=FONT_TITLE,
                 bg=BG2, fg=ACCENT).pack(side='left', padx=12)

        self._session_id_lbl = tk.Label(hdr, text='', font=FONT_SMALL,
                                        bg=BG2, fg=DIM)
        self._session_id_lbl.pack(side='left', padx=4)

        # 按鈕區
        btn_frame = tk.Frame(hdr, bg=BG2)
        btn_frame.pack(side='right', padx=8)

        tk.Button(btn_frame, text='新的一手', font=FONT_BODY,
                  bg=BG3, fg=FG, relief='flat', padx=8,
                  command=self._new_hand).pack(side='left', padx=3)
        tk.Button(btn_frame, text='重置 Session', font=FONT_BODY,
                  bg='#3A1F1F', fg=RED, relief='flat', padx=8,
                  command=self._reset_session).pack(side='left', padx=3)
        tk.Button(btn_frame, text='重新整理', font=FONT_BODY,
                  bg=BG3, fg=ACCENT, relief='flat', padx=8,
                  command=self._refresh).pack(side='left', padx=3)

        # ── 摘要列 ───────────────────────────────────────────────────────────
        summary_frame = tk.Frame(win, bg=BG3, padx=10, pady=8)
        summary_frame.pack(fill='x', padx=1)

        self._acc_lbl    = self._stat_widget(summary_frame, '正確率',   '0%',    GREEN)
        self._ev_lbl     = self._stat_widget(summary_frame, '總EV損失', '0 BB',  RED)
        self._ev100_lbl  = self._stat_widget(summary_frame, 'EV/100手', '0 BB',  YELLOW)
        self._dec_lbl    = self._stat_widget(summary_frame, '決策次數', '0',     FG)
        self._hand_lbl   = self._stat_widget(summary_frame, '手牌數',   '0',     DIM)

        # ── 分隔 ─────────────────────────────────────────────────────────────
        tk.Frame(win, bg=BORDER, height=1).pack(fill='x', padx=1)

        # ── 漏洞條形圖區 ─────────────────────────────────────────────────────
        tk.Label(win, text='漏洞排行（EV 損失）', font=FONT_HEADER,
                 bg=BG, fg=DIM, anchor='w').pack(fill='x', padx=14, pady=(8, 2))

        self._leaks_frame = tk.Frame(win, bg=BG)
        self._leaks_frame.pack(fill='both', expand=True, padx=10, pady=4)

        # ── 底部資訊列 ───────────────────────────────────────────────────────
        tk.Frame(win, bg=BORDER, height=1).pack(fill='x', padx=1)

        info_frame = tk.Frame(win, bg=BG2, padx=10, pady=6)
        info_frame.pack(fill='x')

        self._street_lbl = tk.Label(info_frame, text='最差街道: --', font=FONT_BODY,
                                    bg=BG2, fg=DIM)
        self._street_lbl.pack(side='left', padx=8)
        self._pos_lbl = tk.Label(info_frame, text='最差位置: --', font=FONT_BODY,
                                 bg=BG2, fg=DIM)
        self._pos_lbl.pack(side='left', padx=8)
        self._update_lbl = tk.Label(info_frame, text='', font=FONT_SMALL,
                                    bg=BG2, fg=DIM)
        self._update_lbl.pack(side='right', padx=8)

    def _stat_widget(self, parent, label, value, color) -> tk.Label:
        """建立摘要統計格（label + value）。"""
        f = tk.Frame(parent, bg=BG3, padx=10, pady=4)
        f.pack(side='left', expand=True, fill='x', padx=4)

        tk.Label(f, text=label, font=FONT_SMALL, bg=BG3, fg=DIM).pack()
        val_lbl = tk.Label(f, text=value, font=FONT_LARGE, bg=BG3, fg=color)
        val_lbl.pack()
        return val_lbl

    # ── 資料重新整理 ──────────────────────────────────────────────────────────

    def _refresh(self):
        if not self._win or not self._win.winfo_exists():
            return

        report = get_tracker().get_report()
        self._update_summary(report)
        self._update_leaks(report)
        self._update_info(report)

        # 每 5 秒自動重新整理
        self._after_id = self._win.after(5000, self._refresh)

    def _update_summary(self, r: SessionReport):
        acc_color = GREEN if r.accuracy_rate >= 0.70 else YELLOW if r.accuracy_rate >= 0.50 else RED
        self._acc_lbl.config(text=f'{r.accuracy_rate:.0%}',  fg=acc_color)

        loss_color = GREEN if r.total_ev_loss >= 0 else RED
        self._ev_lbl.config(text=f'{r.total_ev_loss:+.1f}', fg=loss_color)

        ev100_color = GREEN if r.ev_loss_per_100 >= 0 else YELLOW if r.ev_loss_per_100 >= -5 else RED
        self._ev100_lbl.config(text=f'{r.ev_loss_per_100:+.1f}', fg=ev100_color)

        self._dec_lbl.config(text=str(r.total_decisions))
        self._hand_lbl.config(text=str(r.hands_played))
        self._session_id_lbl.config(text=f'[{r.session_id}]')

    def _update_leaks(self, r: SessionReport):
        """清除並重繪漏洞條形圖。"""
        for w in self._leaks_frame.winfo_children():
            w.destroy()

        if not r.leaks:
            tk.Label(self._leaks_frame, text='本 session 無可識別漏洞！',
                     font=FONT_BODY, bg=BG, fg=GREEN).pack(pady=20)
            return

        # 找最大損失值（用於正規化條形）
        max_loss = max(abs(lk.total_ev_loss) for lk in r.leaks) or 1.0

        for lk in r.leaks:
            self._leak_row(self._leaks_frame, lk, max_loss)

    def _leak_row(self, parent, lk: LeakSummary, max_loss: float):
        """單個漏洞的條形圖列。"""
        row = tk.Frame(parent, bg=BG, pady=3)
        row.pack(fill='x', padx=4)

        # 類別名
        name_lbl = tk.Label(row, text=f'{lk.category_zh}',
                            font=FONT_HEADER, bg=BG, fg=YELLOW, width=10, anchor='w')
        name_lbl.pack(side='left', padx=(0, 6))

        # 條形圖
        bar_frame = tk.Frame(row, bg=BG3, height=20, width=240)
        bar_frame.pack(side='left', padx=2)
        bar_frame.pack_propagate(False)

        bar_pct  = min(1.0, abs(lk.total_ev_loss) / max_loss)
        bar_w    = max(4, int(240 * bar_pct))
        bar_color = RED if lk.total_ev_loss < -1.0 else YELLOW if lk.total_ev_loss < 0 else GREEN

        bar = tk.Frame(bar_frame, bg=bar_color, height=20, width=bar_w)
        bar.place(x=0, y=0)

        # 數值
        tk.Label(row, text=f'{lk.total_ev_loss:+.2f}BB  ({lk.count}次  均{lk.avg_ev_loss:+.2f})',
                 font=FONT_BODY, bg=BG, fg=FG).pack(side='left', padx=6)

        # 最差手
        if lk.worst_hand:
            tk.Label(row, text=f'[{lk.worst_hand}]', font=FONT_SMALL,
                     bg=BG, fg=DIM).pack(side='left')

        # 建議（折疊顯示）
        advice_frame = tk.Frame(parent, bg=BG2, padx=8, pady=3)
        advice_frame.pack(fill='x', padx=4, pady=(0, 4))
        tk.Label(advice_frame, text=lk.advice, font=FONT_SMALL,
                 bg=BG2, fg=DIM, wraplength=560, justify='left', anchor='w').pack(fill='x')

    def _update_info(self, r: SessionReport):
        self._street_lbl.config(
            text=f'最差街道: {r.worst_street}',
            fg=RED if r.worst_street not in ('N/A', 'unknown') else DIM
        )
        self._pos_lbl.config(
            text=f'最差位置: {r.worst_position}',
            fg=YELLOW if r.worst_position not in ('N/A',) else DIM
        )
        t = time.strftime('%H:%M:%S')
        self._update_lbl.config(text=f'更新: {t}')

    # ── 按鈕動作 ─────────────────────────────────────────────────────────────

    def _new_hand(self):
        get_tracker().new_hand()
        self._refresh()

    def _reset_session(self):
        """重置 session 並清空記錄。"""
        reset_tracker()
        self._refresh()


# ── 獨立測試 ─────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    from poker.session_tracker import get_tracker

    # 寫入假資料
    tr = get_tracker()
    tr.record_decision('flop', 'BTN', '翻牌有位置', '過牌', '加注', 2.0, 5.1, 0.72, 8.0)
    tr.record_decision('turn', 'CO',  '轉牌接觸式', '跟注', '棄牌', 0.5, -1.2, 0.30, 14.0)
    tr.record_decision('river','SB',  '河牌強牌',  '加注', '加注', 6.3, 6.3, 0.88, 20.0)
    tr.record_decision('preflop','BB','BB防守',    '棄牌', '跟注', 0.0, 2.1, 0.42, 5.5)
    tr.new_hand()
    tr.record_decision('flop', 'BTN', '乾燥翻牌',  '過牌', '加注', 1.5, 4.2, 0.65, 6.0)
    tr.record_decision('flop', 'CO',  '濕潤翻牌',  '加注', '棄牌', 3.0, 0.0, 0.35, 9.0)

    root = tk.Tk()
    root.withdraw()
    panel = SessionPanel(root)
    panel.toggle()
    root.mainloop()
