"""
兩步驟選牌元件：先選點數（13個），再選花色（4個）。

CardPickerFrame  — 可嵌入的選牌框（13點 × 4花）
CardPickerPopup  — 彈出式視窗版本
CardSlot         — 顯示已選牌的槽位按鈕
"""

import tkinter as tk
from typing import Callable, List, Optional, Set

RANKS   = ['A','K','Q','J','T','9','8','7','6','5','4','3','2']
SUITS   = [
    ('♠','s','#7AA8FF','#0D1A3A'),
    ('♥','h','#FF6B6B','#3A1010'),
    ('♦','d','#FF9F43','#3A2000'),
    ('♣','c','#51CF66','#083A15'),
]

BG_USED    = '#111111'
FG_USED    = '#2A2A2A'
BG_SEL     = '#FFD700'
FG_SEL     = '#000000'
BG_HOVER   = '#2A2A4A'
BG_DEFAULT = '#21262D'
FG_DEFAULT = '#C9D1D9'

SUIT_COLORS = {'s':'#7AA8FF','h':'#FF6B6B','d':'#FF9F43','c':'#51CF66'}
SUIT_SYMS   = {'s':'♠','h':'♥','d':'♦','c':'♣'}


class CardPickerFrame(tk.Frame):
    """
    兩步驟選牌格：
      步驟1：點選點數按鈕（A K Q J T 9 8 7 6 5 4 3 2）
      步驟2：點選花色按鈕（♠ ♥ ♦ ♣）
    選完後呼叫 on_select(card_str)。
    """

    def __init__(self, parent, on_select: Callable[[str], None], **kwargs):
        # 只取 tkinter Frame 合法的 kwargs（bg, width, height 等），過濾掉舊版 cell_w/cell_h
        frame_kwargs = {k: v for k, v in kwargs.items()
                        if k not in ('cell_w', 'cell_h')}
        super().__init__(parent, bg=parent['bg'], **frame_kwargs)
        self._on_select  = on_select
        self._selected_rank: Optional[str] = None
        self._used: Set[str] = set()
        self._rank_btns: dict = {}
        self._suit_btns: dict = {}
        self._build()

    def _build(self):
        # ── 點數列 ─────────────────────────────────────────────────
        rank_frame = tk.Frame(self, bg=self['bg'])
        rank_frame.pack(pady=(4, 2))

        tk.Label(rank_frame, text='點數:', bg=self['bg'], fg='#888888',
                 font=('Consolas', 8)).pack(side='left', padx=(0,6))

        for rank in RANKS:
            btn = tk.Button(
                rank_frame, text=rank, width=3, height=1,
                bg=BG_DEFAULT, fg=FG_DEFAULT,
                font=('Consolas', 9, 'bold'),
                relief='flat', bd=1, cursor='hand2',
                command=lambda r=rank: self._rank_clicked(r),
            )
            btn.pack(side='left', padx=1)
            btn.bind('<Enter>', lambda e, b=btn: b.config(bg=BG_HOVER) if b['state'] != 'disabled' else None)
            btn.bind('<Leave>', lambda e, b=btn, r2=rank: self._restore_rank_btn(b, r2))
            self._rank_btns[rank] = btn

        # ── 花色列 ─────────────────────────────────────────────────
        suit_frame = tk.Frame(self, bg=self['bg'])
        suit_frame.pack(pady=(2, 4))

        tk.Label(suit_frame, text='花色:', bg=self['bg'], fg='#888888',
                 font=('Consolas', 8)).pack(side='left', padx=(0,6))

        for sym, suit_char, fg, bg in SUITS:
            btn = tk.Button(
                suit_frame, text=f'{sym}', width=4, height=1,
                bg=bg, fg=fg,
                font=('Consolas', 12, 'bold'),
                relief='flat', bd=1, cursor='hand2',
                state='disabled',
                command=lambda sc=suit_char: self._suit_clicked(sc),
            )
            btn.pack(side='left', padx=4)
            self._suit_btns[suit_char] = (btn, fg, bg)

        # ── 狀態提示 ───────────────────────────────────────────────
        self._hint_lbl = tk.Label(
            self, text='點擊點數開始選牌', bg=self['bg'],
            fg='#555555', font=('Consolas', 8))
        self._hint_lbl.pack()

    def _rank_clicked(self, rank: str):
        self._selected_rank = rank
        # 高亮選中的點數按鈕
        for r, btn in self._rank_btns.items():
            if btn['state'] != 'disabled':
                if r == rank:
                    btn.config(bg=BG_SEL, fg=FG_SEL)
                else:
                    btn.config(bg=BG_DEFAULT, fg=FG_DEFAULT)
        # 啟用花色按鈕（排除已使用的組合）
        for suit_char, (btn, fg, bg) in self._suit_btns.items():
            card = rank + suit_char
            if card in self._used:
                btn.config(state='disabled', bg=BG_USED, fg=FG_USED)
            else:
                btn.config(state='normal', bg=bg, fg=fg)
        self._hint_lbl.config(text=f'選 {rank} 的花色：', fg='#AAAAAA')

    def _suit_clicked(self, suit_char: str):
        if self._selected_rank is None:
            return
        card = self._selected_rank + suit_char
        if card not in self._used:
            self._on_select(card)
        # 重設
        self._selected_rank = None
        for _, (btn, fg, bg) in self._suit_btns.items():
            btn.config(state='disabled', bg=BG_USED, fg=FG_USED)
        for btn in self._rank_btns.values():
            if btn['state'] != 'disabled':
                btn.config(bg=BG_DEFAULT, fg=FG_DEFAULT)
        self._hint_lbl.config(text='點擊點數開始選牌', fg='#555555')

    def _restore_rank_btn(self, btn, rank):
        if btn['state'] == 'disabled':
            return
        if self._selected_rank == rank:
            btn.config(bg=BG_SEL, fg=FG_SEL)
        else:
            btn.config(bg=BG_DEFAULT, fg=FG_DEFAULT)

    def set_used(self, cards: List[str]):
        """標記已使用的牌（灰掉對應按鈕）。"""
        self._used = set(cards)
        # 更新點數按鈕：若該點數所有花色都用完則灰掉
        for rank, btn in self._rank_btns.items():
            all_used = all(rank + s in self._used for s in 'shdc')
            btn.config(state='disabled' if all_used else 'normal',
                       bg=BG_USED if all_used else BG_DEFAULT,
                       fg=FG_USED if all_used else FG_DEFAULT)
        self._selected_rank = None
        for _, (btn, fg, bg) in self._suit_btns.items():
            btn.config(state='disabled')
        self._hint_lbl.config(text='點擊點數開始選牌', fg='#555555')

    def reset(self):
        self._used.clear()
        self.set_used([])


class CardSlot(tk.Label):
    """單張牌槽位按鈕：顯示已選的牌，或「？」佔位符。"""

    def __init__(self, parent, on_click: Callable, **kwargs):
        super().__init__(
            parent, text='？', width=3,
            bg='#1C2128', fg='#444444',
            font=('Consolas', 15, 'bold'),
            relief='groove', bd=2, cursor='hand2', **kwargs)
        self._card: Optional[str] = None
        self.bind('<Button-1>', lambda _: on_click(self))

    def set_card(self, card: Optional[str]):
        self._card = card
        if card:
            suit  = card[-1].lower()
            rank  = card[:-1]
            sym   = SUIT_SYMS.get(suit, suit)
            color = SUIT_COLORS.get(suit, '#CCCCCC')
            self.config(text=rank+sym, fg=color, bg='#182A18', relief='solid')
        else:
            self.config(text='？', fg='#444444', bg='#1C2128', relief='groove')

    def get_card(self) -> Optional[str]:
        return self._card


class CardPickerPopup:
    """彈出式兩步驟選牌視窗，選完後自動關閉。"""

    def __init__(self, parent, used_cards: List[str],
                 callback: Callable[[str], None], title: str = '選牌'):
        self._win = tk.Toplevel(parent)
        self._win.title(title)
        self._win.configure(bg='#0D1117')
        self._win.attributes('-topmost', True)
        self._win.resizable(False, False)
        self._callback = callback

        tk.Label(self._win, text=title, bg='#0D1117', fg='#58A6FF',
                 font=('Consolas', 10, 'bold')).pack(pady=(8, 4))

        picker = CardPickerFrame(self._win, on_select=self._selected)
        picker.pack(padx=16, pady=4)
        picker.set_used(used_cards)

        tk.Button(self._win, text='取消', command=self._win.destroy,
                  bg='#333333', fg='#CCCCCC', font=('Consolas', 9),
                  relief='flat', padx=12).pack(pady=(4, 8))

    def _selected(self, card: str):
        self._callback(card)
        self._win.destroy()
