"""
大盲注翻後防守顧問 (BB Postflop Defense Advisor)

BB 防守翻前開注後，翻牌的翻後策略與普通範圍截然不同：

BB 範圍特性（vs BTN/CO 偷盲後跟注）：
  ✓ 無超強翻前手牌（AA/KK/QQ/AK 在翻前已加注）
  ✓ 大量中等牌：中對子、連張、同花連張、Ax、Kx 百搭
  ✓ 許多底部範圍：23s, 34s, 45s, 72o 等（因底池賠率而跟注）
  ✗ 翻後劣勢（永遠 OOP）

位置劣勢補償策略：
  1. 過牌-加注（Check-Raise）頻率高於標準
     → 低牌面（A23, 567）BB 範圍優勢時 CR 頻率 25-35%
     → 高牌面（KQJ, AQT）villain 範圍優勢，CR 頻率降至 10-15%
  2. 探測注（Probe Bet）— 轉牌 villain 過牌後主動下注
     → 低牌面、對面牌面：探測注頻率 35-50%
     → 高牌面 villain 過牌：探測注頻率 20-30%
  3. 浮牌（Float）— 以中等牌跟注翻牌，轉牌主動搶奪
     → 比 IP 更謹慎（OOP 浮牌成本更高）

翻牌牌面對 BB 的有利度（Range Advantage）：
  BB 有利牌面（低牌面）：
    - 234, 245, 345, 236... BB 有更多兩對/順子機會
    - AA 在翻前被 3-bet，BB 有更多中對子
  中性牌面：
    - KT5, Q82, J63 — 雙方範圍相近
  Villain 有利牌面（高牌面）：
    - AKQ, AKJ, KQJ — BTN/CO 開牌範圍有更多高牌手牌

EV 摘要（OOP vs BTN cbet 後的 BB 選擇）：
  Check-raise (強牌/純詐唬): EV = CR_EV(strong) + CR_EV(bluff) - 3x bet
  Check-call (中等牌): EV = hero_eq × (pot + 2×call) - call
  Check-fold (廢牌): EV = 0（保存籌碼）
  Probe bet (轉牌 villain 過牌): EV = fold_equity × pot + call × equity - bet
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple


# ── Board range advantage assessment ─────────────────────────────────────────

def _bb_board_advantage(community: List[str]) -> Tuple[str, str]:
    """
    Returns (advantage, advantage_zh) from BB's perspective.
    'bb_favor' → low/connected board, BB has range advantage
    'neutral'  → medium board
    'villain_favor' → high-card board, BTN/CO has more high-card combos
    """
    if not community:
        return 'neutral', '中性牌面'

    _RANK_VAL = {'2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,
                 '9':9,'T':10,'J':11,'Q':12,'K':13,'A':14}

    ranks = []
    for c in community[:3]:   # evaluate flop only
        c = c.strip()
        if c:
            r = c[0].upper() if c[0].isdigit() or c[0].upper() in _RANK_VAL else c[0]
            ranks.append(_RANK_VAL.get(r, 0))

    if not ranks:
        return 'neutral', '中性牌面'

    high_count = sum(1 for r in ranks if r >= 10)
    top_rank   = max(ranks) if ranks else 0
    low_count  = sum(1 for r in ranks if r <= 7)

    if low_count >= 2 and top_rank <= 9:
        return 'bb_favor', 'BB有利牌面（低牌）'
    if high_count >= 2:
        return 'villain_favor', 'Villain有利牌面（高牌）'
    return 'neutral', '中性牌面'


# ── Action recommendation ─────────────────────────────────────────────────────

def _bb_action(
    hero_equity:     float,
    street:          str,           # 'flop'/'turn'
    board_advantage: str,
    villain_cbet:    float,         # villain's c-bet frequency (0-1, -1=unknown)
    villain_af:      float,
    is_villain_cbet: bool,          # True if villain just c-bet (hero faces bet)
    pot_bb:          float,
    call_bb:         float,
) -> Tuple[str, str, float, str]:
    """
    Returns (action, action_zh, sizing_pct, tip).
    action: 'check_raise'/'check_call'/'check_fold'/'probe_bet'/'lead_bet'
    """
    eff_cbet = villain_cbet if villain_cbet > 0 else 0.60
    eff_af   = villain_af   if villain_af   > 0 else 1.5

    # ── Facing villain c-bet (hero must call/fold/raise) ──────────────────────
    if is_villain_cbet:
        if hero_equity >= 0.65:
            return 'check_raise', '過牌加注（強牌）', 2.5, '強牌 OOP：加注建立底池'
        if hero_equity >= 0.50 and board_advantage == 'bb_favor':
            return 'check_raise', '過牌加注（半詐唬）', 2.3, 'BB有利牌面半詐唬加注'
        if hero_equity >= 0.38:
            # pot odds calculation
            po = call_bb / max(0.5, pot_bb + call_bb)
            if hero_equity >= po + 0.05:
                return 'check_call', '過牌跟注', 0.0, '勝率超過底池賠率 → 跟注'
            return 'check_fold', '過牌棄牌', 0.0, '勝率不足底池賠率'
        if hero_equity >= 0.25 and board_advantage == 'bb_favor' and eff_af > 1.5:
            return 'check_raise', '過牌加注（詐唬）', 2.3, 'BB有利牌面 + 激進對手 → 純詐唬CR'
        return 'check_fold', '過牌棄牌', 0.0, '勝率不足，棄牌'

    # ── Villain checked (hero can lead/probe) ─────────────────────────────────
    # Villain checked after being the PFR — their range is capped/weak
    if hero_equity >= 0.60:
        # Strong hand: lead for value
        size = 0.60 if board_advantage == 'bb_favor' else 0.50
        return 'lead_bet', '主動下注取值', size, '對手過牌範圍弱 → 主動建底池'
    if hero_equity >= 0.45 and board_advantage in ('bb_favor', 'neutral'):
        # Probe/lead with medium hand
        size = 0.40 if street == 'turn' else 0.35
        return 'probe_bet', '探測注（取值/保護）', size, '對手過牌 + 中等牌 → 探測注'
    if hero_equity >= 0.35 and eff_cbet < 0.45:
        # Villain rarely c-bets, meaning their check is weaker → probe
        return 'probe_bet', '剝削性探測注（對手過牌率高）', 0.33, '對手低C-bet頻率 → 過牌弱'
    return 'check_back',  '過牌（控制底池）', 0.0, '手牌不夠強，控制底池'


_ACTION_ZH = {
    'check_raise': '過牌加注',
    'check_call':  '過牌跟注',
    'check_fold':  '過牌棄牌',
    'probe_bet':   '探測注',
    'lead_bet':    '主動下注',
    'check_back':  '過牌',
}


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class BbPostflopResult:
    # Context
    street:           str
    pot_bb:           float
    call_bb:          float
    is_villain_cbet:  bool

    # Board
    community:        List[str]
    board_advantage:  str
    board_advantage_zh: str

    # Hero equity
    hero_equity:      float

    # Decision
    action:           str
    action_zh:        str
    sizing_pct:       float
    sizing_bb:        float
    action_tip:       str

    # CR / probe frequency
    cr_frequency:     float     # check-raise frequency recommendation
    probe_frequency:  float     # probe bet frequency

    # Villain stats used
    villain_cbet:     float
    villain_af:       float
    villain_hands:    int

    tips:             List[str]
    reasoning:        str
    summary_zh:       str


def analyze_bb_postflop(
    pot_bb:          float,
    hero_equity:     float   = 0.45,
    call_bb:         float   = 0.0,
    community:       List[str] = None,
    is_villain_cbet: bool    = True,
    villain_cbet:    float   = -1.0,
    villain_af:      float   = -1.0,
    villain_vpip:    float   = 0.28,
    villain_hands:   int     = 0,
    street:          str     = 'flop',
) -> BbPostflopResult:
    """
    Advise BB on postflop play after defending against a steal.

    Args:
        pot_bb:          Pot in BB
        hero_equity:     Hero's MC equity (0-1)
        call_bb:         Amount to call if villain bet (0 if villain checked)
        community:       Community cards list
        is_villain_cbet: True if villain just c-bet (hero faces a bet)
        villain_cbet:    Villain's c-bet% from HUD (-1=unknown)
        villain_af:      Villain's AF from HUD (-1=unknown)
        villain_vpip:    Villain's VPIP from HUD
        villain_hands:   HUD sample size
        street:          'flop' or 'turn'
    """
    community   = community or []
    tips: List[str] = []

    eff_cbet = villain_cbet if villain_cbet > 0 else 0.60
    eff_af   = villain_af   if villain_af   > 0 else 1.5

    adv, adv_zh = _bb_board_advantage(community)

    action, action_zh, sizing_pct, tip = _bb_action(
        hero_equity, street, adv, eff_cbet, eff_af,
        is_villain_cbet, pot_bb, call_bb
    )

    sizing_bb = round(pot_bb * sizing_pct, 1) if sizing_pct > 0 else 0.0

    # CR / probe frequency estimates (by board advantage + street)
    _base_cr    = {'bb_favor': 0.28, 'neutral': 0.15, 'villain_favor': 0.08}
    _base_probe = {'bb_favor': 0.45, 'neutral': 0.35, 'villain_favor': 0.22}
    _turn_adj   = -0.05   # slightly lower frequency on turn vs flop
    cr_base    = _base_cr.get(adv, 0.15)
    probe_base = _base_probe.get(adv, 0.35)
    if street == 'turn':
        probe_base = max(0.0, probe_base + _turn_adj)
    cr_freq    = cr_base    if is_villain_cbet else 0.0
    probe_freq = 0.0        if is_villain_cbet else probe_base

    # Tips
    tips.append(tip)
    if adv == 'villain_favor' and action == 'check_raise':
        tips.append('高牌面Villain有利：只加注最強手牌（兩對+），避免半詐唬CR')
    if adv == 'bb_favor' and not is_villain_cbet:
        tips.append(f'BB有利低牌面 + Villain過牌：探測注頻率提高至{probe_freq:.0%}')
    if eff_cbet > 0.75 and is_villain_cbet:
        tips.append(f'對手C-bet頻率={eff_cbet:.0%}（偏高）：加大跟注/加注範圍，他的範圍包含詐唬')
    elif eff_cbet < 0.35 and is_villain_cbet:
        tips.append(f'對手C-bet頻率={eff_cbet:.0%}（低）：他下注時通常有真實牌力，謹慎跟注')
    if villain_hands < 20:
        tips.append(f'HUD樣本不足（{villain_hands}手），使用預設C-bet頻率')

    pos_str = 'BB翻後（OOP）'
    act_str = '對手C-bet後' if is_villain_cbet else '對手過牌後'
    reasoning = (
        f'{pos_str} {street}，{act_str}，{adv_zh}，'
        f'英雄勝率={hero_equity:.0%}，底池={pot_bb:.0f}BB → {action_zh}'
    )
    size_str = f' {sizing_pct:.0%}pot={sizing_bb:.0f}BB' if sizing_pct > 0 else ''
    summary_zh = f'[BB翻後] {hero_equity:.0%} → {action_zh}{size_str}'[:85]

    return BbPostflopResult(
        street           = street,
        pot_bb           = pot_bb,
        call_bb          = call_bb,
        is_villain_cbet  = is_villain_cbet,
        community        = community,
        board_advantage  = adv,
        board_advantage_zh = adv_zh,
        hero_equity      = hero_equity,
        action           = action,
        action_zh        = action_zh,
        sizing_pct       = sizing_pct,
        sizing_bb        = sizing_bb,
        action_tip       = tip,
        cr_frequency     = cr_freq,
        probe_frequency  = probe_freq,
        villain_cbet     = eff_cbet,
        villain_af       = eff_af,
        villain_hands    = villain_hands,
        tips             = tips,
        reasoning        = reasoning,
        summary_zh       = summary_zh,
    )


def bb_postflop_summary(r: BbPostflopResult) -> str:
    """Single-line overlay summary (<=85 chars)."""
    return r.summary_zh[:85]
