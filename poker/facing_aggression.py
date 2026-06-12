"""
行動調整勝率顧問 (Action-Adjusted Equity Advisor)

問題：蒙地卡羅引擎顯示英雄的勝率是「對隨機手牌」的勝率。但對手的每個行動
都大幅縮窄了他們的範圍 — 這讓英雄的實際勝率遠低於 MC 顯示的數字。

最常見的認知錯誤：
  英雄 KQo 翻牌：MC 勝率 = 55%
  對手轉牌過牌加注：對手範圍實際上是前 7% 的手牌（兩對、暗三條、強聽牌）
  英雄的實際勝率 vs 轉牌過牌加注範圍 ≈ 25%（遠低於 55%）

行動與範圍寬度對照表（佔翻前範圍的比例）：
  C-bet 翻牌：55-75%（大多數玩家大範圍 C-bet）
  跟注 C-bet（未加注）：40-60%（多對+聽牌，無空氣）
  翻牌過牌加注：8-12%（暗三條/兩對/強聽牌/怪獸）
  轉牌過牌加注：5-8%（更強，詐唬較少）
  連續下注（翻+轉）：25-40%（縮窄後仍有廣度）
  河牌小注（<50% 底池）：20-35%（薄取值+詐唬）
  河牌大注（>75% 底池）：10-20%（極化：強牌OR詐唬）
  河牌超額下注（>100%）：5-12%（超極化）

勝率調整模型：
  villain_range_pct → 英雄有效勝率調整係數
  當對手範圍縮窄為頂部 X% 的手牌時，英雄的有效勝率下降。

  近似公式：
    adjusted_equity = raw_equity × (range_pct / 0.50)^0.45

  此公式校準於：
  - range=100%（隨機）→ 係數 = 1.00（無調整）
  - range=50% → 係數 ≈ 1.00（廣泛 C-bet，影響不大）
  - range=15% → 係數 ≈ 0.78（有影響）
  - range=8% → 係數 ≈ 0.64（翻牌過牌加注，英雄勝率大幅下降）
  - range=5% → 係數 ≈ 0.55（河牌超額下注）

決策閾值：
  adjusted_equity > required_equity（底池賠率）→ 跟注
  adjusted_equity + blocker_bonus > required_equity → 考慮跟注
  adjusted_equity < required_equity × 0.80 → 棄牌
"""

from dataclasses import dataclass, field
from typing import List, Tuple


# Action type → (range_pct_low, range_pct_high, zh_label)
_ACTION_PROFILES = {
    'cbet_flop':         (0.50, 0.75, '翻牌C-bet'),
    'cbet_turn':         (0.30, 0.50, '轉牌繼續下注'),
    'cbet_river':        (0.20, 0.38, '河牌第一次下注'),
    'double_barrel':     (0.25, 0.45, '翻+轉連續下注'),
    'triple_barrel':     (0.12, 0.25, '三條連續下注'),
    'check_raise_flop':  (0.07, 0.13, '翻牌過牌加注'),
    'check_raise_turn':  (0.04, 0.08, '轉牌過牌加注'),
    'check_raise_river': (0.03, 0.07, '河牌過牌加注'),
    'river_small':       (0.18, 0.35, '河牌小注（<50%pot）'),
    'river_large':       (0.08, 0.18, '河牌大注（>75%pot）'),
    'river_overbet':     (0.04, 0.12, '河牌超額下注'),
    'donk_bet':          (0.20, 0.40, '主動下注（Donk）'),
    'raise_on_board':    (0.05, 0.12, '加注（翻後）'),
}

# AF-based range adjustment for check-raises (higher AF = more bluffs in range)
def _cr_range_adjust(af: float) -> float:
    """High AF villains include more bluffs in check-raises, widening range."""
    if af >= 3.0:
        return 1.25    # range 25% wider (more bluffs)
    if af >= 2.0:
        return 1.10
    if af <= 0.6:
        return 0.85    # passive players CR with only value (narrower)
    return 1.00


def _infer_action_type(
    call_amount: float,
    pot_bb: float,
    street: str,        # 'flop'/'turn'/'river'
    is_checkraise: bool = False,
    prev_bets: int = 0, # how many times villain has bet across streets
) -> str:
    """Auto-classify villain's action type."""
    bet_pct = call_amount / max(1.0, pot_bb)
    if is_checkraise:
        return f'check_raise_{street}'
    if street == 'river':
        if bet_pct < 0.50:
            return 'river_small'
        if bet_pct > 1.00:
            return 'river_overbet'
        return 'river_large'
    if prev_bets >= 2:
        return 'triple_barrel' if prev_bets >= 3 else 'double_barrel'
    return f'cbet_{street}'


def _range_pct_for_action(action_type: str, villain_vpip: float,
                           villain_af: float) -> float:
    """Estimate villain's range width for this specific action."""
    low, high, _ = _ACTION_PROFILES.get(action_type, (0.35, 0.55, '未知'))
    # Use midpoint, adjusted for villain type
    mid = (low + high) / 2.0

    # Wider-ranging players c-bet/barrel with broader ranges
    vpip_adj = (villain_vpip - 0.28) * 0.3  # ±9% at ±30% VPIP diff
    af_adj   = 0.0
    if 'check_raise' in action_type or 'raise' in action_type:
        af_adj = (villain_af - 1.5) * 0.02  # high AF = slightly wider CR range

    return round(min(0.95, max(0.02, mid + vpip_adj + af_adj)), 3)


def _adjusted_equity(raw_equity: float, range_pct: float) -> float:
    """
    Convert hero's raw MC equity to action-adjusted equity.

    Model: when villain's range narrows to top X%, the average hand they hold
    is stronger, reducing hero's effective equity.

    Calibrated formula: adj = raw × (range_pct / 0.50)^0.45
    This ensures:
    - range=100% (random): adj = raw × 2^0.45 = raw × 1.37 → clipped to raw
    - range=50%: adj = raw × 1.00
    - range=15%: adj = raw × 0.78
    - range=8%:  adj = raw × 0.64
    - range=5%:  adj = raw × 0.58
    """
    scale = min(1.0, (range_pct / 0.50) ** 0.45)
    return round(min(raw_equity, raw_equity * scale), 3)


def _required_equity(call_amount: float, pot_bb: float) -> float:
    """Pot odds → minimum equity to profitably call."""
    total_pot = pot_bb + call_amount
    return round(call_amount / (total_pot + call_amount), 3)


@dataclass
class FacingAggressionResult:
    # Equity analysis
    raw_equity:       float   # MC equity vs random
    adjusted_equity:  float   # equity vs villain's action range
    equity_reduction: float   # how much villain's action reduced equity
    required_equity:  float   # pot odds threshold

    # Villain range model
    action_type:      str
    action_zh:        str
    villain_range_pct: float  # estimated range width (fraction of all hands)
    villain_range_label: str  # e.g. "頂部8%手牌（兩對/暗三條/強聽牌）"

    # Decision
    action:           str    # 'call'/'fold'/'raise'/'tank'
    action_zh_rec:    str
    equity_margin:    float  # adjusted_equity - required_equity

    # Context
    call_amount:      float
    pot_bb:           float
    street:           str

    reasoning:        str
    tips:             List[str]
    summary_zh:       str


_RANGE_LABEL_TEMPLATES = {
    'cbet_flop':        '翻前範圍的{pct:.0%}（多數手牌C-bet，廣泛）',
    'cbet_turn':        '翻前範圍的{pct:.0%}（轉牌持續下注，已縮窄）',
    'double_barrel':    '翻前範圍的{pct:.0%}（連續下注，值得關注）',
    'triple_barrel':    '翻前範圍的{pct:.0%}（三條街下注，強or詐唬）',
    'check_raise_flop': '頂部{pct:.0%}（翻牌CR：暗三條/兩對/大聽牌）',
    'check_raise_turn': '頂部{pct:.0%}（轉牌CR：極強手牌，詐唬少）',
    'check_raise_river':'頂部{pct:.0%}（河牌CR：幾乎全是強牌）',
    'river_small':      '{pct:.0%}（河牌小注：薄取值+詐唬混合）',
    'river_large':      '頂部{pct:.0%}（河牌大注：極化，強牌OR詐唬）',
    'river_overbet':    '頂部{pct:.0%}（超額下注：超極化，需要強手牌跟注）',
    'raise_on_board':   '頂部{pct:.0%}（翻後加注：暗三條/強手牌/詐唬）',
}


def analyze_facing_aggression(
    call_amount:   float,
    pot_bb:        float,
    raw_equity:    float,  # MC equity (0-1)
    street:        str     = 'flop',   # 'flop'/'turn'/'river'
    action_type:   str     = '',       # explicit action type, or auto-detect
    is_checkraise: bool    = False,
    prev_bets:     int     = 0,
    villain_vpip:  float   = 0.28,
    villain_af:    float   = -1.0,
    villain_hands: int     = 0,
) -> FacingAggressionResult:
    """
    Calculate hero's action-adjusted equity when facing villain's aggression.

    Args:
        call_amount:   Amount hero must call
        pot_bb:        Pot BEFORE villain's bet
        raw_equity:    Hero's raw MC equity vs random hands (0-1)
        street:        'flop'/'turn'/'river'
        action_type:   Explicit action type (see _ACTION_PROFILES keys),
                       leave empty to auto-detect
        is_checkraise: True if villain checked then raised
        prev_bets:     Number of streets villain has already bet (for barrel detection)
        villain_vpip:  VPIP from HUD
        villain_af:    Aggression Factor from HUD (-1=unknown)
        villain_hands: HUD sample size
    """
    tips: List[str] = []

    # ── Villain model ─────────────────────────────────────────────────────────
    eff_af = max(0.1, villain_af) if villain_af > 0 else {
        0.40: 0.7, 0.30: 1.2, 0.20: 1.5,
    }.get(round(villain_vpip, 1), 1.5)
    # Linear fallback
    if villain_af <= 0:
        eff_af = max(0.5, 2.5 - villain_vpip * 4.0)

    # ── Action classification ─────────────────────────────────────────────────
    if not action_type:
        action_type = _infer_action_type(
            call_amount, pot_bb, street, is_checkraise, prev_bets
        )

    _, _, action_zh = _ACTION_PROFILES.get(action_type, (0, 0, '未知行動'))

    # ── Range estimation ──────────────────────────────────────────────────────
    range_pct = _range_pct_for_action(action_type, villain_vpip, eff_af)

    label_template = _RANGE_LABEL_TEMPLATES.get(action_type, '{pct:.0%}的手牌範圍')
    range_label = label_template.format(pct=range_pct)

    if villain_hands < 20:
        tips.append(f'HUD樣本不足（{villain_hands}手），範圍基於VPIP={villain_vpip:.0%}估算')

    # ── Adjusted equity ───────────────────────────────────────────────────────
    adj_eq   = _adjusted_equity(raw_equity, range_pct)
    req_eq   = _required_equity(call_amount, pot_bb)
    eq_reduction = round(raw_equity - adj_eq, 3)
    margin   = round(adj_eq - req_eq, 3)

    # ── Decision ─────────────────────────────────────────────────────────────
    if adj_eq >= req_eq + 0.08:
        action    = 'call'
        action_zh_rec = f'明確跟注（調整後勝率{adj_eq:.0%} >> 所需{req_eq:.0%}）'
    elif adj_eq >= req_eq + 0.02:
        action    = 'call'
        action_zh_rec = f'邊緣跟注（調整後{adj_eq:.0%} ≈ 所需{req_eq:.0%}）'
    elif adj_eq >= req_eq - 0.04:
        action    = 'tank'
        action_zh_rec = f'邊緣決定（差距{margin:.0%}，考慮其他因素）'
    else:
        action    = 'fold'
        action_zh_rec = f'棄牌（調整後{adj_eq:.0%} << 所需{req_eq:.0%}）'

    # ── Tips ─────────────────────────────────────────────────────────────────
    if eq_reduction >= 0.12:
        tips.append(
            f'此行動（{action_zh}）使你的有效勝率從{raw_equity:.0%}降至{adj_eq:.0%}（-{eq_reduction:.0%}）'
        )
    if 'check_raise' in action_type:
        if eff_af < 1.0:
            tips.append(f'對手AF={eff_af:.1f}（被動）：他們的過牌加注幾乎全是強牌，很少詐唬')
        elif eff_af > 2.5:
            tips.append(f'對手AF={eff_af:.1f}（激進）：他們的過牌加注含更多詐唬，跟注EV稍高')
    if action_type == 'river_overbet':
        tips.append('對手超額下注（>pot）：這是超極化行動，對手要麼有怪獸要麼在詐唬。核對你的阻斷牌')
    if action_type in ('triple_barrel',) and adj_eq < req_eq:
        tips.append('三條街下注後棄牌：注意是否有阻斷牌減少對手強手牌組合數')
    if margin >= 0.05 and raw_equity < req_eq:
        tips.append(f'注意：MC勝率{raw_equity:.0%} < 所需{req_eq:.0%}，但行動調整後反而可跟注？考慮對手的詐唬頻率')

    # ── Reasoning ─────────────────────────────────────────────────────────────
    reasoning = (
        f'{action_zh}→對手範圍估算{range_label}，'
        f'MC勝率{raw_equity:.0%}調整為{adj_eq:.0%}（-{eq_reduction:.0%}），'
        f'所需勝率{req_eq:.0%}，差距{margin:+.0%}，'
        f'→ {action_zh_rec}'
    )

    # ── Summary ─────────────────────────────────────────────────────────────
    summary_zh = (
        f'[行動調整] {action_zh}  '
        f'勝率{raw_equity:.0%}→{adj_eq:.0%}(-{eq_reduction:.0%})  '
        f'vs 所需{req_eq:.0%}  {action}'
    )[:85]

    return FacingAggressionResult(
        raw_equity       = raw_equity,
        adjusted_equity  = adj_eq,
        equity_reduction = eq_reduction,
        required_equity  = req_eq,
        action_type      = action_type,
        action_zh        = action_zh,
        villain_range_pct = range_pct,
        villain_range_label = range_label,
        action           = action,
        action_zh_rec    = action_zh_rec,
        equity_margin    = margin,
        call_amount      = call_amount,
        pot_bb           = pot_bb,
        street           = street,
        reasoning        = reasoning,
        tips             = tips,
        summary_zh       = summary_zh,
    )


def facing_aggression_summary(r: FacingAggressionResult) -> str:
    """Single-line overlay summary (<=85 chars)."""
    return r.summary_zh[:85]
