"""翻前範圍表 — GTO Wizard 風格行動樹 + 13×13 手牌格（支援 6人/9人桌）。

v2 改進（參考 GTO Wizard / PioSOLVER）：
  9. 懸停詳情 — hover 顯示 combo 數/頻率/混合策略分解
  10. EV 熱圖模式 — 切換頻率 ↔ EV 熱圖著色
"""

import tkinter as tk
from typing import Optional, Dict

from poker.ranges import (
    RANKS, hand_at, hand_to_grid, get_frequency,
    scenario_stats, recommend_preflop, SCENARIOS, RANGES, get_mixed_action
)

BG     = '#0D1117'
BG2    = '#161B22'
BG3    = '#21262D'
FG     = '#E6EDF3'
DIM    = '#8B949E'
ACCENT = '#58A6FF'
BORDER = '#30363D'
SEL    = '#1F6FEB'

POSITIONS_6 = ['UTG', 'HJ', 'CO', 'BTN', 'SB', 'BB']
POSITIONS_9 = ['UTG', 'UTG1', 'UTG2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']

# (hero_pos, hero_action, opener, three_bettor) → scenario
# hero_action: 'open'=開牌/3注, 'call'=跟注/防守
_SCENARIO_MAP: Dict[tuple, str] = {
    ('UTG', 'open', None,  None):  'rfi_utg',
    ('HJ',  'open', None,  None):  'rfi_hj',
    ('CO',  'open', None,  None):  'rfi_co',
    ('BTN', 'open', None,  None):  'rfi_btn',
    ('SB',  'open', None,  None):  'rfi_sb',
    # BB defense
    ('BB',  'call', 'UTG', None):  'bb_vs_utg',
    ('BB',  'call', 'HJ',  None):  'bb_vs_hj',
    ('BB',  'call', 'CO',  None):  'bb_vs_co',
    ('BB',  'call', 'BTN', None):  'bb_vs_btn',
    ('BB',  'call', 'SB',  None):  'bb_vs_sb',
    # BB 3-bet
    ('BB',  'open', 'BTN', None):  'threebet_bb_vs_btn',
    ('BB',  'open', 'CO',  None):  'threebet_bb_vs_co',
    # BTN 3-bet
    ('BTN', 'open', 'UTG', None):  'threebet_btn_vs_utg',
    ('BTN', 'open', 'HJ',  None):  'threebet_btn_vs_hj',
    ('BTN', 'open', 'CO',  None):  'threebet_btn_vs_co',
    # CO 3-bet
    ('CO',  'open', 'UTG', None):  'threebet_co_vs_utg',
    ('CO',  'open', 'HJ',  None):  'threebet_co_vs_hj',
    # vs 3-bet
    ('*',   'call', '*',   '*'):   'vs3bet_call',
    ('*',   'open', '*',   '*'):   'vs3bet_4bet',
    # 9-max RFI
    ('UTG1', 'open', None,  None): 'rfi_utg1_9',
    ('UTG2', 'open', None,  None): 'rfi_utg2_9',
    ('LJ',   'open', None,  None): 'rfi_lj_9',
    # 9-max BB defense
    ('BB', 'call', 'UTG1', None):  'bb_vs_utg1_9',
    ('BB', 'call', 'UTG2', None):  'bb_vs_utg2_9',
    ('BB', 'call', 'LJ',   None):  'bb_vs_lj_9',
    ('BB', 'open', 'UTG1', None):  'threebet_bb_vs_co',
    ('BB', 'open', 'UTG2', None):  'threebet_bb_vs_co',
    ('BB', 'open', 'LJ',   None):  'threebet_bb_vs_co',
    # 9-max BTN / CO 3-bet
    ('BTN', 'open', 'UTG1', None): 'threebet_btn_vs_utg',
    ('BTN', 'open', 'UTG2', None): 'threebet_btn_vs_hj',
    ('BTN', 'open', 'LJ',   None): 'threebet_btn_vs_hj',
    ('CO',  'open', 'UTG1', None): 'threebet_co_vs_utg',
    ('CO',  'open', 'UTG2', None): 'threebet_co_vs_hj',
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
    'vs3bet_call':         '面對3注 — 跟注範圍',
    'vs3bet_4bet':         '面對3注 — 4注範圍',
    'rfi_utg_9':    'UTG 開牌 (9人桌)',
    'rfi_utg1_9':   'UTG+1 開牌 (9人桌)',
    'rfi_utg2_9':   'UTG+2 開牌 (9人桌)',
    'rfi_lj_9':     'LJ 開牌 (9人桌)',
    'bb_vs_utg_9':  'BB 防守 vs UTG (9人桌)',
    'bb_vs_utg1_9': 'BB 防守 vs UTG+1 (9人桌)',
    'bb_vs_utg2_9': 'BB 防守 vs UTG+2 (9人桌)',
    'bb_vs_lj_9':   'BB 防守 vs LJ (9人桌)',
}


def _derive_scenario(hero_pos: str, opener: Optional[str],
                     three_bettor: Optional[str], hero_action: str) -> Optional[str]:
    key = (hero_pos, hero_action, opener, three_bettor)
    if key in _SCENARIO_MAP:
        return _SCENARIO_MAP[key]
    # wildcard vs 3-bet
    if three_bettor is not None:
        wk = ('*', hero_action, '*', '*')
        if wk in _SCENARIO_MAP:
            return _SCENARIO_MAP[wk]
    return None


def _cell_bg(freq, hl):
    if hl:           return '#FFFFFF'
    if freq >= 0.9:  return '#1A6B3A'
    if freq >= 0.5:  return '#5E4B00'
    if freq >= 0.1:  return '#5E2800'
    return '#1C2128'

def _cell_fg(freq, hl):
    if hl:           return '#000000'
    if freq >= 0.9:  return '#56D364'
    if freq >= 0.5:  return '#E3B341'
    if freq >= 0.1:  return '#FF7B54'
    return '#484F58'

# EV 熱圖：依 raise_freq 估算相對 EV（-1 到 +1 映射到顏色）
def _ev_cell_bg(raise_f, call_f, hl):
    if hl: return '#FFFFFF'
    score = raise_f * 1.0 + call_f * 0.4   # 簡化 EV 估算
    if score >= 0.7:  return '#0D3B1A'
    if score >= 0.4:  return '#1A3B10'
    if score >= 0.15: return '#3B3000'
    if score > 0:     return '#3B1500'
    return '#1C2128'

def _ev_cell_fg(raise_f, call_f, hl):
    if hl: return '#000000'
    score = raise_f * 1.0 + call_f * 0.4
    if score >= 0.7:  return '#00FF88'
    if score >= 0.4:  return '#88FF44'
    if score >= 0.15: return '#FFD700'
    if score > 0:     return '#FF8C00'
    return '#484F58'

# 牌型組合數
_COMBO_COUNT = {
    's': 4,   # suited
    'o': 12,  # offsuit
    'p': 6,   # pair
}

CELL, PAD, HDR = 34, 2, 20


class RangePanel:
    def __init__(self, parent_root=None, hero_pos: str = 'BTN'):
        self._win = tk.Toplevel(parent_root) if parent_root else tk.Tk()
        self._win.title('翻前範圍表')
        self._win.configure(bg=BG)
        self._win.attributes('-topmost', True)
        self._win.resizable(False, False)

        # 桌型 + 行動樹狀態
        self._table:       str           = '6max'  # '6max' | '9max'
        self._hero_pos:    str           = hero_pos
        self._opener:      Optional[str] = None
        self._three_bet:   Optional[str] = None
        self._hero_action: str           = 'open'
        self._highlight:   Optional[tuple] = None

        self._ev_mode = False   # False=頻率熱圖，True=EV熱圖

        self._build_table_toggle()
        self._build_action_tree()
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
        bar = tk.Frame(self._win, bg='#0A0F1A')
        bar.pack(fill='x')
        tk.Label(bar, text='桌型', bg='#0A0F1A', fg=DIM,
                 font=('Consolas', 8)).pack(side='left', padx=(8, 4))
        self._btn_6max = tk.Button(
            bar, text='6人桌', width=6,
            bg=SEL, fg='#FFFFFF', font=('Consolas', 8),
            relief='flat', cursor='hand2',
            command=lambda: self._set_table('6max'))
        self._btn_6max.pack(side='left', padx=2, pady=3)
        self._btn_9max = tk.Button(
            bar, text='9人桌', width=6,
            bg='#1C2128', fg=DIM, font=('Consolas', 8),
            relief='flat', cursor='hand2',
            command=lambda: self._set_table('9max'))
        self._btn_9max.pack(side='left', padx=2, pady=3)

        # 混合策略圖例
        leg = tk.Frame(bar, bg='#0A0F1A')
        leg.pack(side='right', padx=8)
        for text, color in [('加注/3注', '#E3611A'), ('跟注/防守', '#1A7AE3'), ('棄牌', '#444444')]:
            tk.Frame(leg, bg=color, width=12, height=8).pack(side='left', padx=1)
            tk.Label(leg, text=text, bg='#0A0F1A', fg=DIM,
                     font=('Consolas', 7)).pack(side='left', padx=(0, 5))

    def _set_table(self, table: str):
        self._table = table
        self._btn_6max.config(bg=SEL if table == '6max' else '#1C2128',
                               fg='#FFFFFF' if table == '6max' else DIM)
        self._btn_9max.config(bg=SEL if table == '9max' else '#1C2128',
                               fg='#FFFFFF' if table == '9max' else DIM)
        # 重建開牌者按鈕（位置不同）
        self._opener    = None
        self._three_bet = None
        self._rebuild_opener_buttons()
        self._rebuild_threebet_buttons()
        self._rebuild_hero_buttons()
        self._update_action_tree_ui()
        self._refresh()

    def _positions(self):
        return POSITIONS_9 if self._table == '9max' else POSITIONS_6

    # ══════════════════════════════════════════════════════════════
    # 行動樹
    # ══════════════════════════════════════════════════════════════

    def _build_action_tree(self):
        self._tree_outer = tk.Frame(self._win, bg=BG2, pady=6)
        self._tree_outer.pack(fill='x', padx=4, pady=(4, 0))

        # ── 行1: 開牌者 ─────────────────────────────────────────
        self._row1 = tk.Frame(self._tree_outer, bg=BG2)
        self._row1.pack(fill='x', padx=8, pady=(0, 4))
        self._opener_btns: Dict[str, tk.Button] = {}
        self._rebuild_opener_buttons()

        # ── 行2: 3注者 ──────────────────────────────────────────
        self._row2 = tk.Frame(self._tree_outer, bg=BG2)
        self._row2.pack(fill='x', padx=8, pady=(0, 4))
        self._threebet_btns: Dict[str, tk.Button] = {}
        self._no3bet_btn = None
        self._rebuild_threebet_buttons()

        # ── 行3: Hero位置 ────────────────────────────────────────
        self._row3 = tk.Frame(self._tree_outer, bg=BG2)
        self._row3.pack(fill='x', padx=8, pady=(0, 2))
        self._hero_pos_btns: Dict[str, tk.Button] = {}
        self._rebuild_hero_buttons()

    def _rebuild_opener_buttons(self):
        for w in self._row1.winfo_children(): w.destroy()
        self._opener_btns.clear()
        tk.Label(self._row1, text='開牌者', bg=BG2, fg=DIM,
                 font=('Consolas', 8), width=7, anchor='w').pack(side='left')
        tk.Button(self._row1, text='無', width=4,
                  bg='#1C2128', fg=DIM, font=('Consolas', 8),
                  relief='flat', cursor='hand2',
                  command=lambda: self._set_opener(None)).pack(side='left', padx=2)
        for pos in self._positions()[:-1]:
            btn = tk.Button(self._row1, text=pos, width=5 if len(pos) > 3 else 4,
                            bg='#1C2128', fg=DIM,
                            font=('Consolas', 8), relief='flat', cursor='hand2',
                            command=lambda p=pos: self._set_opener(p))
            btn.pack(side='left', padx=1)
            self._opener_btns[pos] = btn

    def _rebuild_threebet_buttons(self):
        for w in self._row2.winfo_children(): w.destroy()
        self._threebet_btns.clear()
        tk.Label(self._row2, text='3注者', bg=BG2, fg=DIM,
                 font=('Consolas', 8), width=7, anchor='w').pack(side='left')
        self._no3bet_btn = tk.Button(
            self._row2, text='無', width=4,
            bg=SEL, fg='#FFFFFF', font=('Consolas', 8),
            relief='flat', cursor='hand2',
            command=lambda: self._set_three_bet(None))
        self._no3bet_btn.pack(side='left', padx=2)
        for pos in self._positions()[1:]:
            btn = tk.Button(self._row2, text=pos, width=5 if len(pos) > 3 else 4,
                            bg='#1C2128', fg=DIM,
                            font=('Consolas', 8), relief='flat', cursor='hand2',
                            command=lambda p=pos: self._set_three_bet(p))
            btn.pack(side='left', padx=1)
            self._threebet_btns[pos] = btn

    def _rebuild_hero_buttons(self):
        for w in self._row3.winfo_children(): w.destroy()
        self._hero_pos_btns.clear()
        tk.Label(self._row3, text='Hero', bg=BG2, fg=DIM,
                 font=('Consolas', 8), width=7, anchor='w').pack(side='left')
        for pos in self._positions():
            btn = tk.Button(self._row3, text=pos, width=5 if len(pos) > 3 else 4,
                            bg='#1C2128', fg=DIM,
                            font=('Consolas', 8), relief='flat', cursor='hand2',
                            command=lambda p=pos: self._set_hero_pos(p))
            btn.pack(side='left', padx=1)
            self._hero_pos_btns[pos] = btn

        # ── 行4: Hero 行動 ───────────────────────────────────────
        row4 = tk.Frame(self._tree_outer, bg=BG2)
        row4.pack(fill='x', padx=8, pady=(4, 2))
        tk.Label(row4, text='行動', bg=BG2, fg=DIM,
                 font=('Consolas', 8), width=7, anchor='w').pack(side='left')
        self._action_btns: Dict[str, tk.Button] = {}
        action_defs = [
            ('fold', '棄牌', '#442222', '#FF8888'),
            ('call', '跟/防守', '#1C2D1C', '#56D364'),
            ('open', '開/3注/4注', '#1C2840', '#58A6FF'),
        ]
        for key, label, bg, fg in action_defs:
            btn = tk.Button(row4, text=label, padx=8,
                            bg=bg, fg=fg,
                            font=('Consolas', 8), relief='flat', cursor='hand2',
                            command=lambda k=key: self._set_hero_action(k))
            btn.pack(side='left', padx=3)
            self._action_btns[key] = btn

        # ── 情境說明 ─────────────────────────────────────────────
        if not hasattr(self, '_scenario_lbl'):
            self._scenario_lbl = tk.Label(
                self._tree_outer, text='', bg=BG2, fg=ACCENT,
                font=('Consolas', 9, 'bold'), anchor='w')
            self._scenario_lbl.pack(fill='x', padx=8, pady=(4, 2))

        self._update_action_tree_ui()

    def _set_opener(self, pos: Optional[str]):
        self._opener = pos
        self._three_bet = None   # 重置3注
        self._update_action_tree_ui()
        self._refresh()

    def _set_three_bet(self, pos: Optional[str]):
        self._three_bet = pos
        self._update_action_tree_ui()
        self._refresh()

    def _set_hero_pos(self, pos: str):
        self._hero_pos = pos
        self._update_action_tree_ui()
        self._refresh()

    def _set_hero_action(self, action: str):
        self._hero_action = action
        self._refresh_action_btn_colors()
        self._refresh()

    def _update_action_tree_ui(self):
        # 開牌者按鈕顏色
        for pos, btn in self._opener_btns.items():
            if pos == self._opener:
                btn.config(bg='#B45309', fg='#FDE68A')
            else:
                btn.config(bg='#1C2128', fg=DIM)

        # 3注者按鈕顯示（只有在有開牌者時才有意義）
        if self._opener:
            self._row2.pack(fill='x', padx=8, pady=(0, 4))
        else:
            self._row2.pack_forget()

        self._no3bet_btn.config(bg=SEL if self._three_bet is None else '#1C2128',
                                 fg='#FFFFFF' if self._three_bet is None else DIM)
        for pos, btn in self._threebet_btns.items():
            if pos == self._three_bet:
                btn.config(bg='#7C3AED', fg='#DDD6FE')
            else:
                btn.config(bg='#1C2128', fg=DIM)

        # Hero 位置按鈕顏色
        for pos, btn in self._hero_pos_btns.items():
            if pos == self._hero_pos:
                btn.config(bg=SEL, fg='#FFFFFF')
            else:
                btn.config(bg='#1C2128', fg=DIM)

        self._refresh_action_btn_colors()

    def _refresh_action_btn_colors(self):
        colors = {
            'fold': ('#662222', '#FF8888', '#442222', '#FF8888'),
            'call': ('#1A4D1A', '#88FF88', '#1C2D1C', '#56D364'),
            'open': ('#1A3A6B', '#88BBFF', '#1C2840', '#58A6FF'),
        }
        for key, btn in self._action_btns.items():
            sel_bg, sel_fg, nrm_bg, nrm_fg = colors[key]
            if key == self._hero_action:
                btn.config(bg=sel_bg, fg=sel_fg, relief='solid', bd=1)
            else:
                btn.config(bg=nrm_bg, fg=nrm_fg, relief='flat', bd=0)

    def _get_current_scenario(self) -> Optional[str]:
        if self._hero_action == 'fold':
            return None
        return _derive_scenario(
            self._hero_pos, self._opener, self._three_bet, self._hero_action)

    # ══════════════════════════════════════════════════════════════
    # 手牌搜尋
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

        for text, color in [('永遠', '#56D364'), ('混合', '#E3B341'),
                             ('偶爾', '#FF7B54'), ('棄牌', '#484F58')]:
            tk.Label(bar, text='●', bg=BG2, fg=color,
                     font=('Consolas', 9)).pack(side='right')
            tk.Label(bar, text=text, bg=BG2, fg=DIM,
                     font=('Consolas', 8)).pack(side='right', padx=(0, 4))

        tk.Button(bar, text='清除行動', bg='#1C2128', fg=DIM,
                  font=('Consolas', 8), relief='flat', cursor='hand2',
                  command=self._reset_tree).pack(side='right', padx=8)

        # EV 熱圖切換按鈕（PioSOLVER 風格）
        self._ev_mode_btn = tk.Button(
            bar, text='EV 熱圖', bg='#1C2128', fg=DIM,
            font=('Consolas', 8), relief='flat', cursor='hand2',
            command=self._toggle_ev_mode)
        self._ev_mode_btn.pack(side='right', padx=4)

    def _reset_tree(self):
        self._opener    = None
        self._three_bet = None
        self._hero_action = 'open'
        self._update_action_tree_ui()
        self._refresh()

    # ══════════════════════════════════════════════════════════════
    # 範圍格
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
        info.pack(fill='x', padx=4, pady=(0, 0))
        self._range_pct_lbl = tk.Label(
            info, text='', bg=BG2, fg=ACCENT,
            font=('Consolas', 9, 'bold'))
        self._range_pct_lbl.pack(side='left', padx=8)
        self._hand_action_lbl = tk.Label(
            info, text='', bg=BG2, fg=FG,
            font=('Consolas', 9, 'bold'))
        self._hand_action_lbl.pack(side='left', padx=4)
        self._hover_lbl = tk.Label(
            info, text='', bg=BG2, fg=DIM,
            font=('Consolas', 8))
        self._hover_lbl.pack(side='right', padx=8)

    def _build_hover_detail(self):
        """懸停詳情面板（GTO Wizard 風格：combo/頻率/混合策略分解）。"""
        self._detail_frame = tk.Frame(self._win, bg='#0A0F1A', pady=4)
        self._detail_frame.pack(fill='x', padx=4, pady=(0, 4))
        self._detail_lbl = tk.Label(
            self._detail_frame, text='滑鼠懸停手牌格查看詳情',
            bg='#0A0F1A', fg='#3A4A5A',
            font=('Consolas', 8), anchor='w')
        self._detail_lbl.pack(fill='x', padx=8)

    # ══════════════════════════════════════════════════════════════
    # 刷新邏輯
    # ══════════════════════════════════════════════════════════════

    def _refresh(self):
        scenario = self._get_current_scenario()
        rng = RANGES.get(scenario, {}) if scenario else {}

        # 清除舊的混合策略 bar
        self._canvas.delete('mixbar')

        for (row, col), (rect, txt, hand) in self._cells.items():
            freq = rng.get(hand, 0.0)
            hl   = (self._highlight == (row, col))
            if self._ev_mode and scenario:
                raise_f, call_f = get_mixed_action(hand, scenario)
                bg = _ev_cell_bg(raise_f, call_f, hl)
                fg = _ev_cell_fg(raise_f, call_f, hl)
            else:
                bg = _cell_bg(freq, hl)
                fg = _cell_fg(freq, hl)
            self._canvas.itemconfig(
                rect, fill=bg,
                outline='#FFFFFF' if hl else BORDER,
                width=2 if hl else 1)
            self._canvas.itemconfig(txt, fill=fg)

            # 混合策略彩色 bar（格子底部 4px）
            if freq > 0 and scenario and not hl:
                raise_f, call_f = get_mixed_action(hand, scenario)
                x0 = HDR + col * (CELL + PAD) + PAD
                y0 = HDR + row * (CELL + PAD) + PAD
                x1 = x0 + CELL
                bar_y0 = y0 + CELL - 4
                bar_y1 = y0 + CELL - 1
                cw = x1 - x0
                # 加注條（橘色）
                if raise_f > 0:
                    rw = max(1, int(cw * raise_f))
                    self._canvas.create_rectangle(
                        x0, bar_y0, x0 + rw, bar_y1,
                        fill='#E3611A', outline='', tags='mixbar')
                # 跟注條（藍色）
                if call_f > 0:
                    r_off = int(cw * raise_f)
                    cw2 = max(1, int(cw * call_f))
                    self._canvas.create_rectangle(
                        x0 + r_off, bar_y0, x0 + r_off + cw2, bar_y1,
                        fill='#1A7AE3', outline='', tags='mixbar')

        if scenario:
            stats   = scenario_stats(scenario)
            pct     = stats['percent'] * 100
            scen_zh = _SCENARIO_ZH.get(scenario, scenario)
            self._scenario_lbl.config(
                text=f'▶  {scen_zh}  |  {pct:.1f}% ({int(stats["combos"])} 組合)',
                fg=ACCENT)
            self._range_pct_lbl.config(
                text=f'遊玩: {pct:.1f}%  ({int(stats["combos"])} 組合)')
        elif self._hero_action == 'fold':
            self._scenario_lbl.config(text='棄牌 — 不顯示範圍', fg='#888888')
            self._range_pct_lbl.config(text='')
        else:
            pos = self._hero_pos
            op  = self._opener or '—'
            self._scenario_lbl.config(
                text=f'⚠  {pos} 面對 {op} — 此情境暫無資料', fg='#E3B341')
            self._range_pct_lbl.config(text='')

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
        # 只更新 highlight 格子，不全刷
        for (row, col), (rect, txt, _) in self._cells.items():
            hl = (self._highlight == (row, col))
            if hl:
                self._canvas.itemconfig(
                    rect, outline='#FFFFFF', width=2, fill='#FFFFFF')
                self._canvas.itemconfig(txt, fill='#000000')

        if hand and scenario and self._highlight:
            rec = recommend_preflop(hand, scenario)
            zh = {'RAISE':'加注','DEFEND':'防守','3-BET':'3注',
                  'CALL':'跟注','MIXED':'混合','FOLD':'棄牌','4-BET':'4注'}
            action_zh = zh.get(rec['action'], rec['action'])
            color = {'加注':'#56D364','防守':'#56D364','3注':'#DDD6FE',
                     '跟注':'#58A6FF','混合':'#E3B341','棄牌':'#FF7B54',
                     '4注':'#FF9900'}.get(action_zh, FG)
            self._hand_action_lbl.config(
                text=f'{hand}: {action_zh}  ({int(rec["frequency"]*100)}%)',
                fg=color)
        else:
            self._hand_action_lbl.config(text='')

    def _toggle_ev_mode(self):
        """切換頻率熱圖 / EV 熱圖（PioSOLVER 風格）。"""
        self._ev_mode = not self._ev_mode
        if self._ev_mode:
            self._ev_mode_btn.config(bg='#1A3A5C', fg='#4FC3F7', relief='solid', bd=1)
        else:
            self._ev_mode_btn.config(bg='#1C2128', fg=DIM, relief='flat', bd=0)
        self._refresh()

    def _on_hover(self, hand: str):
        scenario = self._get_current_scenario()
        if not scenario:
            self._detail_lbl.config(text='— 未選擇情境 —', fg='#3A4A5A')
            return
        freq       = get_frequency(hand, scenario)
        raise_f, call_f = get_mixed_action(hand, scenario)
        fold_f     = max(0.0, 1.0 - freq)

        # 組合數
        if hand.endswith('s'):    combos = 4
        elif hand.endswith('o'):  combos = 12
        else:                      combos = 6
        in_combos  = round(combos * freq)

        self._hover_lbl.config(
            text=f'{hand}: {"遊玩" if freq > 0 else "棄牌"}  {int(freq * 100)}%')

        # 詳情面板（GTO Wizard 風格）
        if freq > 0:
            r_pct = int(raise_f * 100)
            c_pct = int(call_f  * 100)
            f_pct = max(0, 100 - r_pct - c_pct)
            detail = (f'{hand}  ▸  {in_combos}/{combos} 組合（{int(freq*100)}% 遊玩）    '
                      f'加注 {r_pct}%  跟注 {c_pct}%  棄牌 {f_pct}%')
            self._detail_lbl.config(text=detail, fg='#8ABADF')
        else:
            self._detail_lbl.config(text=f'{hand}  —  棄牌（0 組合進入範圍）', fg='#664444')

    # ══════════════════════════════════════════════════════════════
    # 外部 API（main.py 呼叫）
    # ══════════════════════════════════════════════════════════════

    def set_hero_pos(self, pos: str):
        if pos in POSITIONS:
            self._hero_pos = pos
            self._update_action_tree_ui()
            self._refresh()

    def highlight_hand(self, hand: str):
        self._hand_var.set(hand)
        self._on_hand_changed()

    def set_scenario(self, scenario: str):
        """相容舊 API：直接設情境（跳過行動樹推導）。"""
        if scenario in SCENARIOS:
            # 反推行動樹狀態
            for (hp, ha, op, tb), sc in _SCENARIO_MAP.items():
                if sc == scenario and hp != '*':
                    self._hero_pos    = hp
                    self._hero_action = ha
                    self._opener      = op
                    self._three_bet   = tb
                    self._update_action_tree_ui()
                    self._refresh()
                    return

    def run(self):
        self._win.mainloop()
