"""
即時對手範圍縮小器面板 (Live Villain Range Narrower) — F12

根據觀察到的對手每街行動，貝葉斯更新對手可能的手牌分布。

用法：每次看到對手行動，點擊對應按鈕 → 面板即時更新範圍估算和建議。

佈局：
  ┌──────────────────────────────────────┐
  │ 對手: [S1][S2][S3][S4][S5][S6]       │
  │ 街道: [翻牌][轉牌][河牌]  位置: [B][C]│
  │                                      │
  │ [過牌] [小注33%] [中注60%] [大注100%]│
  │ [跟注] [加注]   [棄牌]               │
  │ ─────────────────────────────────── │
  │ 超強牌 ████████░░░░░░  32%           │
  │ 頂  對 ████████████░░  45%           │
  │ 聽  牌 ████░░░░░░░░░░  15%           │
  │ 弱  牌 ███░░░░░░░░░░░   8%           │
  │ ─────────────────────────────────── │
  │ 建議: 對手強牌多，謹慎跟注/考慮棄牌  │
  │ [重置此座位]                         │
  └──────────────────────────────────────┘
"""

import tkinter as tk
from typing import Optional, Dict
from poker.range_narrower import VillainRangeTracker, NarrowResult

BG     = '#0D1117'
BG2    = '#161B22'
BORDER = '#30363D'
FG     = '#C9D1D9'
ACCENT = '#58A6FF'
GREEN  = '#56D364'
YELLOW = '#E3B341'
RED    = '#FF7B54'
ORANGE = '#FF9F43'
DIM    = '#484F58'
BTN_BG = '#21262D'

# 範圍條顏色
BAR_COLORS = {
    'nuts':      '#FFD700',   # 金色=超強
    'top_pair':  '#56D364',   # 綠色=頂對
    'draw':      '#4FC3F7',   # 藍色=聽牌
    'bluff_weak':'#FF7B54',   # 橘紅=弱牌/詐唬
}

# 行動按鈕: (label, action_key, bet_pct, color)
_ACTIONS = [
    ('過  牌',   'check', 0.0,  DIM),
    ('小注 33%', 'bet',   0.33, YELLOW),
    ('中注 60%', 'bet',   0.60, YELLOW),
    ('大注100%', 'bet',   1.00, ORANGE),
    ('跟  注',   'call',  0.0,  ACCENT),
    ('加  注',   'raise', 0.80, RED),
    ('棄  牌',   'fold',  0.0,  DIM),
]

_STREETS = ['flop', 'turn', 'river']
_STREET_ZH = {'flop': '翻牌', 'turn': '轉牌', 'river': '河牌'}

# 對手起始 VPIP 寬度對應
_VPIP_TO_RANGE = {
    'UTG': 0.15, 'HJ': 0.22, 'CO': 0.28,
    'BTN': 0.42, 'SB': 0.36, 'BB': 0.45,
}


class RangeNarrowerPanel:
    """F12 即時對手範圍縮小面板。"""

    def __init__(self, parent_root: tk.Tk):
        self._root      = parent_root
        self._win: Optional[tk.Toplevel] = None
        self._visible   = False
        self._seat_var  = tk.IntVar(value=1)
        self._street_var = tk.StringVar(value='flop')
        self._pos_var   = tk.StringVar(value='BTN')
        # 每個座位一個 tracker
        self._trackers: Dict[int, VillainRangeTracker] = {}
        self._last_result: Optional[NarrowResult] = None

    # ── 建立/銷毀 ──────────────────────────────────────────────────────────────

    def toggle(self):
        if self._visible and self._win:
            try:
                self._win.destroy()
            except Exception:
                pass
            self._visible = False
            self._win = None
        else:
            self._build()
            self._visible = True

    def _build(self):
        self._win = tk.Toplevel(self._root)
        self._win.title('即時範圍縮小器 (F12)')
        self._win.configure(bg=BG)
        self._win.attributes('-topmost', True)
        self._win.resizable(False, False)
        self._win.protocol('WM_DELETE_WINDOW', self.toggle)

        # ── 標題 ──────────────────────────────────────────────────────────────
        tk.Label(self._win, text='對手範圍追蹤器', bg=BG, fg=ACCENT,
                 font=('Consolas', 10, 'bold')).pack(pady=(8, 2))

        # ── 座位 + 位置行 ─────────────────────────────────────────────────────
        top_row = tk.Frame(self._win, bg=BG2)
        top_row.pack(fill='x', padx=6, pady=2)

        tk.Label(top_row, text='對手:', bg=BG2, fg=FG,
                 font=('Consolas', 9)).pack(side='left', padx=(4, 2))
        for s in range(1, 7):
            tk.Radiobutton(
                top_row, text=str(s), variable=self._seat_var, value=s,
                bg=BG2, fg=FG, selectcolor=ACCENT,
                activebackground=BG2, font=('Consolas', 9), indicatoron=True,
                command=self._on_seat_change,
            ).pack(side='left', padx=1)

        tk.Label(top_row, text='  位置:', bg=BG2, fg=FG,
                 font=('Consolas', 8)).pack(side='left', padx=(6, 2))
        for pos in ['UTG', 'CO', 'BTN', 'SB']:
            tk.Radiobutton(
                top_row, text=pos, variable=self._pos_var, value=pos,
                bg=BG2, fg=DIM, selectcolor=ACCENT,
                activebackground=BG2, font=('Consolas', 8), indicatoron=True,
                command=self._on_pos_change,
            ).pack(side='left', padx=1)

        # ── 街道選擇 ─────────────────────────────────────────────────────────
        st_row = tk.Frame(self._win, bg=BG)
        st_row.pack(padx=6, pady=3)
        tk.Label(st_row, text='街道:', bg=BG, fg=FG,
                 font=('Consolas', 9)).pack(side='left', padx=(0, 4))
        self._street_btns = {}
        for st in _STREETS:
            b = tk.Radiobutton(
                st_row, text=_STREET_ZH[st],
                variable=self._street_var, value=st,
                bg=BTN_BG, fg=YELLOW, selectcolor='#1F4E2A',
                activebackground=BG2, font=('Consolas', 9, 'bold'),
                indicatoron=False, padx=8, pady=4, relief='flat',
                command=self._on_street_change,
            )
            b.pack(side='left', padx=2)
            self._street_btns[st] = b

        # ── 行動按鈕 ─────────────────────────────────────────────────────────
        tk.Frame(self._win, bg=BORDER, height=1).pack(fill='x', padx=6, pady=2)

        btn_outer = tk.Frame(self._win, bg=BG)
        btn_outer.pack(padx=6, pady=4)

        for i, (label, action, bet_pct, color) in enumerate(_ACTIONS):
            row_, col_ = divmod(i, 4)
            b = tk.Button(
                btn_outer, text=label,
                bg=BTN_BG, fg=color,
                activebackground='#2D333B', activeforeground='white',
                font=('Consolas', 9, 'bold'),
                relief='flat', bd=0, padx=10, pady=5, cursor='hand2',
                command=lambda a=action, bp=bet_pct: self._apply_action(a, bp),
            )
            b.grid(row=row_, column=col_, padx=2, pady=2, sticky='ew')
            b.bind('<Enter>', lambda e, b=b: b.config(bg='#2D333B'))
            b.bind('<Leave>', lambda e, b=b: b.config(bg=BTN_BG))

        # ── 分隔線 ────────────────────────────────────────────────────────────
        tk.Frame(self._win, bg=BORDER, height=1).pack(fill='x', padx=6, pady=2)

        # ── 範圍分布條 ────────────────────────────────────────────────────────
        bar_frame = tk.Frame(self._win, bg=BG)
        bar_frame.pack(fill='x', padx=10, pady=4)

        bar_defs = [
            ('超強牌', 'nuts',      BAR_COLORS['nuts']),
            ('頂對+K', 'top_pair',  BAR_COLORS['top_pair']),
            ('聽  牌', 'draw',      BAR_COLORS['draw']),
            ('弱/詐唬', 'bluff_weak', BAR_COLORS['bluff_weak']),
        ]

        self._bar_labels: dict = {}
        self._bar_canvas: dict = {}
        self._pct_labels:  dict = {}

        for label, key, color in bar_defs:
            row = tk.Frame(bar_frame, bg=BG)
            row.pack(fill='x', pady=1)

            tk.Label(row, text=f'{label:4s}', bg=BG, fg=FG,
                     font=('Consolas', 8), width=7, anchor='w').pack(side='left')

            c = tk.Canvas(row, height=14, width=160, bg='#1C2128',
                          highlightthickness=0)
            c.pack(side='left', padx=2)
            self._bar_canvas[key] = c

            pl = tk.Label(row, text='--', bg=BG, fg=color,
                          font=('Consolas', 8), width=5, anchor='e')
            pl.pack(side='left')
            self._pct_labels[key] = (pl, color)

        # ── 行動歷史 ─────────────────────────────────────────────────────────
        self._history_lbl = tk.Label(
            self._win, text='尚無行動記錄', bg=BG, fg=DIM,
            font=('Consolas', 7), wraplength=280,
        )
        self._history_lbl.pack(padx=8, pady=(2, 0))

        # ── 剩餘範圍 + 極化分數 ───────────────────────────────────────────────
        self._stats_lbl = tk.Label(
            self._win, text='', bg=BG, fg=DIM, font=('Consolas', 7),
        )
        self._stats_lbl.pack()

        # ── 分隔線 ────────────────────────────────────────────────────────────
        tk.Frame(self._win, bg=BORDER, height=1).pack(fill='x', padx=6, pady=2)

        # ── 英雄建議 ─────────────────────────────────────────────────────────
        self._advice_lbl = tk.Label(
            self._win, text='點擊按鈕記錄對手行動',
            bg=BG2, fg=YELLOW, font=('Consolas', 9, 'bold'),
            wraplength=280, justify='left',
        )
        self._advice_lbl.pack(fill='x', padx=6, pady=4)

        # ── 重置 ─────────────────────────────────────────────────────────────
        ctrl_row = tk.Frame(self._win, bg=BG)
        ctrl_row.pack(pady=(0, 6))
        tk.Button(
            ctrl_row, text='重置此座位',
            bg=BTN_BG, fg=RED, font=('Consolas', 8),
            activebackground='#2D333B', relief='flat', bd=0,
            padx=8, pady=3, cursor='hand2',
            command=self._reset_seat,
        ).pack(side='left', padx=4)
        tk.Button(
            ctrl_row, text='重置全部',
            bg=BTN_BG, fg=DIM, font=('Consolas', 8),
            activebackground='#2D333B', relief='flat', bd=0,
            padx=8, pady=3, cursor='hand2',
            command=self._reset_all,
        ).pack(side='left', padx=4)

        self._refresh_bars()

    # ── 邏輯 ──────────────────────────────────────────────────────────────────

    def _get_tracker(self) -> VillainRangeTracker:
        seat = self._seat_var.get()
        if seat not in self._trackers:
            pos  = self._pos_var.get()
            rng  = _VPIP_TO_RANGE.get(pos, 0.30)
            self._trackers[seat] = VillainRangeTracker(
                opener_pos=pos, starting_range_pct=rng
            )
        return self._trackers[seat]

    def _apply_action(self, action: str, bet_pct: float):
        tracker = self._get_tracker()
        street  = self._street_var.get()
        tracker.add_action(street, action, bet_pct)
        result  = tracker.get_result()
        self._last_result = result
        self._refresh_bars(result)

        # Auto-advance street after action
        idx = _STREETS.index(street)
        if action in ('bet', 'raise', 'call') and idx < len(_STREETS) - 1:
            pass   # stay on same street — user advances manually

    def _on_seat_change(self):
        seat = self._seat_var.get()
        if seat in self._trackers:
            result = self._trackers[seat].get_result()
            self._refresh_bars(result)
        else:
            self._refresh_bars()

    def _on_pos_change(self):
        seat = self._seat_var.get()
        # Reset tracker for this seat with new position
        if seat in self._trackers:
            del self._trackers[seat]
        self._refresh_bars()

    def _on_street_change(self):
        pass   # just tracks current street for next button click

    def _reset_seat(self):
        seat = self._seat_var.get()
        self._trackers.pop(seat, None)
        self._refresh_bars()

    def _reset_all(self):
        self._trackers.clear()
        self._refresh_bars()

    def _refresh_bars(self, result: Optional[NarrowResult] = None):
        if not self._win:
            return

        if result is None:
            # Show default / blank state
            for key, c in self._bar_canvas.items():
                c.delete('all')
                c.create_rectangle(0, 0, 160, 14, fill='#1C2128', outline='')
            for key, (lbl, color) in self._pct_labels.items():
                lbl.config(text='--', fg=color)
            self._advice_lbl.config(text='選擇座位並點擊行動按鈕以追蹤對手範圍')
            self._history_lbl.config(text='尚無行動記錄')
            self._stats_lbl.config(text='')
            return

        st = result.current_state
        values = {
            'nuts':       st.pct_nuts,
            'top_pair':   st.pct_top_pair,
            'draw':       st.pct_draw,
            'bluff_weak': st.pct_bluff_weak,
        }

        for key, pct in values.items():
            c = self._bar_canvas[key]
            c.delete('all')
            c.create_rectangle(0, 0, 160, 14, fill='#1C2128', outline='')
            bar_w = max(2, int(160 * pct))
            c.create_rectangle(0, 0, bar_w, 14, fill=BAR_COLORS[key], outline='')
            _, color = self._pct_labels[key]
            self._pct_labels[key][0].config(text=f'{pct:.0%}', fg=color)

        # History
        history_parts = []
        for s, a, bp in self._trackers.get(self._seat_var.get(),
                                            VillainRangeTracker()).actions[-5:]:
            st_zh = _STREET_ZH.get(s, s)
            if bp > 0:
                history_parts.append(f'{st_zh}{a[:2]}({int(bp*100)}%)')
            else:
                history_parts.append(f'{st_zh}{a[:2]}')
        self._history_lbl.config(
            text='行動: ' + ' → '.join(history_parts) if history_parts else '尚無行動記錄',
            fg=ACCENT,
        )

        # Stats
        self._stats_lbl.config(
            text=f'剩餘範圍 {st.range_remaining:.0%}  |  極化分 {st.polarization_score:.0%}',
            fg=DIM,
        )

        # Advice
        self._advice_lbl.config(text=f'建議: {result.read_advice}', fg=YELLOW)
