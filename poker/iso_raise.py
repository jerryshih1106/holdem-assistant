"""
孤立加注顧問 (Iso-Raise Advisor)

場景：一名以上玩家跟了大盲注（limp），英雄考慮加注（孤立）。

孤立加注為什麼高 EV？
  1. 跟注者通常是被動/弱型玩家（VPIP 高但 PFR 低），範圍遠差於英雄
  2. 加注可以直接收取底池（跟注者棄牌率 40-65%）
  3. 若有人跟注，英雄通常有位置優勢（後位加注）
  4. 建立一個英雄有範圍優勢的大底池

何時不適合孤立加注？
  - 縮牌玩家（Nit）跟注：他們的跟注範圍異常強，要更謹慎
  - 超過 3 名跟注者：底池多人化，折疊勝算大幅下降
  - 籌碼低於 20BB：應直接推牌
  - 英雄在 UTG 面對 BTN 跟注：英雄已失去位置優勢

孤立注碼公式：
  base = 3BB（標準開局注碼）
  per_limper = +1BB（每個跟注者加一個大盲）
  fish_premium = +1BB（對手是魚/被動型時額外加）
  oop_premium  = +1BB（英雄沒有位置時額外加）
  最終建議 = base + per_limper × n + adjustments
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class IsoRaiseResult:
    # 決策
    should_iso:        bool
    iso_size_bb:       float    # 建議孤立注碼（BB）
    min_size_bb:       float    # 最小有效孤立注碼
    max_size_bb:       float    # 超過此注碼對 EV 無益

    # 手牌資格
    hand_qualifies:    bool     # 此手牌是否達到孤立標準
    min_hand_pct:      float    # 建議孤立的最低手牌百分位（0-1）
    hand_threshold_zh: str      # 中文手牌門檻描述

    # EV 分析
    p_all_fold:        float    # 所有跟注者棄牌的概率
    ev_fold_equity:    float    # 即時收取底池的期望 EV（BB）
    ev_called:         float    # 被跟注後的期望 EV（BB）
    ev_total:          float    # 總期望值（BB）
    ev_vs_limp:        float    # 相比直接跟注多贏的 EV（BB）

    # 情境
    n_limpers:         int
    hero_pos:          str
    villain_profile:   str      # 'fish'/'nit'/'passive'/'unknown'
    is_ip:             bool     # 英雄是否有位置

    # 說明
    key_reason:        str      # 孤立的最主要理由
    tips:              List[str]
    summary_zh:        str


_POS_ORDER = ['UTG', 'UTG1', 'UTG2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']

_VILLAIN_FOLD_RATE = {
    'fish':    0.42,   # calls wide, hard to fold
    'passive': 0.55,   # somewhat foldable
    'tag':     0.65,   # limp-folding is a leak; folds to iso often
    'nit':     0.72,   # very few limps, but folds if it's a trap
    'unknown': 0.52,
}

_VILLAIN_ZH = {
    'fish':    '魚型玩家',
    'passive': '被動型玩家',
    'tag':     'TAG 玩家',
    'nit':     '縮牌玩家',
    'unknown': '未知類型',
}

# Minimum iso hand threshold (as fraction of all hands) by position and n_limpers
# Lower fraction = tighter requirement
_MIN_HAND_THRESHOLD = {
    # (hero_pos_bucket, n_limpers) -> min_hand_pct
    ('late', 1): 0.28,    # BTN/CO, 1 limper → very wide iso
    ('late', 2): 0.18,
    ('late', 3): 0.12,
    ('mid',  1): 0.18,    # HJ/LJ, 1 limper
    ('mid',  2): 0.12,
    ('mid',  3): 0.08,
    ('ep',   1): 0.12,    # UTG/UTG1/UTG2, 1 limper
    ('ep',   2): 0.08,
    ('ep',   3): 0.06,
    ('blind', 1): 0.22,   # SB or BB iso (rare but possible from SB)
    ('blind', 2): 0.15,
    ('blind', 3): 0.10,
}

# Hand threshold descriptions (approximate top-X%)
_HAND_THRESHOLD_ZH = {
    0.28: 'A2s+, K9s+, Q9s+, J9s+, T9s, 22+, ATo+, KJo+',
    0.22: 'A4s+, KTs+, Q9s+, J9s+, 44+, AJo+, KQo',
    0.18: 'A7s+, KTs+, QTs+, 55+, AJo+, KQo',
    0.15: '66+, A8s+, KTs+, AJo+, KQo',
    0.12: '77+, A9s+, KQs, AQo+',
    0.08: '88+, ATs+, KQs, AQo+',
    0.06: '99+, AQs+, AKo',
}


def _pos_bucket(pos: str) -> str:
    """Classify position into late/mid/ep/blind."""
    pos = pos.upper()
    if pos in ('BTN', 'CO'):
        return 'late'
    if pos in ('HJ', 'LJ'):
        return 'mid'
    if pos in ('SB', 'BB'):
        return 'blind'
    return 'ep'


def _classify_villain(vpip: float) -> str:
    """Classify villain type from VPIP."""
    if vpip >= 0.40:
        return 'fish'
    if vpip >= 0.30:
        return 'passive'
    if vpip >= 0.18:
        return 'tag'
    return 'nit'


def analyze_iso_raise(
    hero_pos:          str   = 'BTN',
    n_limpers:         int   = 1,
    hero_hand_pct:     float = 0.20,   # hero's hand percentile vs full range (0-1, higher=stronger)
    hero_stack_bb:     float = 100.0,
    villain_vpip:      float = 0.30,   # average VPIP of limping opponents (0-1)
    hero_is_ip:        bool  = True,   # True if hero acts after all limpers postflop
    pot_before_bb:     float = -1.0,   # -1 = auto-calc from n_limpers (SB+BB+limps)
) -> IsoRaiseResult:
    """
    Analyze whether to iso-raise and calculate optimal sizing.

    Args:
        hero_pos:      Hero's position
        n_limpers:     Number of players who limped (called the BB)
        hero_hand_pct: Hero's hand strength as fraction (0=worst, 1=best hands)
                       Use 0.95 for AA, 0.80 for TT, 0.50 for T9s, 0.15 for 72o
        hero_stack_bb: Effective stack in BB
        villain_vpip:  Average VPIP of limping opponents (decimal, e.g. 0.35)
        hero_is_ip:    True if hero has position postflop vs all limpers
        pot_before_bb: Pot before hero acts. -1 = auto (SB 0.5 + BB 1.0 + n_limpers × 1BB)
    """
    if pot_before_bb <= 0:
        pot_before_bb = 1.5 + n_limpers
    tips: List[str] = []

    # ── Very short stack: push or fold, not iso ───────────────────────────────
    if hero_stack_bb <= 20:
        return IsoRaiseResult(
            should_iso=False, iso_size_bb=0, min_size_bb=0, max_size_bb=0,
            hand_qualifies=False, min_hand_pct=0, hand_threshold_zh='直接推牌',
            p_all_fold=0, ev_fold_equity=0, ev_called=0, ev_total=0, ev_vs_limp=0,
            n_limpers=n_limpers, hero_pos=hero_pos,
            villain_profile='unknown', is_ip=hero_is_ip,
            key_reason=f'籌碼 {hero_stack_bb:.0f}BB 太少，應直接全下或棄牌',
            tips=['20BB 以下，孤立加注無意義，應推/棄'],
            summary_zh=f'[孤立] 短籌碼({hero_stack_bb:.0f}BB)→ 推牌或棄牌',
        )

    # ── Too many limpers: fold equity collapses ────────────────────────────────
    if n_limpers >= 4:
        tips.append(f'{n_limpers}名跟注者：折疊勝算低，除非手牌很強否則不建議孤立')

    villain_type = _classify_villain(villain_vpip)
    fold_rate    = _VILLAIN_FOLD_RATE[villain_type]

    # ── Fold probability ──────────────────────────────────────────────────────
    # BB may also be in the pot and can call; assume BB folds 60-70% of the time
    # vs an iso raise (they already put 1BB in and typically fold to raises)
    bb_fold_rate = 0.65
    p_all_fold   = (fold_rate ** n_limpers) * bb_fold_rate

    # ── ISO SIZE ──────────────────────────────────────────────────────────────
    base_size = 3.0
    per_limper = 1.0
    fish_premium = 1.0 if villain_type == 'fish' else 0.0
    oop_premium  = 1.0 if not hero_is_ip else 0.0
    nit_premium  = 0.5 if villain_type == 'nit' else 0.0   # nit limps = trap, bet bigger

    iso_size = base_size + per_limper * n_limpers + fish_premium + oop_premium + nit_premium
    iso_size = round(min(iso_size, hero_stack_bb * 0.35), 1)  # cap at 35% stack

    min_size = round(base_size + per_limper * n_limpers, 1)
    max_size = round(iso_size + 2.0, 1)

    # ── EV calculation ────────────────────────────────────────────────────────
    # EV when all fold: win current pot + iso raise
    # EV when called: approximate using hero's range edge
    # hero_equity_postflop: IP has ~55-60% edge, OOP ~45-50%
    hero_postflop_equity = 0.57 if hero_is_ip else 0.50
    # Adjust for hand strength (strong hands have more equity)
    hero_postflop_equity += (hero_hand_pct - 0.50) * 0.20

    # Net profit when all fold: win dead money (pot_before), iso investment returned
    ev_fold_equity = p_all_fold * pot_before_bb

    # Net EV when called: equity × total_pot_created - iso_investment
    called_pot = pot_before_bb + iso_size * 2   # pot when one caller matches
    ev_called_per_hand = hero_postflop_equity * called_pot - iso_size
    ev_called_net      = ev_called_per_hand * (1 - p_all_fold)

    ev_total = round(ev_fold_equity + ev_called_net, 2)

    # EV of limping behind: risk 1BB, play for pot_before+1
    ev_limp = hero_postflop_equity * (pot_before_bb + 1.0) - 1.0
    ev_vs_limp = round(ev_total - ev_limp, 2)

    # ── Hand qualification ────────────────────────────────────────────────────
    pos_bucket = _pos_bucket(hero_pos)
    key = (pos_bucket, min(n_limpers, 3))
    min_hand_pct = _MIN_HAND_THRESHOLD.get(key, 0.15)

    # Adjust for villain type
    if villain_type == 'fish':
        min_hand_pct *= 0.80    # can iso wider vs fish (they'll call but lose more)
    elif villain_type == 'nit':
        min_hand_pct *= 1.20    # nit limps are often traps, need stronger hand

    min_hand_pct = round(min(0.50, min_hand_pct), 2)

    # Find matching threshold description
    thresh_zh = ''
    for pct, desc in sorted(_HAND_THRESHOLD_ZH.items()):
        if min_hand_pct <= pct + 0.03:
            thresh_zh = desc
            break
    if not thresh_zh:
        thresh_zh = '99+, AQs+, AKo（謹慎孤立）'

    hand_qualifies = hero_hand_pct >= min_hand_pct

    # ── Should iso? ───────────────────────────────────────────────────────────
    # Main conditions
    should_iso = (
        hand_qualifies
        and n_limpers <= 3
        and hero_stack_bb > 20
        and p_all_fold >= 0.20    # at least 20% chance everyone folds
    )

    # ── Tips ─────────────────────────────────────────────────────────────────
    if villain_type == 'fish':
        tips.append(f'對手魚型(VPIP={villain_vpip:.0%})：孤立是最高 EV 操作，加大注碼')
    elif villain_type == 'nit':
        tips.append(f'縮牌跟注(VPIP={villain_vpip:.0%})：可能慢打強牌，謹慎孤立')
    if not hero_is_ip:
        tips.append('英雄無位置（OOP）：加大注碼以補償位置劣勢')
    if n_limpers >= 3:
        tips.append(f'{n_limpers}名跟注者：孤立注碼要更大，需要更強手牌')
    if not hand_qualifies:
        tips.append(f'手牌強度（百分位 {hero_hand_pct:.0%}）未達到孤立門檻（{min_hand_pct:.0%}）')

    # ── Key reason ─────────────────────────────────────────────────────────────
    if should_iso:
        key_reason = (
            f'{n_limpers}名{_VILLAIN_ZH[villain_type]}跟注，'
            f'折疊勝算 {p_all_fold:.0%}，'
            f'孤立注 {iso_size:.0f}BB，EV ≈ {ev_vs_limp:+.1f}BB（vs 跟注）'
        )
    else:
        if not hand_qualifies:
            key_reason = f'手牌不夠強（{hero_hand_pct:.0%} < 門檻 {min_hand_pct:.0%}），建議棄牌'
        elif n_limpers >= 4:
            key_reason = f'跟注者太多（{n_limpers}人），折疊勝算太低'
        else:
            key_reason = f'孤立條件不佳（折疊勝算 {p_all_fold:.0%}）'

    # ── Summary ────────────────────────────────────────────────────────────────
    if should_iso:
        summary_zh = (
            f'[孤立] {n_limpers}跟注  '
            f'{iso_size:.0f}BB  '
            f'棄牌率{p_all_fold:.0%}  '
            f'EV{ev_vs_limp:+.1f}BB  '
            f'{_VILLAIN_ZH[villain_type][:4]}'
        )[:85]
    else:
        summary_zh = f'[孤立] 不建議（{key_reason[:30]}）'

    return IsoRaiseResult(
        should_iso        = should_iso,
        iso_size_bb       = iso_size,
        min_size_bb       = min_size,
        max_size_bb       = max_size,
        hand_qualifies    = hand_qualifies,
        min_hand_pct      = min_hand_pct,
        hand_threshold_zh = thresh_zh,
        p_all_fold        = round(p_all_fold, 3),
        ev_fold_equity    = round(ev_fold_equity, 2),
        ev_called         = round(ev_called_net, 2),
        ev_total          = ev_total,
        ev_vs_limp        = ev_vs_limp,
        n_limpers         = n_limpers,
        hero_pos          = hero_pos,
        villain_profile   = villain_type,
        is_ip             = hero_is_ip,
        key_reason        = key_reason,
        tips              = tips,
        summary_zh        = summary_zh,
    )


def iso_raise_summary(r: IsoRaiseResult) -> str:
    """Single-line overlay summary (<=85 chars)."""
    return r.summary_zh[:85]
