"""HUD 對手統計面板（F2）— 繁體中文介面。"""

import tkinter as tk
from tkinter import ttk
from typing import Optional

from poker.hud import HUDTracker, PlayerStats

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

ACTIONS_ZH = [
    ('vpip',       '主動入池（VPIP）'),
    ('pfr',        '翻前加注（PFR）'),
    ('3bet',       '三倍注（含 VPIP+PFR）'),
    ('3bet_opp',   '三倍注機會（面對加注）'),
    ('fold_3b',    '遇三倍注棄牌'),
    ('fold_3b_opp','遇三倍注機會'),
    ('cbet',       '持續注（C-bet）'),
    ('cbet_opp',   '持續注機會'),
    ('fcbet',      '遇持續注棄牌'),
    ('fcbet_opp',  '遇持續注機會'),
    ('bet',        '下注/加注（用於攻擊因子）'),
    ('call',       '跟注（用於攻擊因子）'),
]
ACTION_KEYS = [a[0] for a in ACTIONS_ZH]

COLS = [
    ('座位',4),('暱稱',9),('手數',5),('入池%',5),
    ('加注%',5),('3B%',5),('F3B',5),('C注',5),('F持',5),('AF',5),('牌風',10),
]

TYPE_ZH = {
    'Nit':'緊被動','TAG':'緊主動','Passive':'鬆被動',
    'LAG':'鬆主動','Fish/Calling':'跟注魚','Maniac':'瘋狗','Unknown':'未知',
}


class HUDPanel:
    def __init__(self, tracker: HUDTracker, parent_root=None):
        self._tracker = tracker
        self._win = tk.Toplevel(parent_root) if parent_root else tk.Tk()
        self._win.title('對手統計 (HUD)')
        self._win.configure(bg=BG)
        self._win.attributes('-topmost', True)
        self._win.resizable(True, False)
        self._seat_var   = tk.IntVar(value=1)
        self._action_var = tk.StringVar(value=ACTION_KEYS[0])
        self._name_vars: dict = {}
        self._build_setup()
        self._build_table()
        self._build_recorder()
        self._build_exploit()
        self._refresh()

    def _build_setup(self):
        bar = tk.Frame(self._win, bg=BG2, pady=6)
        bar.pack(fill='x', padx=4, pady=(4,0))
        tk.Label(bar, text='啟用座位:', bg=BG2, fg=DIM, font=('Consolas', 9)).pack(side='left', padx=(8,4))
        self._seats_var = tk.StringVar(value='1 2 3 4 5 6')
        tk.Entry(bar, textvariable=self._seats_var, bg=BG3, fg=FG,
                 insertbackground=FG, font=('Consolas', 9), width=16, relief='flat', bd=4).pack(side='left', padx=4)
        tk.Button(bar, text='初始化/重置座位', command=self._init_seats,
                  bg='#238636', fg='white', font=('Consolas', 9), relief='flat', padx=8).pack(side='left', padx=6)
        tk.Button(bar, text='新的一手', command=self._new_hand,
                  bg='#1F6FEB', fg='white', font=('Consolas', 9, 'bold'), relief='flat', padx=10).pack(side='right', padx=8)

    def _init_seats(self):
        try: seats = [int(s) for s in self._seats_var.get().split()]
        except ValueError: return
        self._tracker.set_players(seats)
        self._refresh()

    def _new_hand(self):
        try: seats = [int(s) for s in self._seats_var.get().split()]
        except ValueError: return
        self._tracker.new_hand(seats)
        self._refresh()

    def _build_table(self):
        frame = tk.Frame(self._win, bg=BG)
        frame.pack(fill='x', padx=4, pady=4)
        header = tk.Frame(frame, bg=BG2)
        header.pack(fill='x')
        for col, width in COLS:
            tk.Label(header, text=col, bg=BG2, fg=DIM, font=('Consolas', 8, 'bold'),
                     width=width, anchor='center').pack(side='left', padx=1)
        tk.Frame(frame, bg=BORDER, height=1).pack(fill='x', pady=2)
        self._table_frame = tk.Frame(frame, bg=BG)
        self._table_frame.pack(fill='x')

    def _refresh(self):
        for w in self._table_frame.winfo_children(): w.destroy()
        players = self._tracker.all_players()
        if not players:
            tk.Label(self._table_frame, text='無玩家資料 — 輸入座位並點擊「初始化」',
                     bg=BG, fg=DIM, font=('Consolas', 9)).pack(pady=8)
            return
        for p in sorted(players, key=lambda x: x.seat):
            self._add_row(p)
        try:
            seat = self._seat_var.get()
            p = self._tracker.get_player(seat)
            self._exploit_lbl.config(text=p.exploit_note(), fg=YELLOW)
        except Exception: pass

    def _add_row(self, p: PlayerStats):
        row = tk.Frame(self._table_frame, bg=BG, pady=1)
        row.pack(fill='x')
        type_color = p.player_color()
        def lbl(text, width, fg=FG, bold=False):
            f = ('Consolas', 8, 'bold') if bold else ('Consolas', 8)
            tk.Label(row, text=text, bg=BG, fg=fg, font=f, width=width, anchor='center').pack(side='left', padx=1)
        lbl(str(p.seat), 4, ACCENT, bold=True)
        if p.seat not in self._name_vars: self._name_vars[p.seat] = tk.StringVar(value=p.name)
        nv = self._name_vars[p.seat]
        name_e = tk.Entry(row, textvariable=nv, bg=BG3, fg=FG, insertbackground=FG,
                          font=('Consolas', 8), width=9, relief='flat', bd=2)
        name_e.pack(side='left', padx=1)
        name_e.bind('<FocusOut>', lambda e, s=p.seat, v=nv: self._tracker.rename(s, v.get()))
        lbl(str(p.hands), 5)
        lbl(self._pct(p.vpip_pct),  5, self._pct_color(p.vpip_pct, 15, 30))
        lbl(self._pct(p.pfr_pct),   5, self._pct_color(p.pfr_pct,  10, 20))
        lbl(self._pct(p.threebet_pct), 5, self._pct_color(p.threebet_pct, 5, 12))
        lbl(self._pct(p.fold_3b_pct),  5, self._fold_color(p.fold_3b_pct))
        lbl(self._pct(p.cbet_pct),  5, self._pct_color(p.cbet_pct, 40, 70))
        lbl(self._pct(p.fcbet_pct), 5, self._fold_color(p.fcbet_pct))
        lbl(p.fmt(p.af, 1), 5)
        type_zh = TYPE_ZH.get(p.player_type(), p.player_type())
        lbl(type_zh, 10, type_color, bold=True)

    def _pct(self, val): return '—' if val is None else f'{val:.0f}'
    def _pct_color(self, v, lo, hi): return DIM if v is None else (RED if v>hi else GREEN if v<lo else FG)
    def _fold_color(self, v): return DIM if v is None else (GREEN if v>65 else RED if v<35 else FG)

    def _build_recorder(self):
        tk.Frame(self._win, bg=BORDER, height=1).pack(fill='x', padx=4, pady=4)
        frame = tk.Frame(self._win, bg=BG2, pady=6)
        frame.pack(fill='x', padx=4)
        tk.Label(frame, text='記錄行動', bg=BG2, fg=ACCENT, font=('Consolas', 9, 'bold')).pack(side='left', padx=8)
        tk.Label(frame, text='座位:', bg=BG2, fg=DIM, font=('Consolas', 9)).pack(side='left', padx=(8,2))
        tk.Spinbox(frame, from_=1, to=9, width=3, textvariable=self._seat_var,
                   bg=BG3, fg=FG, buttonbackground=BG3, font=('Consolas', 10),
                   relief='flat', command=self._on_seat_change).pack(side='left', padx=4)
        tk.Label(frame, text='行動:', bg=BG2, fg=DIM, font=('Consolas', 9)).pack(side='left', padx=(8,2))
        cb = ttk.Combobox(frame, textvariable=self._action_var,
                          values=ACTION_KEYS, width=16, state='readonly', font=('Consolas', 9))
        cb.pack(side='left', padx=4)

        shortcuts_frame = tk.Frame(frame, bg=BG2)
        shortcuts_frame.pack(side='left', padx=8)
        for key, label in [('[V]','入池'),('[P]','加注'),('[3]','三倍注'),('[F]','遇三棄'),('[C]','持續注')]:
            tk.Label(shortcuts_frame, text=key, bg=BG2, fg=DIM, font=('Consolas', 7)).pack(side='left')
            tk.Label(shortcuts_frame, text=label, bg=BG2, fg='#555555', font=('Consolas', 7)).pack(side='left', padx=(0,4))

        tk.Button(frame, text='記錄 ↵', command=self._record_action,
                  bg='#238636', fg='white', font=('Consolas', 9, 'bold'), relief='flat', padx=10).pack(side='right', padx=8)

        self._win.bind('v', lambda _: self._quick_record('vpip'))
        self._win.bind('p', lambda _: self._quick_record('pfr'))
        self._win.bind('3', lambda _: self._quick_record('3bet'))
        self._win.bind('f', lambda _: self._quick_record('fold_3b'))
        self._win.bind('c', lambda _: self._quick_record('cbet'))
        self._win.bind('<Return>', lambda _: self._record_action())

    def _on_seat_change(self):
        try:
            p = self._tracker.get_player(self._seat_var.get())
            self._exploit_lbl.config(text=p.exploit_note(), fg=YELLOW)
        except Exception: pass

    def _record_action(self):
        self._tracker.record(self._seat_var.get(), self._action_var.get())
        self._refresh()

    def _quick_record(self, action: str):
        self._action_var.set(action)
        self._record_action()

    def _build_exploit(self):
        frame = tk.Frame(self._win, bg=BG, pady=4)
        frame.pack(fill='x', padx=8)
        tk.Label(frame, text='剝削提示:', bg=BG, fg=DIM, font=('Consolas', 8)).pack(side='left')
        self._exploit_lbl = tk.Label(frame, text='選擇一個座位以查看剝削建議',
                                      bg=BG, fg=DIM, font=('Consolas', 8), wraplength=560, justify='left')
        self._exploit_lbl.pack(side='left', padx=6)

    def run(self): self._win.mainloop()
