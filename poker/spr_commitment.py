"""
SPR（籌碼底池比）承諾決策顧問 (Stack-to-Pot Ratio Commitment Advisor)

SPR = 有效籌碼 / 底池

SPR 決定了英雄應該在什麼手牌強度下全押：

SPR < 2  （超低）：底對/任何頂對 → 自動全押
SPR 2-4  （低）：頂對良踢 + → 全押，頂對弱踢考慮
SPR 4-7  （中）：只有兩對 + 才全押，頂對控池
SPR 7-13 （中高）：順子/同花 + 才全押，頂對過牌跟注
SPR > 13 （高）：只有超強牌（同花/順子/葫蘆+）才全押

EV 承諾模型（simplified）：
  EV_commit   = equity × (stack + pot) - stack × (1 - eq_to_make_money)
  EV_no_commit = eq_no_commit × pot

牌型分類：
  'overpair_strong'    : AA/KK  (可信頂對)
  'overpair_medium'    : QQ-JJ  (中高對)
  'tpgk'              : TPGK（頂對良踢）
  'tpwk'              : TPWK（頂對弱踢）
  'second_pair'        : 次對
  'two_pair'           : 兩對
  'set'                : 三條/套裝
  'straight'           : 順子
  'flush'              : 同花
  'full_house_plus'    : 葫蘆+
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple


# ── SPR zones ─────────────────────────────────────────────────────────────────

def spr_zone(spr: float) -> Tuple[str, str]:
    """Return (zone_key, zone_zh)."""
    if spr < 2:
        return 'ultra_low',  '超低 SPR (<2)'
    if spr < 4:
        return 'low',        '低 SPR (2-4)'
    if spr < 7:
        return 'medium',     '中 SPR (4-7)'
    if spr < 13:
        return 'medium_high','中高 SPR (7-13)'
    return 'high',           '高 SPR (>13)'


# ── Hand strength → equity estimate (vs villain's calling range) ──────────────

_HAND_EQUITY: dict = {
    'overpair_strong': 0.80,
    'overpair_medium': 0.74,
    'tpgk':            0.68,
    'tpwk':            0.60,
    'second_pair':     0.52,
    'two_pair':        0.75,
    'set':             0.85,
    'straight':        0.82,
    'flush':           0.83,
    'full_house_plus': 0.93,
    'air':             0.15,
}

_HAND_ZH: dict = {
    'overpair_strong': 'AA/KK（超強頂對）',
    'overpair_medium': 'QQ-JJ（強頂對）',
    'tpgk':            '頂對良踢',
    'tpwk':            '頂對弱踢',
    'second_pair':     '次對',
    'two_pair':        '兩對',
    'set':             '三條',
    'straight':        '順子',
    'flush':           '同花',
    'full_house_plus': '葫蘆或更強',
    'air':             '空氣/詐唬',
}


# ── Commitment threshold by SPR zone ──────────────────────────────────────────

# Maps zone_key → minimum hand strength required to commit stack
_COMMIT_THRESHOLD: dict = {
    'ultra_low':   'second_pair',      # any pair good enough
    'low':         'tpgk',             # TPGK+
    'medium':      'two_pair',         # two pair+
    'medium_high': 'set',              # set+ (85% equity, make full houses)
    'high':        'flush',            # flush+
}

# Ordered from weakest to strongest for comparison
_STRENGTH_ORDER = [
    'air', 'second_pair', 'tpwk', 'tpgk',
    'overpair_medium', 'overpair_strong',
    'two_pair', 'set', 'straight', 'flush', 'full_house_plus',
]


def _hand_rank(hand_type: str) -> int:
    try:
        return _STRENGTH_ORDER.index(hand_type)
    except ValueError:
        return 0


def _should_commit(hand_type: str, zone_key: str) -> bool:
    threshold = _COMMIT_THRESHOLD.get(zone_key, 'flush')
    return _hand_rank(hand_type) >= _hand_rank(threshold)


# ── EV model ──────────────────────────────────────────────────────────────────

def _ev_commit(equity: float, pot_bb: float, stack_bb: float) -> float:
    """EV of committing all chips (calling or shoving)."""
    total_pot = pot_bb + 2 * stack_bb     # after getting it all in
    return round(equity * total_pot - stack_bb, 2)


def _ev_no_commit(equity: float, pot_bb: float) -> float:
    """Simplified EV of not committing (pot control, take the pot fraction)."""
    return round(equity * pot_bb * 0.65, 2)   # 65% pot expected to win by showdown


# ── Action recommendation ─────────────────────────────────────────────────────

def _recommend_action(
    hand_type:   str,
    zone_key:    str,
    is_ip:       bool,
    villain_af:  float,
    pot_bb:      float,
    stack_bb:    float,
) -> Tuple[str, str, str]:
    """
    Returns (action_key, action_zh, sizing_hint).
    action_key: 'stack_off' / 'build_pot' / 'pot_control' / 'give_up'
    """
    commit = _should_commit(hand_type, zone_key)
    equity = _HAND_EQUITY.get(hand_type, 0.50)
    ev_com = _ev_commit(equity, pot_bb, stack_bb)
    ev_no  = _ev_no_commit(equity, pot_bb)

    if commit and ev_com > 0:
        if zone_key in ('ultra_low', 'low'):
            return 'stack_off', '全押/跟注全押', '100% 有效籌碼'
        else:
            # Build pot towards stack-off
            bet_pct = min(0.75, max(0.50, stack_bb / (pot_bb * 3)))
            return 'build_pot', '建築底池（下注 → 全押）', f'{bet_pct:.0%} pot'
    elif hand_type in ('tpwk', 'second_pair', 'air') or not commit:
        if villain_af > 2.5 and is_ip:
            return 'pot_control', '控制底池（過牌跟注）', '0（過牌）'
        elif villain_af < 1.2:
            return 'pot_control', '控制底池（薄下注）', '33% pot'
        return 'pot_control', '控制底池', '0（過牌）'
    return 'give_up', '放棄/棄牌', '0'


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class SprCommitmentResult:
    # SPR context
    spr:            float
    zone_key:       str
    zone_zh:        str
    effective_stack: float
    pot_bb:         float

    # Hand info
    hand_type:      str
    hand_zh:        str
    hand_equity:    float

    # Decision
    should_commit:  bool
    action_key:     str
    action_zh:      str
    sizing_hint:    str
    commit_threshold_zh: str   # minimum hand to commit at this SPR

    # EV
    ev_commit:      float
    ev_no_commit:   float

    # Position
    is_ip:          bool

    reasoning:      str
    tips:           List[str]
    summary_zh:     str


def analyze_spr_commitment(
    pot_bb:       float,
    stack_bb:     float,
    hand_type:    str   = 'tpgk',
    is_ip:        bool  = True,
    villain_af:   float = -1.0,
    villain_vpip: float = 0.28,
    villain_hands: int  = 0,
) -> SprCommitmentResult:
    """
    Advise on SPR-based commitment decisions.

    Args:
        pot_bb:       Pot size in BB
        stack_bb:     Effective stack in BB (min of hero/villain remaining)
        hand_type:    Hero's hand category (see module docstring)
        is_ip:        True if hero is in position
        villain_af:   Aggression Factor (-1=unknown)
        villain_vpip: VPIP from HUD
        villain_hands: HUD sample size
    """
    tips: List[str] = []

    spr = round(stack_bb / max(0.5, pot_bb), 2)
    zone_key, zone_zh = spr_zone(spr)

    hand_zh    = _HAND_ZH.get(hand_type, hand_type)
    hand_equity = _HAND_EQUITY.get(hand_type, 0.55)
    commit      = _should_commit(hand_type, zone_key)
    threshold   = _COMMIT_THRESHOLD.get(zone_key, 'flush')
    threshold_zh = _HAND_ZH.get(threshold, threshold)

    eff_af = villain_af if villain_af > 0 else max(0.5, 2.0 - villain_vpip * 3.0)

    action_key, action_zh, sizing_hint = _recommend_action(
        hand_type, zone_key, is_ip, eff_af, pot_bb, stack_bb
    )

    ev_com = _ev_commit(hand_equity, pot_bb, stack_bb)
    ev_no  = _ev_no_commit(hand_equity, pot_bb)

    # Tips
    if spr < 2:
        tips.append(f'SPR={spr:.1f}（超低）：底對或更好都承諾，不要尋找理由棄牌')
    elif spr < 4:
        tips.append(f'SPR={spr:.1f}（低）：TPGK+ 自動承諾，考慮翻前縮短底池深度')
    elif spr >= 13:
        tips.append(f'SPR={spr:.1f}（高）：只有堅果線才全押，其餘控池')
    if not commit and hand_equity >= 0.60:
        tips.append(f'{hand_zh} vs SPR={spr:.1f}：此SPR下建議控池，非全押線')
    if commit and ev_com < 0:
        tips.append(f'全押EV={ev_com:+.1f}BB（負值），重新評估對手範圍')
    if villain_hands < 15:
        tips.append(f'HUD樣本少（{villain_hands}手），預設對手類型')
    if not is_ip and zone_key in ('medium', 'medium_high'):
        tips.append('OOP中等SPR：傾向過牌而非主動建築底池')

    pos_str  = 'IP（有位置）' if is_ip else 'OOP（無位置）'
    reasoning = (
        f'SPR={spr:.1f}（{zone_zh}），{pos_str}，'
        f'手牌={hand_zh}（勝率估計{hand_equity:.0%}），'
        f'承諾門檻={threshold_zh}。'
        f'EV全押={ev_com:+.1f}BB vs EV控池={ev_no:+.1f}BB → {action_zh}'
    )

    commit_str = '全押' if commit else '控池'
    summary_zh = f'[SPR {spr:.1f}] {hand_zh} → {action_zh} ({commit_str})'[:85]

    return SprCommitmentResult(
        spr              = spr,
        zone_key         = zone_key,
        zone_zh          = zone_zh,
        effective_stack  = stack_bb,
        pot_bb           = pot_bb,
        hand_type        = hand_type,
        hand_zh          = hand_zh,
        hand_equity      = hand_equity,
        should_commit    = commit,
        action_key       = action_key,
        action_zh        = action_zh,
        sizing_hint      = sizing_hint,
        commit_threshold_zh = threshold_zh,
        ev_commit        = ev_com,
        ev_no_commit     = ev_no,
        is_ip            = is_ip,
        reasoning        = reasoning,
        tips             = tips,
        summary_zh       = summary_zh,
    )


def spr_commitment_summary(r: SprCommitmentResult) -> str:
    """Single-line overlay summary (<=85 chars)."""
    return r.summary_zh[:85]
