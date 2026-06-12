"""
對手筆記面板 (Opponent Notes Panel) — F11

快速記錄對手的可利用特徵，輔助每手牌的決策。

佈局：
  ┌──────────────────────────────────┐
  │  座位: [1][2][3][4][5][6]        │
  │  [廣跟翻前][棄3bet][廣3BET][過站]│
  │  [棄翻牌CB][從不詐唬][河牌過詐]  │
  │  [高估TP][OOP過棄][跛入][傾斜]   │
  │  ─────────────────────────────── │
  │  自訂: [輸入框] [+加入]          │
  │  筆記: tag1 | tag2 | 自訂文字    │
  │  建議: 只下注 value，不要詐唬    │
  └──────────────────────────────────┘
"""

import tkinter as tk
from typing import Optional, Callable
from poker.notes import NotesTracker, EXPLOIT_TAGS, TAG_BY_ID

BG      = '#0D1117'
BG2     = '#161B22'
BORDER  = '#30363D'
FG      = '#C9D1D9'
ACCENT  = '#58A6FF'
GREEN   = '#56D364'
YELLOW  = '#E3B341'
RED     = '#FF7B54'
ORANGE  = '#FF9F43'
BTN_BG  = '#21262D'
BTN_ON  = '#1F4E2A'
BTN_ON_FG = '#56D364'

# 標籤分類顏色
_CAT_COLORS = {
    'preflop':  '#58A6FF',
    'postflop': '#E3B341',
    'tilt':     '#FF7B54',
}


class NotesPanel:
    """F11 對手筆記浮動面板。"""

    def __init__(self, parent_root: tk.Tk, notes_tracker: NotesTracker,
                 on_update: Optional[Callable] = None):
        self._root    = parent_root
        self._notes   = notes_tracker
        self._on_update = on_update
        self._win: Optional[tk.Toplevel] = None
        self._seat_var = tk.IntVar(value=1)
        self._text_var = tk.StringVar()
        self._visible  = False
        self._btn_refs: dict = {}    # tag_id → Button widget

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
        self._win.title('對手筆記 (F11)')
        self._win.configure(bg=BG)
        self._win.attributes('-topmost', True)
        self._win.resizable(False, False)
        self._win.protocol('WM_DELETE_WINDOW', self.toggle)

        # ── 標題 ──────────────────────────────────────────────────────────────
        tk.Label(self._win, text='對手筆記', bg=BG, fg=ACCENT,
                 font=('Consolas', 10, 'bold')).pack(pady=(8, 2))

        # ── 座位選擇 ──────────────────────────────────────────────────────────
        seat_row = tk.Frame(self._win, bg=BG2, bd=1, relief='flat')
        seat_row.pack(fill='x', padx=6, pady=2)
        tk.Label(seat_row, text='座位:', bg=BG2, fg=FG,
                 font=('Consolas', 9)).pack(side='left', padx=4)
        for s in range(1, 7):
            b = tk.Radiobutton(
                seat_row, text=str(s),
                variable=self._seat_var, value=s,
                bg=BG2, fg=FG, selectcolor=ACCENT,
                activebackground=BG2, activeforeground=FG,
                font=('Consolas', 9), indicatoron=True,
                command=self._refresh_display,
            )
            b.pack(side='left', padx=2)

        # ── 標籤按鈕（分類分行）────────────────────────────────────────────
        tag_frame = tk.Frame(self._win, bg=BG)
        tag_frame.pack(padx=6, pady=4, fill='x')

        cats = ['preflop', 'postflop', 'tilt']
        cat_labels_zh = {'preflop': '翻前', 'postflop': '翻後', 'tilt': '心理'}

        self._btn_refs = {}
        for cat in cats:
            row_tags = [t for t in EXPLOIT_TAGS if t['cat'] == cat]
            if not row_tags:
                continue
            cat_color = _CAT_COLORS.get(cat, FG)
            row_f = tk.Frame(tag_frame, bg=BG)
            row_f.pack(fill='x', pady=1)
            tk.Label(row_f, text=f'{cat_labels_zh[cat]}:', bg=BG, fg=cat_color,
                     font=('Consolas', 7, 'bold'), width=4).pack(side='left', padx=(0, 2))
            for tag in row_tags:
                tid = tag['id']
                b = tk.Button(
                    row_f,
                    text=tag['label'],
                    bg=BTN_BG, fg=cat_color,
                    activebackground='#2D333B', activeforeground=cat_color,
                    font=('Consolas', 8),
                    relief='flat', bd=0, padx=6, pady=3,
                    cursor='hand2',
                    command=lambda t=tid: self._toggle_tag(t),
                )
                b.pack(side='left', padx=1)
                self._btn_refs[tid] = b

        # ── 自訂文字 ─────────────────────────────────────────────────────────
        tk.Frame(self._win, bg=BORDER, height=1).pack(fill='x', padx=6, pady=3)

        txt_row = tk.Frame(self._win, bg=BG)
        txt_row.pack(fill='x', padx=6, pady=2)
        tk.Label(txt_row, text='自訂:', bg=BG, fg=FG,
                 font=('Consolas', 8)).pack(side='left', padx=(0, 4))
        entry = tk.Entry(
            txt_row, textvariable=self._text_var,
            bg='#21262D', fg=FG, insertbackground=FG,
            font=('Consolas', 9), width=22, relief='flat', bd=4,
        )
        entry.pack(side='left')
        entry.bind('<Return>', lambda _: self._add_text())
        tk.Button(
            txt_row, text='+', bg=ACCENT, fg='#000000',
            activebackground='#4080CC', font=('Consolas', 9, 'bold'),
            relief='flat', bd=0, padx=6, pady=2, cursor='hand2',
            command=self._add_text,
        ).pack(side='left', padx=4)

        # ── 目前筆記 ─────────────────────────────────────────────────────────
        tk.Frame(self._win, bg=BORDER, height=1).pack(fill='x', padx=6, pady=2)

        self._notes_lbl = tk.Label(
            self._win, text='(尚無筆記)',
            bg=BG, fg=FG, font=('Consolas', 8),
            wraplength=280, justify='left',
        )
        self._notes_lbl.pack(padx=8, pady=(2, 1), anchor='w')

        self._advice_lbl = tk.Label(
            self._win, text='',
            bg=BG2, fg=YELLOW, font=('Consolas', 9, 'bold'),
            wraplength=280, justify='left',
        )
        self._advice_lbl.pack(fill='x', padx=6, pady=2)

        # ── 清除按鈕 ─────────────────────────────────────────────────────────
        tk.Button(
            self._win, text='清除此座位筆記',
            bg=BTN_BG, fg=RED,
            activebackground='#2D333B', font=('Consolas', 8),
            relief='flat', bd=0, padx=6, pady=3, cursor='hand2',
            command=self._clear_seat,
        ).pack(pady=(0, 6))

        self._refresh_display()

    def _toggle_tag(self, tag_id: str):
        seat = self._seat_var.get()
        self._notes.toggle_tag(seat, tag_id)
        self._refresh_display()
        if self._on_update:
            self._on_update()

    def _add_text(self):
        text = self._text_var.get().strip()
        if not text:
            return
        seat = self._seat_var.get()
        self._notes.add_text(seat, text)
        self._text_var.set('')
        self._refresh_display()
        if self._on_update:
            self._on_update()

    def _clear_seat(self):
        seat = self._seat_var.get()
        self._notes.clear(seat)
        self._refresh_display()
        if self._on_update:
            self._on_update()

    def _refresh_display(self):
        if not self._win:
            return
        seat = self._seat_var.get()
        n = self._notes.get(seat)

        # 更新標籤按鈕顯示狀態
        for tid, btn in self._btn_refs.items():
            active = n.has_tag(tid)
            if active:
                btn.config(bg=BTN_ON, fg=BTN_ON_FG, relief='groove')
            else:
                cat = TAG_BY_ID.get(tid, {}).get('cat', 'postflop')
                btn.config(bg=BTN_BG, fg=_CAT_COLORS.get(cat, FG), relief='flat')

        # 更新筆記顯示
        parts = n.tag_labels + n.text
        if parts:
            txt = ' | '.join(parts)
            self._notes_lbl.config(text=f'S{seat}: {txt}', fg=FG)
        else:
            self._notes_lbl.config(text=f'S{seat}: (尚無筆記)', fg='#484F58')

        # 利用建議
        advice = self._notes.exploit_advice(seat)
        if advice:
            self._advice_lbl.config(text=f'建議: {advice}', fg=YELLOW)
        else:
            self._advice_lbl.config(text='')

    def update_seat(self, seat: int):
        """由外部同步目前焦點座位。"""
        if not self._win:
            return
        self._seat_var.set(seat)
        self._refresh_display()
