"""
即時對手讀牌摘要 (Real-time Villain Reads Summary)

問題：HUD 數字（VPIP=42%, PFR=11%, AF=0.7）對大多數玩家沒有直接意義。
本模組將這些數字轉換為當前情境下最有價值的 2-3 條行動指引。

核心設計：
  不同情境（翻前/翻後 + 英雄/對手的行動）有不同的最重要 HUD 數據。

  翻前英雄行動（RFI/3-bet 決定）：
    最重要：PFR%、3bet%、FCbet、WTSD
    → 應調整：偷盲頻率、3-bet 範圍

  翻後英雄主動（C-bet / barrel 決定）：
    最重要：FCbet%（fold to cbet）、WTSD
    → 應調整：C-bet 頻率、注碼大小

  翻後英雄面對下注（跟注 / 棄牌 / 加注）：
    最重要：AF（攻擊因子）、WTSD、注碼大小
    → 應調整：跟注範圍、加注頻率

  河牌（任何情境）：
    最重要：WTSD（到河牌比例）
    → 應調整：薄取值頻率、詐唬頻率

優先級排序規則：
  EV 影響越大的調整排越前面。
  影響 = |偏差| × 底池大小 × 頻率
  例：FCbet=78% 偏差 23% × 頻率高 → 高優先
      3bet=14% 偏差 6% × 頻率低 → 低優先
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# ── Population averages (6-max cash 100NL baseline) ───────────────────────────

_POP = {
    'vpip':     0.27,
    'pfr':      0.20,
    'af':       1.80,
    'wtsd':     0.29,
    'fcbet':    0.55,   # fold to c-bet
    'threebet': 0.07,
    'fold_3b':  0.60,   # fold to 3-bet
}


# ── Read generation ───────────────────────────────────────────────────────────

@dataclass
class VillainRead:
    priority:    int        # 1 = highest priority
    stat_name:   str        # e.g. 'FCbet'
    stat_value:  float
    deviation:   float      # vs population (+ = above, - = below)
    situation:   str        # when this read applies
    action_zh:   str        # specific action recommendation
    ev_impact:   str        # 'high'/'medium'/'low'


def _read_fcbet(fcbet: float, situation: str) -> Optional[VillainRead]:
    dev = fcbet - _POP['fcbet']
    if abs(dev) < 0.10:
        return None
    if dev > 0:
        action = f'所有翻牌C-bet（他棄牌{fcbet:.0%}），轉牌繼續施壓'
    else:
        action = f'只用強牌/聽牌C-bet（他跟注{1-fcbet:.0%}），跳過詐唬'
    return VillainRead(
        priority   = 1,
        stat_name  = f'FCbet={fcbet:.0%}',
        stat_value = fcbet,
        deviation  = dev,
        situation  = '翻牌/轉牌主動行動',
        action_zh  = action,
        ev_impact  = 'high' if abs(dev) > 0.18 else 'medium',
    )


def _read_wtsd(wtsd: float, situation: str) -> Optional[VillainRead]:
    dev = wtsd - _POP['wtsd']
    if abs(dev) < 0.07:
        return None
    if dev > 0:
        action = f'絕不詐唬（他WTSD={wtsd:.0%}攤牌到底），只用頂20%手牌大注取值'
    else:
        action = f'河牌大注詐唬（他WTSD={wtsd:.0%}易棄牌），超池詐唬獲利'
    return VillainRead(
        priority   = 1 if abs(dev) > 0.12 else 2,
        stat_name  = f'WTSD={wtsd:.0%}',
        stat_value = wtsd,
        deviation  = dev,
        situation  = '河牌決策',
        action_zh  = action,
        ev_impact  = 'high' if abs(dev) > 0.12 else 'medium',
    )


def _read_af(af: float, situation: str) -> Optional[VillainRead]:
    if af < 0:
        return None
    dev = af - _POP['af']
    if abs(dev) < 0.60:
        return None
    if dev > 0:
        action = f'強牌過牌讓他詐唬（AF={af:.1f}激進），不要主動下注'
    else:
        action = f'主動建底池（AF={af:.1f}被動），不等他下注，主動領注取值'
    return VillainRead(
        priority   = 2,
        stat_name  = f'AF={af:.1f}',
        stat_value = af,
        deviation  = dev,
        situation  = '翻後主動行動選擇',
        action_zh  = action,
        ev_impact  = 'high' if abs(dev) > 1.2 else 'medium',
    )


def _read_threebet(threebet: float, situation: str) -> Optional[VillainRead]:
    if threebet < 0:
        return None
    dev = threebet - _POP['threebet']
    if abs(dev) < 0.04:
        return None
    if dev > 0:
        action = f'對手3-bet={threebet:.0%}（激進），緊縮開牌/4-bet比他的3-bet寬'
    else:
        action = f'對手3-bet={threebet:.0%}（保守），放心開寬，他3-bet=真實牌力'
    return VillainRead(
        priority   = 2,
        stat_name  = f'3bet={threebet:.0%}',
        stat_value = threebet,
        deviation  = dev,
        situation  = '翻前開牌/面對3-bet',
        action_zh  = action,
        ev_impact  = 'high' if abs(dev) > 0.08 else 'medium',
    )


def _read_vpip_pfr(vpip: float, pfr: float) -> Optional[VillainRead]:
    gap = vpip - pfr   # large gap = passive caller
    if vpip < 0.18:
        action = f'縮牌型（VPIP={vpip:.0%}），對他的加注棄牌95%，他有真實牌力'
        return VillainRead(priority=2, stat_name=f'VPIP={vpip:.0%}', stat_value=vpip,
                           deviation=vpip - _POP['vpip'], situation='翻前/翻後被動',
                           action_zh=action, ev_impact='medium')
    if vpip > 0.42:
        action = f'魚型（VPIP={vpip:.0%}），放棄詐唬，薄取值範圍擴大到 top 40%'
        return VillainRead(priority=1, stat_name=f'VPIP={vpip:.0%}', stat_value=vpip,
                           deviation=vpip - _POP['vpip'], situation='所有街道',
                           action_zh=action, ev_impact='high')
    if gap > 0.20:
        action = f'跟注型（VPIP-PFR差={gap:.0%}），他主動加注=強牌，被動跟注=寬廣範圍'
        return VillainRead(priority=2, stat_name=f'跟注型', stat_value=gap,
                           deviation=gap - 0.08, situation='翻前讀牌',
                           action_zh=action, ev_impact='medium')
    return None


def _read_fold_3b(fold_3b: float) -> Optional[VillainRead]:
    if fold_3b < 0:
        return None
    dev = fold_3b - _POP['fold_3b']
    if abs(dev) < 0.12:
        return None
    if dev > 0:
        action = f'對手3-bet棄牌率={fold_3b:.0%}，從所有位置大幅增加3-bet頻率'
    else:
        action = f'對手3-bet棄牌率={fold_3b:.0%}（低），只3-bet真實強牌，不輕易3-bet詐唬'
    return VillainRead(
        priority   = 1 if dev > 0.15 else 2,
        stat_name  = f'F3bet={fold_3b:.0%}',
        stat_value = fold_3b,
        deviation  = dev,
        situation  = '翻前3-bet決策',
        action_zh  = action,
        ev_impact  = 'high' if abs(dev) > 0.18 else 'medium',
    )


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class VillainReadsResult:
    # Raw stats used
    vpip:        float
    pfr:         float
    af:          float
    wtsd:        float
    fcbet:       float
    threebet:    float
    fold_3b:     float
    hands:       int

    # Generated reads
    reads:       List[VillainRead]   # sorted by priority desc
    top_read_zh: str                 # most important read
    summary_zh:  str                 # overlay summary (<=85 chars)

    # Player type
    player_type: str
    player_type_zh: str


def _classify_player_type(vpip: float, pfr: float, af: float, wtsd: float) -> Tuple[str, str]:
    if vpip > 0.45 and pfr < 0.15:
        return 'fish', '魚（被動鬆散）'
    if vpip > 0.40:
        return 'lag_fish', '鬆激/魚'
    if vpip < 0.18:
        return 'nit', '縮牌（緊型）'
    if vpip > 0.28 and pfr > 0.22 and af > 2.0:
        return 'lag', '鬆激（LAG）'
    if 0.22 <= vpip <= 0.32 and 0.15 <= pfr <= 0.24:
        return 'tag', '標準緊激（TAG）'
    if af < 0.8 and wtsd > 0.34:
        return 'calling_station', '跟注站（被動）'
    return 'unknown', '一般玩家'


def analyze_villain_reads(
    vpip:      float  = 0.27,
    pfr:       float  = 0.20,
    af:        float  = 1.80,
    wtsd:      float  = 0.29,
    fcbet:     float  = 0.55,
    threebet:  float  = 0.07,
    fold_3b:   float  = 0.60,
    hands:     int    = 0,
    situation: str    = 'postflop_facing_bet',  # context hint
) -> VillainReadsResult:
    """
    Generate prioritized villain reads from HUD stats.

    Args:
        vpip:      VPIP (0-1)
        pfr:       PFR (0-1)
        af:        Aggression Factor
        wtsd:      Went to Showdown (0-1)
        fcbet:     Fold to C-bet (0-1)
        threebet:  3-bet% (0-1)
        fold_3b:   Fold to 3-bet% (0-1)
        hands:     HUD sample size
        situation: hint for prioritization
    """
    reads: List[VillainRead] = []

    r = _read_fcbet(fcbet, situation)
    if r: reads.append(r)
    r = _read_wtsd(wtsd, situation)
    if r: reads.append(r)
    r = _read_af(af, situation)
    if r: reads.append(r)
    r = _read_threebet(threebet, situation)
    if r: reads.append(r)
    r = _read_vpip_pfr(vpip, pfr)
    if r: reads.append(r)
    r = _read_fold_3b(fold_3b)
    if r: reads.append(r)

    # Sort: priority ASC, then by abs deviation DESC
    reads.sort(key=lambda x: (x.priority, -abs(x.deviation)))

    ptype, ptype_zh = _classify_player_type(vpip, pfr, af, wtsd)

    if not reads:
        top_read = f'[{ptype_zh}] 對手數據接近均衡，無明顯剝削點'
    else:
        top_read = f'[{ptype_zh}] {reads[0].action_zh}'

    # Summary: type + top 1 exploit
    if reads:
        r0 = reads[0]
        summary_zh = f'[讀牌] {ptype_zh} {r0.stat_name}: {r0.action_zh}'[:85]
    else:
        summary_zh = f'[讀牌] {ptype_zh} VPIP{vpip:.0%}/PFR{pfr:.0%} — 接近均衡'[:85]

    return VillainReadsResult(
        vpip         = vpip,
        pfr          = pfr,
        af           = af,
        wtsd         = wtsd,
        fcbet        = fcbet,
        threebet     = threebet,
        fold_3b      = fold_3b,
        hands        = hands,
        reads        = reads,
        top_read_zh  = top_read,
        summary_zh   = summary_zh,
        player_type  = ptype,
        player_type_zh = ptype_zh,
    )


def villain_reads_summary(r: VillainReadsResult) -> str:
    """Single-line overlay summary (<=85 chars)."""
    return r.summary_zh[:85]
