"""
轉牌桶注/放棄決策顧問 (Turn Barrel / Give-Up Decision)

場景：英雄翻牌 C-bet，對手跟注 → 現在到了轉牌，應該繼續下注（桶注）還是放棄？

這是撲克中最常見的多街決策之一，也是漏洞最大的地方：
  - 過多桶注：浪費籌碼在劣勢牌面，對手繼續跟注或加注
  - 過少桶注：讓對手用免費摸牌改善手牌，或放棄過多 fold equity

決策框架：

一、轉牌牌質對英雄範圍的影響：
  極佳  → 空白低牌（<8），翻前加注者的範圍未被影響，對手聽牌未成
  良好  → 高牌（A/K/Q）且英雄翻前從 EP 加注（代表有 AK/AQ/AA/KK）
  中立  → 普通中牌，不特別有利或不利
  不好  → 同花完成（4張同花色在轉牌）或順子完成
  極差  → 轉牌配對翻牌的大牌（對手可能有暗三條/兩對）

二、英雄手牌類型（從手牌百分位估算）：
  ≥ 0.82 = 超強牌（暗三條/兩對/強超對） → 幾乎全桶注
  0.65-0.81 = 強牌（頂對好踢腳/超對） → 多數情況桶注
  0.50-0.64 = 中等牌（頂對中踢腳/第二對） → 只在好轉牌桶注
  0.35-0.49 = 弱牌（空氣/未成聽牌） → 只在極佳轉牌桶注（代表某種接近成功的詐唬）
  < 0.35 = 純空氣 → 只在極少情況桶注（范圍代表）

三、對手跟注翻牌的範圍分析：
  對手跟注 C-bet 通常有：中等對子、聽牌（同花/順子）、弱頂對
  在空白轉牌上：他們的許多聽牌未完成 → 英雄桶注可獲得 fold equity
  在完成轉牌上：他們的聽牌完成 → 英雄的桶注頻率應大幅降低

桶注頻率計算：
  base_freq = 由手牌強度決定（0.10 到 0.85）
  card_adj  = 由轉牌牌質決定（-0.30 到 +0.20）
  villain_adj = 由對手 AF/WTSD 決定（±0.08）
  final = clamp(base + card_adj + villain_adj, 0.05, 0.95)

桶注尺寸：
  IP + 空白牌面：60-70% 底池（充分但不過大）
  IP + 中立牌面：50-60% 底池
  OOP：33-50% 底池（小注保護，讓對手做出錯誤）
  有強牌：可大注（70-80%）
  詐唬：65-75%（需要足夠的 fold equity）
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


# ── Turn card quality assessment ──────────────────────────────────────────────

def assess_turn_card_quality(
    completes_flush:     bool = False,
    completes_straight:  bool = False,
    pairs_board:         bool = False,
    is_blank:            bool = True,   # low card (2-7) that doesn't help draws
    is_high_card:        bool = False,  # A/K/Q
    hero_opened_ep:      bool = False,  # True if hero opened from UTG/HJ
) -> str:
    """
    Classify how good the turn card is for the pre-flop aggressor.
    Returns: 'excellent'/'good'/'neutral'/'bad'/'very_bad'
    """
    if completes_flush or completes_straight:
        return 'very_bad'   # villain's draws complete → never barrel as bluff
    if pairs_board:
        return 'bad'        # villain's two-pair/trips possible
    if is_blank:
        return 'excellent'  # draws miss, hero's range advantage maintained
    if is_high_card:
        if hero_opened_ep:
            return 'good'   # EP range has many A/K combos → card is in hero's range
        return 'neutral'    # high card can help villain's AK/KQ too
    return 'neutral'


# ── Hand type classification ───────────────────────────────────────────────────

def _hand_type(hero_pct: float) -> str:
    if hero_pct >= 0.82:   return 'strong'    # two pair / set / strong overpair
    if hero_pct >= 0.65:   return 'solid'     # top pair GK / overpair
    if hero_pct >= 0.50:   return 'medium'    # TP medium kicker / second pair
    if hero_pct >= 0.35:   return 'weak'      # weak pair / strong draw
    return 'air'                              # pure bluff / missed draw


_HAND_TYPE_ZH = {
    'strong': '強牌（兩對/暗三條/超對）',
    'solid':  '穩牌（頂對好踢腳/超對）',
    'medium': '中牌（頂對中踢腳/第二對）',
    'weak':   '弱牌（弱對/強聽牌）',
    'air':    '空氣（錯過/詐唬）',
}

_CARD_QUALITY_ZH = {
    'excellent': '極佳（空白牌，聽牌未成）',
    'good':      '良好（高牌，在英雄範圍內）',
    'neutral':   '中立（普通牌）',
    'bad':       '不好（配對牌面）',
    'very_bad':  '極差（完成了同花/順子）',
}


# ── Barrel frequency ───────────────────────────────────────────────────────────

def _barrel_frequency(
    hand_type: str,
    card_quality: str,
    villain_af: float,
    villain_wtsd: float,
    is_ip: bool,
) -> float:
    """Calculate recommended barrel frequency."""
    base = {'strong': 0.82, 'solid': 0.65, 'medium': 0.40, 'weak': 0.25, 'air': 0.10}
    freq = base.get(hand_type, 0.40)

    quality_adj = {
        'excellent': +0.20,
        'good':      +0.10,
        'neutral':    0.00,
        'bad':       -0.18,
        'very_bad':  -0.32,
    }
    freq += quality_adj.get(card_quality, 0.0)

    # High AF villain: raises more → barrel less (avoid being blown off)
    if villain_af > 2.5:
        freq -= 0.08
    elif villain_af > 0 and villain_af < 0.8:
        freq -= 0.05   # passive villain: barrel less (gives up pot, doesn't fold)

    # High WTSD villain: calls down → only barrel strong hands
    if villain_wtsd > 0.40:
        freq -= 0.05   # tighten bluff barrels vs calling station
    elif villain_wtsd > 0 and villain_wtsd < 0.22:
        freq += 0.05   # villain folds easily → bluff more often

    # OOP adjustment: barrel less (harder to barrel effectively OOP)
    if not is_ip:
        freq -= 0.08

    return round(max(0.05, min(0.95, freq)), 3)


# ── Barrel sizing ─────────────────────────────────────────────────────────────

def _barrel_size(
    hand_type: str, card_quality: str, is_ip: bool, pot_bb: float
) -> float:
    """Return recommended barrel size as fraction of pot."""
    if not is_ip:
        # OOP: smaller bet to protect and not over-commit
        return 0.40 if card_quality in ('excellent', 'good') else 0.33
    # IP
    if hand_type in ('strong',):
        return 0.70   # build pot with strong hands
    if card_quality == 'very_bad':
        return 0.60   # if still barreling on scare card, larger to represent
    if card_quality in ('excellent', 'good'):
        return 0.60
    return 0.50


# ── EV estimates ──────────────────────────────────────────────────────────────

def _ev_barrel(
    hero_pct: float, villain_af: float, villain_wtsd: float,
    pot_bb: float, bet_pct: float
) -> float:
    """Simplified EV of barreling the turn."""
    eff_wtsd = villain_wtsd if villain_wtsd > 0 else 0.30
    bet = pot_bb * bet_pct
    # Fold equity: villain has draws (30-40% of range) that miss blank turns
    fold_equity = max(0.10, min(0.60, 0.40 - (villain_af - 1.5) * 0.05 if villain_af > 0 else 0.35))
    # When villain calls: hero wins based on equity
    eq_called = max(0.10, hero_pct - 0.08)   # villain calling range is stronger than average
    ev_fold = pot_bb
    ev_call = eq_called * (pot_bb + 2 * bet) - bet
    return round(fold_equity * ev_fold + (1 - fold_equity) * ev_call, 2)


def _ev_give_up(hero_pct: float, pot_bb: float) -> float:
    """EV of checking turn and giving up (checking back)."""
    # Hero checks, villain might bet. Hero's equity in checked-down pot.
    return round(hero_pct * pot_bb * 0.75, 2)   # partial pot recovery at showdown


@dataclass
class TurnBarrelResult:
    # Decision
    should_barrel:     bool
    barrel_frequency:  float    # recommended frequency for this hand type + card combo
    action:            str      # 'barrel'/'give_up'/'check_draw'
    action_zh:         str

    # Barrel specifics
    barrel_size_pct:   float    # as fraction of pot
    barrel_size_bb:    float

    # EV
    ev_barrel:         float
    ev_give_up:        float

    # Classification
    hand_type:         str
    hand_type_zh:      str
    card_quality:      str
    card_quality_zh:   str

    # Context
    hero_hand_pct:     float
    is_ip:             bool
    pot_bb:            float
    villain_af:        float
    villain_wtsd:      float

    reasoning:         str
    tips:              List[str]
    summary_zh:        str


def analyze_turn_barrel(
    pot_bb:             float,
    hero_hand_pct:      float = 0.60,
    stack_bb:           float = 100.0,
    is_ip:              bool  = True,
    completes_flush:    bool  = False,
    completes_straight: bool  = False,
    pairs_board:        bool  = False,
    turn_is_blank:      bool  = True,    # 2-7, doesn't change much
    turn_is_high_card:  bool  = False,   # A/K/Q
    hero_opened_ep:     bool  = False,   # hero opened from UTG/HJ
    villain_vpip:       float = 0.28,
    villain_af:         float = -1.0,
    villain_wtsd:       float = -1.0,
    villain_hands:      int   = 0,
) -> TurnBarrelResult:
    """
    Advise on whether to barrel the turn after a flop c-bet was called.

    Args:
        pot_bb:             Pot in BB at turn (before any bet)
        hero_hand_pct:      Hero's hand percentile (0-1)
        stack_bb:           Effective stack in BB
        is_ip:              True if hero is in position
        completes_flush:    True if turn completes a flush (4 of same suit)
        completes_straight: True if turn completes an obvious straight
        pairs_board:        True if turn pairs the flop board
        turn_is_blank:      True if turn is a low card (2-7) that doesn't change much
        turn_is_high_card:  True if turn is A/K/Q
        hero_opened_ep:     True if hero opened from UTG/HJ (wide high-card range)
        villain_vpip:       VPIP from HUD
        villain_af:         Aggression Factor (-1=unknown)
        villain_wtsd:       Went To Showdown % (-1=unknown)
        villain_hands:      HUD sample size
    """
    tips: List[str] = []

    # ── Effective villain stats ───────────────────────────────────────────────
    eff_af   = villain_af   if villain_af   > 0 else max(0.4, 2.0 - villain_vpip * 2.0)
    eff_wtsd = villain_wtsd if villain_wtsd > 0 else 0.30

    # ── Turn card quality ─────────────────────────────────────────────────────
    card_quality = assess_turn_card_quality(
        completes_flush     = completes_flush,
        completes_straight  = completes_straight,
        pairs_board         = pairs_board,
        is_blank            = turn_is_blank,
        is_high_card        = turn_is_high_card,
        hero_opened_ep      = hero_opened_ep,
    )
    card_quality_zh = _CARD_QUALITY_ZH.get(card_quality, card_quality)

    # ── Hand type ─────────────────────────────────────────────────────────────
    hand_type    = _hand_type(hero_hand_pct)
    hand_type_zh = _HAND_TYPE_ZH.get(hand_type, hand_type)

    # ── Barrel frequency ──────────────────────────────────────────────────────
    barrel_freq = _barrel_frequency(hand_type, card_quality, eff_af, eff_wtsd, is_ip)
    barrel_pct  = _barrel_size(hand_type, card_quality, is_ip, pot_bb)
    barrel_bb   = round(pot_bb * barrel_pct, 1)

    # ── Decision ──────────────────────────────────────────────────────────────
    should_barrel = barrel_freq >= 0.50   # barrel if recommended frequency >= 50%

    # Special case: strong draw (0.35-0.49) on excellent card → semi-bluff barrel
    if hand_type == 'weak' and card_quality == 'excellent' and barrel_freq >= 0.35:
        should_barrel = True

    if should_barrel:
        action    = 'barrel'
        action_zh = f'桶注（{barrel_pct:.0%}底池={barrel_bb:.0f}BB，頻率={barrel_freq:.0%}）'
    elif hand_type in ('weak', 'air') and card_quality not in ('excellent', 'good'):
        action    = 'give_up'
        action_zh = '放棄（過牌，不繼續詐唬）'
    else:
        action    = 'check_draw'
        action_zh = '過牌（中等牌，轉牌不佳，控制底池）'

    # ── EV ────────────────────────────────────────────────────────────────────
    ev_barrel_val  = _ev_barrel(hero_hand_pct, eff_af, eff_wtsd, pot_bb, barrel_pct)
    ev_give_up_val = _ev_give_up(hero_hand_pct, pot_bb)

    # ── Tips ─────────────────────────────────────────────────────────────────
    if villain_hands < 15:
        tips.append(f'HUD樣本不足（{villain_hands}手），使用VPIP={villain_vpip:.0%}估算對手類型')
    if card_quality == 'very_bad':
        tips.append('同花/順子完成：強烈建議過牌。繼續桶注只代表你有那張牌，對手知道')
    if card_quality == 'excellent' and hand_type in ('weak', 'air'):
        tips.append('空白轉牌：對手翻牌的聽牌未成，這是你獲取fold equity的好時機')
    if eff_af > 2.5:
        tips.append(f'對手AF={eff_af:.1f}（激進）：他可能用加注回應桶注，弱手牌謹慎桶注')
    if eff_wtsd > 0.40:
        tips.append(f'對手WTSD={eff_wtsd:.0%}（站台式）：他不會因為你桶注而棄牌；只桶注強牌')
    if not is_ip:
        tips.append('OOP桶注：風險更高，對手可以浮注/加注。縮小尺寸，減少頻率')
    if hand_type == 'strong':
        tips.append('強牌：幾乎全桶注（只在同花完成時考慮過牌）')

    # ── Reasoning ─────────────────────────────────────────────────────────────
    pos_str = 'IP' if is_ip else 'OOP'
    reasoning = (
        f'轉牌{pos_str}，翻牌C-bet被跟注後，'
        f'英雄手牌={hand_type_zh}（{hero_hand_pct:.0%}），'
        f'轉牌牌質={card_quality_zh}，'
        f'對手VPIP={villain_vpip:.0%}/AF={eff_af:.1f}/WTSD={eff_wtsd:.0%}，'
        f'建議桶注頻率={barrel_freq:.0%}→{action_zh}'
    )

    # ── Summary ───────────────────────────────────────────────────────────────
    summary_zh = f'[轉牌桶注] {card_quality_zh[:6]} {hand_type_zh[:5]} → {action}'[:85]

    return TurnBarrelResult(
        should_barrel   = should_barrel,
        barrel_frequency = barrel_freq,
        action          = action,
        action_zh       = action_zh,
        barrel_size_pct = barrel_pct,
        barrel_size_bb  = barrel_bb,
        ev_barrel       = ev_barrel_val,
        ev_give_up      = ev_give_up_val,
        hand_type       = hand_type,
        hand_type_zh    = hand_type_zh,
        card_quality    = card_quality,
        card_quality_zh = card_quality_zh,
        hero_hand_pct   = hero_hand_pct,
        is_ip           = is_ip,
        pot_bb          = pot_bb,
        villain_af      = eff_af,
        villain_wtsd    = eff_wtsd,
        reasoning       = reasoning,
        tips            = tips,
        summary_zh      = summary_zh,
    )


def turn_barrel_summary(r: TurnBarrelResult) -> str:
    """Single-line overlay summary (<=85 chars)."""
    return r.summary_zh[:85]
