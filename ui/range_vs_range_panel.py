"""
Range vs Range 視覺面板 (F9)

雙 13×13 格面板：
  左格：對手範圍 — 每手牌依 VPIP/PFR 估算的出現頻率（深藍=常見，淺色=罕見）
  右格：英雄優勢 — 英雄手牌是否打得贏對手範圍中的各手牌
         深綠 = 英雄大幅領先（勝率 > 65%）
         淡綠 = 英雄略微領先（50-65%）
         黃色 = 接近平手（45-55%）
         淡紅 = 英雄略輸（35-50%）
         深紅 = 英雄大幅落後（< 35%）

快捷鍵：F9 開/關
用途：
  薄取值？右格大多是綠 → 可以取值
  詐唬接住？右格大多是紅 → 對手有值牌，考慮棄牌
"""

import tkinter as tk
from typing import List, Optional, Tuple, Dict

BG         = '#0D1117'
PANEL_BG   = '#161B22'
BORDER     = '#30363D'
TEXT_FG    = '#C9D1D9'
TITLE_FG   = '#58A6FF'
GREEN_DARK = '#1A4A2A'
GREEN_MID  = '#2D6A3F'
GREEN_LT   = '#3A8A52'
YELLOW     = '#8A6A00'
RED_LT     = '#7A2020'
RED_DARK   = '#4A0E0E'
EMPTY_BG   = '#1A1A2A'

# 13 ranks 高→低
_RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']

# 翻前手牌類型：pair=pocket pair, s=suited, o=offsuit
def _hand_str(r1: str, r2: str) -> str:
    i1, i2 = _RANKS.index(r1), _RANKS.index(r2)
    if i1 == i2:
        return r1 + r2          # pair
    if i1 < i2:
        return r1 + r2 + 's' if True else r1 + r2 + 'o'
    return r2 + r1 + 's' if True else r2 + r1 + 'o'


def _cell_hand(row: int, col: int) -> str:
    r1, r2 = _RANKS[row], _RANKS[col]
    if row == col:
        return r1 + r2          # pocket pair
    if row < col:
        return r1 + r2 + 's'   # suited (upper-triangle)
    return r2 + r1 + 'o'       # offsuit (lower-triangle)


# 簡易翻前手牌勝率估算（vs 隨機範圍的 preflop equity）
_PREFLOP_EQ: Dict[str, float] = {
    # Pairs
    'AA':0.852,'KK':0.823,'QQ':0.799,'JJ':0.775,'TT':0.751,
    '99':0.720,'88':0.693,'77':0.663,'66':0.632,'55':0.600,
    '44':0.569,'33':0.536,'22':0.503,
    # Suited broadways
    'AKs':0.672,'AQs':0.660,'AJs':0.652,'ATs':0.644,
    'KQs':0.635,'KJs':0.627,'KTs':0.620,
    'QJs':0.615,'QTs':0.608,'JTs':0.608,
    # Suited one-gappers
    'A9s':0.631,'A8s':0.625,'A7s':0.618,'A6s':0.613,'A5s':0.614,
    'A4s':0.607,'A3s':0.601,'A2s':0.595,
    'K9s':0.612,'K8s':0.604,'Q9s':0.598,'J9s':0.596,'T9s':0.596,
    '98s':0.580,'87s':0.568,'76s':0.554,'65s':0.542,'54s':0.528,
    # Offsuit broadways
    'AKo':0.651,'AQo':0.636,'AJo':0.625,'ATo':0.615,
    'KQo':0.613,'KJo':0.603,'KTo':0.593,
    'QJo':0.587,'QTo':0.578,'JTo':0.573,
    # Others fallback handled by eq_vs_random()
}

def _eq_vs_random(hand: str) -> float:
    if hand in _PREFLOP_EQ:
        return _PREFLOP_EQ[hand]
    # Fallback estimate: pairs > suited > offsuit
    r1 = hand[0]; r2 = hand[1] if len(hand) >= 2 else '2'
    is_pair = (r1 == r2)
    is_suited = hand.endswith('s')
    rank_val = {'A':14,'K':13,'Q':12,'J':11,'T':10,'9':9,'8':8,
                '7':7,'6':6,'5':5,'4':4,'3':3,'2':2}
    v1 = rank_val.get(r1, 5); v2 = rank_val.get(r2, 3)
    if is_pair:
        return 0.50 + (v1 - 2) / 24
    gap = abs(v1 - v2)
    base = 0.50 + (v1 + v2 - 4) / 80
    suited_bonus = 0.02 if is_suited else 0
    gap_penalty  = gap * 0.005
    return min(0.85, max(0.48, base + suited_bonus - gap_penalty))


# 對手出現頻率（近似 VPIP 下各手牌的開牌機率）
_TIGHT_HANDS = {
    'AA','KK','QQ','JJ','TT','99','88',
    'AKs','AQs','AJs','ATs','KQs','KJs','QJs',
    'AKo','AQo','AJo',
}
_MEDIUM_HANDS = {
    '77','66','55','44','33','22',
    'A9s','A8s','A7s','A6s','A5s','A4s','A3s','A2s',
    'K9s','K8s','K7s','K6s','KTs','QTs','JTs','T9s',
    'ATo','KQo','KJo','KTo','QJo','QTo','JTo',
}


def _villain_freq(hand: str, villain_vpip: float) -> float:
    """估算對手以此 VPIP 打出這手牌的頻率（0=不在範圍,1=常見）。"""
    if hand in _TIGHT_HANDS:
        return 1.0
    if hand in _MEDIUM_HANDS:
        return min(1.0, villain_vpip / 0.30)   # vpip<30% 只打精選手牌
    # 寬鬆牌（垃圾牌）
    return max(0.0, (villain_vpip - 0.35) / 0.30)


def _equity_color(eq: float, threshold: float = 0.50) -> str:
    """根據英雄 vs 此手牌的勝率著色。"""
    delta = eq - threshold
    if delta > 0.20:
        return '#1A6B2A'    # 深綠
    if delta > 0.08:
        return '#2D8A3F'    # 綠
    if delta > -0.02:
        return '#6B6B00'    # 黃
    if delta > -0.12:
        return '#7A2020'    # 淡紅
    return '#5A0E0E'        # 深紅


def _villain_freq_color(freq: float) -> str:
    """依頻率著色（深藍=常見，灰=罕見）。"""
    if freq >= 0.80:
        return '#1A4A7A'
    if freq >= 0.50:
        return '#1A3A6A'
    if freq >= 0.20:
        return '#1A2A4A'
    if freq > 0.0:
        return '#161B22'
    return '#0D1117'


class RangeVsRangePanel:
    """F9 Range vs Range 雙格視覺面板。"""

    CELL = 30      # 格子尺寸
    GAP  = 16      # 兩個格子之間的間距

    def __init__(self, parent_root: tk.Tk):
        self._root   = parent_root
        self._win    = tk.Toplevel(parent_root)
        self._win.title('Range vs Range')
        self._win.configure(bg=BG)
        self._win.attributes('-topmost', True)
        self._win.resizable(False, False)

        # 狀態
        self._hero_hand:    Optional[List[str]] = None
        self._community:    List[str] = []
        self._villain_vpip: float = 0.30
        self._villain_pos:  str   = 'BTN'

        # 格子按鈕: [left_cells, right_cells] each 13×13
        self._left_cells:  List[List[tk.Label]] = []
        self._right_cells: List[List[tk.Label]] = []

        self._build_ui()
        self._win.protocol('WM_DELETE_WINDOW', self._on_close)

    def _build_ui(self):
        C = self.CELL
        G = self.GAP
        N = 13

        # ── 標題列 ────────────────────────────────────────────────────────────
        header = tk.Frame(self._win, bg=BG)
        header.pack(fill='x', padx=8, pady=(8, 4))

        self._title_lbl = tk.Label(
            header, text='Range vs Range',
            bg=BG, fg=TITLE_FG, font=('Consolas', 11, 'bold'))
        self._title_lbl.pack(side='left')

        # VPIP 輸入
        tk.Label(header, text='對手VPIP%:', bg=BG, fg=TEXT_FG,
                 font=('Consolas', 9)).pack(side='right', padx=(0, 4))
        self._vpip_var = tk.StringVar(value='30')
        vcmd = (self._win.register(self._on_vpip_change), '%P')
        tk.Entry(header, textvariable=self._vpip_var,
                 bg='#1C2128', fg='#E0E0E0', insertbackground='white',
                 font=('Consolas', 9), width=5, relief='flat', bd=3,
                 validate='key', validatecommand=vcmd).pack(side='right')

        # ── 左格標題（對手範圍頻率）── 右格標題（英雄優勢） ──────────────────
        label_row = tk.Frame(self._win, bg=BG)
        label_row.pack(padx=8, pady=2)

        lbl_w = N * C + G // 2
        tk.Label(label_row, text='對手範圍頻率',
                 bg=BG, fg='#58A6FF', font=('Consolas', 9, 'bold'),
                 width=lbl_w // 6).pack(side='left', padx=(20, 40))
        tk.Label(label_row, text='英雄領先 / 落後',
                 bg=BG, fg='#56D364', font=('Consolas', 9, 'bold')).pack(side='left')

        # ── 雙格容器 ─────────────────────────────────────────────────────────
        grids_frame = tk.Frame(self._win, bg=BG)
        grids_frame.pack(padx=8, pady=4)

        left_frame  = tk.Frame(grids_frame, bg=BG)
        right_frame = tk.Frame(grids_frame, bg=BG)
        left_frame.pack(side='left', padx=(0, G))
        right_frame.pack(side='left')

        # 每格上方的 rank 標頭
        for frame in (left_frame, right_frame):
            tk.Label(frame, text=' ', bg=BG, width=2,
                     font=('Consolas', 7)).grid(row=0, column=0)
            for ci, r in enumerate(_RANKS):
                tk.Label(frame, text=r, bg=BG, fg='#666677',
                         font=('Consolas', 7), width=3).grid(row=0, column=ci + 1)

        # 建立格子
        for grid_frame, cell_list in [(left_frame, self._left_cells),
                                       (right_frame, self._right_cells)]:
            cell_list.clear()
            for ri, r1 in enumerate(_RANKS):
                row_cells = []
                tk.Label(grid_frame, text=r1, bg=BG, fg='#666677',
                         font=('Consolas', 7), width=2).grid(row=ri + 1, column=0)
                for ci, r2 in enumerate(_RANKS):
                    hand = _cell_hand(ri, ci)
                    lbl = tk.Label(
                        grid_frame,
                        text=hand[:2],
                        bg=EMPTY_BG, fg='#999999',
                        font=('Consolas', 6),
                        width=3, height=1,
                        relief='flat', bd=1,
                    )
                    lbl.grid(row=ri + 1, column=ci + 1, padx=1, pady=1)
                    row_cells.append(lbl)
                cell_list.append(row_cells)

        # ── 圖例 ──────────────────────────────────────────────────────────────
        legend = tk.Frame(self._win, bg=BG)
        legend.pack(fill='x', padx=8, pady=(2, 6))

        legends = [
            ('#1A6B2A', '強力領先'),
            ('#2D8A3F', '領先'),
            ('#6B6B00', '接近'),
            ('#7A2020', '落後'),
            ('#5A0E0E', '大幅落後'),
        ]
        for color, text in legends:
            f = tk.Frame(legend, bg=color, width=12, height=12)
            f.pack(side='left', padx=(4, 2))
            tk.Label(legend, text=text, bg=BG, fg='#888888',
                     font=('Consolas', 7)).pack(side='left', padx=(0, 8))

        # 初始渲染
        self._redraw()

    def update(
        self,
        hero_hand:     Optional[List[str]],
        community:     List[str],
        villain_vpip:  float = 0.30,
        villain_pos:   str   = 'BTN',
    ):
        """更新面板顯示。villain_vpip 為小數 (0-1)。"""
        self._hero_hand    = hero_hand
        self._community    = community
        self._villain_vpip = villain_vpip
        self._villain_pos  = villain_pos
        self._vpip_var.set(str(int(villain_vpip * 100)))
        try:
            self._win.after(0, self._redraw)
        except Exception:
            pass

    def _on_vpip_change(self, val: str) -> bool:
        if val == '' or val.isdigit():
            try:
                v = int(val) if val else 30
                self._villain_vpip = max(5, min(85, v)) / 100.0
                self._win.after(10, self._redraw)
            except ValueError:
                pass
        return True

    def _redraw(self):
        """重新計算並渲染兩個格子。"""
        vpip = self._villain_vpip
        hero = self._hero_hand or []

        # 確定英雄手牌的勝率表（vs 每個對手手牌）
        hero_eq_map: Dict[str, float] = {}
        if len(hero) >= 2:
            hero_eq_map = _precompute_hero_vs_all(hero)

        for ri in range(13):
            for ci in range(13):
                hand = _cell_hand(ri, ci)
                freq = _villain_freq(hand, vpip)

                # 左格：頻率
                l_bg = _villain_freq_color(freq)
                l_fg = '#CCCCCC' if freq >= 0.20 else '#444444'
                self._left_cells[ri][ci].config(bg=l_bg, fg=l_fg)

                # 右格：英雄優勢
                if not hero_eq_map:
                    self._right_cells[ri][ci].config(bg=EMPTY_BG, fg='#444444')
                elif freq <= 0.0:
                    self._right_cells[ri][ci].config(bg='#0D0D1A', fg='#222222')
                else:
                    eq = hero_eq_map.get(hand, _eq_vs_random(hand))
                    r_bg = _equity_color(eq)
                    r_fg = '#CCCCCC' if abs(eq - 0.50) > 0.10 else '#AAAAAA'
                    self._right_cells[ri][ci].config(bg=r_bg, fg=r_fg)

        # 標題更新
        hero_str = ''.join(hero[:2]) if len(hero) >= 2 else '?  ?'
        ahead_count = sum(
            1 for h, eq in hero_eq_map.items()
            if eq > 0.52 and _villain_freq(h, vpip) > 0.05
        )
        total_count = sum(
            1 for h in hero_eq_map
            if _villain_freq(h, vpip) > 0.05
        )
        pct = f'{int(ahead_count/total_count*100)}%' if total_count else '--'
        self._title_lbl.config(
            text=f'Hero: {hero_str}  vs  {self._villain_pos}({int(vpip*100)}%VPIP)  '
                 f'領先對手範圍 {pct}({ahead_count}/{total_count}手牌)'
        )

    def _on_close(self):
        self._win.destroy()


# ── 英雄手牌 vs 所有 169 手牌的翻前勝率 ────────────────────────────────────────

def _precompute_hero_vs_all(hero: List[str]) -> Dict[str, float]:
    """
    快速估算英雄手牌 vs 所有 169 種對手手牌的翻前勝率。
    用預計算的 preflop equity 差值估算（不做 Monte Carlo）。
    """
    try:
        from poker.hand_percentile import _HAND_EQUITY_ORDER
        hero_hand_str = _hero_to_hand_str(hero)
        hero_eq = _eq_vs_random(hero_hand_str) if hero_hand_str else 0.50

        result: Dict[str, float] = {}
        for hand, base_eq in _HAND_EQUITY_ORDER:
            # 粗略估算：若英雄 eq 更高，通常領先；反之落後
            # 更精確：hero_eq vs hand_eq 之差 → hero 在這個對決中的勝率
            diff = hero_eq - base_eq
            # 轉換為 hero 在此對決的近似勝率
            # 兩手牌直接對決：hero_share ≈ 0.5 + k * (hero_eq - opp_eq)
            # 係數 k 由測試值決定（約 0.5-0.7）
            hero_share = 0.50 + 0.60 * diff
            result[hand] = max(0.05, min(0.95, hero_share))
        return result
    except Exception:
        return {}


def _hero_to_hand_str(hero: List[str]) -> str:
    """將 ['Ah','Kd'] 轉為 'AKo' 格式。"""
    if len(hero) < 2:
        return ''
    r1, s1 = hero[0][:-1], hero[0][-1]
    r2, s2 = hero[1][:-1], hero[1][-1]
    ranks = ['A','K','Q','J','T','9','8','7','6','5','4','3','2']
    i1, i2 = (ranks.index(r) if r in ranks else 12 for r in (r1, r2))
    if i1 > i2:
        r1, s1, r2, s2 = r2, s2, r1, s1
    if r1 == r2:
        return r1 + r2
    suited = 's' if s1 == s2 else 'o'
    return r1 + r2 + suited
