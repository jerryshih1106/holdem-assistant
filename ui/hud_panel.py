"""HUD 對手統計面板（F2）— 繁體中文介面。

v2：信心指示燈 + 同心環圖
v4（第三輪 GTO Wizard 改進）：
  8. 牌桌座位視覺圖 — 橢圓桌面 + 座位 HUD 迷你標籤
  9. 座位 HUD 懸浮詳情 — 滑鼠移到任何行顯示全部統計浮窗
"""

import math
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

# 牌桌位置（6-max），以橢圓參數座標
TABLE_POSITIONS_6 = [
    (0.50, 0.05),  # 座位 1 — 上方中央 (BTN/CO 視情況)
    (0.88, 0.22),  # 座位 2 — 右上
    (0.88, 0.75),  # 座位 3 — 右下
    (0.50, 0.92),  # 座位 4 — 下方中央
    (0.12, 0.75),  # 座位 5 — 左下
    (0.12, 0.22),  # 座位 6 — 左上（Hero）
]


def _pct_color(v, lo, hi):
    if v is None: return DIM
    return RED if v > hi else (GREEN if v < lo else FG)


def _fold_color(v):
    if v is None: return DIM
    return GREEN if v > 65 else (RED if v < 35 else FG)


# ─── 懸浮統計詳情 popup ────────────────────────────────────────────────────────

class _StatsTooltip:
    """滑鼠移到座位行時顯示完整統計浮窗。"""

    def __init__(self, root):
        self._root = root
        self._win  = None

    def show(self, widget, player: PlayerStats):
        self.hide()
        try:
            x = widget.winfo_rootx() + widget.winfo_width() + 4
            y = widget.winfo_rooty()
        except Exception:
            return
        self._win = tk.Toplevel(self._root)
        self._win.wm_overrideredirect(True)
        self._win.wm_attributes('-topmost', True)
        self._win.wm_geometry(f'+{x}+{y}')
        self._win.configure(bg='#0D1117')

        frame = tk.Frame(self._win, bg='#0D1117', bd=1, relief='solid')
        frame.pack(padx=1, pady=1)

        def row(label, value, color=FG):
            r = tk.Frame(frame, bg='#0D1117')
            r.pack(fill='x', padx=8, pady=1)
            tk.Label(r, text=label, bg='#0D1117', fg=DIM,
                     font=('Consolas', 8), width=16, anchor='e').pack(side='left')
            tk.Label(r, text=value, bg='#0D1117', fg=color,
                     font=('Consolas', 8, 'bold'), anchor='w').pack(side='left', padx=(4, 0))

        type_zh = TYPE_ZH.get(player.player_type(), player.player_type())
        type_col = player.player_color()

        # 標題
        hdr = tk.Frame(frame, bg='#161B22')
        hdr.pack(fill='x')
        tk.Label(hdr, text=f"  S{player.seat}  {player.name}  ({player.hands} 手)",
                 bg='#161B22', fg=ACCENT, font=('Consolas', 9, 'bold'),
                 anchor='w', pady=3).pack(fill='x', padx=4)

        # 分隔
        tk.Frame(frame, bg=BORDER, height=1).pack(fill='x')

        row('VPIP',  f"{player.vpip_pct:.0f}%"  if player.vpip_pct  is not None else '—',
            _pct_color(player.vpip_pct, 15, 30))
        row('PFR',   f"{player.pfr_pct:.0f}%"   if player.pfr_pct   is not None else '—',
            _pct_color(player.pfr_pct, 10, 20))
        row('3-Bet', f"{player.threebet_pct:.0f}%" if player.threebet_pct is not None else '—',
            _pct_color(player.threebet_pct, 5, 12))
        row('遇3-Bet棄', f"{player.fold_3b_pct:.0f}%" if player.fold_3b_pct is not None else '—',
            _fold_color(player.fold_3b_pct))
        row('C-Bet',  f"{player.cbet_pct:.0f}%"  if player.cbet_pct  is not None else '—',
            _pct_color(player.cbet_pct, 40, 70))
        row('遇C-Bet棄',f"{player.fcbet_pct:.0f}%" if player.fcbet_pct is not None else '—',
            _fold_color(player.fcbet_pct))
        row('攻擊因子', f"{player.af:.1f}" if player.af is not None else '—')
        tk.Frame(frame, bg=BORDER, height=1).pack(fill='x', pady=2)
        row('牌風', type_zh, type_col)

        # 剝削提示
        note = player.exploit_note()
        if note:
            tk.Frame(frame, bg=BORDER, height=1).pack(fill='x')
            tk.Label(frame, text=note, bg='#0D1117', fg=YELLOW,
                     font=('Consolas', 7), wraplength=280, justify='left',
                     padx=8, pady=4).pack(fill='x')

    def hide(self):
        if self._win:
            try: self._win.destroy()
            except Exception: pass
            self._win = None


# ─── 牌桌視覺圖 ──────────────────────────────────────────────────────────────

class TableCanvas(tk.Canvas):
    """橢圓桌面 + 座位 HUD 迷你標籤（v4 新增）。"""

    def __init__(self, parent, tracker: HUDTracker, **kwargs):
        kwargs.setdefault('bg', BG2)
        kwargs.setdefault('width', 320)
        kwargs.setdefault('height', 160)
        kwargs.setdefault('highlightthickness', 0)
        super().__init__(parent, **kwargs)
        self._tracker = tracker
        self.bind('<Configure>', lambda e: self.redraw())

    def redraw(self):
        self.delete('all')
        w = self.winfo_width()  or 320
        h = self.winfo_height() or 160
        # 桌面橢圓
        mx, my = w // 2, h // 2
        rx, ry = int(w * 0.38), int(h * 0.38)
        # 外陰影
        self.create_oval(mx-rx-3, my-ry-3, mx+rx+3, my+ry+3, fill='#090D13', outline='')
        # 桌面綠色
        self.create_oval(mx-rx, my-ry, mx+rx, my+ry,
                         fill='#0A2218', outline='#1A4A2A', width=3)
        # 桌面文字
        self.create_text(mx, my, text='♠', fill='#1A4A2A', font=('Consolas', 22))

        # 每個座位
        players = {p.seat: p for p in self._tracker.all_players()}
        for i, (px_frac, py_frac) in enumerate(TABLE_POSITIONS_6):
            seat_num = i + 1
            sx = int(px_frac * w)
            sy = int(py_frac * h)

            p = players.get(seat_num)
            if p and p.hands > 0:
                self._draw_seat_with_stats(sx, sy, seat_num, p)
            else:
                self._draw_empty_seat(sx, sy, seat_num)

    def _draw_empty_seat(self, x, y, seat_num: int):
        r = 16
        self.create_oval(x-r, y-r, x+r, y+r, fill='#1A1E26', outline='#2A3040', width=2)
        self.create_text(x, y, text=f'S{seat_num}', fill='#3A4A5A', font=('Consolas', 8))

    def _draw_seat_with_stats(self, x, y, seat_num: int, p: PlayerStats):
        r = 18
        # 顏色根據牌風
        color_map = {'TAG': '#1A3A5C', 'LAG': '#3A1A2A', 'Nit': '#1A2A1A',
                     'Fish/Calling': '#3A2A1A', 'Maniac': '#3A1A1A', 'Passive': '#2A2A1A'}
        bg_col = color_map.get(p.player_type(), '#1A2030')

        self.create_oval(x-r, y-r, x+r, y+r, fill=bg_col, outline=p.player_color(), width=2)

        # 座位號
        self.create_text(x, y - 6, text=f'S{seat_num}', fill=FG, font=('Consolas', 7, 'bold'))

        # VPIP/PFR 一行
        vpip_str = f"V{int(p.vpip_pct or 0)}" if p.vpip_pct is not None else 'V?'
        pfr_str  = f"P{int(p.pfr_pct or 0)}"  if p.pfr_pct  is not None else 'P?'
        self.create_text(x, y + 5, text=f"{vpip_str}/{pfr_str}",
                         fill=DIM, font=('Consolas', 6))

        # 信心燈
        conf_color = GREEN if p.hands >= 100 else (YELLOW if p.hands >= 30 else RED)
        self.create_oval(x+r-5, y-r+1, x+r+1, y-r+7, fill=conf_color, outline='')


# ─── HUD Panel ───────────────────────────────────────────────────────────────

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
        self._stats_tip = _StatsTooltip(self._win)
        self._build_setup()
        self._build_table_canvas()   # v4：牌桌視覺圖
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

    # ── 牌桌視覺圖（v4 新增）─────────────────────────────────────────

    def _build_table_canvas(self):
        frame = tk.Frame(self._win, bg=BG2)
        frame.pack(fill='x', padx=4, pady=(4, 0))
        header = tk.Frame(frame, bg=BG2)
        header.pack(fill='x', pady=(2, 0))
        tk.Label(header, text='牌桌概觀', bg=BG2, fg=DIM,
                 font=('Consolas', 8, 'bold')).pack(side='left', padx=8)
        tk.Label(header, text='V=VPIP  P=PFR  ●=樣本信心', bg=BG2, fg='#333A44',
                 font=('Consolas', 7)).pack(side='left', padx=4)
        self._table_canvas = TableCanvas(frame, self._tracker, width=340, height=160)
        self._table_canvas.pack(padx=8, pady=(2, 4))
        self._win.after(100, self._table_canvas.redraw)

    # ── 統計表格 ────────────────────────────────────────────────────

    def _build_table(self):
        frame = tk.Frame(self._win, bg=BG)
        frame.pack(fill='x', padx=4, pady=4)
        header = tk.Frame(frame, bg=BG2)
        header.pack(fill='x')
        tk.Label(header, text='●', bg=BG2, fg=DIM, font=('Consolas', 8),
                 width=2, anchor='center').pack(side='left', padx=1)
        for col, width in COLS:
            tk.Label(header, text=col, bg=BG2, fg=DIM, font=('Consolas', 8, 'bold'),
                     width=width, anchor='center').pack(side='left', padx=1)
        tk.Frame(frame, bg=BORDER, height=1).pack(fill='x', pady=2)
        self._table_frame = tk.Frame(frame, bg=BG)
        self._table_frame.pack(fill='x')

        # 同心環圖
        ring_frame = tk.Frame(self._win, bg=BG2)
        ring_frame.pack(fill='x', padx=4, pady=(0, 4))
        tk.Label(ring_frame, text='VPIP / PFR 分布', bg=BG2, fg=DIM,
                 font=('Consolas', 8)).pack(side='left', padx=8)
        self._ring_canvas = tk.Canvas(ring_frame, bg=BG2, width=220, height=60,
                                       highlightthickness=0)
        self._ring_canvas.pack(side='left', padx=4)
        self._ring_canvas.bind('<Configure>', lambda e: self._draw_rings())

    def _refresh(self):
        for w in self._table_frame.winfo_children(): w.destroy()
        players = self._tracker.all_players()
        if not players:
            tk.Label(self._table_frame, text='無玩家資料 — 輸入座位並點擊「初始化」',
                     bg=BG, fg=DIM, font=('Consolas', 9)).pack(pady=8)
            self._draw_rings()
            if hasattr(self, '_table_canvas'):
                self._table_canvas.redraw()
            return
        for p in sorted(players, key=lambda x: x.seat):
            self._add_row(p)
        self._draw_rings()
        if hasattr(self, '_table_canvas'):
            self._table_canvas.redraw()
        try:
            seat = self._seat_var.get()
            p = self._tracker.get_player(seat)
            self._exploit_lbl.config(text=p.exploit_note(), fg=YELLOW)
        except Exception: pass

    def _confidence_color(self, hands: int) -> str:
        if hands >= 100: return GREEN
        if hands >= 30:  return YELLOW
        return RED

    def _add_row(self, p: PlayerStats):
        row = tk.Frame(self._table_frame, bg=BG, pady=1)
        row.pack(fill='x')
        type_color = p.player_color()

        def lbl(text, width, fg=FG, bold=False):
            f = ('Consolas', 8, 'bold') if bold else ('Consolas', 8)
            tk.Label(row, text=text, bg=BG, fg=fg, font=f,
                     width=width, anchor='center').pack(side='left', padx=1)

        # 信心指示燈
        conf_color = self._confidence_color(p.hands)
        conf_lbl = tk.Label(row, text='●', bg=BG, fg=conf_color,
                            font=('Consolas', 9), width=2, anchor='center')
        conf_lbl.pack(side='left', padx=1)

        lbl(str(p.seat), 4, ACCENT, bold=True)
        if p.seat not in self._name_vars:
            self._name_vars[p.seat] = tk.StringVar(value=p.name)
        nv = self._name_vars[p.seat]
        name_e = tk.Entry(row, textvariable=nv, bg=BG3, fg=FG, insertbackground=FG,
                          font=('Consolas', 8), width=9, relief='flat', bd=2)
        name_e.pack(side='left', padx=1)
        name_e.bind('<FocusOut>', lambda e, s=p.seat, v=nv: self._tracker.rename(s, v.get()))
        lbl(str(p.hands), 5)
        lbl(self._pct(p.vpip_pct),     5, _pct_color(p.vpip_pct, 15, 30))
        lbl(self._pct(p.pfr_pct),      5, _pct_color(p.pfr_pct, 10, 20))
        lbl(self._pct(p.threebet_pct), 5, _pct_color(p.threebet_pct, 5, 12))
        lbl(self._pct(p.fold_3b_pct),  5, _fold_color(p.fold_3b_pct))
        lbl(self._pct(p.cbet_pct),     5, _pct_color(p.cbet_pct, 40, 70))
        lbl(self._pct(p.fcbet_pct),    5, _fold_color(p.fcbet_pct))
        lbl(p.fmt(p.af, 1), 5)
        type_zh = TYPE_ZH.get(p.player_type(), p.player_type())
        lbl(type_zh, 10, type_color, bold=True)

        # 懸浮詳情（v4 新增）— 整行綁定 Enter/Leave
        row.bind('<Enter>', lambda e, player=p, w=row: self._stats_tip.show(w, player))
        row.bind('<Leave>', lambda e: self._stats_tip.hide())
        for child in row.winfo_children():
            child.bind('<Enter>', lambda e, player=p, w=row: self._stats_tip.show(w, player))
            child.bind('<Leave>', lambda e: self._stats_tip.hide())

    def _pct(self, val): return '—' if val is None else f'{val:.0f}'

    def _draw_rings(self):
        c = self._ring_canvas
        c.delete('all')
        players = [p for p in self._tracker.all_players() if p.hands > 0]
        if not players:
            c.create_text(110, 30, text='無資料', fill=DIM, font=('Consolas', 8))
            return
        slot_w = 36
        for i, p in enumerate(sorted(players, key=lambda x: x.seat)[:6]):
            cx = 18 + i * slot_w
            cy = 30
            r_outer, r_inner = 16, 9
            vpip = (p.vpip_pct or 0) / 100
            vpip_color = '#56D364' if vpip < 0.30 else ('#E3B341' if vpip < 0.45 else '#FF7B54')
            self._draw_arc(c, cx, cy, r_outer, vpip, vpip_color, '#1A2A1A')
            pfr = (p.pfr_pct or 0) / 100
            self._draw_arc(c, cx, cy, r_inner, pfr, '#4FC3F7', '#1A1A2E')
            c.create_text(cx, cy + r_outer + 6, text=f'S{p.seat}',
                          fill=DIM, font=('Consolas', 6))

    def _draw_arc(self, c, cx, cy, r, frac, fill_col, bg_col):
        c.create_arc(cx-r, cy-r, cx+r, cy+r, start=90, extent=360,
                     style='arc', outline=bg_col, width=4)
        if frac > 0:
            extent = min(frac * 360, 359.9)
            c.create_arc(cx-r, cy-r, cx+r, cy+r, start=90, extent=-extent,
                         style='arc', outline=fill_col, width=4)

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
                                      bg=BG, fg=DIM, font=('Consolas', 8),
                                      wraplength=560, justify='left')
        self._exploit_lbl.pack(side='left', padx=6)

    def run(self): self._win.mainloop()
