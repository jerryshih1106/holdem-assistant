"""
河牌中等手牌顧問 (River Medium-Strength Hand Advisor)

涵蓋勝率 42-60% 的河牌決策 — 這是最難做決策的區域，也是漏洞最多的地方。

現有模組：
  river_value.py   → 勝率 >= 60%（取值下注）
  river_bluff.py   → 勝率 < 42%（詐唬）
  river_medium.py  → 勝率 42-60%（中等手牌：薄取值/過牌跟注/過牌棄牌）

決策框架（英雄主動行動，call_amount == 0）：

薄取值（Thin Value Bet）條件：
  - 對手 WTSD > 0.28（喜歡攤牌）+ 對手有更多比英雄差的手牌 → 英雄下注可獲取EV
  - IP + 安全牌面 + 勝率 > 0.50 → 40-50% 底池薄取值
  - OOP + 對手 AF < 1.5（被動）+ 安全牌面 → 33-40% 底池薄取值

阻擋注（Blocking Bet）：
  - OOP + 激進對手（AF > 2.0）→ 先下小注（25-33% 底池）阻止對手大注
  - 對手下注會讓英雄面臨不好的決定

過牌跟注（Check-Call）：
  - 對手 AF > 2.0（會詐唬）→ 讓對手下注，然後跟注
  - 英雄勝率 > 所需勝率（底池賠率）時跟注

過牌棄牌（Check-Fold）：
  - 安全牌面 + 被動對手（不詐唬）→ 對手下注時棄牌（他有真實牌力）
  - 危險牌面 + 英雄中等手牌 → 過牌棄牌

EV 簡化模型：
  EV(薄取值) = call_rate × [eq_when_called × (pot+bet) - (1-eq)×bet] + (1-call_rate) × pot
  EV(過牌) = check_then_call_ev or check_then_fold_ev

英雄在 call 被加注時的行動：
  - 薄取值後被加注 → 通常棄牌（中等手牌面對加注=基本棄牌）
  - 過牌跟注後被再加注 → 通常棄牌（除非有特殊強牌）

牌面危險程度（board_danger）：
  'safe'      → 乾燥牌面，沒有完成的聽牌
  'moderate'  → 對面牌面，有些可能的聽牌
  'dangerous' → 完成的同花/順子，英雄的中等手牌被擊敗的機率高
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple


# ── Villain profile classification ────────────────────────────────────────────

def _villain_profile_medium(vpip: float, af: float, wtsd: float) -> str:
    eff_wtsd = wtsd if wtsd > 0 else 0.30
    eff_af   = af   if af   > 0 else 1.5
    if eff_wtsd > 0.40 or vpip > 0.42:
        return 'calling_station'
    if eff_af > 2.5:
        return 'aggressive'
    if eff_af < 0.9 and vpip < 0.27:
        return 'passive_tight'
    return 'balanced'


# ── EV estimates ──────────────────────────────────────────────────────────────

def _ev_thin_value_bet(hero_pct: float, villain_wtsd: float, pot_bb: float,
                        bet_pct: float) -> float:
    """EV of thin value betting on river."""
    bet = pot_bb * bet_pct
    eff_wtsd = villain_wtsd if villain_wtsd > 0 else 0.32
    # Villain call rate: WTSD × adjustment factor
    call_rate = min(0.75, eff_wtsd * 1.8)
    # When villain calls: they have a mix of worse/better hands
    # For hero at 52-58%, villain calling range has more weaker hands than stronger ones
    # Model: hero wins (hero_pct - 0.12) of call situations
    eq_called = max(0.05, min(0.85, hero_pct - 0.12))
    ev_called  = eq_called * (pot_bb + 2 * bet) - bet
    ev_fold    = pot_bb      # villain folds, hero takes pot
    return round(call_rate * ev_called + (1 - call_rate) * ev_fold, 2)


def _ev_check(hero_pct: float, villain_af: float, pot_bb: float,
              call_if_bet: bool = True) -> float:
    """EV of checking river with a medium hand."""
    eff_af = villain_af if villain_af > 0 else 1.5
    # Villain bet frequency after hero checks
    bet_freq = min(0.80, max(0.20, eff_af * 0.28))
    # If villain bets and hero calls:
    ev_call_bet  = hero_pct * (pot_bb + pot_bb * 0.6) - pot_bb * 0.6
    # If villain checks: hero wins based on showdown equity
    ev_check_check = hero_pct * pot_bb
    if call_if_bet:
        return round(bet_freq * ev_call_bet + (1 - bet_freq) * ev_check_check, 2)
    else:
        # Check-fold: just win pot when villain checks, lose nothing when villain bets
        return round((1 - bet_freq) * ev_check_check, 2)


# ── Core decision logic ───────────────────────────────────────────────────────

def _decide_action(
    hero_pct:     float,
    is_ip:        bool,
    board_danger: str,     # 'safe'/'moderate'/'dangerous'
    villain_af:   float,
    villain_vpip: float,
    villain_wtsd: float,
) -> Tuple[str, float, bool]:
    """
    Returns: (action, bet_size_pct, call_if_raised)
      action: 'thin_value_bet'/'blocking_bet'/'check_call'/'check_fold'
    """
    eff_af   = max(0.1, villain_af   if villain_af   > 0 else 1.5)
    eff_wtsd = max(0.1, villain_wtsd if villain_wtsd > 0 else 0.30)
    profile  = _villain_profile_medium(villain_vpip, eff_af, eff_wtsd)

    danger_penalty = {'safe': 0, 'moderate': -0.06, 'dangerous': -0.14}
    eff_pct = hero_pct + danger_penalty.get(board_danger, 0.0)

    # ── Dangerous board: most medium hands check ──────────────────────────────
    if board_danger == 'dangerous':
        if eff_pct >= 0.56 and profile == 'calling_station':
            return 'thin_value_bet', 0.33, False   # still value bet vs station
        if profile == 'aggressive':
            return 'check_fold', 0.0, False         # vs aggressive: check-fold
        return 'check_call', 0.0, True              # vs passive/balanced: check-call 1 bet

    # ── Strong medium (55-60%) ────────────────────────────────────────────────
    if hero_pct >= 0.55:
        if is_ip:
            if board_danger == 'safe':
                return 'thin_value_bet', 0.40, False
            else:
                return 'thin_value_bet', 0.33, False
        else:  # OOP
            if eff_af > 2.0:
                return 'blocking_bet', 0.25, True   # block bet to avoid huge bet
            elif board_danger == 'safe' and eff_wtsd > 0.28:
                return 'thin_value_bet', 0.35, False
            else:
                return 'check_call', 0.0, True

    # ── Middle medium (48-55%) ────────────────────────────────────────────────
    elif hero_pct >= 0.48:
        if profile == 'aggressive' and board_danger != 'dangerous':
            return 'check_call', 0.0, True          # let them bluff
        if is_ip and board_danger == 'safe' and eff_wtsd >= 0.30:
            return 'thin_value_bet', 0.40, False
        if profile == 'calling_station':
            return 'thin_value_bet', 0.33, False    # station always calls → value
        if board_danger == 'safe':
            return 'check_call', 0.0, True
        return 'check_fold', 0.0, False

    # ── Weak medium (42-48%) ─────────────────────────────────────────────────
    else:
        if is_ip and board_danger == 'safe' and eff_wtsd > 0.40:
            return 'thin_value_bet', 0.33, False    # calling station pays even weak bets
        if profile == 'aggressive':
            return 'check_call', 0.0, True           # let bluffer fire
        if profile == 'passive_tight':
            return 'check_fold', 0.0, False          # passive = value when they bet
        return 'check_fold', 0.0, False


# ── Action labels ─────────────────────────────────────────────────────────────

_ACTION_ZH = {
    'thin_value_bet': '薄取值下注',
    'blocking_bet':   '阻擋注（先手小注）',
    'check_call':     '過牌跟注',
    'check_fold':     '過牌棄牌',
}

_BOARD_DANGER_ZH = {
    'safe':      '安全牌面（無完成聽牌）',
    'moderate':  '中度危險（對面/部分聽牌）',
    'dangerous': '危險牌面（同花/順子完成）',
}


@dataclass
class RiverMediumResult:
    # Decision
    action:            str     # 'thin_value_bet'/'blocking_bet'/'check_call'/'check_fold'
    action_zh:         str
    call_if_raised:    bool    # if hero bets, should they call a raise?

    # Bet sizing (if applicable)
    bet_size_pct:      float
    bet_size_bb:       float

    # EV
    ev_bet:            float
    ev_check_call:     float
    ev_check_fold:     float

    # Inputs
    hero_hand_pct:     float
    is_ip:             bool
    board_danger:      str
    board_danger_zh:   str
    villain_profile:   str

    # Pot/stack context
    pot_bb:            float
    stack_bb:          float

    reasoning:         str
    tips:              List[str]
    summary_zh:        str


def analyze_river_medium(
    pot_bb:           float,
    hero_hand_pct:    float  = 0.52,
    stack_bb:         float  = 100.0,
    is_ip:            bool   = True,
    board_danger:     str    = 'safe',   # 'safe'/'moderate'/'dangerous'
    villain_vpip:     float  = 0.28,
    villain_af:       float  = -1.0,
    villain_wtsd:     float  = -1.0,
    villain_hands:    int    = 0,
) -> RiverMediumResult:
    """
    Advise on river play with medium-strength hands (42-60% equity zone).

    Args:
        pot_bb:        Pot in BB (hero acts first, call_amount=0)
        hero_hand_pct: Hero's hand percentile (0.42-0.60)
        stack_bb:      Effective stack in BB
        is_ip:         True if hero is in position
        board_danger:  'safe'/'moderate'/'dangerous'
        villain_vpip:  VPIP from HUD
        villain_af:    Aggression Factor from HUD
        villain_wtsd:  Went To Showdown from HUD
        villain_hands: HUD sample size
    """
    tips: List[str] = []

    # ── Effective villain stats ───────────────────────────────────────────────
    eff_af   = villain_af   if villain_af   > 0 else max(0.3, 2.0 - villain_vpip * 3.0)
    eff_wtsd = villain_wtsd if villain_wtsd > 0 else 0.30

    profile = _villain_profile_medium(villain_vpip, eff_af, eff_wtsd)
    profile_zh = {
        'calling_station': '跟注型（站台式）',
        'aggressive':      '激進型',
        'passive_tight':   '被動緊型',
        'balanced':        '均衡型',
    }.get(profile, '均衡型')

    # ── Core decision ─────────────────────────────────────────────────────────
    action, bet_pct, call_if_raised = _decide_action(
        hero_hand_pct, is_ip, board_danger, eff_af, villain_vpip, eff_wtsd
    )
    action_zh = _ACTION_ZH.get(action, action)

    bet_bb = round(pot_bb * bet_pct, 1) if bet_pct > 0 else 0.0

    # ── EV estimates ──────────────────────────────────────────────────────────
    ev_bet         = _ev_thin_value_bet(hero_hand_pct, eff_wtsd, pot_bb, bet_pct if bet_pct > 0 else 0.40)
    ev_check_call  = _ev_check(hero_hand_pct, eff_af, pot_bb, call_if_bet=True)
    ev_check_fold  = _ev_check(hero_hand_pct, eff_af, pot_bb, call_if_bet=False)

    # ── Tips ─────────────────────────────────────────────────────────────────
    if villain_hands < 20:
        tips.append(f'HUD樣本不足（{villain_hands}手），對手類型推測為{profile_zh}')
    if action in ('thin_value_bet', 'blocking_bet'):
        tips.append(f'被加注時棄牌（中等手牌面對加注=落後，不要英雄式跟注）')
    if action == 'check_call' and profile == 'aggressive':
        tips.append(f'對手AF={eff_af:.1f}（激進）：過牌讓他詐唬，再跟注獲取EV')
    if action == 'check_fold' and board_danger == 'dangerous':
        tips.append(f'危險牌面：對手下注代表強牌（完成的同花/順子），棄牌正確')
    if board_danger == 'safe' and eff_wtsd > 0.38:
        tips.append(f'對手WTSD={eff_wtsd:.0%}（喜歡攤牌）：薄取值更有利，他會付清')
    if not is_ip and action in ('thin_value_bet',):
        tips.append('OOP薄取值：被加注後棄牌，不要追加跟注')
    if hero_hand_pct < 0.48 and action == 'thin_value_bet':
        tips.append(f'弱中等牌薄取值：只在對手WTSD>{eff_wtsd:.0%}（站台式）時才有利')

    # ── Reasoning ─────────────────────────────────────────────────────────────
    pos_str  = 'IP（有位置）' if is_ip else 'OOP（無位置）'
    danger_zh = _BOARD_DANGER_ZH.get(board_danger, board_danger)
    reasoning = (
        f'河牌{pos_str}，勝率={hero_hand_pct:.0%}（中等手牌區），'
        f'底池={pot_bb:.0f}BB，{danger_zh}，'
        f'對手={profile_zh}(VPIP={villain_vpip:.0%}/AF={eff_af:.1f}/WTSD={eff_wtsd:.0%})。'
        f'ev薄取值={ev_bet:+.1f}BB vs ev過牌跟注={ev_check_call:+.1f}BB → {action_zh}'
    )

    # ── Summary ───────────────────────────────────────────────────────────────
    size_str = f' {bet_pct:.0%}pot={bet_bb:.0f}BB' if bet_pct > 0 else ''
    summary_zh = f'[河牌中等] {hero_hand_pct:.0%} {action_zh}{size_str}'[:85]

    return RiverMediumResult(
        action          = action,
        action_zh       = action_zh,
        call_if_raised  = call_if_raised,
        bet_size_pct    = bet_pct,
        bet_size_bb     = bet_bb,
        ev_bet          = ev_bet,
        ev_check_call   = ev_check_call,
        ev_check_fold   = ev_check_fold,
        hero_hand_pct   = hero_hand_pct,
        is_ip           = is_ip,
        board_danger    = board_danger,
        board_danger_zh = danger_zh,
        villain_profile = profile,
        pot_bb          = pot_bb,
        stack_bb        = stack_bb,
        reasoning       = reasoning,
        tips            = tips,
        summary_zh      = summary_zh,
    )


def river_medium_summary(r: RiverMediumResult) -> str:
    """Single-line overlay summary (<=85 chars)."""
    return r.summary_zh[:85]
