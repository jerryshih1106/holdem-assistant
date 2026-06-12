"""
勝率信心區間計算器 (Winrate Confidence Interval Calculator)

核心問題：「我現在輸了 50BB，是壞牌還是真的打得爛？」

撲克方差的現實：
  - 6-max NLHE 典型標準差約 80-100 BB/100 手
  - 在 200 手樣本內，±40 BB/100 的波動完全正常
  - 看起來很糟的 -20 BB/100 可能只是方差，不代表負 EV

信心區間公式（95% CI，正態近似）：
  標準誤差 SE = σ / √n    (σ ≈ 80 BB/100 手，n = 樣本手牌數)
  95% CI = [winrate - 1.96×SE, winrate + 1.96×SE]

可靠性評估：
  < 100 手：幾乎無法判斷（CI 超過 ±60 BB/100）
  100-500 手：非常不確定
  500-2000 手：開始有參考價值
  2000+ 手：初步可靠
  10000+ 手：相當可靠

實際用途：
  1. 告訴玩家「你目前的下滑在正常範圍內，不要傾斜」
  2. 告訴玩家「你已打了足夠手數，現在的輸法值得分析」
  3. 基於統計顯著性決定是否需要改變策略

重要：
  此計算假設 EV（而非現金）勝率服從正態分佈。
  使用 EV 統計而非現金結果（減少壞牌運影響）。
"""

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class WinrateStatsResult:
    # 觀察值
    hands:           int     # 樣本手數
    ev_per_100:      float   # EV 勝率 BB/100
    total_ev_bb:     float   # 總 EV BB

    # 信心區間（95%）
    std_dev_per_100: float   # 每 100 手標準差（來自標準估計）
    std_error:       float   # 標準誤差 BB/100
    ci_lower:        float   # 下界 BB/100
    ci_upper:        float   # 上界 BB/100
    ci_half_width:   float   # ±半寬 BB/100

    # 可靠性
    reliability:     str     # 'very_low'/'low'/'medium'/'high'/'very_high'
    reliability_zh:  str
    hands_for_next:  int     # 再打多少手才能達到下一個可靠度等級

    # 判斷
    is_clearly_winning: bool    # CI 下界 > +5 BB/100
    is_clearly_losing:  bool    # CI 上界 < -5 BB/100
    in_normal_variance: bool    # 當前結果在 95% 信心區間內屬正常波動
    verdict:            str     # 'winning'/'losing'/'uncertain'

    # 建議
    advice:          str
    summary_zh:      str      # 單行顯示


# 可靠度等級與手牌門檻
_RELIABILITY_THRESHOLDS = [
    (100,   'very_low', '幾乎無法判斷', 500),
    (500,   'low',      '參考性低',    2000),
    (2000,  'medium',   '初步參考',    5000),
    (5000,  'high',     '有參考價值',  10000),
    (10000, 'very_high','可靠',        None),
]

# Typical standard deviation for 6-max NLHE in BB per 100 hands
_STD_DEV_PER_100 = 82.0


def _get_reliability(hands: int) -> tuple:
    """Return (reliability_key, zh, hands_for_next)."""
    for threshold, key, zh, next_level in _RELIABILITY_THRESHOLDS:
        if hands < threshold:
            prev_thresh = [t for t in _RELIABILITY_THRESHOLDS if t[0] < threshold]
            return key, zh, next_level if next_level else 0
    return 'very_high', '可靠', 0


def calculate_winrate_stats(
    hands:          int,
    ev_per_100:     float,
    total_ev_bb:    Optional[float] = None,
    game_type:      str = '6max',    # '6max'/'hu'/'9max' — affects σ estimate
) -> WinrateStatsResult:
    """
    Calculate confidence interval and reliability assessment for observed winrate.

    Args:
        hands:       Number of hands played
        ev_per_100:  Observed EV winrate in BB per 100 hands
        total_ev_bb: Total EV in BB (optional, calculated from other args if None)
        game_type:   '6max', 'hu', or '9max' (affects standard deviation estimate)
    """
    # Standard deviation estimate by game type
    sigma = {
        'hu':   120.0,
        '6max': 82.0,
        'fr':   65.0,
        '9max': 65.0,
    }.get(game_type, 82.0)

    if total_ev_bb is None:
        total_ev_bb = ev_per_100 * hands / 100.0

    if hands <= 0:
        return WinrateStatsResult(
            hands=0, ev_per_100=0.0, total_ev_bb=0.0,
            std_dev_per_100=sigma, std_error=999.0,
            ci_lower=-999.0, ci_upper=999.0, ci_half_width=999.0,
            reliability='very_low', reliability_zh='無資料',
            hands_for_next=100,
            is_clearly_winning=False, is_clearly_losing=False,
            in_normal_variance=True, verdict='uncertain',
            advice='尚無資料，繼續記錄決策。',
            summary_zh='[勝率] 資料不足',
        )

    # Standard error of the mean winrate (in BB/100)
    # SE = σ / √n  where σ is std dev per 100 hands and n is hundreds of hands
    se = sigma / math.sqrt(hands / 100.0)

    # 95% CI
    z = 1.96
    ci_lower = round(ev_per_100 - z * se, 1)
    ci_upper = round(ev_per_100 + z * se, 1)
    ci_half  = round(z * se, 1)

    # Reliability assessment
    rel_key, rel_zh, hands_for_next = _get_reliability(hands)

    # Verdicts
    is_winning  = ci_lower > 5.0
    is_losing   = ci_upper < -5.0
    # "Normal variance": current EV is within CI_half of zero
    # i.e., would a zero-EV player see this result with >5% probability?
    in_normal   = abs(ev_per_100) < ci_half

    if is_winning:
        verdict = 'winning'
    elif is_losing:
        verdict = 'losing'
    else:
        verdict = 'uncertain'

    # Advice
    if hands < 100:
        advice = f'僅 {hands} 手，任何結果都正常。繼續記錄更多局。'
    elif is_winning:
        advice = f'統計上正贏錢！{hands} 手 CI=[{ci_lower:.0f},{ci_upper:.0f}] BB/100。'
    elif is_losing:
        advice = f'統計上正輸錢，請分析漏洞。{hands} 手 CI=[{ci_lower:.0f},{ci_upper:.0f}] BB/100。'
    elif in_normal:
        advice = (
            f'結果在正常方差範圍內。{hands} 手 CI=[{ci_lower:.0f},{ci_upper:.0f}] BB/100。'
            f'再打 {max(0, hands_for_next - hands)} 手才能判斷。'
        )
    else:
        advice = f'{hands} 手 EV={ev_per_100:+.1f} BB/100，CI=[{ci_lower:.0f},{ci_upper:.0f}]，結果不確定。'

    # Summary line (overlay display)
    sign = '+' if ev_per_100 >= 0 else ''
    verdict_emoji_map = {'winning': '盈利', 'losing': '虧損', 'uncertain': '不確定'}
    summary_zh = (
        f'[勝率] {sign}{ev_per_100:.1f}BB/100  '
        f'95%CI=[{ci_lower:.0f},{ci_upper:.0f}]  '
        f'{rel_zh}({hands}手)'
    )[:80]

    return WinrateStatsResult(
        hands            = hands,
        ev_per_100       = round(ev_per_100, 2),
        total_ev_bb      = round(total_ev_bb, 2),
        std_dev_per_100  = sigma,
        std_error        = round(se, 2),
        ci_lower         = ci_lower,
        ci_upper         = ci_upper,
        ci_half_width    = ci_half,
        reliability      = rel_key,
        reliability_zh   = rel_zh,
        hands_for_next   = max(0, hands_for_next - hands) if hands_for_next else 0,
        is_clearly_winning = is_winning,
        is_clearly_losing  = is_losing,
        in_normal_variance = in_normal,
        verdict          = verdict,
        advice           = advice,
        summary_zh       = summary_zh,
    )


def winrate_stats_summary(r: WinrateStatsResult) -> str:
    """Single-line overlay display (<=80 chars)."""
    return r.summary_zh[:80]
