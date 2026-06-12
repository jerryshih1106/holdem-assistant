"""
河牌純詐唬最優化器 (River Pure Bluff Optimizer)

場景：河牌圈，英雄有未完成的聽牌或純空氣牌，考慮是否詐唬。

為什麼這很重要？
  - 永不詐唬 = 對手永遠跟注（對手知道你只有強牌），EV極低
  - 隨機詐唬 = 花費籌碼而不考慮阻斷牌或折疊率，也是EV極低
  - 最優詐唬 = 用正確的手牌（最好的阻斷牌）在正確的頻率詐唬

核心公式：
  詐唬保本折疊率 (Alpha) = bet / (pot + bet)

  如果 villain_FCBet >= alpha → 詐唬 EV 為正
  如果 villain_FCBet < alpha → 詐唬 EV 為負

  EV(bluff) = P(fold) × pot - P(call) × bet
            = FCBet × pot - (1 - FCBet) × bet

最佳詐唬候選手牌（優先順序）：
  1. 未完成花色聽牌 + Ace 阻斷牌（Ace-high missed flush draw）
     → 兩個優點：代表沖牌，同時阻斷對手的堅果沖牌
  2. 未完成花色聽牌（Missed flush draw）
     → 可代表已成牌，board 有沖牌威脅
  3. 未完成順子聽牌（Missed straight draw）
     → 可代表順子
  4. 阻斷牌 + 弱牌（Blocker hand）
     → 手中有對手strongest calling hand 的 Ace 或 King
  5. 純空氣（Pure air）
     → 最差的詐唬，需要最高的折疊率才合算

詐唬注碼選擇：
  - 河牌詐唬通常使用 大注碼（75-100% 底池甚至超額下注）
  - 理由：大注碼讓對手的底池賠率更差，折疊率更高
  - 如果使用 33% 底池詐唬：alpha = 0.33/(1+0.33) = 25%（太低，對手很少需要棄牌）
  - 如果使用 100% 底池詐唬：alpha = 1.0/2.0 = 50%（要求更高，但每次成功獲得更多）
  - 最常用：75-100% pot，除非確定對手FCBet極高時可用更小

阻斷牌評分原則：
  - 阻斷對手的【跟注】手牌 > 阻斷對手的【棄牌】手牌
  - 例：板面 Ac Jc 7h 2s Qd（沖牌未完成）
    → 英雄手中有 Kc：阻斷對手的King-high flush draw（但他也沒跟注的理由）
    → 英雄手中有 Ac：阻斷對手的 Ace-high flush draw（對手想跟注的最強手牌之一）
    → Ac 是更好的阻斷牌

"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional


@dataclass
class RiverBluffResult:
    # 詐唬建議
    should_bluff:     bool
    bluff_frequency:  float   # 推薦詐唬頻率（0-1）
    bet_size_pct:     float   # 推薦注碼（佔底池比例）
    bet_size_bb:      float   # 推薦注碼（BB）

    # EV 分析
    ev_bluff:         float   # 詐唬 EV（BB）
    ev_check:         float   # 過牌 EV（通常接近 0 for bluffs）
    alpha:            float   # 保本折疊率 = bet/(pot+bet)
    villain_fold_rate: float  # 估算對手在此注碼的棄牌率

    # 詐唬品質
    bluff_type:       str     # 'ace_blocker_flush'/'missed_flush'/'missed_straight'/'blocker'/'air'
    bluff_type_zh:    str
    blocker_score:    float   # 0-1，阻斷牌品質
    has_ace_blocker:  bool    # 英雄持有 Ace（最通用阻斷牌）
    has_flush_blocker: bool   # 英雄持有同花色 Ace/King
    missed_flush:     bool    # 有未完成花色聽牌
    missed_straight:  bool    # 有未完成順子聽牌

    # 情境
    pot_bb:           float
    villain_fcbet:    float   # fold-to-cbet % used
    villain_wtsd:     float   # WTSD % used
    hero_hand_pct:    float   # should be low for bluffs

    # 說明
    reasoning:        str
    tips:             List[str]
    summary_zh:       str


def _rank_val(r: str) -> int:
    return {'2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,
            'T':10,'J':11,'Q':12,'K':13,'A':14}.get(r.upper(), 0)


def _detect_draws(hole: List[str], board: List[str]) -> dict:
    """
    Detect what draws hero had and whether they missed.
    Board should contain all 5 river cards.

    Returns dict with:
      missed_flush: bool  — hero had 2 suited cards that matched a board suit
      missed_straight: bool — hero had connecting cards towards a possible straight
      flush_suit: str — which suit the flush draw was in
      has_ace_of_flush_suit: bool — hero has Ace of the flush suit
      has_king_of_flush_suit: bool
      general_ace_blocker: bool — hero has any Ace
      board_has_pair: bool
    """
    result = {
        'missed_flush': False,
        'missed_straight': False,
        'flush_suit': '',
        'has_ace_of_flush_suit': False,
        'has_king_of_flush_suit': False,
        'general_ace_blocker': any(c[:-1].upper() == 'A' for c in hole),
        'board_has_pair': False,
    }

    if len(hole) < 2 or len(board) < 5:
        return result

    # ── Missed flush detection ────────────────────────────────────────────────
    # A missed flush draw: hero has 2 cards of same suit, board has 2 of that suit
    # (total would be 4 suited cards on turn, 5th didn't come on river)
    # Simpler: look for any suit where there are 3 on board but 5th didn't complete flush
    from collections import Counter
    board_suits = Counter(c[-1].lower() for c in board)

    hole_suits = [c[-1].lower() for c in hole]
    hole_rank_suit = [(c[:-1].upper(), c[-1].lower()) for c in hole]

    for suit, count in board_suits.items():
        # Possible flush draw scenario: board has exactly 3 of this suit (incomplete)
        # meaning a turn flush draw (3 on flop + hero 2 same suit = possible 4-flush)
        # This is an approximation without knowing turn board
        if count == 3:
            hole_of_suit = [r for r, s in hole_rank_suit if s == suit]
            if len(hole_of_suit) >= 1:
                result['missed_flush'] = True
                result['flush_suit'] = suit
                if 'A' in hole_of_suit:
                    result['has_ace_of_flush_suit'] = True
                if 'K' in hole_of_suit:
                    result['has_king_of_flush_suit'] = True

        # If board has 4 of same suit but hero has that suit = made flush (not a bluff candidate)
        if count == 4:
            hole_of_suit = [r for r, s in hole_rank_suit if s == suit]
            if hole_of_suit:
                result['missed_flush'] = False  # hero made the flush!

    # ── Missed straight detection ─────────────────────────────────────────────
    hole_ranks = {_rank_val(c[:-1]) for c in hole}
    board_ranks = {_rank_val(c[:-1]) for c in board}
    all_ranks = hole_ranks | board_ranks

    # Look for 4 cards in a 5-wide window (OESD that missed on river)
    for lo in range(2, 15):
        hi = lo + 4
        in_window = {r for r in all_ranks if lo <= r <= hi}
        hole_in_window = {r for r in hole_ranks if lo <= r <= hi}
        if len(in_window) == 4 and len(hole_in_window) >= 1:
            result['missed_straight'] = True
            break

    # ── Board pair detection ──────────────────────────────────────────────────
    board_rank_counts = Counter(_rank_val(c[:-1]) for c in board)
    if any(v >= 2 for v in board_rank_counts.values()):
        result['board_has_pair'] = True

    return result


def _blocker_score(draw_info: dict) -> float:
    """
    Score the blocker quality of hero's hand for river bluffing (0-1).

    Best blockers:
    - Ace of flush suit (blocks nut flush caller)
    - King of flush suit (blocks 2nd nut flush)
    - General Ace (blocks villain's Ax calling hands)

    Combined with missed draw (can represent the made hand):
    - Missed flush + Ace of that suit = near-perfect bluff candidate
    """
    score = 0.0
    if draw_info['has_ace_of_flush_suit']:
        score += 0.50
    elif draw_info['has_king_of_flush_suit']:
        score += 0.30
    if draw_info['missed_flush']:
        score += 0.30
    if draw_info['missed_straight']:
        score += 0.20
    if draw_info['general_ace_blocker']:
        score += 0.15
    return round(min(1.0, score), 2)


def _bluff_type(draw_info: dict) -> Tuple[str, str]:
    if draw_info['missed_flush'] and draw_info['has_ace_of_flush_suit']:
        return 'ace_blocker_flush', 'Ace阻斷+未完成花色聽牌（最優）'
    if draw_info['missed_flush']:
        return 'missed_flush', '未完成花色聽牌'
    if draw_info['missed_straight']:
        return 'missed_straight', '未完成順子聽牌'
    if draw_info['general_ace_blocker']:
        return 'blocker', 'Ace阻斷牌+弱牌'
    return 'air', '純空氣'


def _villain_fold_rate_at_size(size_pct: float, fcbet: float) -> float:
    """
    Estimate villain's fold rate at a given bet size.
    Base fold rate = fcbet (fold to general bet).
    Larger bets → higher fold rate (villain's EV decreases).
    """
    # Scale fold rate by bet size: 50% pot = base, 75% = +5%, 100% = +10%
    size_adj = (size_pct - 0.50) * 0.20
    return round(min(0.90, max(0.05, fcbet + size_adj)), 3)


def _optimal_bluff_size(blocker_score: float, fcbet: float,
                        bluff_type: str) -> float:
    """
    Choose optimal bet size for river bluff.

    Key principle: larger bets have higher fold equity but require fold rate > alpha.

    If villain folds a lot (FCBet > 60%): can use smaller bets (they fold anyway)
    If villain calls wide (FCBet < 40%): need premium bluff candidates OR don't bluff
    Strong bluff candidate (high blocker): use 75-100% pot (represent the value)
    Weak bluff candidate (pure air): risky, avoid or use small bet
    """
    if bluff_type in ('ace_blocker_flush', 'missed_flush', 'missed_straight'):
        # Can use large sizing to represent made hand
        if fcbet > 0.65:
            return 0.75    # villain folds to most bets, 75% is fine
        return 1.00        # need to apply max pressure if villain sticky
    elif bluff_type == 'blocker':
        return 0.75
    else:
        # Pure air: avoid or go small (less commitment)
        if fcbet > 0.70:
            return 0.50
        return 0.33   # minimal commitment for bad bluff candidates


def analyze_river_bluff(
    hole_cards:      List[str],
    community:       List[str],   # all 5 river cards
    hero_hand_pct:   float = 0.20,  # should be low (< 0.45) for bluffs
    pot_bb:          float = 20.0,
    stack_bb:        float = 100.0,
    villain_fcbet:   float = -1.0,  # fold-to-cbet from HUD (-1 = unknown)
    villain_wtsd:    float = -1.0,  # WTSD from HUD (-1 = unknown)
    villain_vpip:    float = 0.28,
    villain_hands:   int   = 0,
) -> RiverBluffResult:
    """
    Determine if and how to bluff on the river with a weak hand.

    Args:
        hole_cards:    Hero's 2 hole cards (e.g. ['Ah', 'Th'])
        community:     All 5 board cards (river)
        hero_hand_pct: Hero's MC win probability (should be low for bluffs)
        pot_bb:        Pot size in BB before hero acts
        villain_fcbet: Villain's fold-to-c-bet % from HUD (0-1, -1=unknown)
        villain_wtsd:  Villain's WTSD % from HUD (0-1, -1=unknown)
        villain_vpip:  Villain's VPIP from HUD
        villain_hands: HUD sample size
    """
    tips: List[str] = []

    # ── Estimate villain fold rate ────────────────────────────────────────────
    # FCBet from HUD is fold-to-cbet; use as proxy for river fold tendency
    if villain_fcbet > 0:
        eff_fcbet = villain_fcbet
    elif villain_wtsd > 0:
        # If WTSD known: higher WTSD = calls more = lower fold rate
        eff_fcbet = max(0.10, 0.80 - villain_wtsd * 1.5)
    else:
        # Estimate from VPIP: fish fold less, nits fold more
        if villain_vpip >= 0.40:
            eff_fcbet = 0.35
        elif villain_vpip >= 0.30:
            eff_fcbet = 0.48
        elif villain_vpip >= 0.20:
            eff_fcbet = 0.55
        else:
            eff_fcbet = 0.65

    eff_wtsd = max(0.0, villain_wtsd) if villain_wtsd > 0 else (
        0.45 if villain_vpip >= 0.40 else
        0.35 if villain_vpip >= 0.28 else 0.25
    )

    if villain_hands < 20:
        tips.append(f'HUD樣本不足（{villain_hands}手），棄牌率基於VPIP估算')

    # ── Detect hero's draw information ────────────────────────────────────────
    hole  = [c.strip() for c in hole_cards if c.strip()]
    board = [c.strip() for c in community if c.strip()]
    draw_info    = _detect_draws(hole, board)
    blocker_sc   = _blocker_score(draw_info)
    btype, btype_zh = _bluff_type(draw_info)

    # ── Optimal sizing ────────────────────────────────────────────────────────
    bet_pct = _optimal_bluff_size(blocker_sc, eff_fcbet, btype)
    bet_bb  = round(min(stack_bb, pot_bb * bet_pct), 1)

    # ── EV calculation ────────────────────────────────────────────────────────
    alpha           = round(bet_pct / (1 + bet_pct), 3)  # breakeven fold rate
    villain_fold    = _villain_fold_rate_at_size(bet_pct, eff_fcbet)
    ev_bluff_val    = round(villain_fold * pot_bb - (1 - villain_fold) * bet_bb, 2)
    ev_check        = round(hero_hand_pct * pot_bb * 0.20, 2)  # near 0 for bluffs

    # ── Should bluff? ─────────────────────────────────────────────────────────
    # Primary condition: EV > 0 (fold rate exceeds alpha)
    ev_positive = ev_bluff_val > 0

    # Secondary conditions:
    # 1. Hero's hand is weak enough to be a bluff candidate (not value)
    is_bluff_candidate = hero_hand_pct < 0.42
    # 2. Board texture supports bluffing (flush/straight on board = more represent)
    board_supports = draw_info['missed_flush'] or draw_info['missed_straight']

    should_bluff = ev_positive and is_bluff_candidate

    # Bluff frequency calibration
    if not should_bluff:
        bluff_freq = 0.0
    elif btype == 'ace_blocker_flush':
        bluff_freq = 0.80   # premium bluff, do frequently
    elif btype == 'missed_flush':
        bluff_freq = 0.60
    elif btype == 'missed_straight':
        bluff_freq = 0.50
    elif btype == 'blocker':
        bluff_freq = 0.30
    else:
        # Pure air: only bluff if fold rate is very high
        bluff_freq = 0.15 if villain_fold > 0.65 else 0.0

    # Reduce frequency vs callers (high WTSD)
    if eff_wtsd > 0.40:
        bluff_freq *= 0.60
        tips.append(f'對手WTSD={eff_wtsd:.0%}（高）：減少詐唬頻率')

    bluff_freq = round(min(1.0, bluff_freq), 2)

    # ── Tips ─────────────────────────────────────────────────────────────────
    if not ev_positive:
        tips.append(f'詐唬EV為負：對手棄牌率{villain_fold:.0%} < 保本{alpha:.0%}')
    if not is_bluff_candidate:
        tips.append(f'手牌太強（{hero_hand_pct:.0%}）：不需要詐唬，直接下注取值')
    if draw_info['has_ace_of_flush_suit']:
        tips.append('持有沖牌花色的Ace：阻斷對手的堅果沖牌，詐唬代表性極高')
    elif draw_info['missed_flush']:
        tips.append('未完成花色聽牌：可代表沖牌做大注碼詐唬')
    if draw_info['missed_straight']:
        tips.append('未完成順子聽牌：可代表順子做河牌詐唬')
    if btype == 'air' and should_bluff:
        tips.append('純空氣詐唬：此類詐唬高風險，頻率控制在10-15%以避免被剝削')
    if eff_fcbet < alpha:
        tips.append(f'對手FCBet={eff_fcbet:.0%} < 保本折疊率{alpha:.0%}：此尺寸詐唬無利可圖')

    # ── Reasoning ─────────────────────────────────────────────────────────────
    reasoning = (
        f'{btype_zh}（阻斷分{blocker_sc:.2f}），'
        f'保本折疊率{alpha:.0%}，'
        f'對手預估棄牌{villain_fold:.0%}，'
        f'EV={ev_bluff_val:+.1f}BB，'
        f'{"建議" if should_bluff else "不建議"}詐唬'
    )

    # ── Summary ─────────────────────────────────────────────────────────────
    if should_bluff:
        summary_zh = (
            f'[河牌詐唬] {btype_zh[:12]}  '
            f'{bet_pct:.0%}pot={bet_bb:.0f}BB  '
            f'折疊率{villain_fold:.0%}  EV={ev_bluff_val:+.1f}BB'
        )[:85]
    else:
        summary_zh = (
            f'[河牌詐唬] 不建議  '
            f'折疊率{villain_fold:.0%} vs 保本{alpha:.0%}'
        )[:85]

    return RiverBluffResult(
        should_bluff       = should_bluff,
        bluff_frequency    = bluff_freq,
        bet_size_pct       = bet_pct if should_bluff else 0.0,
        bet_size_bb        = bet_bb if should_bluff else 0.0,
        ev_bluff           = ev_bluff_val,
        ev_check           = ev_check,
        alpha              = alpha,
        villain_fold_rate  = villain_fold,
        bluff_type         = btype,
        bluff_type_zh      = btype_zh,
        blocker_score      = blocker_sc,
        has_ace_blocker    = draw_info['general_ace_blocker'],
        has_flush_blocker  = draw_info['has_ace_of_flush_suit'] or draw_info['has_king_of_flush_suit'],
        missed_flush       = draw_info['missed_flush'],
        missed_straight    = draw_info['missed_straight'],
        pot_bb             = pot_bb,
        villain_fcbet      = eff_fcbet,
        villain_wtsd       = eff_wtsd,
        hero_hand_pct      = hero_hand_pct,
        reasoning          = reasoning,
        tips               = tips,
        summary_zh         = summary_zh,
    )


def river_bluff_summary(r: RiverBluffResult) -> str:
    """Single-line overlay summary (<=85 chars)."""
    return r.summary_zh[:85]
