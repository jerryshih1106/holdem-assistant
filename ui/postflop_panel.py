"""翻牌後分析面板（F3）— 繁體中文介面 + 牌按鈕輸入。"""

import tkinter as tk
from tkinter import ttk
from typing import List, Optional

from poker.board_texture import analyze_board, BoardTexture, wetness_bar
from poker.blockers import blocker_report
from ui.card_picker import CardPickerPopup, CardSlot

BG     = '#0D1117'
BG2    = '#161B22'
BG3    = '#21262D'
FG     = '#E6EDF3'
DIM    = '#8B949E'
ACCENT = '#58A6FF'
GREEN  = '#56D364'
YELLOW = '#E3B341'
RED    = '#FF7B54'
ORANGE = '#FF9900'
BORDER = '#30363D'

ADV_COLORS = {'raiser': GREEN, 'caller': YELLOW, 'neutral': DIM}
ADV_ZH     = {'raiser': '加注方範圍有利', 'caller': '跟注方範圍有利', 'neutral': '均勢牌面'}


class PostflopPanel:
    def __init__(self, parent_root=None):
        self._win = tk.Toplevel(parent_root) if parent_root else tk.Tk()
        self._win.title('翻牌後分析')
        self._win.configure(bg=BG)
        self._win.attributes('-topmost', True)
        self._win.resizable(False, False)
        self._win.geometry('430x580+680+20')

        self._board_cards: List[Optional[str]] = [None]*5
        self._hole_cards:  List[Optional[str]] = [None, None]
        self._players_var  = tk.IntVar(value=2)
        self._is_aggressor = tk.BooleanVar(value=True)

        self._build_ui()

    def _build_ui(self):
        self._build_input_bar()
        self._build_card_slots()
        self._build_texture_section()
        self._build_cbet_section()
        self._build_blocker_section()
        self._build_multiway_section()

    def _build_input_bar(self):
        bar = tk.Frame(self._win, bg=BG2, pady=6)
        bar.pack(fill='x', padx=4, pady=(4,0))
        tk.Label(bar, text='對手人數:', bg=BG2, fg=DIM, font=('Consolas',9)).pack(side='left', padx=(8,2))
        tk.Spinbox(bar, from_=2, to=9, textvariable=self._players_var,
                   bg=BG3, fg=FG, buttonbackground=BG3, font=('Consolas',9),
                   width=3, relief='flat').pack(side='left', padx=4)
        tk.Checkbutton(bar, text='我是翻前加注方', variable=self._is_aggressor,
                       bg=BG2, fg=FG, selectcolor=BG3, font=('Consolas',9)).pack(side='left', padx=8)
        tk.Button(bar, text='分析', command=self._analyse,
                  bg='#238636', fg='white', font=('Consolas',9,'bold'), relief='flat', padx=10).pack(side='right', padx=8)

    def _build_card_slots(self):
        tk.Frame(self._win, bg=BORDER, height=1).pack(fill='x', padx=4, pady=2)
        outer = tk.Frame(self._win, bg=BG, pady=4)
        outer.pack(fill='x', padx=8)

        # 手牌列
        r1 = tk.Frame(outer, bg=BG)
        r1.pack(fill='x', pady=(0,4))
        tk.Label(r1, text='我的手牌:', bg=BG, fg=DIM, font=('Consolas',9)).pack(side='left', padx=(0,4))
        self._h_slots = []
        for i in range(2):
            s = CardSlot(r1, on_click=lambda sl, i=i: self._pick_card('hole', i, sl))
            s.pack(side='left', padx=2)
            self._h_slots.append(s)

        # 公牌列
        r2 = tk.Frame(outer, bg=BG)
        r2.pack(fill='x')
        tk.Label(r2, text='公    牌:', bg=BG, fg=DIM, font=('Consolas',9)).pack(side='left', padx=(0,4))
        self._b_slots = []
        for i in range(5):
            s = CardSlot(r2, on_click=lambda sl, i=i: self._pick_card('board', i, sl))
            s.pack(side='left', padx=1)
            self._b_slots.append(s)
        tk.Button(r2, text='清除', bg='#442222', fg='#FF8888',
                  font=('Consolas',8), relief='flat', cursor='hand2',
                  command=self._clear_cards).pack(side='right', padx=4)

    def _pick_card(self, kind, idx, slot):
        used = [c for c in self._hole_cards + self._board_cards if c]
        def on_select(card):
            if kind == 'hole':
                self._hole_cards[idx] = card
                self._h_slots[idx].set_card(card)
            else:
                self._board_cards[idx] = card
                self._b_slots[idx].set_card(card)
            self._analyse()
        CardPickerPopup(self._win, used, on_select,
                        title=f'選{"手牌" if kind=="hole" else "公牌"} {idx+1}')

    def _clear_cards(self):
        self._board_cards = [None]*5
        self._hole_cards  = [None, None]
        for s in self._h_slots: s.set_card(None)
        for s in self._b_slots: s.set_card(None)
        self._reset_labels()

    def _build_texture_section(self):
        tk.Frame(self._win, bg=BORDER, height=1).pack(fill='x', padx=4, pady=2)
        frame = tk.Frame(self._win, bg=BG, pady=4)
        frame.pack(fill='x', padx=12)

        r1 = tk.Frame(frame, bg=BG); r1.pack(fill='x')
        tk.Label(r1, text='牌面紋理:', bg=BG, fg=DIM, font=('Consolas',9)).pack(side='left')
        self._texture_lbl = tk.Label(r1, text='—', bg=BG, fg=ACCENT, font=('Consolas',11,'bold'))
        self._texture_lbl.pack(side='left', padx=6)

        r2 = tk.Frame(frame, bg=BG); r2.pack(fill='x', pady=2)
        tk.Label(r2, text='範圍優勢:', bg=BG, fg=DIM, font=('Consolas',9)).pack(side='left')
        self._adv_lbl = tk.Label(r2, text='—', bg=BG, fg=DIM, font=('Consolas',10,'bold'))
        self._adv_lbl.pack(side='left', padx=6)

        r3 = tk.Frame(frame, bg=BG); r3.pack(fill='x', pady=2)
        tk.Label(r3, text='潤濕程度: ', bg=BG, fg=DIM, font=('Consolas',9)).pack(side='left')
        self._wet_lbl = tk.Label(r3, text='', bg=BG, fg=YELLOW, font=('Consolas',9))
        self._wet_lbl.pack(side='left')

        self._draw_lbl = tk.Label(frame, text='', bg=BG, fg=DIM, font=('Consolas',9))
        self._draw_lbl.pack(anchor='w', pady=2)

    def _build_cbet_section(self):
        tk.Frame(self._win, bg=BORDER, height=1).pack(fill='x', padx=4, pady=2)
        frame = tk.Frame(self._win, bg=BG2, pady=8)
        frame.pack(fill='x', padx=4)
        tk.Label(frame, text='持續注策略（有位置加注方）', bg=BG2, fg=ACCENT,
                 font=('Consolas',9,'bold')).pack(padx=10, anchor='w')
        row = tk.Frame(frame, bg=BG2); row.pack(fill='x', padx=10, pady=4)
        tk.Label(row, text='頻率:', bg=BG2, fg=DIM, font=('Consolas',9)).pack(side='left')
        self._cbet_freq_lbl = tk.Label(row, text='—', bg=BG2, fg=GREEN, font=('Consolas',18,'bold'))
        self._cbet_freq_lbl.pack(side='left', padx=6)
        tk.Label(row, text='注碼:', bg=BG2, fg=DIM, font=('Consolas',9)).pack(side='left', padx=(16,2))
        self._cbet_size_lbl = tk.Label(row, text='—', bg=BG2, fg=YELLOW, font=('Consolas',18,'bold'))
        self._cbet_size_lbl.pack(side='left')
        self._cbet_note_lbl = tk.Label(frame, text='', bg=BG2, fg=DIM, font=('Consolas',8),
                                        wraplength=390, justify='left')
        self._cbet_note_lbl.pack(padx=10, anchor='w')

    def _build_blocker_section(self):
        tk.Frame(self._win, bg=BORDER, height=1).pack(fill='x', padx=4, pady=2)
        frame = tk.Frame(self._win, bg=BG, pady=6)
        frame.pack(fill='x', padx=12)
        tk.Label(frame, text='阻牌分析', bg=BG, fg=ACCENT, font=('Consolas',9,'bold')).pack(anchor='w')
        row = tk.Frame(frame, bg=BG); row.pack(fill='x', pady=4)
        tk.Label(row, text='詐唬品質:', bg=BG, fg=DIM, font=('Consolas',9)).pack(side='left')
        self._bluff_score_lbl = tk.Label(row, text='—', bg=BG, fg=FG, font=('Consolas',11,'bold'))
        self._bluff_score_lbl.pack(side='left', padx=6)
        tk.Label(row, text='跟注品質:', bg=BG, fg=DIM, font=('Consolas',9)).pack(side='left', padx=(12,2))
        self._call_score_lbl = tk.Label(row, text='—', bg=BG, fg=FG, font=('Consolas',11,'bold'))
        self._call_score_lbl.pack(side='left', padx=6)
        self._blocker_note_lbl = tk.Label(frame, text='', bg=BG, fg=DIM, font=('Consolas',8),
                                           wraplength=390, justify='left')
        self._blocker_note_lbl.pack(anchor='w')

    def _build_multiway_section(self):
        tk.Frame(self._win, bg=BORDER, height=1).pack(fill='x', padx=4, pady=2)
        self._multiway_lbl = tk.Label(self._win, text='', bg=BG, fg=ORANGE,
                                       font=('Consolas',9,'bold'), pady=4)
        self._multiway_lbl.pack()

    def _analyse(self):
        board = [c for c in self._board_cards if c]
        hole  = [c for c in self._hole_cards  if c]
        players = self._players_var.get()
        if not board:
            self._reset_labels()
            return
        tex = analyze_board(board)
        self._update_texture(tex)
        self._update_cbet(tex, players)
        if len(hole) >= 2: self._update_blockers(hole, board)
        self._update_multiway(players, tex)

    def _update_texture(self, tex):
        # 中文化紋理名稱
        zh_map = {
            'Dry Rainbow': '乾燥彩虹', 'Two-tone': '雙色', 'Two-tone Paired': '雙色配對',
            'Connected Rainbow': '連張彩虹', 'Connected Rainbow Paired': '連張配對',
            'Wet — Flush + Straight draws': '潮濕-同花+順子聽牌', 'Monotone': '單色同花',
            'Flush on board': '公牌同花已成', 'Dry Paired': '乾燥配對', 'Pre-flop': '翻前',
        }
        name = zh_map.get(tex.texture_name, tex.texture_name)
        self._texture_lbl.config(text=name)
        adv_color = ADV_COLORS.get(tex.range_advantage, DIM)
        self._adv_lbl.config(text=ADV_ZH.get(tex.range_advantage,'—'), fg=adv_color)
        wet_pct = int(tex.wetness * 100)
        bar = wetness_bar(tex.wetness, 16)
        wet_color = YELLOW if tex.wetness > 0.5 else GREEN if tex.wetness < 0.3 else ORANGE
        self._wet_lbl.config(text=f'{bar}  {wet_pct}%', fg=wet_color)
        parts = []
        if tex.flush_draw or tex.monotone or tex.flush_complete:
            parts.append('同花聽牌' if tex.flush_draw else '單色' if tex.monotone else '同花已完成')
        if tex.str8_outs > 0: parts.append(f'{tex.str8_outs} 張順子補牌')
        if tex.has_pair: parts.append('配對牌面')
        self._draw_lbl.config(text='  '.join(parts) if parts else '無主要聽牌')

    def _update_cbet(self, tex, players):
        freq = tex.cbet_freq
        size = tex.cbet_size
        if players >= 3:
            freq = max(0.15, freq * (1 - 0.15 * (players - 2)))
            size = min(0.85, size * 1.1)
        color = GREEN if freq >= 0.6 else YELLOW if freq >= 0.4 else RED
        self._cbet_freq_lbl.config(text=f'{int(freq*100)}%', fg=color)
        self._cbet_size_lbl.config(text=f'{int(size*100)}% 底池')
        # 中文化 note
        note_map = {
            'Trip board — mostly check, opponent likely has nothing': '三條牌面 — 多數情況過牌，對手很少有牌',
            'Monotone — bet only with strong hands or nut flush draw': '單色牌面 — 只在強牌或堅果同花聽牌時下注',
            'Flush complete — check range unless you have the flush': '同花已完成 — 沒有同花請過牌',
            'Dry paired — check mostly; bet thinly with top pair+': '乾燥配對 — 多數過牌，頂對以上可薄薄下注',
            'Wet board — polarised: bet strong hands/bluffs, check middle': '潮濕牌面 — 極化策略：強牌/詐唬下注，中等牌力過牌',
            'Semi-wet — mix: bet top pair+, check weak pairs/draws': '半潮濕 — 混合：頂對以上下注，弱對/聽牌過牌',
            'Dry board — high-frequency small bet entire range': '乾燥牌面 — 高頻小注整個範圍',
        }
        note = note_map.get(tex.cbet_note, tex.cbet_note)
        if players >= 3: note = f'【{players}人底池，降低頻率】' + note
        self._cbet_note_lbl.config(text=note)

    def _update_blockers(self, hole, board):
        value_hands = ['AA','KK','QQ','JJ','TT','AKs','AKo','AQs','AQo','AJs','KQs','KJs','QJs','JTs']
        bluff_hands = ['A5s','A4s','A3s','A2s','K5s','Q5s','J5s','T5s','76s','65s','54s']
        report = blocker_report(hole, board, value_hands, bluff_hands)
        bs, cs = report['bluff_score'], report['call_score']
        bluff_color = GREEN if bs>0.6 else YELLOW if bs>0.35 else RED
        call_color  = GREEN if cs>0.6 else YELLOW if cs>0.35 else RED
        self._bluff_score_lbl.config(text=f'{int(bs*100)}/100', fg=bluff_color)
        self._call_score_lbl.config(text=f'{int(cs*100)}/100', fg=call_color)
        self._blocker_note_lbl.config(text=report['note'])

    def _update_multiway(self, players, tex):
        if players >= 3:
            self._multiway_lbl.config(
                text=f'多人底池（{players} 人）— 大幅收緊跟注範圍，減少詐唬', fg=ORANGE)
        else:
            self._multiway_lbl.config(text='單挑底池', fg=DIM)

    def _reset_labels(self):
        for lbl in [self._texture_lbl, self._adv_lbl, self._wet_lbl, self._draw_lbl,
                    self._cbet_freq_lbl, self._cbet_size_lbl, self._cbet_note_lbl,
                    self._blocker_note_lbl, self._bluff_score_lbl, self._call_score_lbl]:
            lbl.config(text='—')

    def update_from_detection(self, board: List[str], hole: List[str], players: int = 2):
        for i, c in enumerate(board[:5]):
            if self._board_cards[i] != c:
                self._board_cards[i] = c
                self._b_slots[i].set_card(c)
        for i, c in enumerate(hole[:2]):
            if self._hole_cards[i] != c:
                self._hole_cards[i] = c
                self._h_slots[i].set_card(c)
        self._players_var.set(players)
        self._analyse()

    def run(self): self._win.mainloop()
