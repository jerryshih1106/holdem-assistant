"""
底池跟蹤器面板（F7，取代原本的 F7=Force detect）。

使用快速按鈕逐街追蹤底池，自動更新 CONFIG.poker.pot_size。
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from poker.pot_tracker import PotTracker
from poker.mrating import calculate_m, zone_advice

BG    = '#0D1117'
BG2   = '#161B22'
BG3   = '#21262D'
FG    = '#E6EDF3'
DIM   = '#8B949E'
ACCENT = '#58A6FF'
GREEN  = '#56D364'
YELLOW = '#E3B341'
RED    = '#FF7B54'
ORANGE = '#FF9F43'
BORDER = '#30363D'

STREET_COLORS = {
    'preflop': '#1A3A5C',
    'flop':    '#1A4A2A',
    'turn':    '#3A3A1A',
    'river':   '#3A1A1A',
}


class PotPanel:
    def __init__(self, tracker: PotTracker, on_pot_change: Optional[Callable] = None,
                 parent_root=None):
        self._tracker      = tracker
        self._on_pot_change = on_pot_change

        self._win = tk.Toplevel(parent_root) if parent_root else tk.Tk()
        self._win.title('底池跟蹤 + M-Ratio')
        self._win.configure(bg=BG)
        self._win.attributes('-topmost', True)
        self._win.resizable(False, False)
        self._win.geometry('420x480+400+20')

        # 輸入變數
        self._bb_var     = tk.IntVar(value=20)
        self._sb_var     = tk.IntVar(value=10)
        self._ante_var   = tk.IntVar(value=0)
        self._stack_var  = tk.IntVar(value=1000)
        self._players_var = tk.IntVar(value=6)
        self._custom_amt  = tk.StringVar(value='')

        self._build_ui()
        self._refresh()

    def _build_ui(self):
        self._build_blinds()
        self._build_pot_display()
        self._build_action_buttons()
        self._build_common_sizes()
        self._build_m_ratio()
        self._build_log()

    # ── 盲注設定 ─────────────────────────────────────────────────────

    def _build_blinds(self):
        bar = tk.Frame(self._win, bg=BG2, pady=6)
        bar.pack(fill='x', padx=4, pady=(4,0))

        lbl = dict(bg=BG2, fg=DIM, font=('Consolas',8))
        ent = dict(bg=BG3, fg=FG, insertbackground=FG, font=('Consolas',9),
                   relief='flat', bd=3, width=5)

        tk.Label(bar, text='BB:', **lbl).grid(row=0, column=0, padx=(8,2))
        tk.Entry(bar, textvariable=self._bb_var,   **ent).grid(row=0, column=1, padx=2)
        tk.Label(bar, text='SB:', **lbl).grid(row=0, column=2, padx=(6,2))
        tk.Entry(bar, textvariable=self._sb_var,   **ent).grid(row=0, column=3, padx=2)
        tk.Label(bar, text='前注:', **lbl).grid(row=0, column=4, padx=(6,2))
        tk.Entry(bar, textvariable=self._ante_var, **ent).grid(row=0, column=5, padx=2)
        tk.Label(bar, text='籌碼:', **lbl).grid(row=0, column=6, padx=(6,2))
        tk.Entry(bar, textvariable=self._stack_var, bg=BG3, fg=FG,
                 insertbackground=FG, font=('Consolas',9), relief='flat', bd=3,
                 width=6).grid(row=0, column=7, padx=2)

        tk.Button(bar, text='新的一手', command=self._new_hand,
                  bg='#1F6FEB', fg='white', font=('Consolas',9,'bold'),
                  relief='flat', padx=8).grid(row=0, column=8, padx=8)

    # ── 底池顯示 ─────────────────────────────────────────────────────

    def _build_pot_display(self):
        tk.Frame(self._win, bg=BORDER, height=1).pack(fill='x', padx=4, pady=2)
        frame = tk.Frame(self._win, bg=BG, pady=4)
        frame.pack(fill='x', padx=8)

        row = tk.Frame(frame, bg=BG); row.pack(fill='x')
        tk.Label(row, text='街道:', bg=BG, fg=DIM, font=('Consolas',9)).pack(side='left')
        self._street_lbl = tk.Label(row, text='翻前', bg=BG, fg=ACCENT,
                                     font=('Consolas',12,'bold'))
        self._street_lbl.pack(side='left', padx=6)

        tk.Label(row, text='底池:', bg=BG, fg=DIM, font=('Consolas',9)).pack(side='left', padx=(12,2))
        self._pot_lbl = tk.Label(row, text='0', bg=BG, fg=GREEN,
                                  font=('Consolas',18,'bold'))
        self._pot_lbl.pack(side='left')

        tk.Label(row, text='跟注額:', bg=BG, fg=DIM, font=('Consolas',9)).pack(side='left', padx=(12,2))
        self._call_lbl = tk.Label(row, text='0', bg=BG, fg=YELLOW,
                                   font=('Consolas',14,'bold'))
        self._call_lbl.pack(side='left')

        # 街道進度按鈕
        streets_row = tk.Frame(frame, bg=BG); streets_row.pack(fill='x', pady=4)
        self._street_btns = []
        for s, zh in [('preflop','翻前'),('flop','翻牌'),('turn','轉牌'),('river','河牌')]:
            btn = tk.Button(streets_row, text=zh, width=6,
                            bg=STREET_COLORS.get(s, BG3), fg=DIM,
                            font=('Consolas',8), relief='flat', cursor='hand2',
                            command=lambda st=s: self._go_to_street(st))
            btn.pack(side='left', padx=2)
            self._street_btns.append((s, btn))

    def _go_to_street(self, street: str):
        self._tracker.go_to_street(street)
        self._refresh()

    # ── 行動按鈕 ─────────────────────────────────────────────────────

    def _build_action_buttons(self):
        tk.Frame(self._win, bg=BORDER, height=1).pack(fill='x', padx=4, pady=2)
        frame = tk.Frame(self._win, bg=BG2, pady=6)
        frame.pack(fill='x', padx=4)
        tk.Label(frame, text='行動按鈕', bg=BG2, fg=ACCENT,
                 font=('Consolas',9,'bold')).pack(anchor='w', padx=8)

        # 翻前行動
        row1 = tk.Frame(frame, bg=BG2); row1.pack(fill='x', padx=8, pady=2)
        tk.Label(row1, text='翻前:', bg=BG2, fg=DIM, font=('Consolas',8)).pack(side='left')
        for txt, action, amt in [
            ('平跟','limp',0), ('開牌×3','open',self._bb_var.get()*3 if hasattr(self,'_bb_var') else 60),
            ('棄牌','fold',0), ('跟注','call',0),
        ]:
            tk.Button(row1, text=txt, bg=BG3, fg=FG, font=('Consolas',8),
                      relief='flat', padx=6, cursor='hand2',
                      command=lambda a=action, v=amt: self._quick_action(a, v)
                      ).pack(side='left', padx=2)

        # 翻後行動
        row2 = tk.Frame(frame, bg=BG2); row2.pack(fill='x', padx=8, pady=2)
        tk.Label(row2, text='翻後:', bg=BG2, fg=DIM, font=('Consolas',8)).pack(side='left')
        for txt, action in [('過牌','check'),('棄牌','fold')]:
            tk.Button(row2, text=txt, bg=BG3, fg=DIM, font=('Consolas',8),
                      relief='flat', padx=6, cursor='hand2',
                      command=lambda a=action: self._quick_action(a, 0)
                      ).pack(side='left', padx=2)

        # 自訂金額
        row3 = tk.Frame(frame, bg=BG2); row3.pack(fill='x', padx=8, pady=2)
        tk.Label(row3, text='自訂金額:', bg=BG2, fg=DIM, font=('Consolas',8)).pack(side='left')
        self._custom_entry = tk.Entry(row3, textvariable=self._custom_amt,
                                       bg=BG3, fg=FG, insertbackground=FG,
                                       font=('Consolas',9), width=8, relief='flat', bd=3)
        self._custom_entry.pack(side='left', padx=4)
        for txt, action in [('下注','bet'),('跟注','call'),('加注','raise')]:
            tk.Button(row3, text=txt, bg='#1A3A5C', fg=FG, font=('Consolas',8),
                      relief='flat', padx=6, cursor='hand2',
                      command=lambda a=action: self._custom_action(a)
                      ).pack(side='left', padx=2)

        self._custom_entry.bind('<Return>', lambda _: self._custom_action('bet'))

    def _quick_action(self, action: str, amount: int = 0):
        if action == 'call':
            amount = self._tracker.call_size
        self._tracker.action(action, amount)
        self._notify()
        self._refresh()

    def _custom_action(self, action: str):
        try:
            amt = int(self._custom_amt.get() or 0)
        except ValueError:
            return
        self._tracker.action(action, amt)
        self._custom_amt.set('')
        self._notify()
        self._refresh()

    # ── 常用注碼 ─────────────────────────────────────────────────────

    def _build_common_sizes(self):
        tk.Frame(self._win, bg=BORDER, height=1).pack(fill='x', padx=4, pady=2)
        frame = tk.Frame(self._win, bg=BG, pady=4)
        frame.pack(fill='x', padx=8)
        tk.Label(frame, text='建議注碼:', bg=BG, fg=DIM, font=('Consolas',8)).pack(side='left')
        self._size_btns_frame = tk.Frame(frame, bg=BG)
        self._size_btns_frame.pack(side='left', padx=6)

    def _refresh_size_buttons(self):
        for w in self._size_btns_frame.winfo_children(): w.destroy()
        sizes = self._tracker.common_sizes()
        for label, amt in sizes.items():
            tk.Button(self._size_btns_frame, text=f'{label}\n({amt})',
                      bg='#1A2A1A', fg=GREEN, font=('Consolas',7),
                      relief='flat', padx=4, cursor='hand2',
                      command=lambda a=amt: self._set_custom(a)
                      ).pack(side='left', padx=2)

    def _set_custom(self, amount: int):
        self._custom_amt.set(str(amount))

    # ── M-Ratio ──────────────────────────────────────────────────────

    def _build_m_ratio(self):
        tk.Frame(self._win, bg=BORDER, height=1).pack(fill='x', padx=4, pady=2)
        frame = tk.Frame(self._win, bg=BG2, pady=6)
        frame.pack(fill='x', padx=4)
        tk.Label(frame, text='M-Ratio 壓力計', bg=BG2, fg=ACCENT,
                 font=('Consolas',9,'bold')).pack(padx=8, anchor='w')

        row = tk.Frame(frame, bg=BG2); row.pack(fill='x', padx=8, pady=2)
        self._m_value_lbl = tk.Label(row, text='M = —', bg=BG2, fg=GREEN,
                                      font=('Consolas',14,'bold'))
        self._m_value_lbl.pack(side='left')
        self._m_zone_lbl = tk.Label(row, text='', bg=BG2, fg=DIM,
                                     font=('Consolas',10,'bold'))
        self._m_zone_lbl.pack(side='left', padx=8)

        self._m_strategy_lbl = tk.Label(frame, text='', bg=BG2, fg=DIM,
                                         font=('Consolas',8), wraplength=380,
                                         justify='left')
        self._m_strategy_lbl.pack(padx=8, anchor='w')

        tk.Label(frame, text='人數:', bg=BG2, fg=DIM, font=('Consolas',8)).pack(side='left', padx=(8,2))
        tk.Spinbox(frame, from_=2, to=9, textvariable=self._players_var, width=3,
                   bg=BG3, fg=FG, buttonbackground=BG3, font=('Consolas',9),
                   relief='flat', command=self._refresh).pack(side='left', padx=2)

    # ── 行動日誌 ─────────────────────────────────────────────────────

    def _build_log(self):
        tk.Frame(self._win, bg=BORDER, height=1).pack(fill='x', padx=4, pady=2)
        frame = tk.Frame(self._win, bg=BG, pady=2)
        frame.pack(fill='x', padx=8)
        tk.Label(frame, text='行動記錄:', bg=BG, fg=DIM, font=('Consolas',7)).pack(anchor='w')
        self._log_lbl = tk.Label(frame, text='', bg=BG, fg='#666666',
                                  font=('Consolas',7), wraplength=390, justify='left')
        self._log_lbl.pack(anchor='w')

    # ── 更新 ─────────────────────────────────────────────────────────

    def _new_hand(self):
        self._tracker.big_blind   = self._bb_var.get()
        self._tracker.small_blind = self._sb_var.get()
        self._tracker.new_hand()
        self._notify()
        self._refresh()

    def _notify(self):
        if self._on_pot_change:
            self._on_pot_change(self._tracker.pot, self._tracker.call_size)

    def _refresh(self):
        # 街道
        zh = {'preflop':'翻前','flop':'翻牌','turn':'轉牌','river':'河牌'}
        self._street_lbl.config(text=zh.get(self._tracker.street, ''))
        color = STREET_COLORS.get(self._tracker.street, BG3)
        self._win.configure()

        # 底池
        self._pot_lbl.config(text=str(self._tracker.pot))
        self._call_lbl.config(text=str(self._tracker.call_size))

        # 常用注碼
        self._refresh_size_buttons()

        # M-Ratio
        try:
            stack   = self._stack_var.get()
            bb      = self._bb_var.get()
            sb      = self._sb_var.get()
            ante    = self._ante_var.get()
            players = self._players_var.get()
            mr = calculate_m(stack, bb, sb, ante, players)
            m  = mr.m_effective
            self._m_value_lbl.config(text=f'M = {m:.1f}', fg=mr.zone_color)
            self._m_zone_lbl.config(text=f'[{mr.zone}]', fg=mr.zone_color)
            self._m_strategy_lbl.config(text=mr.strategy)
        except Exception:
            pass

        # 日誌
        self._log_lbl.config(text=self._tracker.log_summary())

    def run(self): self._win.mainloop()
