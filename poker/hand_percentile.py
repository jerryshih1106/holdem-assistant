"""
翻後牌力百分位 vs 對手範圍 (Hand Strength Percentile vs Villain Range)

核心問題：「我的手牌在對手整個範圍中排第幾%？」

  percentile = 0.85 → 我的牌比對手範圍的 85% 都強 → 取值下注
  percentile = 0.50 → 中等 → 視位置和街道決定
  percentile = 0.20 → 弱 → 大多數時候應棄牌

行動門檻（基準值，可依街道/位置調整）：
  > 0.80 → 強取值（value bet / raise）
  0.65-0.80 → 薄取值或過牌-跟注（thin value / check-call）
  0.50-0.65 → 過牌-跟注 or 詐唬接住（bluff catch）
  0.35-0.50 → 中邊緣（check-fold in many spots）
  < 0.35 → 棄牌（give up vs bet）

對手範圍的建立：
  - 基於 VPIP 和行動（過牌/下注/加注）推斷
  - 使用 hand_strength 的 treys 引擎快速評估所有 combo
  - 過濾掉與公牌或英雄手牌衝突的 combo

性能：
  - ~200-400 個 villain combo，每個 O(1) treys 評估
  - 典型執行時間 < 5ms
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from treys import Card, Evaluator

_eval = Evaluator()

RANKS = ['A','K','Q','J','T','9','8','7','6','5','4','3','2']
SUITS = ['h','d','c','s']

# 所有 169 種手牌，按粗略強度排序（用於構建對手範圍）
# 翻前 equity 估算排序（近似值）
_HAND_EQUITY_ORDER: List[Tuple[str, float]] = [
    ('AA', 0.852), ('KK', 0.823), ('QQ', 0.800), ('JJ', 0.775), ('TT', 0.751),
    ('AKs',0.672), ('AQs',0.660), ('AJs',0.651), ('AKo',0.656), ('KQs',0.634),
    ('ATs',0.641), ('AQo',0.645), ('99', 0.722), ('KJs',0.624), ('AJo',0.635),
    ('KTs',0.615), ('QJs',0.616), ('KQo',0.619), ('88', 0.693), ('QTs',0.605),
    ('ATo',0.620), ('JTs',0.600), ('A9s',0.627), ('KJo',0.606), ('77', 0.662),
    ('K9s',0.591), ('QJo',0.601), ('Q9s',0.578), ('A8s',0.618), ('JTo',0.583),
    ('KTo',0.593), ('66', 0.632), ('T9s',0.576), ('A7s',0.608), ('J9s',0.570),
    ('55', 0.600), ('A9o',0.607), ('Q8s',0.563), ('K8s',0.576), ('T8s',0.559),
    ('A5s',0.598), ('J8s',0.553), ('A6s',0.601), ('98s',0.558), ('A4s',0.591),
    ('QTo',0.561), ('K7s',0.562), ('44', 0.570), ('A3s',0.581), ('87s',0.543),
    ('T9o',0.559), ('J9o',0.548), ('A2s',0.573), ('Q9o',0.554), ('K6s',0.549),
    ('K9o',0.571), ('T7s',0.540), ('33', 0.535), ('97s',0.537), ('K5s',0.534),
    ('J7s',0.526), ('22', 0.500), ('86s',0.527), ('K4s',0.516), ('76s',0.527),
    ('Q7s',0.520), ('A8o',0.594), ('T8o',0.535), ('K3s',0.505), ('J8o',0.524),
    ('96s',0.516), ('65s',0.515), ('K2s',0.494), ('75s',0.508), ('Q6s',0.504),
    ('A7o',0.583), ('Q5s',0.493), ('85s',0.495), ('J6s',0.490), ('T6s',0.486),
    ('K8o',0.550), ('Q8o',0.534), ('A5o',0.567), ('54s',0.499), ('64s',0.492),
    ('95s',0.497), ('J5s',0.473), ('Q4s',0.479), ('K7o',0.535), ('T5s',0.467),
    ('A4o',0.558), ('74s',0.479), ('Q3s',0.466), ('J4s',0.459), ('A6o',0.573),
    ('Q2s',0.453), ('K6o',0.519), ('T4s',0.450), ('A3o',0.545), ('J3s',0.443),
    ('84s',0.462), ('53s',0.478), ('Q7o',0.492), ('T3s',0.434), ('K5o',0.500),
    ('J2s',0.429), ('94s',0.449), ('43s',0.458), ('A2o',0.533), ('T2s',0.419),
    ('93s',0.436), ('K4o',0.483), ('63s',0.455), ('92s',0.424), ('87o',0.514),
    ('83s',0.444), ('J7o',0.494), ('73s',0.429), ('82s',0.432), ('K3o',0.466),
    ('Q6o',0.469), ('97o',0.506), ('T7o',0.501), ('72s',0.419), ('K2o',0.450),
    ('62s',0.421), ('Q5o',0.455), ('52s',0.437), ('76o',0.489), ('J6o',0.454),
    ('Q4o',0.436), ('42s',0.421), ('32s',0.426), ('96o',0.476), ('J5o',0.429),
    ('86o',0.487), ('65o',0.470), ('Q3o',0.420), ('T6o',0.443), ('Q2o',0.404),
    ('85o',0.448), ('75o',0.460), ('T5o',0.416), ('J4o',0.408), ('54o',0.449),
    ('95o',0.445), ('J3o',0.390), ('64o',0.439), ('T4o',0.398), ('J2o',0.375),
    ('84o',0.406), ('74o',0.424), ('T3o',0.380), ('53o',0.419), ('T2o',0.360),
    ('94o',0.388), ('43o',0.395), ('63o',0.389), ('93o',0.371), ('92o',0.353),
    ('83o',0.374), ('73o',0.358), ('82o',0.352), ('72o',0.320), ('62o',0.334),
    ('52o',0.360), ('42o',0.344), ('32o',0.336),
]


# ── 範圍構建 ───────────────────────────────────────────────────────────────────

def _build_range_combos(
    range_pct:       float,       # 對手範圍百分比（0.25 = 25%）
    dead_cards:      List[str],   # 已知不可能的牌（英雄手牌 + 公牌）
    street_action:   str = 'any', # 'check'/'bet'/'raise'/'any' 行動縮小範圍
) -> List[Tuple[str, str]]:
    """
    根據 VPIP/range_pct 構建對手的具體手牌 combo 列表。

    回傳 [(card1, card2), ...] 的合法 combo 列表。
    """
    dead_set = set(c.upper() for c in dead_cards)

    # 依 range_pct 選取排名靠前的手牌
    # 完整 169 種手牌，按股票順序，前 range_pct% 的組合
    total_weight = sum(
        (6 if len(h)==2 else 4 if h[2]=='s' else 12) * eq
        for h, eq in _HAND_EQUITY_ORDER
    )
    cutoff_weight = total_weight * range_pct

    # 若 street_action 暗示窄化範圍
    action_mult = {
        'raise': 0.40,   # 加注 → 更強的範圍
        'bet':   0.55,   # 下注 → 中上範圍
        'call':  0.80,   # 跟注 → 寬範圍
        'check': 0.90,   # 過牌 → 寬範圍（但排除太強的牌）
        'any':   1.00,
    }.get(street_action, 1.0)
    cutoff_weight *= action_mult

    combos: List[Tuple[str, str]] = []
    accum  = 0.0

    for hand, eq in _HAND_EQUITY_ORDER:
        if accum >= cutoff_weight:
            break
        weight = (6 if len(hand)==2 else 4 if hand[2]=='s' else 12) * eq
        # 展開此手牌的所有具體 combo
        for c1, c2 in _hand_combos(hand):
            if c1.upper() in dead_set or c2.upper() in dead_set:
                continue
            combos.append((c1, c2))
        accum += weight

    return combos


def _hand_combos(hand: str) -> List[Tuple[str, str]]:
    """展開手牌符號為所有 2 張牌的 combo。"""
    if len(hand) == 2:    # pair
        r  = hand[0]
        cs = [r + s for s in SUITS]
        return [(cs[i], cs[j]) for i in range(4) for j in range(i+1, 4)]

    r1, r2, stype = hand[0], hand[1], hand[2]
    c1s = [r1 + s for s in SUITS]
    c2s = [r2 + s for s in SUITS]
    if stype == 's':
        return [(c1s[i], c2s[i]) for i in range(4)]
    else:
        return [(c1s[i], c2s[j]) for i in range(4) for j in range(4) if i != j]


# ── 主函數 ────────────────────────────────────────────────────────────────────

@dataclass
class HandPercentileResult:
    # 輸入
    hole_cards:       List[str]
    community:        List[str]
    villain_range_pct: float

    # 核心結果
    percentile:       float    # hero beats X% of villain range (0-1)
    vs_range_equity:  float    # win rate vs villain range (ties = 0.5)
    villain_combos:   int      # 有效 villain combo 數量

    # 行動建議
    action_advice:    str      # 'value'/'thin_value'/'check_call'/'bluff_catch'/'fold'
    action_zh:        str      # 中文行動標籤
    bucket:           str      # 'nuts+'/'strong'/'medium'/'marginal'/'weak'
    bucket_zh:        str      # 中文分桶標籤
    bet_size_hint:    float    # 建議注碼（0=不下注）

    # 牌型
    hero_rank:        int      # treys hand rank (1=best)
    reasoning:        str
    tips:             List[str] = field(default_factory=list)


# 行動映射
_ACTION_MAP = {
    'value':       ('強取值', 0.75),
    'thin_value':  ('薄取值', 0.50),
    'check_call':  ('過牌跟注', 0.0),
    'bluff_catch': ('詐唬接住', 0.0),
    'fold':        ('棄牌', 0.0),
}


def calc_hand_percentile(
    hole_cards:          List[str],
    community:           List[str],
    villain_range_pct:   float = 0.30,    # 對手 VPIP 估算
    villain_action:      str   = 'any',   # 對手本街行動縮小範圍
    position:            str   = 'ip',    # 'ip'/'oop'
    pot_bb:              float = 10.0,
    is_river:            bool  = False,
) -> Optional[HandPercentileResult]:
    """
    計算英雄手牌在對手範圍中的強度百分位。

    Args:
        hole_cards:          英雄手牌，如 ['Ah', 'Kd']
        community:           公牌，如 ['Qh', 'Jd', 'Ts']
        villain_range_pct:   對手估算範圍比例（如 VPIP = 0.25）
        villain_action:      對手本街行動（縮小範圍）
        position:            英雄位置
        pot_bb:              目前底池
        is_river:            是否河牌（影響行動門檻）

    Returns:
        HandPercentileResult 或 None（牌數不足）
    """
    if len(hole_cards) < 2 or len(community) < 3:
        return None

    # 清理牌面輸入
    hole = [c.strip() for c in hole_cards if c and len(c) >= 2]
    board = [c.strip() for c in community if c and len(c) >= 2]
    if len(hole) < 2 or len(board) < 3:
        return None

    # 評估英雄手牌
    try:
        h_cards  = [Card.new(c) for c in hole]
        b_cards  = [Card.new(c) for c in board]
        hero_rank = _eval.evaluate(b_cards, h_cards)
    except Exception:
        return None

    # 構建對手 combo 列表
    dead = hole + board
    villain_combos = _build_range_combos(villain_range_pct, dead, villain_action)

    if not villain_combos:
        return None

    # 對手每個 combo 的評估
    beats = 0.0
    total = 0
    for c1, c2 in villain_combos:
        try:
            v_cards  = [Card.new(c1), Card.new(c2)]
            v_rank   = _eval.evaluate(b_cards, v_cards)
            total   += 1
            if hero_rank < v_rank:    # 小 rank = 更強
                beats += 1.0
            elif hero_rank == v_rank:
                beats += 0.5          # 平手算一半
        except Exception:
            continue

    if total == 0:
        return None

    pct = beats / total

    # ── 行動建議 ──────────────────────────────────────────────────────────────
    # 河牌門檻略低（更多薄取值）；OOP 門檻稍高（更保守）
    river_adj  = +0.05 if is_river else 0.0
    oop_adj    = +0.05 if position == 'oop' else 0.0
    value_line = 0.75 + oop_adj - river_adj   # value bet 門檻
    thin_line  = 0.60 + oop_adj - river_adj   # thin value 門檻
    cc_line    = 0.45                          # check-call / bluff-catch 門檻

    if pct >= value_line:
        action, bet_hint = 'value',       0.75
        bucket, bucket_zh = 'nuts+',      '超強牌/堅果'
    elif pct >= thin_line:
        action, bet_hint = 'thin_value',  0.50
        bucket, bucket_zh = 'strong',     '強牌'
    elif pct >= cc_line:
        action, bet_hint = 'check_call',  0.0
        bucket, bucket_zh = 'medium',     '中等牌'
    elif pct >= 0.30:
        action, bet_hint = 'bluff_catch', 0.0
        bucket, bucket_zh = 'marginal',   '邊緣牌'
    else:
        action, bet_hint = 'fold',        0.0
        bucket, bucket_zh = 'weak',       '弱牌'

    action_zh, _ = _ACTION_MAP[action]

    # ── 解釋 ──────────────────────────────────────────────────────────────────
    reasons = [
        f'打敗對手 {villain_combos.__len__()} 個 combo 中的 {pct:.0%}',
        f'對手範圍 {villain_range_pct:.0%} ({villain_action} 後)',
        f'百分位 {pct:.0%} → {bucket_zh} → {action_zh}',
    ]

    tips = [
        f'若對手 bet，對應 alpha 門檻約 {max(0.25, 0.5 - pct * 0.3):.0%}',
    ]
    if pct >= 0.80:
        tips.append('超強：積極下注/加注，不要放棄 EV')
    elif pct >= 0.60:
        tips.append(f'強牌：考慮 {int(bet_hint*100)}% 底池取值，河牌可能薄取值')
    elif pct >= 0.45:
        tips.append('中等：以過牌跟注為主，不要對大注轉化為折疊')
    else:
        tips.append('邊緣/弱牌：除非對手詐唬率高，否則考慮棄牌')

    return HandPercentileResult(
        hole_cards        = hole,
        community         = board,
        villain_range_pct = villain_range_pct,
        percentile        = round(pct, 3),
        vs_range_equity   = round(pct, 3),
        villain_combos    = total,
        action_advice     = action,
        action_zh         = action_zh,
        bucket            = bucket,
        bucket_zh         = bucket_zh,
        bet_size_hint     = bet_hint,
        hero_rank         = hero_rank,
        reasoning         = '；'.join(reasons),
        tips              = tips,
    )


def percentile_summary(r: HandPercentileResult) -> str:
    """單行摘要，用於 overlay 顯示。"""
    return (f'對手範圍百分位 {r.percentile:.0%}（{r.bucket_zh}）  '
            f'建議：{r.action_zh}'
            + (f'  {int(r.bet_size_hint*100)}%底池' if r.bet_size_hint > 0 else ''))


def quick_percentile(
    hole:           List[str],
    community:      List[str],
    vpip:           float = 0.30,
    villain_action: str   = 'any',
) -> str:
    """一行快速查詢。"""
    r = calc_hand_percentile(hole, community, vpip, villain_action)
    if r is None:
        return '牌數不足（需要至少3張公牌）'
    return percentile_summary(r)
