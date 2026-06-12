"""局史與漏洞分析面板（F5）— 繁體中文介面。"""

import tkinter as tk
from tkinter import ttk
from typing import List, Optional

from poker.history import HistoryTracker, HandRecord

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


class HistoryPanel:
    def __init__(self, tracker: HistoryTracker, parent_root=None):
        self._tracker = tracker
        self._win = tk.Toplevel(parent_root) if parent_root else tk.Tk()
        self._win.title('局史與漏洞分析')
        self._win.configure(bg=BG)
        self._win.attributes('-topmost', True)
        self._win.geometry('700x480+20+480')

        notebook = ttk.Notebook(self._win)
        notebook.pack(fill='both', expand=True, padx=4, pady=4)
        style = ttk.Style()
        style.theme_use('default')
        style.configure('TNotebook', background=BG, borderwidth=0)
        style.configure('TNotebook.Tab', background=BG2, foreground=FG,
                        font=('Consolas', 9), padding=[10, 4])
        style.map('TNotebook.Tab', background=[('selected', BG3)])

        self._tab_stats  = tk.Frame(notebook, bg=BG)
        self._tab_leaks  = tk.Frame(notebook, bg=BG)
        self._tab_hands  = tk.Frame(notebook, bg=BG)
        self._tab_record = tk.Frame(notebook, bg=BG)

        notebook.add(self._tab_stats,  text='本場統計')
        notebook.add(self._tab_leaks,  text='漏洞分析')
        notebook.add(self._tab_hands,  text='近期手牌')
        notebook.add(self._tab_record, text='記錄手牌')

        self._build_stats_tab()
        self._build_leaks_tab()
        self._build_hands_tab()
        self._build_record_tab()
        notebook.bind('<<NotebookTabChanged>>', lambda _: self._refresh_current(notebook))
        self._refresh_stats()

    def _build_stats_tab(self):
        f = self._tab_stats
        tk.Button(f, text='重新整理', command=self._refresh_stats,
                  bg='#238636', fg='white', font=('Consolas',9), relief='flat', padx=8
                  ).pack(anchor='e', padx=8, pady=4)
        self._stats_text = tk.Text(f, bg=BG2, fg=FG, font=('Consolas',10),
                                    relief='flat', state='disabled', wrap='none', padx=8, pady=8)
        self._stats_text.pack(fill='both', expand=True, padx=4, pady=4)

    def _refresh_stats(self):
        stats = self._tracker.session_stats()
        lines = [
            f'場次 #{stats.session_id}',
            f'已打手數   : {stats.hands}',
            f'本場淨損益 : {stats.profit:+,} 籌碼',
            f'bb/100     : {stats.bb_per_100():.1f}' if stats.bb_per_100() is not None else 'bb/100     : — （需 20 手以上）',
            f'跟隨建議率 : {stats.rec_follow_pct():.0f}%' if stats.rec_follow_pct() else '跟隨建議率 : —',
            '',
            f'{"位置":6s} {"手數":>6s} {"入池%":>7s} {"加注%":>7s}',
            '-' * 32,
        ]
        for pos in ['UTG','HJ','CO','BTN','SB','BB']:
            h = stats.hands_by_pos.get(pos, 0)
            if h == 0: continue
            v = stats.vpip_pct(pos)
            p = stats.pfr_pct(pos)
            lines.append(
                f'{pos:6s} {h:>6d} '
                f'{f"{v:.0f}%" if v is not None else "—":>7s} '
                f'{f"{p:.0f}%" if p is not None else "—":>7s}'
            )
        self._set_text(self._stats_text, '\n'.join(lines))

    def _build_leaks_tab(self):
        f = self._tab_leaks
        tk.Button(f, text='分析漏洞', command=self._refresh_leaks,
                  bg='#8B1A1A', fg='white', font=('Consolas',9,'bold'),
                  relief='flat', padx=10).pack(anchor='e', padx=8, pady=4)
        cols = ('位置','統計項目','你的數值','GTO基準','差距','嚴重程度')
        self._leak_tree = ttk.Treeview(f, columns=cols, show='headings', height=8)
        widths = [70,90,70,70,60,80]
        for col, w in zip(cols, widths):
            self._leak_tree.heading(col, text=col)
            self._leak_tree.column(col, width=w, anchor='center')
        style = ttk.Style()
        style.configure('Treeview', background=BG2, foreground=FG,
                        fieldbackground=BG2, font=('Consolas',9))
        style.configure('Treeview.Heading', background=BG3, foreground=ACCENT,
                        font=('Consolas',9,'bold'))
        self._leak_tree.pack(fill='x', padx=4, pady=4)
        self._tip_lbl = tk.Label(f, text='', bg=BG, fg=YELLOW, font=('Consolas',9),
                                  wraplength=660, justify='left')
        self._tip_lbl.pack(padx=8, pady=4, anchor='w')
        self._leak_tree.bind('<<TreeviewSelect>>', self._on_leak_select)

    def _refresh_leaks(self):
        for row in self._leak_tree.get_children(): self._leak_tree.delete(row)
        leaks = self._tracker.find_leaks()
        if not leaks:
            self._leak_tree.insert('','end', values=('—','—','—','—','—','未發現漏洞'))
            return
        STAT_ZH = {'vpip':'主動入池率','pfr':'翻前加注率','cbet':'持續注率','fold_cbet':'遇持續注棄牌率'}
        SEVERITY_ZH = {'High':'嚴重','Medium':'中等'}
        for leak in leaks:
            tag = 'high' if leak['severity']=='High' else 'medium'
            self._leak_tree.insert('','end', iid=str(id(leak)), values=(
                leak['position'],
                STAT_ZH.get(leak['stat'], leak['stat']),
                f"{leak['hero_value']:.0f}%",
                f"{leak['gto_value']:.0f}%",
                f"{leak['diff']:+.0f}%",
                SEVERITY_ZH.get(leak['severity'], leak['severity']),
            ), tags=(tag,))
        self._leak_tree.tag_configure('high',   foreground=RED)
        self._leak_tree.tag_configure('medium', foreground=YELLOW)
        self._leaks_data = leaks

    def _on_leak_select(self, _):
        sel = self._leak_tree.selection()
        if not sel: return
        idx = list(self._leak_tree.get_children()).index(sel[0])
        if hasattr(self,'_leaks_data') and idx < len(self._leaks_data):
            self._tip_lbl.config(text='建議：' + self._leaks_data[idx]['tip'])

    def _build_hands_tab(self):
        f = self._tab_hands
        tk.Button(f, text='重新整理', command=self._refresh_hands,
                  bg='#238636', fg='white', font=('Consolas',9), relief='flat', padx=8
                  ).pack(anchor='e', padx=8, pady=4)
        cols = ('位置','手牌','公牌','我的行動','建議','損益')
        self._hands_tree = ttk.Treeview(f, columns=cols, show='headings', height=14)
        widths = [55,80,145,75,75,80]
        for col, w in zip(cols, widths):
            self._hands_tree.heading(col, text=col)
            self._hands_tree.column(col, width=w, anchor='center')
        self._hands_tree.pack(fill='both', expand=True, padx=4, pady=4)

    def _refresh_hands(self):
        for row in self._hands_tree.get_children(): self._hands_tree.delete(row)
        hands = self._tracker.recent_hands(20)
        for h in hands:
            followed = h['hero_action'].upper() == h['rec_action'].upper()
            tag = 'followed' if followed else 'deviated'
            self._hands_tree.insert('','end', values=(
                h['position'], ' '.join(h['hole_cards']), ' '.join(h['community']),
                h['hero_action'], h['rec_action'], f"{h['outcome']:+,}",
            ), tags=(tag,))
        self._hands_tree.tag_configure('followed', foreground=GREEN)
        self._hands_tree.tag_configure('deviated',  foreground=YELLOW)

    def _build_record_tab(self):
        f = self._tab_record
        lbl = dict(bg=BG, fg=DIM, font=('Consolas',9))
        ent = dict(bg=BG3, fg=FG, insertbackground=FG, font=('Consolas',10), relief='flat', bd=4)

        self._r_pos   = tk.StringVar(value='BTN')
        self._r_hole  = tk.StringVar()
        self._r_board = tk.StringVar()
        self._r_pot   = tk.StringVar(value='0')
        self._r_call  = tk.StringVar(value='0')
        self._r_stack = tk.StringVar(value='1000')
        self._r_out   = tk.StringVar(value='0')
        self._r_hero  = tk.StringVar(value='棄牌')
        self._r_rec   = tk.StringVar(value='棄牌')

        fields = [
            ('位置', self._r_pos, 8), ('手牌', self._r_hole, 12),
            ('公牌', self._r_board, 18), ('底池', self._r_pot, 8),
            ('跟注額', self._r_call, 8), ('籌碼', self._r_stack, 8),
            ('損益', self._r_out, 8), ('我的行動', self._r_hero, 10),
            ('建議行動', self._r_rec, 10),
        ]
        for i, (name, var, w) in enumerate(fields):
            r, c = divmod(i, 2)
            tk.Label(f, text=name+':', **lbl).grid(row=r, column=c*2, sticky='e', padx=8, pady=4)
            tk.Entry(f, textvariable=var, width=w, **ent).grid(row=r, column=c*2+1, sticky='w', padx=4, pady=4)

        tk.Button(f, text='儲存手牌', command=self._save_hand,
                  bg='#238636', fg='white', font=('Consolas',10,'bold'),
                  relief='flat', padx=14).grid(row=5, column=0, columnspan=4, pady=8)
        self._save_status = tk.Label(f, text='', bg=BG, fg=GREEN, font=('Consolas',9))
        self._save_status.grid(row=6, column=0, columnspan=4)

    def _save_hand(self):
        try:
            rec = HandRecord(
                hand_id=None, session_id=self._tracker.session_id,
                position=self._r_pos.get().strip().upper(),
                hole_cards=self._r_hole.get().strip().split(),
                community=self._r_board.get().strip().split(),
                pot_size=int(self._r_pot.get() or 0),
                call_amount=int(self._r_call.get() or 0),
                hero_stack=int(self._r_stack.get() or 0),
                outcome=int(self._r_out.get() or 0),
                hero_action=self._r_hero.get().strip(),
                rec_action=self._r_rec.get().strip(),
                followed_rec=(self._r_hero.get().strip() == self._r_rec.get().strip()),
            )
            self._tracker.record_hand(rec)
            self._save_status.config(text='已儲存。', fg=GREEN)
        except Exception as e:
            self._save_status.config(text=f'錯誤: {e}', fg=RED)

    def _set_text(self, widget, content):
        widget.config(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('end', content)
        widget.config(state='disabled')

    def _refresh_current(self, nb):
        tab = nb.tab(nb.select(), 'text')
        if tab == '本場統計':  self._refresh_stats()
        elif tab == '漏洞分析': self._refresh_leaks()
        elif tab == '近期手牌': self._refresh_hands()

    def run(self): self._win.mainloop()
