"""
快速 HUD 行動記錄器 (Quick HUD Action Recorder) — F10

在實戰中不打開完整 F2 面板，快速記錄對手行動。

佈局：
  ┌─────────────────────────────┐
  │  Seat: [1][2][3][4][5][6]   │
  │  VPIP  PFR  3B  F3B         │
  │  CB   FCB  BET  CALL        │
  │  ─────────────────────────  │
  │  S1: VPIP=45% PFR=12%       │
  └─────────────────────────────┘

快捷鍵：F10 開/關
"""

import tkinter as tk
from typing import Optional, Callable
from poker.hud import HUDTracker

BG       = '#0D1117'
BG2      = '#161B22'
BORDER   = '#30363D'
FG       = '#C9D1D9'
ACCENT   = '#58A6FF'
GREEN    = '#56D364'
YELLOW   = '#E3B341'
RED      = '#FF7B54'
BTN_BG   = '#21262D'
BTN_ACT  = '#1F6FEB'


class QuickRecorder:
    """F10 快速 HUD 記錄浮動面板。"""

    # 行動 → hud.record() 的 action 字串
    _ACTIONS = [
        ('VPIP',  'vpip',    GREEN,  '入局'),
        ('PFR',   'pfr',     GREEN,  '翻前加注'),
        ('3BET',  '3bet',    ACCENT, '3-bet'),
        ('F3B',   'fold_3b', RED,    '棄牌到3bet'),
        ('CB',    'cbet',    YELLOW, 'C-bet'),
        ('FCB',   'fcbet',   RED,    '棄牌到CB'),
        ('BET',   'bet',     YELLOW, '下注'),
        ('CALL',  'call',    FG,     '跟注'),
    ]

    def __init__(self, parent_root: tk.Tk, hud_tracker: HUDTracker,
                 on_update: Optional[Callable] = None):
        self._root    = parent_root
        self._hud     = hud_tracker
        self._on_update = on_update
        self._win: Optional[tk.Toplevel] = None
        self._seat_var = tk.IntVar(value=1)
        self._visible  = False

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
        self._win.title('HUD 記錄 (F10)')
        self._win.configure(bg=BG)
        self._win.attributes('-topmost', True)
        self._win.resizable(False, False)
        self._win.protocol('WM_DELETE_WINDOW', self.toggle)

        pad = dict(padx=4, pady=3)

        # ── 標題 ──────────────────────────────────────────────────────────────
        tk.Label(self._win, text='HUD 快速記錄',
                 bg=BG, fg=ACCENT, font=('Consolas', 10, 'bold')).pack(pady=(8, 2))

        # ── 座位選擇 ──────────────────────────────────────────────────────────
        seat_row = tk.Frame(self._win, bg=BG2, bd=1, relief='flat')
        seat_row.pack(fill='x', padx=6, pady=2)
        tk.Label(seat_row, text='座位:', bg=BG2, fg=FG,
                 font=('Consolas', 9)).pack(side='left', padx=4)

        for s in range(1, 7):
            b = tk.Radiobutton(
                seat_row, text=str(s),
                variable=self._seat_var, value=s,
                bg=BG2, fg=FG, selectcolor=BTN_ACT,
                activebackground=BG2, activeforeground=FG,
                font=('Consolas', 9), indicatoron=True,
                command=self._refresh_stats,
            )
            b.pack(side='left', padx=2)

        # ── 行動按鈕（2 行 × 4 列）──────────────────────────────────────────
        btn_frame = tk.Frame(self._win, bg=BG)
        btn_frame.pack(padx=6, pady=4)

        for i, (label, action, color, tooltip) in enumerate(self._ACTIONS):
            row_, col_ = divmod(i, 4)
            b = tk.Button(
                btn_frame,
                text=label,
                bg=BTN_BG, fg=color,
                activebackground=BTN_ACT, activeforeground='white',
                font=('Consolas', 9, 'bold'),
                relief='flat', bd=0, padx=10, pady=5,
                cursor='hand2',
                command=lambda a=action: self._record(a),
            )
            b.grid(row=row_, column=col_, padx=2, pady=2, sticky='ew')
            b.bind('<Enter>', lambda e, b=b, c=color: b.config(bg='#2D333B'))
            b.bind('<Leave>', lambda e, b=b: b.config(bg=BTN_BG))

        # ── 分隔線 ──────────────────────────────────────────────────────────
        tk.Frame(self._win, bg=BORDER, height=1).pack(fill='x', padx=6, pady=2)

        # ── 目前座位統計 ─────────────────────────────────────────────────────
        self._stats_lbl = tk.Label(
            self._win, text='選擇座位後記錄行動',
            bg=BG, fg=FG, font=('Consolas', 8),
            wraplength=240, justify='left',
        )
        self._stats_lbl.pack(padx=8, pady=(2, 6))

        # ── 重置本局 ─────────────────────────────────────────────────────────
        tk.Button(
            self._win, text='新一手 (重置行動計數)',
            bg=BTN_BG, fg=YELLOW,
            activebackground='#2D333B', font=('Consolas', 8),
            relief='flat', bd=0, padx=6, pady=3, cursor='hand2',
            command=self._new_hand,
        ).pack(pady=(0, 6))

        self._refresh_stats()

    def _record(self, action: str):
        seat = self._seat_var.get()
        try:
            self._hud.record(seat, action)
            if self._on_update:
                self._on_update()
            self._refresh_stats()
            self._flash_feedback(action)
        except Exception as e:
            self._stats_lbl.config(text=f'記錄失敗: {e}', fg=RED)

    def _refresh_stats(self):
        if not self._win:
            return
        seat = self._seat_var.get()
        players = self._hud.all_players()
        opp = next((p for p in players if p.seat == seat), None)
        if opp and opp.hands >= 1:
            vpip = f'{opp.vpip_pct:.0f}%' if opp.vpip_pct else '--'
            pfr  = f'{opp.pfr_pct:.0f}%'  if opp.pfr_pct  else '--'
            af   = f'{opp.af:.1f}'         if opp.af       else '--'
            cb   = f'{opp.cbet_pct:.0f}%'  if opp.cbet_pct else '--'
            fcb  = f'{opp.fcbet_pct:.0f}%' if opp.fcbet_pct else '--'
            ptype = opp.player_type if isinstance(opp.player_type, str) else '--'
            text = (f'S{seat} ({opp.name or "?"}) {opp.hands}手  '
                    f'VPIP={vpip} PFR={pfr} AF={af}\n'
                    f'CB={cb} FCB={fcb}  [{ptype}]')
        else:
            text = f'座位 {seat}：尚無資料（點擊按鈕記錄行動）'
        self._stats_lbl.config(text=text, fg=FG)

    def _flash_feedback(self, action: str):
        """短暫顯示「已記錄」提示。"""
        label_map = {a: l for l, a, *_ in self._ACTIONS}
        label = label_map.get(action, action)
        orig_text = self._stats_lbl.cget('text')
        self._stats_lbl.config(text=f'[已記錄: {label}] ' + orig_text, fg=GREEN)
        self._win.after(800, lambda: self._stats_lbl.config(text=orig_text, fg=FG))

    def _new_hand(self):
        """
        開始新一手：對所有已記錄過的座位增加手牌計數。
        這讓 VPIP% = vpip_count/hands 計算正確。
        """
        try:
            players = self._hud.all_players()
            active_seats = [p.seat for p in players if p.hands == 0 or True]
            # 只對有座位數據的玩家增加手牌數
            active_seats = [p.seat for p in players]
            if active_seats:
                self._hud.new_hand(active_seats)
                self._stats_lbl.config(
                    text=f'新的一手：{len(active_seats)} 個座位 +1 手', fg=GREEN)
                self._refresh_stats()
            else:
                self._stats_lbl.config(text='尚無座位資料', fg=YELLOW)
        except Exception as e:
            self._stats_lbl.config(text=f'錯誤: {e}', fg=RED)
