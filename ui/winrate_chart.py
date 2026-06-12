"""
Session Win Rate 趨勢圖面板

即時顯示本場 session 的累積 BB 走勢，幫助識別：
  - 下行趨勢（tilt 警告）
  - 上行趨勢（最佳狀態）
  - 平盤（穩定但無獲益）

佈局：
  ┌──────────────────────────────────────┐
  │  本場勝率  +18.5BB  35手  +0.53BB/h  │
  │  ────────────────────────────────── │
  │  [折線圖：累積 BB 走勢]              │
  │  ────────────────────────────────── │
  │  +20                                 │
  │      ╭──╮                            │
  │  +10 │  ╰──╮                        │
  │   0  ─────────────────────── (零線) │
  │  -10      ╰──╯                       │
  └──────────────────────────────────────┘
"""

import tkinter as tk
from typing import List, Optional

BG     = '#0D1117'
BG2    = '#161B22'
BORDER = '#30363D'
FG     = '#C9D1D9'
ACCENT = '#58A6FF'
GREEN  = '#56D364'
RED    = '#FF7B54'
YELLOW = '#E3B341'
DIM    = '#484F58'
GRID   = '#1C2128'

CHART_W = 320
CHART_H = 140
PAD_L   = 40    # left margin for y-axis labels
PAD_R   = 10
PAD_T   = 10
PAD_B   = 20    # bottom for x-axis


class WinRateChart:
    """
    即時 BB 走勢圖面板（可嵌入或獨立視窗）。

    用法：
        chart = WinRateChart(parent_root)
        chart.add_result(+2.5)   # 這手贏了 2.5BB
        chart.add_result(-1.0)
    """

    def __init__(self, parent_root: tk.Tk):
        self._root    = parent_root
        self._win: Optional[tk.Toplevel] = None
        self._visible = False
        self._results: List[float] = []     # per-hand BB results
        self._cumulative: List[float] = []  # cumulative BB

    # ── 公開 API ──────────────────────────────────────────────────────────────

    def add_result(self, bb_change: float):
        """記錄一手結果（正數=贏，負數=輸）並重繪。"""
        self._results.append(bb_change)
        cum = (self._cumulative[-1] if self._cumulative else 0.0) + bb_change
        self._cumulative.append(cum)
        if self._visible:
            self._redraw()

    def reset(self):
        """重置本 session 記錄。"""
        self._results.clear()
        self._cumulative.clear()
        if self._visible:
            self._redraw()

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

    # ── 建立視窗 ──────────────────────────────────────────────────────────────

    def _build(self):
        self._win = tk.Toplevel(self._root)
        self._win.title('Session 勝率走勢')
        self._win.configure(bg=BG)
        self._win.attributes('-topmost', True)
        self._win.resizable(False, False)
        self._win.protocol('WM_DELETE_WINDOW', self.toggle)

        # ── 標題統計 ─────────────────────────────────────────────────────────
        tk.Label(self._win, text='Session 勝率走勢', bg=BG, fg=ACCENT,
                 font=('Consolas', 10, 'bold')).pack(pady=(8, 2))

        self._stats_lbl = tk.Label(
            self._win, text='本場: 0BB  0手', bg=BG, fg=FG,
            font=('Consolas', 9),
        )
        self._stats_lbl.pack()

        # ── 圖表 Canvas ───────────────────────────────────────────────────────
        tk.Frame(self._win, bg=BORDER, height=1).pack(fill='x', padx=6, pady=3)

        self._canvas = tk.Canvas(
            self._win,
            width=CHART_W + PAD_L + PAD_R,
            height=CHART_H + PAD_T + PAD_B,
            bg=BG2, highlightthickness=0,
        )
        self._canvas.pack(padx=6, pady=4)

        # ── 按鈕 ─────────────────────────────────────────────────────────────
        ctrl = tk.Frame(self._win, bg=BG)
        ctrl.pack(pady=(0, 6))
        tk.Button(
            ctrl, text='+ 贏  (手動輸入)', bg='#1A3A1A', fg=GREEN,
            font=('Consolas', 8), relief='flat', bd=0, padx=6, pady=3,
            cursor='hand2', command=self._prompt_add,
        ).pack(side='left', padx=4)
        tk.Button(
            ctrl, text='重置', bg='#21262D', fg=RED,
            font=('Consolas', 8), relief='flat', bd=0, padx=6, pady=3,
            cursor='hand2', command=self.reset,
        ).pack(side='left', padx=4)

        self._redraw()

    # ── 繪製圖表 ──────────────────────────────────────────────────────────────

    def _redraw(self):
        if not self._win:
            return
        c = self._canvas
        c.delete('all')

        data = self._cumulative
        n    = len(data)

        # ── 統計更新 ──────────────────────────────────────────────────────────
        if data:
            total_bb  = data[-1]
            hands     = len(data)
            bb100     = (total_bb / hands * 100) if hands > 0 else 0
            sign      = '+' if total_bb >= 0 else ''
            color     = GREEN if total_bb >= 0 else RED
            self._stats_lbl.config(
                text=f'本場: {sign}{total_bb:.1f}BB  {hands}手  '
                     f'({sign}{bb100:.1f}BB/100)',
                fg=color,
            )
        else:
            self._stats_lbl.config(text='本場: 0BB  0手', fg=FG)

        # ── 圖表繪製 ──────────────────────────────────────────────────────────
        w = CHART_W
        h = CHART_H

        # 繪圖區偏移
        ox = PAD_L   # left origin
        oy = PAD_T   # top origin

        if not data:
            # 空圖提示
            c.create_text(
                ox + w // 2, oy + h // 2,
                text='尚無記錄\n使用 + 按鈕或程式自動記錄',
                fill=DIM, font=('Consolas', 9), justify='center',
            )
            return

        # 動態Y軸範圍
        max_val = max(max(data), 0)
        min_val = min(min(data), 0)
        y_range = max(abs(max_val), abs(min_val), 5) * 1.15

        def to_xy(idx: int, val: float) -> tuple:
            x = ox + (idx / max(n - 1, 1)) * w if n > 1 else ox + w // 2
            y = oy + h // 2 - (val / y_range) * (h // 2)
            return (x, y)

        # ── 網格 ─────────────────────────────────────────────────────────────
        for level in [y_range * 0.5, 0, -y_range * 0.5]:
            _, y = to_xy(0, level)
            c.create_line(ox, y, ox + w, y,
                          fill=GRID if level != 0 else DIM,
                          dash=(4, 4) if level != 0 else (),
                          width=1 if level != 0 else 2)
            label = f'{level:+.0f}' if level != 0 else '0'
            c.create_text(ox - 4, y, text=label, fill=DIM,
                          font=('Consolas', 7), anchor='e')

        # ── Y 軸 ─────────────────────────────────────────────────────────────
        c.create_line(ox, oy, ox, oy + h, fill=DIM, width=1)

        # ── 填色區域（上方綠，下方紅）────────────────────────────────────────
        _, zero_y = to_xy(0, 0)
        if n >= 2:
            # 收集正區和負區分別填色
            pts_above = [ox, zero_y]
            pts_below = [ox, zero_y]
            for i, v in enumerate(data):
                x, y = to_xy(i, v)
                pts_above.extend([x, min(y, zero_y)])
                pts_below.extend([x, max(y, zero_y)])
            pts_above.extend([ox + w if n > 1 else ox, zero_y])
            pts_below.extend([ox + w if n > 1 else ox, zero_y])

            if len(pts_above) >= 6:
                c.create_polygon(pts_above, fill='#1A3A1A', outline='')
            if len(pts_below) >= 6:
                c.create_polygon(pts_below, fill='#3A1A1A', outline='')

        # ── 折線 ─────────────────────────────────────────────────────────────
        if n >= 2:
            pts = []
            for i, v in enumerate(data):
                x, y = to_xy(i, v)
                pts.extend([x, y])
            # Color based on end value
            line_color = GREEN if data[-1] >= 0 else RED
            c.create_line(*pts, fill=line_color, width=2, smooth=True)

        # ── 當前點 ────────────────────────────────────────────────────────────
        if data:
            lx, ly = to_xy(n - 1, data[-1])
            dot_color = GREEN if data[-1] >= 0 else RED
            c.create_oval(lx - 4, ly - 4, lx + 4, ly + 4,
                          fill=dot_color, outline=BG, width=2)
            sign = '+' if data[-1] >= 0 else ''
            c.create_text(lx, ly - 12, text=f'{sign}{data[-1]:.1f}',
                          fill=dot_color, font=('Consolas', 8))

        # ── X 軸手牌數標記 ────────────────────────────────────────────────────
        for label_i in [0, n // 2, n - 1]:
            if label_i < n:
                x, _ = to_xy(label_i, 0)
                c.create_text(x, oy + h + 8, text=str(label_i + 1),
                              fill=DIM, font=('Consolas', 7))

        # ── 下行警告 ──────────────────────────────────────────────────────────
        if n >= 10:
            last10 = data[-10:]
            trend  = last10[-1] - last10[0]
            if trend <= -10:
                c.create_text(
                    ox + w - 5, oy + 10,
                    text='下行警告！', fill=RED, font=('Consolas', 8, 'bold'),
                    anchor='e',
                )
            elif trend >= 8:
                c.create_text(
                    ox + w - 5, oy + 10,
                    text='最佳狀態', fill=GREEN, font=('Consolas', 8),
                    anchor='e',
                )

    def _prompt_add(self):
        """手動輸入一手結果的對話框。"""
        win = tk.Toplevel(self._win)
        win.title('記錄手牌結果')
        win.configure(bg=BG)
        win.attributes('-topmost', True)
        win.geometry(f'200x100+{self._win.winfo_x()+40}+{self._win.winfo_y()+40}')

        tk.Label(win, text='輸入本手 BB（正/負）:', bg=BG, fg=FG,
                 font=('Consolas', 9)).pack(pady=(8, 2))
        var = tk.StringVar()
        e = tk.Entry(win, textvariable=var, bg='#21262D', fg=FG,
                     insertbackground=FG, font=('Consolas', 11),
                     width=10, relief='flat', bd=4, justify='center')
        e.pack()
        e.focus_set()

        def _ok():
            try:
                val = float(var.get())
                self.add_result(val)
                win.destroy()
            except ValueError:
                pass

        e.bind('<Return>', lambda _: _ok())
        tk.Button(win, text='確認', command=_ok, bg=ACCENT, fg='#000',
                  font=('Consolas', 9, 'bold'), relief='flat', pady=3).pack(pady=4)
