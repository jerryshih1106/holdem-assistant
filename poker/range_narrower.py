"""
對手行動範圍縮小器 (Villain Range Narrower)

每當對手採取行動（過牌/跟注/加注/棄牌），根據 GTO 範圍理論
貝葉斯更新對手可能持有的手牌範圍，並輸出：
  - 剩餘範圍百分比（相對起始範圍）
  - 範圍極化分數（強牌 vs 詐唬 vs 中等）
  - 最可能的手牌類別

行動信號（簡化 GTO 理論）：
  CHECK → 移除純強牌（強牌通常下注），保留中等牌/弱牌
  BET/RAISE → 移除純廢牌（廢牌通常棄牌），保留強牌+詐唬
  CALL → 移除超強牌（超強牌通常加注）和純廢牌（廢牌不跟）
         保留中等強度：頂對、draws、中等頂對
  FOLD → 範圍資訊確認：弱牌/邊緣牌居多（對未來手無直接用）

範圍分類（簡化四類）：
  'nuts_strong' → 頂強牌（sets, two-pair, straights, flushes）
  'top_pair'    → 頂對+好踢腳
  'draw'        → 聽牌（flush/straight draws）
  'bluff_weak'  → 詐唬/廢牌（底對、空氣）
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple


@dataclass
class RangeState:
    """對手在某一時間點的範圍估算。"""
    street:             str             # preflop/flop/turn/river
    action:             str             # 最後行動
    # 四類手牌的估算比例（總和=1）
    pct_nuts:           float = 0.15
    pct_top_pair:       float = 0.35
    pct_draw:           float = 0.20
    pct_bluff_weak:     float = 0.30
    # 整體範圍縮窄程度（1.0=開始，越小=越窄）
    range_remaining:    float = 1.0
    polarization_score: float = 0.5    # 0=合併(merged) 1=極化(polarized)
    notes:              str = ''


@dataclass
class NarrowResult:
    villain_pos:        str
    actions_seen:       List[str]       # e.g. ['check','bet','call']
    streets_seen:       List[str]
    current_state:      RangeState
    likely_categories:  List[str]       # 按機率排序的手牌類別
    range_summary:      str
    read_advice:        str             # 給英雄的行動建議
    history:            List[RangeState] = field(default_factory=list)


class VillainRangeTracker:
    """
    追蹤單一對手從翻前到河牌的行動序列，
    即時縮小其可能範圍。

    使用方式：
        tracker = VillainRangeTracker(opener_pos='BTN', starting_range_pct=0.42)
        tracker.add_action('flop', 'check')
        tracker.add_action('turn', 'bet', bet_size_pct=0.6)
        result = tracker.get_result()
    """

    def __init__(
        self,
        opener_pos:           str   = 'BTN',
        starting_range_pct:   float = 0.30,   # 開牌者的翻前範圍（佔全部手牌）
        player_type:          str   = 'TAG',
    ):
        self.opener_pos = opener_pos
        self.player_type = player_type

        # 根據玩家類型初始化起始範圍分布
        self._init_starting_range(starting_range_pct)

        self.actions: List[Tuple[str, str, float]] = []   # (street, action, bet_size)
        self.history: List[RangeState] = []

        initial = RangeState(
            street='preflop', action='open',
            pct_nuts=self._init_nuts,
            pct_top_pair=self._init_tp,
            pct_draw=self._init_draw,
            pct_bluff_weak=self._init_bluff,
            range_remaining=1.0,
        )
        self.history.append(initial)
        self.current = initial

    def _init_starting_range(self, rng_pct: float):
        """根據位置和範圍寬度初始化四類比例。"""
        if rng_pct <= 0.15:   # 緊手（UTG）
            self._init_nuts, self._init_tp = 0.25, 0.40
            self._init_draw, self._init_bluff = 0.20, 0.15
        elif rng_pct <= 0.25:   # 標準（HJ/CO）
            self._init_nuts, self._init_tp = 0.18, 0.37
            self._init_draw, self._init_bluff = 0.22, 0.23
        elif rng_pct <= 0.40:   # 寬（BTN）
            self._init_nuts, self._init_tp = 0.13, 0.32
            self._init_draw, self._init_bluff = 0.25, 0.30
        else:                    # 超寬（SB/fish）
            self._init_nuts, self._init_tp = 0.10, 0.28
            self._init_draw, self._init_bluff = 0.27, 0.35

    def add_action(
        self,
        street:       str,
        action:       str,         # 'check'/'bet'/'call'/'raise'/'fold'
        bet_size_pct: float = 0.5, # 相對底池的注碼（bet/raise 時有效）
    ) -> RangeState:
        """
        登記對手的一個行動，更新範圍估算。
        回傳更新後的 RangeState。
        """
        self.actions.append((street, action, bet_size_pct))
        new_state = self._apply_action(
            self.current, street, action, bet_size_pct
        )
        self.history.append(new_state)
        self.current = new_state
        return new_state

    def _apply_action(
        self,
        prev:         RangeState,
        street:       str,
        action:       str,
        bet_size_pct: float,
    ) -> RangeState:
        n = prev.pct_nuts
        tp = prev.pct_top_pair
        d = prev.pct_draw
        bw = prev.pct_bluff_weak
        remaining = prev.range_remaining

        action = action.lower()

        if action == 'check':
            # 過牌：移除部分純強牌（強牌通常下注），保留中等/弱/draws
            # 翻牌過牌比轉牌/河牌過牌弱得多
            nuts_decay  = 0.55 if street == 'flop' else 0.35
            tp_decay    = 0.90
            draw_decay  = 0.95   # draws 有時過牌等轉牌
            bluff_decay = 1.00
            remaining_decay = 0.85
            note = f'{street}過牌 → 移除大部分強牌，保留中等/draws'
            n  *= nuts_decay
            tp *= tp_decay
            d  *= draw_decay
            bw *= bluff_decay
            remaining *= remaining_decay

        elif action in ('bet', 'raise'):
            # 下注/加注：移除純廢牌，保留強牌+詐唬
            if bet_size_pct >= 0.75:   # 大注
                nuts_stay  = 1.00
                tp_decay   = 0.70   # 大注 top pair 少見
                draw_decay = 0.80   # draws 可能半詐唬
                bluff_decay = 0.45  # 部分詐唬，但不是所有廢牌都詐唬
                remaining_decay = 0.72
                note = f'{street}大注 → 極化：強牌或詐唬，移除中等牌'
            elif bet_size_pct >= 0.4:  # 中等注
                nuts_stay  = 0.95
                tp_decay   = 0.88
                draw_decay = 0.85
                bluff_decay = 0.55
                remaining_decay = 0.78
                note = f'{street}中注 → 半極化：強牌+部分 draws+選擇性詐唬'
            else:                      # 小注
                nuts_stay  = 0.90
                tp_decay   = 0.95
                draw_decay = 0.90
                bluff_decay = 0.70
                remaining_decay = 0.85
                note = f'{street}小注 → 合併：廣泛範圍，中等牌居多'
            n  *= nuts_stay
            tp *= tp_decay
            d  *= draw_decay
            bw *= bluff_decay
            remaining *= remaining_decay

        elif action == 'call':
            # 跟注：移除超強牌（超強通常加注）和純廢牌（廢牌不跟）
            # 保留：頂對、中對、draws、部分中等牌
            nuts_decay = 0.50   # nuts 多半加注，不跟注
            tp_decay   = 0.95
            draw_decay = 0.98
            bluff_decay = 0.40  # 純廢牌不跟注
            remaining_decay = 0.80
            note = f'{street}跟注 → 保留 draws+頂對，移除超強牌和純廢牌'
            n  *= nuts_decay
            tp *= tp_decay
            d  *= draw_decay
            bw *= bluff_decay
            remaining *= remaining_decay

        elif action == 'fold':
            # 棄牌：確認對手範圍確實很弱（但這手牌結束了，作為記錄）
            remaining_decay = 0.30
            note = f'{street}棄牌 → 對手範圍確認為弱/邊緣牌'
            n  *= 0.1
            tp *= 0.3
            d  *= 0.5
            bw *= 0.9
            remaining *= remaining_decay
        else:
            note = f'{street} 未知行動'

        # 重新標準化到總和=1
        total = n + tp + d + bw
        if total > 0:
            n, tp, d, bw = n/total, tp/total, d/total, bw/total

        # 極化分數：(nuts + bluff) / (tp + draw)
        polar_num = n + bw
        polar_den = tp + d
        if polar_den > 0:
            polarization = min(1.0, polar_num / (polar_num + polar_den))
        else:
            polarization = 0.5

        return RangeState(
            street             = street,
            action             = action,
            pct_nuts           = round(n, 3),
            pct_top_pair       = round(tp, 3),
            pct_draw           = round(d, 3),
            pct_bluff_weak     = round(bw, 3),
            range_remaining    = round(prev.range_remaining * remaining_decay
                                       if action in ('check', 'fold')
                                       else prev.range_remaining * remaining_decay, 3),
            polarization_score = round(polarization, 2),
            notes              = note,
        )

    def get_result(self) -> NarrowResult:
        st = self.current
        actions_list = [a[1] for a in self.actions]
        streets_list = [a[0] for a in self.actions]

        # 按比例排序最可能類別
        cats = [
            ('超強牌 (Set/Two-pair/直/同花)',   st.pct_nuts),
            ('頂對+好踢腳',                     st.pct_top_pair),
            ('Draws (同花/順子聽牌)',            st.pct_draw),
            ('詐唬/弱牌',                        st.pct_bluff_weak),
        ]
        cats.sort(key=lambda x: x[1], reverse=True)
        likely = [c[0] for c in cats if c[1] >= 0.10]

        # 範圍摘要
        summary = (
            f'強牌 {st.pct_nuts:.0%}  '
            f'頂對 {st.pct_top_pair:.0%}  '
            f'聽牌 {st.pct_draw:.0%}  '
            f'弱牌 {st.pct_bluff_weak:.0%}  '
            f'[剩餘範圍 {st.range_remaining:.0%}]'
        )

        # 對英雄的建議
        advice = _hero_advice(st, actions_list)

        return NarrowResult(
            villain_pos      = self.opener_pos,
            actions_seen     = actions_list,
            streets_seen     = streets_list,
            current_state    = st,
            likely_categories = likely,
            range_summary    = summary,
            read_advice      = advice,
            history          = self.history,
        )


def _hero_advice(st: RangeState, actions: List[str]) -> str:
    """根據對手範圍估算，給出英雄的行動建議。"""
    dominant_bluff = st.pct_bluff_weak > 0.40
    dominant_value = st.pct_nuts > 0.35
    polarized = st.polarization_score > 0.65

    last_action = actions[-1] if actions else ''

    if last_action in ('bet', 'raise'):
        if dominant_bluff:
            return f'對手範圍弱牌多（{st.pct_bluff_weak:.0%}），考慮跟注或加注'
        elif dominant_value:
            return f'對手範圍強牌多（{st.pct_nuts:.0%}），謹慎跟注/考慮棄牌'
        elif polarized:
            return (f'極化範圍 (極化分={st.polarization_score:.0%})：'
                    f'用 MDF 防守，避免過度棄牌')
        else:
            return f'合併範圍，頂對+聽牌居多，按底池賠率決定'
    elif last_action == 'check':
        if st.pct_nuts < 0.15:
            return '對手過牌後強牌少，可主動下注施壓'
        else:
            return '謹慎：對手可能持有陷阱強牌（過牌-加注威脅）'
    elif last_action == 'call':
        if st.pct_draw > 0.35:
            return f'聽牌多（{st.pct_draw:.0%}），牌面完成時謹慎'
        else:
            return '對手持有中等強度牌，繼續施壓可獲值'
    return '繼續觀察更多行動以縮小範圍'


def quick_narrow(
    actions: List[Tuple[str, str, float]],   # [(street, action, bet_pct), ...]
    opener_pos:  str   = 'BTN',
    range_pct:   float = 0.35,
) -> NarrowResult:
    """
    快速分析：一次傳入所有行動序列。

    Example:
        result = quick_narrow([
            ('flop', 'check', 0),
            ('turn', 'bet',   0.6),
            ('river', 'bet',  0.8),
        ], opener_pos='CO', range_pct=0.27)
    """
    tracker = VillainRangeTracker(opener_pos=opener_pos, starting_range_pct=range_pct)
    for street, action, bet_pct in actions:
        tracker.add_action(street, action, bet_pct)
    return tracker.get_result()
