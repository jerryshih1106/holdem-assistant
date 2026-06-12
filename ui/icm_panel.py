"""ICM 計算器面板（F6）— 繁體中文介面。"""

import tkinter as tk
from tkinter import ttk
from typing import List

from poker.icm import icm_equity, icm_push_ev, risk_premium, format_icm_table

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
MAX_PLAYERS = 9


class ICMPanel:
    def __init__(self, parent_root=None):
        self._win = tk.Toplevel(parent_root) if parent_root else tk.Tk()
        self._win.title('ICM 計算器')
        self._win.configure(bg=BG)
        self._win.attributes('-topmost', True)
        self._win.resizable(False, False)
        self._win.geometry('520x580+680+480')
        self._n_players  = tk.IntVar(value=6)
        self._stack_vars = [tk.StringVar(value='') for _ in range(MAX_PLAYERS)]
        self._name_vars  = [tk.StringVar(value=f'座位{i+1}') for i in range(MAX_PLAYERS)]
        self._prize_vars = [tk.StringVar(value='') for _ in range(5)]
        self._hero_idx   = tk.IntVar(value=0)
        self._hero_eq    = tk.DoubleVar(value=0.50)
        self._hero_opp   = tk.IntVar(value=1)
        self._build_ui()

    def _build_ui(self):
        self._build_setup()
        self._build_table_input()
        self._build_prizes()
        self._build_hero_section()
        self._build_results()

    def _build_setup(self):
        bar = tk.Frame(self._win, bg=BG2, pady=6)
        bar.pack(fill='x', padx=4, pady=(4,0))
        tk.Label(bar, text='玩家人數:', bg=BG2, fg=DIM, font=('Consolas',9)).pack(side='left', padx=(8,2))
        tk.Spinbox(bar, from_=2, to=9, textvariable=self._n_players,
                   bg=BG3, fg=FG, buttonbackground=BG3, font=('Consolas',9),
                   width=3, relief='flat', command=self._refresh_input).pack(side='left', padx=4)
        tk.Button(bar, text='計算 ICM', command=self._calculate,
                  bg='#238636', fg='white', font=('Consolas',9,'bold'),
                  relief='flat', padx=10).pack(side='right', padx=8)

    def _build_table_input(self):
        self._input_frame = tk.Frame(self._win, bg=BG)
        self._input_frame.pack(fill='x', padx=8, pady=4)
        self._refresh_input()

    def _refresh_input(self):
        for w in self._input_frame.winfo_children(): w.destroy()
        n = self._n_players.get()
        lbl = dict(bg=BG, fg=DIM, font=('Consolas',8))
        ent = dict(bg=BG3, fg=FG, insertbackground=FG, font=('Consolas',9), relief='flat', bd=3)
        hdr = tk.Frame(self._input_frame, bg=BG)
        hdr.pack(fill='x')
        for t, w in [('座位',5),('名稱',12),('籌碼',10),('英雄?',6)]:
            tk.Label(hdr, text=t, width=w, **lbl).pack(side='left', padx=2)
        for i in range(n):
            row = tk.Frame(self._input_frame, bg=BG)
            row.pack(fill='x', pady=1)
            tk.Label(row, text=str(i+1), width=5, **lbl).pack(side='left', padx=2)
            tk.Entry(row, textvariable=self._name_vars[i], width=12, **ent).pack(side='left', padx=2)
            tk.Entry(row, textvariable=self._stack_vars[i], width=10, **ent).pack(side='left', padx=2)
            tk.Radiobutton(row, text='', variable=self._hero_idx, value=i,
                           bg=BG, activebackground=BG, selectcolor=BG2).pack(side='left', padx=4)

    def _build_prizes(self):
        tk.Frame(self._win, bg=BORDER, height=1).pack(fill='x', padx=4, pady=4)
        frame = tk.Frame(self._win, bg=BG2, pady=6)
        frame.pack(fill='x', padx=4)
        tk.Label(frame, text='獎金結構（前 5 名）:', bg=BG2, fg=ACCENT,
                 font=('Consolas',9,'bold')).pack(padx=8, anchor='w')
        row = tk.Frame(frame, bg=BG2)
        row.pack(padx=8, pady=4)
        labels = ['冠軍','亞軍','季軍','第四','第五']
        for i in range(5):
            tk.Label(row, text=labels[i], bg=BG2, fg=DIM, font=('Consolas',8)).grid(row=0, column=i*2, padx=(8,2))
            tk.Entry(row, textvariable=self._prize_vars[i], width=8,
                     bg=BG3, fg=FG, insertbackground=FG, font=('Consolas',9),
                     relief='flat', bd=3).grid(row=0, column=i*2+1, padx=2)

    def _build_hero_section(self):
        tk.Frame(self._win, bg=BORDER, height=1).pack(fill='x', padx=4, pady=4)
        frame = tk.Frame(self._win, bg=BG, pady=4)
        frame.pack(fill='x', padx=12)
        tk.Label(frame, text='全下 EV 分析（選填）:', bg=BG, fg=ACCENT,
                 font=('Consolas',9,'bold')).pack(anchor='w')
        row = tk.Frame(frame, bg=BG)
        row.pack(fill='x', pady=4)
        tk.Label(row, text='英雄勝率:', bg=BG, fg=DIM, font=('Consolas',9)).pack(side='left')
        tk.Scale(row, variable=self._hero_eq, from_=0.01, to=0.99, resolution=0.01,
                 orient='horizontal', length=150, bg=BG, fg=FG, troughcolor=BG2,
                 highlightthickness=0).pack(side='left', padx=8)
        self._eq_lbl = tk.Label(row, text='50%', bg=BG, fg=YELLOW, font=('Consolas',10,'bold'))
        self._eq_lbl.pack(side='left')
        self._hero_eq.trace_add('write', lambda *_: self._eq_lbl.config(text=f'{self._hero_eq.get()*100:.0f}%'))
        row2 = tk.Frame(frame, bg=BG)
        row2.pack(fill='x')
        tk.Label(row2, text='對手座位:', bg=BG, fg=DIM, font=('Consolas',9)).pack(side='left')
        tk.Spinbox(row2, from_=1, to=9, textvariable=self._hero_opp,
                   bg=BG3, fg=FG, buttonbackground=BG3, font=('Consolas',9),
                   width=3, relief='flat').pack(side='left', padx=6)

    def _build_results(self):
        tk.Frame(self._win, bg=BORDER, height=1).pack(fill='x', padx=4, pady=4)
        self._result_text = tk.Text(self._win, bg=BG2, fg=FG, font=('Consolas',9),
                                     relief='flat', state='disabled', wrap='none', padx=8, pady=8, height=10)
        self._result_text.pack(fill='both', expand=True, padx=4, pady=4)

    def _calculate(self):
        n = self._n_players.get()
        try:
            stacks = [int(self._stack_vars[i].get() or 0) for i in range(n)]
            prizes = [float(self._prize_vars[i].get()) for i in range(5) if self._prize_vars[i].get().strip()]
        except ValueError as e:
            self._show(f'輸入錯誤: {e}')
            return
        if not prizes: prizes = [1.0]
        names = [self._name_vars[i].get() or f'座位{i+1}' for i in range(n)]
        eq    = icm_equity(stacks, prizes)
        total = sum(stacks)
        lines = ['ICM 權益表', '=' * 50]
        lines.append(format_icm_table(stacks, prizes, names))
        hero_i = self._hero_idx.get()
        opp_i  = self._hero_opp.get() - 1
        if 0 <= hero_i < n and 0 <= opp_i < n and hero_i != opp_i:
            hero_eq_val = self._hero_eq.get()
            eff = min(stacks[hero_i], stacks[opp_i])
            win_s  = stacks[hero_i] + eff
            lose_s = stacks[hero_i] - eff
            icm_ev, base, chip_ev = icm_push_ev(hero_i, win_s, lose_s, stacks, prizes, hero_eq_val)
            rp = risk_premium(hero_i, stacks, prizes)
            lines += [
                '',
                f'全下 vs 座位{opp_i+1}（勝率 {hero_eq_val*100:.0f}%）',
                '-' * 40,
                f'目前 ICM 權益 : ${base:,.0f}',
                f'全下 ICM EV  : ${icm_ev:,.0f}',
                f'全下籌碼 EV  : ${chip_ev:,.0f}',
                f'ICM 風險溢價 : {rp*100:+.1f}%（需要額外這麼多的勝率才值得）',
                '',
                ('推牌（ICM 正期望值）' if icm_ev >= base else '棄牌（ICM 認為風險不值得）'),
            ]
        self._show('\n'.join(lines))

    def _show(self, text):
        self._result_text.config(state='normal')
        self._result_text.delete('1.0','end')
        self._result_text.insert('end', text)
        self._result_text.config(state='disabled')

    def run(self): self._win.mainloop()
