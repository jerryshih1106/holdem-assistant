"""
走牌模擬器 (Runout Equity Simulator)

分析翻牌/轉牌後每張可能的來牌對英雄勝率的影響。

核心問題：
  「有幾成的後續牌對我不利？我現在需要下注保護嗎？」
  「哪些來牌讓我的頂對變成劣勢？」

輸出分類：
  safe_cards  : 來牌後勝率上升 (delta >= +3%)   — 可以慢打/check-call
  scare_cards : 來牌後勝率下降 (delta <= -5%)   — 需要現在下注保護
  neutral     : 勝率變化在 -5% ~ +3% 之間

決策建議：
  pct_scare >= 40%  → 必須下注保護（太多有害牌面）
  pct_scare >= 25%  → 建議下注保護
  pct_safe  >= 70%  → 可以慢打（大多數牌面對我有利）
  equity 已很高     → 注意被反超的牌（nut-change cards）

注意：本模組使用背景執行緒計算，設計為非同步使用。
"""

import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from poker.equity import calculate_equity


# 所有 52 張牌的標準符號
_RANKS  = 'AKQJT98765432'
_SUITS  = 'shdc'
_ALL_CARDS = [r + s for r in _RANKS for s in _SUITS]


@dataclass
class RunoutResult:
    # 基準勝率（當前牌面）
    base_equity:    float

    # 各可能來牌的勝率
    card_equities:  Dict[str, float]   # e.g. {"Ah": 0.75, "2c": 0.43, ...}

    # 分類
    safe_cards:     List[Tuple[str, float, float]]   # (card, equity, delta) delta > 0
    scare_cards:    List[Tuple[str, float, float]]   # (card, equity, delta) delta < 0
    neutral_cards:  List[Tuple[str, float, float]]

    # 統計
    n_possible:     int     # 可能的來牌總數
    pct_safe:       float   # 有利來牌比例（0-1）
    pct_scare:      float   # 有害來牌比例（0-1）
    avg_safe_delta: float   # 有利牌平均勝率提升
    avg_scare_delta: float  # 有害牌平均勝率損失

    # 決策
    should_protect:  bool    # 是否應該立即下注保護
    can_slow_play:   bool    # 是否可以慢打設陷阱
    protection_urgency: str  # 'high'/'medium'/'low'/'none'

    # 顯示用
    top_safe:        List[str]   # 最好的 3 張來牌
    top_scare:       List[str]   # 最差的 3 張來牌
    summary:         str
    tips:            List[str] = field(default_factory=list)


def _normalize_card(card: str) -> str:
    """將 treys 格式（Ah/2c）統一化。"""
    return card.strip()


def simulate_runouts(
    hole_cards:        List[str],
    community:         List[str],
    villain_range_pct: float = 0.30,   # 對手範圍（小數，如 0.30=30%）
    n_per_card:        int   = 80,     # 每張來牌的 Monte Carlo 次數
    safe_threshold:    float = 0.03,   # 勝率提升 >= 3% 算 safe
    scare_threshold:   float = -0.05,  # 勝率下降 >= 5% 算 scare
) -> RunoutResult:
    """
    計算每張可能來牌後的英雄勝率，分類 safe/scare/neutral。

    Args:
        hole_cards:        英雄手牌（2張）
        community:         當前公牌（3張=翻牌, 4張=轉牌）
        villain_range_pct: 對手範圍比例（小數，用於 Monte Carlo）
        n_per_card:        每張來牌的模擬次數（建議 80-150）
        safe_threshold:    勝率提升多少算 safe
        scare_threshold:   勝率下降多少算 scare（負值）

    Returns:
        RunoutResult
    """
    dead = set(hole_cards) | set(community)
    candidates = [c for c in _ALL_CARDS if c not in dead]

    # 基準勝率（當前牌面）
    base_win, base_tie, _ = calculate_equity(
        hole_cards, community,
        num_opponents=1,
        iterations=500,
    )
    base_equity = base_win + base_tie * 0.5

    # 各來牌勝率
    card_equities: Dict[str, float] = {}
    for card in candidates:
        new_comm = community + [card]
        try:
            w, t, _ = calculate_equity(
                hole_cards, new_comm,
                num_opponents=1,
                iterations=n_per_card,
            )
            card_equities[card] = round(w + t * 0.5, 4)
        except Exception:
            card_equities[card] = base_equity

    # 分類並計算 delta
    safe_cards    = []
    scare_cards   = []
    neutral_cards = []

    for card, eq in card_equities.items():
        delta = eq - base_equity
        entry = (card, eq, round(delta, 4))
        if delta >= safe_threshold:
            safe_cards.append(entry)
        elif delta <= scare_threshold:
            scare_cards.append(entry)
        else:
            neutral_cards.append(entry)

    # 排序：safe 由高到低，scare 由低到高（最差在前）
    safe_cards.sort(key=lambda x: -x[2])
    scare_cards.sort(key=lambda x: x[2])
    neutral_cards.sort(key=lambda x: -x[2])

    n = len(candidates)
    pct_safe  = len(safe_cards)  / n if n else 0
    pct_scare = len(scare_cards) / n if n else 0

    avg_safe_delta  = (sum(d for _, _, d in safe_cards)  / len(safe_cards))  if safe_cards  else 0.0
    avg_scare_delta = (sum(d for _, _, d in scare_cards) / len(scare_cards)) if scare_cards else 0.0

    # 決策邏輯
    should_protect = pct_scare >= 0.25
    can_slow_play  = pct_safe >= 0.70 and base_equity >= 0.70

    if pct_scare >= 0.40:
        urgency = 'high'
    elif pct_scare >= 0.25:
        urgency = 'medium'
    elif pct_scare >= 0.12:
        urgency = 'low'
    else:
        urgency = 'none'

    # 頂部 safe/scare（顯示用）
    def _card_zh(card_equity_delta):
        c, eq, d = card_equity_delta
        sign = '+' if d >= 0 else ''
        return f'{c}({sign}{int(d*100)}%)'

    top_safe  = [_card_zh(x) for x in safe_cards[:3]]
    top_scare = [_card_zh(x) for x in scare_cards[:3]]

    # 摘要
    urgency_zh = {'high': '必須保護', 'medium': '建議下注', 'low': '可下注', 'none': '可慢打'}
    summary = (
        f'有利牌{int(pct_safe*100)}% / 有害牌{int(pct_scare*100)}%  '
        f'→ {urgency_zh.get(urgency, "")}  '
        f'最差:{",".join(top_scare[:2]) or "無"}'
    )

    tips = []
    if urgency == 'high':
        tips.append(f'{int(pct_scare*100)}% 的牌面對我有害，翻牌必須立刻下注保護')
    if can_slow_play:
        tips.append(f'勝率高({int(base_equity*100)}%)且多數來牌對我有利，可以考慮慢打')
    if scare_cards and scare_cards[0][2] <= -0.20:
        worst = scare_cards[0][0]
        tips.append(f'最危險來牌：{worst}（勝率下降 {abs(int(scare_cards[0][2]*100))}%）')

    return RunoutResult(
        base_equity      = round(base_equity, 4),
        card_equities    = card_equities,
        safe_cards       = safe_cards,
        scare_cards      = scare_cards,
        neutral_cards    = neutral_cards,
        n_possible       = n,
        pct_safe         = round(pct_safe, 3),
        pct_scare        = round(pct_scare, 3),
        avg_safe_delta   = round(avg_safe_delta, 4),
        avg_scare_delta  = round(avg_scare_delta, 4),
        should_protect   = should_protect,
        can_slow_play    = can_slow_play,
        protection_urgency = urgency,
        top_safe         = top_safe,
        top_scare        = top_scare,
        summary          = summary,
        tips             = tips,
    )


def runout_summary(r: RunoutResult) -> str:
    """單行摘要，用於 overlay 顯示。"""
    urgency_map = {
        'high':   '必須保護',
        'medium': '建議下注',
        'low':    '可下注',
        'none':   '可慢打',
    }
    action = urgency_map.get(r.protection_urgency, '')
    scare_str = ','.join(r.top_scare[:2]) if r.top_scare else '無'
    return (f'走牌: 有利{int(r.pct_safe*100)}% 有害{int(r.pct_scare*100)}%  '
            f'{action}  危險牌:{scare_str}')


# ── 非同步包裝器 ────────────────────────────────────────────────────────────────

class AsyncRunoutSimulator:
    """
    非同步走牌模擬器，避免阻塞 UI 主執行緒。

    使用方式：
        sim = AsyncRunoutSimulator()
        sim.start(hole, community, callback=lambda r: overlay.update_runout(r.summary))
        # callback 在計算完成後被呼叫（在背景執行緒中）
    """

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._last_key: Optional[tuple] = None

    def start(
        self,
        hole_cards:   List[str],
        community:    List[str],
        callback,
        villain_range_pct: float = 0.30,
        n_per_card:   int   = 80,
    ):
        """啟動背景計算。若牌面未改變則跳過重算。"""
        key = (tuple(sorted(hole_cards)), tuple(community))
        if key == self._last_key:
            return  # 牌面未變，不重算

        self._last_key = key

        def _run():
            try:
                result = simulate_runouts(
                    hole_cards, community,
                    villain_range_pct=villain_range_pct,
                    n_per_card=n_per_card,
                )
                callback(result)
            except Exception:
                pass

        if self._thread and self._thread.is_alive():
            return  # 上一次計算未完成，跳過

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
