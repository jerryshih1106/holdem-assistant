"""推/棄分析面板（F4）— 繁體中文介面。"""

import tkinter as tk
from tkinter import ttk
from typing import Optional

from poker.pushfold import push_range, bb_call_range, push_advice, push_range_percent, PUSH_ORDER
from poker.ranges import RANKS, hand_at, hand_to_grid

BG     = '#0D1117'
BG2    = '#161B22'
FG     = '#E6EDF3'
DIM    = '#8B949E'
ACCENT = '#58A6FF'
BORDER = '#30363D'
PUSH_BG, PUSH_FG = '#1A6B3A', '#56D364'
FOLD_BG, FOLD_FG = '#1C2128', '#484F58'
CALL_BG, CALL_FG = '#3B2300', '#E3B341'
CELL, PAD, HDR = 36, 2, 20

POS_ZH = {'UTG':'早位','HJ':'中位','CO':'切位','BTN':'莊家','SB':'小盲'}


class PushFoldPanel:
    def __init__(self, parent_root=None):
        self._win = tk.Toplevel(parent_root) if parent_root else tk.Tk()
        self._win.title('Nash 推/棄分析')
        self._win.configure(bg=BG)
        self._win.attributes('-topmost', True)
        self._win.resizable(False, False)
        self._pos_var   = tk.StringVar(value='BTN')
        self._stack_var = tk.DoubleVar(value=10.0)
        self._hand_var  = tk.StringVar(value='')
        self._show_bb   = tk.BooleanVar(value=True)
        self._highlight: Optional[tuple] = None
        self._build_controls()
        self._build_grid()
        self._build_info()
        self._refresh()

    def _build_controls(self):
        bar = tk.Frame(self._win, bg=BG2, pady=6)
        bar.pack(fill='x', padx=4, pady=(4,0))
        tk.Label(bar, text='位置:', bg=BG2, fg=DIM, font=('Consolas',9)).pack(side='left', padx=(8,2))
        for pos in ['UTG','HJ','CO','BTN','SB']:
            zh = POS_ZH.get(pos, pos)
            tk.Radiobutton(bar, text=f'{zh}({pos})', variable=self._pos_var, value=pos,
                           bg=BG2, fg=FG, selectcolor=BG2, activebackground=BG2,
                           font=('Consolas',8), command=self._refresh).pack(side='left', padx=2)
        tk.Label(bar, text='  籌碼(bb):', bg=BG2, fg=DIM, font=('Consolas',9)).pack(side='left', padx=(8,2))
        tk.Scale(bar, variable=self._stack_var, from_=3, to=25, resolution=0.5,
                 orient='horizontal', length=120, bg=BG2, fg=FG, troughcolor=BG,
                 highlightthickness=0, command=lambda _: self._refresh()).pack(side='left', padx=4)
        tk.Checkbutton(bar, text='顯示BB跟注', variable=self._show_bb,
                       bg=BG2, fg=FG, selectcolor=BG2, activebackground=BG2,
                       font=('Consolas',8), command=self._refresh).pack(side='right', padx=8)

    def _build_grid(self):
        n = 13
        w = HDR + n*(CELL+PAD)+PAD
        h = HDR + n*(CELL+PAD)+PAD
        outer = tk.Frame(self._win, bg=BG)
        outer.pack(padx=6, pady=4)
        self._canvas = tk.Canvas(outer, width=w, height=h, bg=BG, highlightthickness=0)
        self._canvas.pack()
        self._cells = {}
        for i in range(n):
            cx = HDR + i*(CELL+PAD)+CELL//2
            self._canvas.create_text(cx, HDR//2, text=RANKS[i], fill=DIM, font=('Consolas',7,'bold'))
            ry = HDR + i*(CELL+PAD)+CELL//2
            self._canvas.create_text(HDR//2, ry, text=RANKS[i], fill=DIM, font=('Consolas',7,'bold'))
        for row in range(n):
            for col in range(n):
                x0 = HDR + col*(CELL+PAD)+PAD
                y0 = HDR + row*(CELL+PAD)+PAD
                x1, y1 = x0+CELL, y0+CELL
                hand = hand_at(row, col)
                rect = self._canvas.create_rectangle(x0,y0,x1,y1, fill=FOLD_BG, outline=BORDER, width=1)
                txt  = self._canvas.create_text((x0+x1)//2,(y0+y1)//2, text=hand, fill=FOLD_FG, font=('Consolas',6))
                self._cells[(row,col)] = (rect, txt, hand)
                self._canvas.tag_bind(rect, '<Enter>', lambda e, h=hand: self._on_hover(h))
                self._canvas.tag_bind(txt,  '<Enter>', lambda e, h=hand: self._on_hover(h))

    def _build_info(self):
        bar = tk.Frame(self._win, bg=BG2, pady=4)
        bar.pack(fill='x', padx=4, pady=(0,4))
        tk.Label(bar, text='手牌:', bg=BG2, fg=DIM, font=('Consolas',9)).pack(side='left', padx=(8,2))
        e = tk.Entry(bar, textvariable=self._hand_var, bg='#21262D', fg=FG,
                     insertbackground=FG, font=('Consolas',10), width=6, relief='flat', bd=4)
        e.pack(side='left', padx=4)
        e.bind('<Return>', lambda _: self._on_hand_change())
        e.bind('<KeyRelease>', lambda _: self._on_hand_change())
        self._pct_lbl = tk.Label(bar, text='推牌範圍: —', bg=BG2, fg=ACCENT, font=('Consolas',10,'bold'))
        self._pct_lbl.pack(side='left', padx=12)
        self._advice_lbl = tk.Label(bar, text='', bg=BG2, fg=FG, font=('Consolas',10,'bold'))
        self._advice_lbl.pack(side='left', padx=6)
        self._hover_lbl = tk.Label(bar, text='', bg=BG2, fg=DIM, font=('Consolas',8))
        self._hover_lbl.pack(side='right', padx=8)
        # 圖例
        leg = tk.Frame(bar, bg=BG2)
        leg.pack(side='right', padx=8)
        for text, color in [('推', PUSH_FG),('BB跟', CALL_FG),('棄', FOLD_FG)]:
            tk.Label(leg, text='■', bg=BG2, fg=color, font=('Consolas',9)).pack(side='left')
            tk.Label(leg, text=text, bg=BG2, fg=DIM, font=('Consolas',7)).pack(side='left', padx=(0,4))

    def _refresh(self):
        pos = self._pos_var.get()
        stack = self._stack_var.get()
        push_rng = push_range(pos, stack)
        call_rng = bb_call_range(stack) if self._show_bb.get() else frozenset()
        pct = push_range_percent(pos, stack)
        for (row,col),(rect,txt,hand) in self._cells.items():
            hl = (self._highlight == (row,col))
            in_push = hand in push_rng
            in_call = hand in call_rng and not in_push
            if hl:    bg, fg, ow, w = '#FFFFFF','#000000','#FFFFFF',2
            elif in_push: bg, fg, ow, w = PUSH_BG, PUSH_FG, BORDER, 1
            elif in_call: bg, fg, ow, w = CALL_BG, CALL_FG, BORDER, 1
            else:         bg, fg, ow, w = FOLD_BG, FOLD_FG, BORDER, 1
            self._canvas.itemconfig(rect, fill=bg, outline=ow, width=w)
            self._canvas.itemconfig(txt, fill=fg)
        pos_zh = POS_ZH.get(pos, pos)
        self._pct_lbl.config(text=f'{pos_zh}推牌範圍: {pct:.0f}%  ({int(pct/100*169)} 手)')

    def _on_hand_change(self):
        hand = self._hand_var.get().strip().upper()
        pos = self._pos_var.get()
        stack = self._stack_var.get()
        all_hands = {hand_at(r,c) for r in range(13) for c in range(13)}
        if hand in all_hands:
            self._highlight = hand_to_grid(hand) if len(hand) >= 3 else None
        else:
            self._highlight = None
        self._refresh()
        adv = push_advice(hand, pos, stack)
        action_zh = '推牌' if adv['action']=='PUSH' else '棄牌' if adv['action']=='FOLD' else adv['action']
        color = '#56D364' if adv['action']=='PUSH' else '#FF7B54'
        self._advice_lbl.config(text=f'{hand}: {action_zh}', fg=color)

    def _on_hover(self, hand):
        pos = self._pos_var.get()
        stack = self._stack_var.get()
        adv = push_advice(hand, pos, stack)
        bb_c = hand in bb_call_range(stack)
        action_zh = '推牌' if adv['action']=='PUSH' else '棄牌'
        self._hover_lbl.config(text=f'{hand}: {action_zh}  (BB跟注: {"是" if bb_c else "否"})')

    def set_hand(self, hand, position=None, stack_bb=None):
        if position: self._pos_var.set(position)
        if stack_bb is not None: self._stack_var.set(stack_bb)
        self._hand_var.set(hand)
        self._on_hand_change()

    def run(self): self._win.mainloop()
