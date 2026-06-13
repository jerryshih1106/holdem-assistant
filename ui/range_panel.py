"""翻前範圍表 — GTO Wizard 風格重設計。

v3 改進：
  - 橢圓牌桌圖：點擊座位選 Hero 位置 / 開牌者
  - 行動頻率條：加注%/跟注%/棄牌% 可點選篩選範圍格
  - 更沉穩的色板（降低亮度，提高辨識度）
  - 保留 13×13 範圍格 + Hover 詳情
"""

import math
import tkinter as tk
from typing import Optional, Dict

from poker.ranges import (
    RANKS, hand_at, hand_to_grid, get_frequency,
    scenario_stats, recommend_preflop, SCENARIOS, RANGES,
    get_mixed_action, combo_count, MIXED_ACTIONS, POSITIONS,
)

# ── 色板 ──────────────────────────────────────────────────────────────────────
BG     = '#0E0E14'
BG2    = '#0A0A10'
BG3    = '#16161E'
FG     = '#C9D1D9'
DIM    = '#5A6470'
ACCENT = '#2F81F7'
BORDER = '#1E1E28'
SEL    = '#1A5CC8'

FELT_BG      = '#091409'
FELT_LINE    = '#183218'
SEAT_NORMAL  = '#16161E'
SEAT_HERO    = '#1A3566'
SEAT_OPENER  = '#3A2800'
SEAT_LBL     = '#8ABADF'

BAR_RAISE    = '#B05018'
BAR_CALL     = '#1A5A8A'
BAR_FOLD     = '#2A3040'
BAR_SEL_OUT  = '#FFFFFF'

# ── 位置 ──────────────────────────────────────────────────────────────────────
POSITIONS_6 = ['UTG', 'HJ', 'CO', 'BTN', 'SB', 'BB']
POSITIONS_9 = ['UTG', 'UTG1', 'UTG2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']

# 橢圓牌桌座位座標 (pos, x, y) — canvas 280×110
_SEATS_6 = [
    ('BTN', 140,  14),
    ('CO',  228,  36),
    ('HJ',  228,  76),
    ('UTG', 140,  98),
    ('BB',   52,  76),
    ('SB',   52,  36),
]
_SEATS_9_EXTRA = {
    'UTG1': (186, 100), 'UTG2': (228,  98), 'LJ': (228, 58),
}

# ── Scenario 對照表 ────────────────────────────────────────────────────────────
_SCENARIO_MAP: Dict[tuple, str] = {
    ('UTG', 'open', None,  None):  'rfi_utg',
    ('HJ',  'open', None,  None):  'rfi_hj',
    ('CO',  'open', None,  None):  'rfi_co',
    ('BTN', 'open', None,  None):  'rfi_btn',
    ('SB',  'open', None,  None):  'rfi_sb',
    ('BB',  'call', 'UTG', None):  'bb_vs_utg',
    ('BB',  'call', 'HJ',  None):  'bb_vs_hj',
    ('BB',  'call', 'CO',  None):  'bb_vs_co',
    ('BB',  'call', 'BTN', None):  'bb_vs_btn',
    ('BB',  'call', 'SB',  None):  'bb_vs_sb',
    ('BB',  'open', 'BTN', None):  'threebet_bb_vs_btn',
    ('BB',  'open', 'CO',  None):  'threebet_bb_vs_co',
    ('BTN', 'open', 'UTG', None):  'threebet_btn_vs_utg',
    ('BTN', 'open', 'HJ',  None):  'threebet_btn_vs_hj',
    ('BTN', 'open', 'CO',  None):  'threebet_btn_vs_co',
    ('CO',  'open', 'UTG', None):  'threebet_co_vs_utg',
    ('CO',  'open', 'HJ',  None):  'threebet_co_vs_hj',
    ('*',   'call', '*',   '*'):   'vs3bet_call',
    ('*',   'open', '*',   '*'):   'vs3bet_4bet',
    ('UTG1','open', None,  None):  'rfi_utg1_9',
    ('UTG2','open', None,  None):  'rfi_utg2_9',
    ('LJ',  'open', None,  None):  'rfi_lj_9',
    ('BB',  'call', 'UTG1',None):  'bb_vs_utg1_9',
    ('BB',  'call', 'UTG2',None):  'bb_vs_utg2_9',
    ('BB',  'call', 'LJ',  None):  'bb_vs_lj_9',
    ('BB',  'open', 'UTG1',None):  'threebet_bb_vs_co',
    ('BB',  'open', 'UTG2',None):  'threebet_bb_vs_co',
    ('BB',  'open', 'LJ',  None):  'threebet_bb_vs_co',
    ('BTN', 'open', 'UTG1',None):  'threebet_btn_vs_utg',
    ('BTN', 'open', 'UTG2',None):  'threebet_btn_vs_hj',
    ('BTN', 'open', 'LJ',  None):  'threebet_btn_vs_hj',
    ('CO',  'open', 'UTG1',None):  'threebet_co_vs_utg',
    ('CO',  'open', 'UTG2',None):  'threebet_co_vs_hj',
}

_SCENARIO_ZH: Dict[str, str] = {
    'rfi_utg':             'UTG 開牌',
    'rfi_hj':              'HJ 開牌',
    'rfi_co':              'CO 開牌',
    'rfi_btn':             'BTN 開牌',
    'rfi_sb':              'SB 開牌',
    'bb_vs_utg':           'BB 防守 vs UTG',
    'bb_vs_hj':            'BB 防守 vs HJ',
    'bb_vs_co':            'BB 防守 vs CO',
    'bb_vs_btn':           'BB 防守 vs BTN',
    'bb_vs_sb':            'BB 防守 vs SB',
    'threebet_btn_vs_utg': 'BTN 3注 vs UTG',
    'threebet_btn_vs_hj':  'BTN 3注 vs HJ',
    'threebet_btn_vs_co':  'BTN 3注 vs CO',
    'threebet_co_vs_utg':  'CO 3注 vs UTG',
    'threebet_co_vs_hj':   'CO 3注 vs HJ',
    'threebet_bb_vs_btn':  'BB 3注 vs BTN',
    'threebet_bb_vs_co':   'BB 3注 vs CO',
    'vs3bet_call':         '面對3注 — 跟注',
    'vs3bet_4bet':         '面對3注 — 4注',
    'rfi_utg1_9':          'UTG+1 開牌',
    'rfi_utg2_9':          'UTG+2 開牌',
    'rfi_lj_9':            'LJ 開牌',
    'bb_vs_utg1_9':        'BB 防守 vs UTG+1',
    'bb_vs_utg2_9':        'BB 防守 vs UTG+2',
    'bb_vs_lj_9':          'BB 防守 vs LJ',
}


def _derive_scenario(hero_pos, opener, three_bettor, hero_action) -> Optional[str]:
    key = (hero_pos, hero_action, opener, three_bettor)
    if key in _SCENARIO_MAP:
        return _SCENARIO_MAP[key]
    if three_bettor is not None:
        wk = ('*', hero_action, '*', '*')
        if wk in _SCENARIO_MAP:
            return _SCENARIO_MAP[wk]
    return None


# ── 格子著色 ──────────────────────────────────────────────────────────────────
def _cell_bg(freq, hl):
    if hl:           return '#FFFFFF'
    if freq >= 0.9:  return '#163A1A'
    if freq >= 0.5:  return '#3A3000'
    if freq >= 0.1:  return '#3A1800'
    return '#0E0E14'

def _cell_fg(freq, hl):
    if hl:           return '#000000'
    if freq >= 0.9:  return '#4ACA60'
    if freq >= 0.5:  return '#C8A030'
    if freq >= 0.1:  return '#C86040'
    return '#3A4050'

def _ev_cell_bg(raise_f, call_f, hl):
    if hl: return '#FFFFFF'
    score = raise_f * 1.0 + call_f * 0.4
    if score >= 0.7:  return '#0A2A12'
    if score >= 0.4:  return '#183010'
    if score >= 0.15: return '#302800'
    if score > 0:     return '#301200'
    return '#0E0E14'

def _ev_cell_fg(raise_f, call_f, hl):
    if hl: return '#000000'
    score = raise_f * 1.0 + call_f * 0.4
    if score >= 0.7:  return '#00E070'
    if score >= 0.4:  return '#70D030'
    if score >= 0.15: return '#C8B000'
    if score > 0:     return '#C06000'
    return '#3A4050'

_COMBO_COUNT = {'s': 4, 'o': 12, 'p': 6}
CELL, PAD, HDR = 34, 2, 20


class RangePanel:
    def __init__(self, parent_root=None, hero_pos: str = 'BTN'):
        self._win = tk.Toplevel(parent_root) if parent_root else tk.Tk()
        self._win.title('翻前範圍表')
        self._win.configure(bg=BG)
        self._win.attributes('-topmost', True)
        self._win.resizable(False, False)

        self._table:       str           = '6max'
        self._hero_pos:    str           = hero_pos
        self._opener:      Optional[str] = None
        self._three_bet:   Optional[str] = None
        self._hero_action: str           = 'open'
        self._highlight:   Optional[tuple] = None
        self._ev_mode:     bool          = False
        self._freq_view:   Optional[str] = None   # 'raise'/'call'/'fold'/None

        self._build_table_toggle()
        self._build_oval_table()
        self._build_freq_bars()
        self._sep()
        self._build_hand_filter()
        self._build_grid()
        self._build_info()
        self._build_hover_detail()
        self._refresh()

    # ══════════════════════════════════════════════════════════════
    # 桌型切換
    # ══════════════════════════════════════════════════════════════

    def _build_table_toggle(self):
        bar = tk.Frame(self._win, bg=BG2)
        bar.pack(fill='x')

        tk.Label(bar, text='桌型', bg=BG2, fg=DIM,
                 font=('Consolas', 8)).pack(side='left', padx=(8, 4), pady=4)

        self._btn_6max = tk.Button(
            bar, text='6人桌', width=6,
            bg=SEL, fg='#FFFFFF', font=('Consolas', 8),
            relief='flat', cursor='hand2',
            command=lambda: self._set_table('6max'))
        self._btn_6max.pack(side='left', padx=2, pady=3)

        self._btn_9max = tk.Button(
            bar, text='9人桌', width=6,
            bg=BG3, fg=DIM, font=('Consolas', 8),
            relief='flat', cursor='hand2',
            command=lambda: self._set_table('9max'))
        self._btn_9max.pack(side='left', padx=2, pady=3)

        # 圖例
        leg = tk.Frame(bar, bg=BG2)
        leg.pack(side='right', padx=8)
        for text, color in [('加注', BAR_RAISE), ('跟注', BAR_CALL), ('棄牌', BAR_FOLD)]:
            tk.Frame(leg, bg=color, width=10, height=8).pack(side='left', padx=1)
            tk.Label(leg, text=text, bg=BG2, fg=DIM,
                     font=('Consolas', 7)).pack(side='left', padx=(0, 6))

    def _set_table(self, table: str):
        self._table = table
        self._btn_6max.config(bg=SEL    if table == '6max' else BG3,
                               fg='#FFF' if table == '6max' else DIM)
        self._btn_9max.config(bg=SEL    if table == '9max' else BG3,
                               fg='#FFF' if table == '9max' else DIM)
        self._opener = self._three_bet = None
        self._redraw_seats()
        self._refresh()

    def _positions(self):
        return POSITIONS_9 if self._table == '9max' else POSITIONS_6

    # ══════════════════════════════════════════════════════════════
    # 橢圓牌桌 + 座位
    # ══════════════════════════════════════════════════════════════

    def _build_oval_table(self):
        outer = tk.Frame(self._win, bg=BG2, pady=4)
        outer.pack(fill='x', padx=4, pady=(4, 0))

        # 情境說明列
        self._scenario_lbl = tk.Label(
            outer, text='點擊座位選擇位置', bg=BG2, fg=DIM,
            font=('Consolas', 9, 'bold'), anchor='w')
        self._scenario_lbl.pack(fill='x', padx=8, pady=(0, 4))

        # 牌桌畫布
        self._table_canvas = tk.Canvas(
            outer, width=280, height=110,
            bg=BG2, highlightthickness=0)
        self._table_canvas.pack()

        # 氈面橢圓
        cx, cy, rx, ry = 140, 55, 105, 40
        self._table_canvas.create_oval(
            cx-rx, cy-ry, cx+rx, cy+ry,
            fill=FELT_BG, outline=FELT_LINE, width=3)
        self._table_canvas.create_oval(
            cx-rx+8, cy-ry+6, cx+rx-8, cy+ry-6,
            fill='', outline='#0F200F', width=1)

        # 莊家籌碼（D）
        self._dealer_chip = self._table_canvas.create_text(
            158, 14, text='D', fill='#A08018',
            font=('Consolas', 6, 'bold'))

        # 座位橢圓
        self._seat_ovals: dict = {}
        for (pos, sx, sy) in _SEATS_6:
            tag = f'seat_{pos}'
            ov = self._table_canvas.create_oval(
                sx-18, sy-10, sx+18, sy+10,
                fill=SEAT_NORMAL, outline='#2A3A4A', width=1, tags=tag)
            tx = self._table_canvas.create_text(
                sx, sy, text=pos,
                fill=SEAT_LBL, font=('Consolas', 7, 'bold'), tags=tag)
            self._table_canvas.tag_bind(tag, '<Button-1>',
                lambda e, p=pos: self._on_seat_click(p))
            self._table_canvas.tag_bind(tag, '<Button-3>',
                lambda e, p=pos: self._on_seat_right_click(p))
            self._table_canvas.tag_bind(tag, '<Control-Button-1>',
                lambda e, p=pos: self._on_seat_right_click(p))
            self._table_canvas.tag_bind(tag, '<Enter>',
                lambda e, p=pos: self._on_seat_hover(p, True))
            self._table_canvas.tag_bind(tag, '<Leave>',
                lambda e, p=pos: self._on_seat_hover(p, False))
            self._seat_ovals[pos] = (ov, tx)

        # 清除按鈕（右側）
        tk.Button(outer, text='重置', bg=BG3, fg=DIM,
                  font=('Consolas', 7), relief='flat', cursor='hand2',
                  command=self._reset_tree).pack(side='right', padx=8, pady=2)

        # 開牌者說明列
        self._opener_lbl = tk.Label(
            outer, text='左鍵=選自己  右鍵/Ctrl+左鍵=選開牌者',
            bg=BG2, fg='#3A4A5A', font=('Consolas', 6), anchor='w')
        self._opener_lbl.pack(fill='x', padx=8)

        self._redraw_seats()

    def _on_seat_click(self, pos: str):
        """左鍵：設 Hero 位置，並更新行動。"""
        if self._opener is None:
            self._hero_pos    = pos
            self._hero_action = 'open'
        elif pos == self._hero_pos:
            # 再點自己：切換 open / call
            self._hero_action = 'call' if self._hero_action == 'open' else 'open'
        else:
            self._hero_pos    = pos
            self._hero_action = 'call'
        self._redraw_seats()
        self._refresh()

    def _on_seat_right_click(self, pos: str):
        """右鍵：設此座位為開牌者。"""
        if pos != self._hero_pos:
            self._opener      = pos
            self._three_bet   = None
            self._hero_action = 'call'
        else:
            self._opener = None
        self._redraw_seats()
        self._refresh()

    def _on_seat_hover(self, pos: str, entering: bool):
        if pos not in self._seat_ovals:
            return
        ov, _ = self._seat_ovals[pos]
        is_active = (pos == self._hero_pos or pos == self._opener)
        if entering and not is_active:
            self._table_canvas.itemconfig(ov, outline='#4A6A8A', width=2)
        elif not entering and not is_active:
            self._table_canvas.itemconfig(ov, outline='#2A3A4A', width=1)

    def _redraw_seats(self):
        for pos, (ov, tx) in self._seat_ovals.items():
            if pos == self._hero_pos:
                fill, outline, w, fg = SEAT_HERO, '#3A6ABF', 2, '#FFFFFF'
            elif pos == self._opener:
                fill, outline, w, fg = SEAT_OPENER, '#A06018', 2, '#D09030'
            else:
                fill, outline, w, fg = SEAT_NORMAL, '#2A3A4A', 1, SEAT_LBL
            self._table_canvas.itemconfig(ov, fill=fill, outline=outline, width=w)
            self._table_canvas.itemconfig(tx, fill=fg)

        # 莊家籌碼跟著 BTN（如果 hero 是 BTN 就變暗）
        d_col = '#806010' if self._hero_pos == 'BTN' else '#A08018'
        self._table_canvas.itemconfig(self._dealer_chip, fill=d_col)

    def _reset_tree(self):
        self._opener = self._three_bet = None
        self._hero_action = 'open'
        self._freq_view   = None
        self._redraw_seats()
        self._refresh()

    # ══════════════════════════════════════════════════════════════
    # 行動頻率條（可點選篩選範圍格）
    # ══════════════════════════════════════════════════════════════

    def _build_freq_bars(self):
        outer = tk.Frame(self._win, bg=BG2, pady=2)
        outer.pack(fill='x', padx=4)

        self._freq_canvas = tk.Canvas(
            outer, height=60, bg=BG2, highlightthickness=0)
        self._freq_canvas.pack(fill='x', padx=8, pady=(2, 0))
        self._freq_canvas.bind('<Configure>', lambda e: self._redraw_freq_bars())
        self._freq_canvas.bind('<Button-1>',  self._on_freq_bar_click)
        self._freq_bar_bounds: list = []

        self._freq_hint_lbl = tk.Label(
            outer, text='點擊頻率條篩選範圍',
            bg=BG2, fg='#2A3A4A', font=('Consolas', 6), anchor='w')
        self._freq_hint_lbl.pack(fill='x', padx=8)

    def _calc_scenario_freqs(self, scenario: Optional[str]) -> tuple:
        """計算當前情境的加注%/跟注%/棄牌%（按組合數加權）。"""
        if not scenario:
            return 0.0, 0.0, 1.0
        mixed = MIXED_ACTIONS.get(scenario, {})
        total_w = raise_w = call_w = 0.0
        for hand, (rf, cf) in mixed.items():
            n = combo_count(hand)
            total_w += n
            raise_w += n * rf
            call_w  += n * cf
        if total_w == 0:
            return 0.0, 0.0, 1.0
        r = raise_w / total_w
        c = call_w  / total_w
        return r, c, max(0.0, 1.0 - r - c)

    def _redraw_freq_bars(self):
        c = self._freq_canvas
        c.delete('all')
        self._freq_bar_bounds.clear()

        scenario = self._get_current_scenario()
        r_pct, call_pct, fold_pct = self._calc_scenario_freqs(scenario)

        w      = c.winfo_width() or 264
        bar_h  = 16
        gap    = 2
        lbl_w  = 52
        bar_w  = w - lbl_w - 6

        rows = [
            ('raise', '加注/開牌', BAR_RAISE, r_pct),
            ('call',  '跟注/防守', BAR_CALL,  call_pct),
            ('fold',  '棄  牌',   BAR_FOLD,  fold_pct),
        ]
        for i, (action, label, color, pct) in enumerate(rows):
            y0 = i * (bar_h + gap) + 2
            y1 = y0 + bar_h
            mid_y = (y0 + y1) // 2

            # 標籤
            c.create_text(lbl_w - 4, mid_y, text=label,
                          fill=DIM, font=('Consolas', 7), anchor='e')
            # 背景軌道
            c.create_rectangle(lbl_w, y0, lbl_w + bar_w, y1,
                               fill=BG3, outline=BORDER)
            # 填充
            fill_x = lbl_w + max(1, int(bar_w * pct))
            c.create_rectangle(lbl_w, y0, fill_x, y1,
                               fill=color, outline='')
            # 百分比文字
            pct_str = f'{int(pct * 100)}%'
            c.create_text(lbl_w + bar_w - 4, mid_y, text=pct_str,
                          fill=FG, font=('Consolas', 7, 'bold'), anchor='e')
            # 選中外框
            if self._freq_view == action:
                c.create_rectangle(lbl_w, y0, lbl_w + bar_w, y1,
                                   fill='', outline=BAR_SEL_OUT, width=2)
            # 命中區域記錄
            self._freq_bar_bounds.append((lbl_w, y0, lbl_w + bar_w, y1, action))

    def _on_freq_bar_click(self, event):
        for (x0, y0, x1, y1, action) in self._freq_bar_bounds:
            if x0 <= event.x <= x1 and y0 <= event.y <= y1:
                if self._freq_view == action:
                    self._freq_view = None
                    self._freq_hint_lbl.config(text='點擊頻率條篩選範圍', fg='#2A3A4A')
                else:
                    self._freq_view = action
                    labels = {'raise': '顯示：加注/開牌範圍',
                              'call':  '顯示：跟注/防守範圍',
                              'fold':  '顯示：棄牌區（灰色）'}
                    self._freq_hint_lbl.config(
                        text=labels.get(action, ''), fg=ACCENT)
                self._redraw_freq_bars()
                self._refresh()
                break

    # ══════════════════════════════════════════════════════════════
    # 手牌搜尋列
    # ══════════════════════════════════════════════════════════════

    def _build_hand_filter(self):
        bar = tk.Frame(self._win, bg=BG2, pady=4)
        bar.pack(fill='x', padx=4)
        tk.Label(bar, text='手牌:', bg=BG2, fg=DIM,
                 font=('Consolas', 9)).pack(side='left', padx=(8, 2))
        self._hand_var = tk.StringVar()
        e = tk.Entry(bar, textvariable=self._hand_var, bg=BG3, fg=FG,
                     insertbackground=FG, font=('Consolas', 10),
                     width=6, relief='flat', bd=4)
        e.pack(side='left', padx=4)
        e.bind('<KeyRelease>', lambda _: self._on_hand_changed())

        # 圖例
        for text, color in [('永遠', '#4ACA60'), ('混合', '#C8A030'),
                             ('偶爾', '#C86040'), ('棄牌', '#3A4050')]:
            tk.Label(bar, text='●', bg=BG2, fg=color,
                     font=('Consolas', 9)).pack(side='right')
            tk.Label(bar, text=text, bg=BG2, fg=DIM,
                     font=('Consolas', 8)).pack(side='right', padx=(0, 4))

        self._ev_mode_btn = tk.Button(
            bar, text='EV熱圖', bg=BG3, fg=DIM,
            font=('Consolas', 8), relief='flat', cursor='hand2',
            command=self._toggle_ev_mode)
        self._ev_mode_btn.pack(side='right', padx=8)

    # ══════════════════════════════════════════════════════════════
    # 13×13 範圍格
    # ══════════════════════════════════════════════════════════════

    def _sep(self):
        tk.Frame(self._win, bg=BORDER, height=1).pack(fill='x')

    def _build_grid(self):
        n = 13
        total_w = HDR + n * (CELL + PAD) + PAD
        total_h = HDR + n * (CELL + PAD) + PAD
        outer = tk.Frame(self._win, bg=BG)
        outer.pack(padx=4, pady=4)
        self._canvas = tk.Canvas(outer, width=total_w, height=total_h,
                                  bg=BG, highlightthickness=0)
        self._canvas.pack()
        self._cells = {}
        for i in range(n):
            x = PAD + HDR // 2
            y = HDR + i * (CELL + PAD) + CELL // 2
            self._canvas.create_text(x, y, text=RANKS[i], fill=DIM,
                                      font=('Consolas', 7, 'bold'))
            x2 = HDR + i * (CELL + PAD) + CELL // 2
            self._canvas.create_text(x2, HDR // 2, text=RANKS[i], fill=DIM,
                                      font=('Consolas', 7, 'bold'))
        for row in range(n):
            for col in range(n):
                x0 = HDR + col * (CELL + PAD) + PAD
                y0 = HDR + row * (CELL + PAD) + PAD
                x1, y1 = x0 + CELL, y0 + CELL
                hand = hand_at(row, col)
                rect = self._canvas.create_rectangle(
                    x0, y0, x1, y1, fill=_cell_bg(0, False),
                    outline=BORDER, width=1)
                txt = self._canvas.create_text(
                    (x0 + x1) / 2, (y0 + y1) / 2,
                    text=hand, fill=_cell_fg(0, False),
                    font=('Consolas', 6))
                self._cells[(row, col)] = (rect, txt, hand)
                self._canvas.tag_bind(rect, '<Enter>',
                                       lambda e, h=hand: self._on_hover(h))
                self._canvas.tag_bind(txt,  '<Enter>',
                                       lambda e, h=hand: self._on_hover(h))

    def _build_info(self):
        info = tk.Frame(self._win, bg=BG2, pady=4)
        info.pack(fill='x', padx=4)
        self._range_pct_lbl = tk.Label(
            info, text='', bg=BG2, fg=ACCENT, font=('Consolas', 9, 'bold'))
        self._range_pct_lbl.pack(side='left', padx=8)
        self._hand_action_lbl = tk.Label(
            info, text='', bg=BG2, fg=FG, font=('Consolas', 9, 'bold'))
        self._hand_action_lbl.pack(side='left', padx=4)
        self._hover_lbl = tk.Label(
            info, text='', bg=BG2, fg=DIM, font=('Consolas', 8))
        self._hover_lbl.pack(side='right', padx=8)

    def _build_hover_detail(self):
        self._detail_frame = tk.Frame(self._win, bg=BG3, pady=4)
        self._detail_frame.pack(fill='x', padx=4, pady=(0, 4))
        self._detail_lbl = tk.Label(
            self._detail_frame, text='懸停手牌格查看詳情',
            bg=BG3, fg='#2A3A4A', font=('Consolas', 8), anchor='w')
        self._detail_lbl.pack(fill='x', padx=8)

        # 混合策略視覺 bar
        self._mix_bar_canvas = tk.Canvas(
            self._detail_frame, height=10, bg=BG3, highlightthickness=0)
        self._mix_bar_canvas.pack(fill='x', padx=8, pady=(2, 0))

    # ══════════════════════════════════════════════════════════════
    # 刷新邏輯
    # ══════════════════════════════════════════════════════════════

    def _get_current_scenario(self) -> Optional[str]:
        if self._hero_action == 'fold':
            return None
        return _derive_scenario(
            self._hero_pos, self._opener, self._three_bet, self._hero_action)

    def _refresh(self):
        scenario = self._get_current_scenario()
        rng      = RANGES.get(scenario, {}) if scenario else {}

        self._canvas.delete('mixbar')

        for (row, col), (rect, txt, hand) in self._cells.items():
            freq = rng.get(hand, 0.0)
            hl   = (self._highlight == (row, col))
            raise_f, call_f = get_mixed_action(hand, scenario) if scenario else (0.0, 0.0)

            # 頻率條篩選
            fv = self._freq_view
            if fv == 'raise':
                eff = raise_f
            elif fv == 'call':
                eff = call_f
            elif fv == 'fold':
                eff = 1.0 - freq
            else:
                eff = freq

            if self._ev_mode and scenario:
                bg = _ev_cell_bg(raise_f, call_f, hl)
                fg = _ev_cell_fg(raise_f, call_f, hl)
            else:
                bg = _cell_bg(eff, hl)
                fg = _cell_fg(eff, hl)

            self._canvas.itemconfig(
                rect, fill=bg,
                outline='#FFFFFF' if hl else BORDER,
                width=2 if hl else 1)
            self._canvas.itemconfig(txt, fill=fg)

            # 底部混合策略 bar
            if freq > 0 and scenario and not hl:
                x0 = HDR + col * (CELL + PAD) + PAD
                y0 = HDR + row * (CELL + PAD) + PAD
                x1 = x0 + CELL
                by0, by1 = y0 + CELL - 4, y0 + CELL - 1
                cw = x1 - x0
                if raise_f > 0:
                    rw = max(1, int(cw * raise_f))
                    self._canvas.create_rectangle(
                        x0, by0, x0 + rw, by1,
                        fill=BAR_RAISE, outline='', tags='mixbar')
                if call_f > 0:
                    off = int(cw * raise_f)
                    cw2 = max(1, int(cw * call_f))
                    self._canvas.create_rectangle(
                        x0 + off, by0, x0 + off + cw2, by1,
                        fill=BAR_CALL, outline='', tags='mixbar')

        # 情境標籤
        if scenario:
            stats   = scenario_stats(scenario)
            pct     = stats['percent'] * 100
            scen_zh = _SCENARIO_ZH.get(scenario, scenario)
            lbl = f'▶  {scen_zh}  |  {pct:.1f}% ({int(stats["combos"])} 組合)'
            self._scenario_lbl.config(text=lbl, fg=ACCENT)
            self._range_pct_lbl.config(
                text=f'遊玩: {pct:.1f}%  ({int(stats["combos"])} 組合)')
        elif self._hero_action == 'fold':
            self._scenario_lbl.config(text='棄牌 — 不顯示範圍', fg='#555555')
            self._range_pct_lbl.config(text='')
        else:
            op = self._opener or '—'
            self._scenario_lbl.config(
                text=f'⚠  {self._hero_pos} 面對 {op} — 此情境無資料', fg='#8A6820')
            self._range_pct_lbl.config(text='')

        self._redraw_freq_bars()
        self._on_hand_changed()

    def _on_hand_changed(self):
        hand = self._hand_var.get().strip().upper()
        scenario = self._get_current_scenario()
        rng = RANGES.get(scenario, {}) if scenario else {}
        self._highlight = None
        if hand:
            for candidate in [hand, hand + 's', hand + 'o']:
                if candidate in rng:
                    self._highlight = hand_to_grid(candidate)
                    hand = candidate
                    break
        for (row, col), (rect, txt, _) in self._cells.items():
            hl = (self._highlight == (row, col))
            if hl:
                self._canvas.itemconfig(
                    rect, outline='#FFFFFF', width=2, fill='#FFFFFF')
                self._canvas.itemconfig(txt, fill='#000000')
        if hand and scenario and self._highlight:
            rec = recommend_preflop(hand, scenario)
            zh = {'RAISE':'加注','DEFEND':'防守','3-BET':'3注','CALL':'跟注',
                  'MIXED':'混合','FOLD':'棄牌','4-BET':'4注'}
            action_zh = zh.get(rec['action'], rec['action'])
            color = {'加注':'#4ACA60','防守':'#4ACA60','3注':'#A0A0F0',
                     '跟注':'#2F81F7','混合':'#C8A030','棄牌':'#C86040',
                     '4注':'#C07020'}.get(action_zh, FG)
            self._hand_action_lbl.config(
                text=f'{hand}: {action_zh}  ({int(rec["frequency"]*100)}%)',
                fg=color)
            # 更新 hover 詳情
            self._on_hover(hand)
        else:
            self._hand_action_lbl.config(text='')

    def _toggle_ev_mode(self):
        self._ev_mode = not self._ev_mode
        self._ev_mode_btn.config(
            bg=SEL if self._ev_mode else BG3,
            fg='#FFFFFF' if self._ev_mode else DIM,
            relief='solid' if self._ev_mode else 'flat', bd=1 if self._ev_mode else 0)
        self._refresh()

    def _on_hover(self, hand: str):
        scenario = self._get_current_scenario()
        if not scenario:
            self._detail_lbl.config(text='— 未選擇情境 —', fg='#2A3A4A')
            return
        freq        = get_frequency(hand, scenario)
        raise_f, call_f = get_mixed_action(hand, scenario)
        fold_f      = max(0.0, 1.0 - freq)
        combos_total = combo_count(hand)
        in_combos    = round(combos_total * freq)

        self._hover_lbl.config(
            text=f'{hand}: {"遊玩" if freq > 0 else "棄牌"}  {int(freq*100)}%')

        if freq > 0:
            r_pct = int(raise_f * 100)
            c_pct = int(call_f  * 100)
            f_pct = max(0, 100 - r_pct - c_pct)
            detail = (f'{hand}  ▸  {in_combos}/{combos_total} 組合  '
                      f'加注 {r_pct}%  跟注 {c_pct}%  棄牌 {f_pct}%')
            self._detail_lbl.config(text=detail, fg='#7ABADF')
            # 畫混合策略 bar
            self._draw_mix_bar(raise_f, call_f)
        else:
            self._detail_lbl.config(
                text=f'{hand}  —  棄牌（{combos_total} 組合不入範圍）', fg='#6A3030')
            self._mix_bar_canvas.delete('all')

    def _draw_mix_bar(self, raise_f: float, call_f: float):
        c = self._mix_bar_canvas
        c.delete('all')
        w = c.winfo_width() or 264
        fold_f = max(0.0, 1.0 - raise_f - call_f)
        segments = [
            (raise_f, BAR_RAISE, f'加{int(raise_f*100)}%'),
            (call_f,  BAR_CALL,  f'跟{int(call_f*100)}%'),
            (fold_f,  BAR_FOLD,  f'棄{int(fold_f*100)}%'),
        ]
        offset = 0
        for frac, color, label in segments:
            bw = int(w * frac)
            if bw > 0:
                c.create_rectangle(offset, 0, offset + bw, 10, fill=color, outline='')
                if bw > 20:
                    c.create_text(offset + bw // 2, 5, text=label,
                                  fill='#FFFFFF', font=('Consolas', 5))
            offset += bw

    # ══════════════════════════════════════════════════════════════
    # 外部 API
    # ══════════════════════════════════════════════════════════════

    def set_hero_pos(self, pos: str):
        if pos in POSITIONS:
            self._hero_pos = pos
            self._redraw_seats()
            self._refresh()

    def highlight_hand(self, hand: str):
        self._hand_var.set(hand)
        self._on_hand_changed()

    def set_scenario(self, scenario: str):
        if scenario in SCENARIOS:
            for (hp, ha, op, tb), sc in _SCENARIO_MAP.items():
                if sc == scenario and hp != '*':
                    self._hero_pos    = hp
                    self._hero_action = ha
                    self._opener      = op
                    self._three_bet   = tb
                    self._redraw_seats()
                    self._refresh()
                    return

    def run(self):
        self._win.mainloop()
