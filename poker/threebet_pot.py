"""
3-Bet 底池翻牌顧問 (3-Bet Pot Post-flop Advisor)

場景：英雄在翻前進行了3-bet（或面對3-bet），翻牌後的底池比單次加注底池大
3-4倍，同時有效籌碼深度（SPR）更低。

為什麼3-bet底池不同？
  1. SPR更低：單次加注底池 SPR≈10-15，3-bet底池 SPR≈3-5
  2. 更快達到承諾點：較低SPR意味著更少的手牌強度可以全押
  3. C-bet頻率更高：雙方範圍更極化，更多空氣牌需要持續壓力
  4. 更大的注碼：用2/3pot到全底池（而非1/2pot）
  5. 複雜性降低：範圍更極化，策略更簡單（bet/fold而非check/call）

典型3-bet底池 SPR計算：
  BTN 開 3BB → SB/BB 3-bet 至 10BB → BTN 跟注 = 底池約 21BB
  若各100BB，有效籌碼 = 90BB，SPR = 90/21 ≈ 4.3
  若各150BB，SPR = 140/21 ≈ 6.7

承諾點手牌強度（SPR-based）：
  SPR ≤ 3: 頂對任何踢腳都可以全押
  SPR 3-5: 頂對好踢腳（TPTK）可以全押
  SPR 5-8: 需要頂對頂踢腳才能全押
  SPR > 8: 需要兩對/暗三條以上才能全押（接近普通底池策略）

C-bet 頻率（3-bet底池）：
  IP（有位置）：
    乾燥板面（A72彩虹）: 80-85%（範圍優勢極大）
    中等板面（T87兩門）: 60-70%
    配對板面（KK3）: 70-75%
    濕潤板面（JT9兩門）: 50-60%

  OOP（無位置）：
    乾燥板面: 60-65%（較IP低，有位置劣勢）
    中等板面: 45-55%
    配對板面: 55-60%
    濕潤板面: 35-45%

C-bet 注碼（3-bet底池）：
  偏好使用 2/3 pot 到 pot（不同於SRP的1/2 pot）
  理由：SPR低時需要更大注碼才能將對手逼到困難決定

翻牌加注（Check-Raise in 3-bet pot）：
  IP一般較少用CR（因為SPR低，CR = 基本全押）
  OOP CR頻率較高（沒有位置時需要用CR保護）
  CR需要：強手牌（前15%）或者非常好的詐唬+阻斷牌
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ThreeBetPotResult:
    # 翻牌行動建議
    action:         str    # 'cbet'/'check_cr'/'check_call'/'check_fold'
    action_zh:      str
    cbet_frequency: float  # 建議C-bet頻率
    cbet_size_pct:  float  # 建議注碼（佔底池比例）
    cbet_size_bb:   float  # 建議注碼（BB）

    # 承諾點分析
    spr:                float   # 翻牌時的 SPR
    commitment_pct:     float   # 需要此比例以上的手牌強度才能承諾
    hero_can_commit:    bool    # 英雄是否達到承諾點
    commit_threshold:   str     # 描述需要什麼手牌

    # 手牌分類
    hero_hand_pct:      float
    hand_category:      str     # 'nut'/'strong'/'medium'/'weak'/'bluff'
    hand_zh:            str

    # 情境
    pot_bb:             float
    stack_bb:           float
    hero_is_ip:         bool
    board_type:         str     # 'dry'/'medium'/'wet'/'paired'
    hero_was_3better:   bool    # True = 英雄是3-bet者，False = 英雄是跟注者

    # 對手調整
    villain_type:       str
    villain_vpip:       float

    # 說明
    reasoning:          str
    tips:               List[str]
    summary_zh:         str


_BOARD_ZH = {
    'dry':    '乾燥',
    'medium': '中等',
    'wet':    '濕潤',
    'paired': '配對',
}


def _classify_board(board_type: str) -> str:
    return _BOARD_ZH.get(board_type, board_type)


def _commitment_threshold(spr: float) -> tuple:
    """
    Return (min_hand_pct_to_commit, description) based on SPR.
    Lower SPR = lower hand strength needed to commit.
    """
    if spr <= 2.0:
        return 0.60, '頂對任何踢腳'
    if spr <= 3.5:
        return 0.65, '頂對好踢腳 (TP+)'
    if spr <= 5.0:
        return 0.72, '頂對頂踢腳 (TPTK)'
    if spr <= 7.0:
        return 0.78, '超對/頂對+踢腳Ace (TPTK+)'
    if spr <= 10.0:
        return 0.82, '強兩對/暗三條以上'
    return 0.88, '強兩對/暗三條以上（接近普通底池）'


def _cbet_frequency(hero_is_ip: bool, board_type: str,
                    hero_was_3better: bool) -> float:
    """
    Base c-bet frequency in 3-bet pots by position and board texture.
    3-bettor c-bets more frequently (they have range advantage).
    """
    if hero_is_ip and hero_was_3better:
        freqs = {'dry': 0.83, 'medium': 0.68, 'wet': 0.55, 'paired': 0.73}
    elif hero_is_ip and not hero_was_3better:
        # IP but caller (less range advantage, still positional advantage)
        freqs = {'dry': 0.65, 'medium': 0.52, 'wet': 0.42, 'paired': 0.60}
    elif not hero_is_ip and hero_was_3better:
        # OOP 3-bettor — range advantage but position disadvantage
        freqs = {'dry': 0.63, 'medium': 0.50, 'wet': 0.38, 'paired': 0.57}
    else:
        # OOP caller — least c-bet
        freqs = {'dry': 0.50, 'medium': 0.38, 'wet': 0.28, 'paired': 0.45}
    return freqs.get(board_type, 0.55)


def _cbet_size(spr: float, board_type: str) -> float:
    """
    Recommended c-bet size in 3-bet pots.
    Higher spr = slightly smaller sizing (more room to maneuver).
    Wet board = larger sizing.
    """
    if board_type == 'wet':
        return 1.00 if spr < 5 else 0.75
    if board_type == 'dry':
        return 0.60 if spr < 4 else 0.50
    if board_type == 'paired':
        return 0.50
    return 0.67  # medium


def _hand_category(hero_hand_pct: float) -> tuple:
    if hero_hand_pct >= 0.88:
        return 'nut', '堅果/準堅果'
    if hero_hand_pct >= 0.76:
        return 'strong', '強手牌'
    if hero_hand_pct >= 0.63:
        return 'medium', '中強手牌（TPTK/超對）'
    if hero_hand_pct >= 0.45:
        return 'weak', '中弱手牌（中對/無對+聽牌）'
    return 'bluff', '詐唬/空氣'


def analyze_threebet_pot(
    pot_bb:          float,
    hero_hand_pct:   float = 0.70,
    stack_bb:        float = 100.0,
    hero_is_ip:      bool  = True,
    hero_was_3better: bool = True,    # True = hero 3-bet, False = hero called 3-bet
    board_type:      str   = 'medium',  # 'dry'/'medium'/'wet'/'paired'
    villain_vpip:    float = 0.28,
    villain_hands:   int   = 0,
) -> ThreeBetPotResult:
    """
    Advise on flop play in a 3-bet pot.

    Args:
        pot_bb:           Pot size at flop (after preflop 3-bet action)
        hero_hand_pct:    Hero's hand strength percentile (0-1)
        stack_bb:         Effective stack remaining at flop
        hero_is_ip:       True if hero acts last post-flop
        hero_was_3better: True if hero made the 3-bet preflop
        board_type:       Flop texture classification
        villain_vpip:     Villain's VPIP from HUD
        villain_hands:    HUD sample size
    """
    tips: List[str] = []

    # ── SPR ───────────────────────────────────────────────────────────────────
    spr = round(stack_bb / max(1.0, pot_bb), 2)

    # ── Commitment analysis ───────────────────────────────────────────────────
    commit_pct, commit_desc = _commitment_threshold(spr)
    hero_can_commit = hero_hand_pct >= commit_pct

    # ── Hand classification ───────────────────────────────────────────────────
    hand_cat, hand_zh = _hand_category(hero_hand_pct)

    # ── Villain type ──────────────────────────────────────────────────────────
    if villain_vpip >= 0.40:
        villain_type = 'fish'
    elif villain_vpip >= 0.30:
        villain_type = 'passive'
    elif villain_vpip >= 0.18:
        villain_type = 'tag'
    else:
        villain_type = 'nit'

    if villain_hands < 15:
        tips.append(f'HUD樣本不足（{villain_hands}手）')

    # ── C-bet frequency ───────────────────────────────────────────────────────
    base_cbet_freq = _cbet_frequency(hero_is_ip, board_type, hero_was_3better)

    # Adjust for villain type
    if villain_type == 'fish':
        # Fish call more → reduce bluff c-bets, increase value sizing
        base_cbet_freq *= 0.90
    elif villain_type == 'nit':
        # Nit folds more → slightly higher c-bet freq
        base_cbet_freq = min(1.0, base_cbet_freq * 1.10)

    cbet_freq = round(base_cbet_freq, 2)

    # ── C-bet sizing ──────────────────────────────────────────────────────────
    size_pct = _cbet_size(spr, board_type)
    size_bb  = round(pot_bb * size_pct, 1)

    # ── Action recommendation ─────────────────────────────────────────────────
    if hand_cat in ('nut', 'strong'):
        # Value bet always
        action    = 'cbet'
        action_zh = f'C-bet 價值（{size_pct:.0%}pot）'
        tips.append('強手牌：在3-bet底池積極下注，對手難以棄牌')

    elif hand_cat == 'medium':
        # TPTK/overpair: usually c-bet, occasionally check-call OOP
        if hero_can_commit:
            action    = 'cbet'
            action_zh = f'C-bet + 承諾（SPR={spr:.1f}，{commit_desc}可全押）'
            tips.append(f'SPR={spr:.1f}：{commit_desc}達到承諾點，可以準備下注-跟注或者下注-加注全押')
        elif not hero_is_ip:
            action    = 'check_call'
            action_zh = '過牌跟注（OOP + 非全押承諾）'
            tips.append('OOP非承諾手牌：過牌保護位置，跟注對手下注')
        else:
            action    = 'cbet'
            action_zh = f'C-bet 保護（{size_pct:.0%}pot）'
            tips.append('IP 中等手牌：C-bet 為主，但若被加注可能需要棄牌')

    elif hand_cat == 'weak':
        # Mid pair, pair + draw: check more, only cbet occasionally
        if hero_is_ip and hero_was_3better:
            action    = 'cbet' if cbet_freq > 0.60 else 'check_call'
            action_zh = (f'偶爾C-bet ({cbet_freq:.0%}頻率)' if action == 'cbet'
                         else '過牌跟注（範圍保護）')
        else:
            action    = 'check_call'
            action_zh = '過牌跟注'
        tips.append('弱手牌：3-bet底池中中對以下謹慎行事')

    else:
        # Bluff/air: c-bet at appropriate frequency for balance
        if cbet_freq >= 0.50:
            action    = 'cbet'
            action_zh = f'詐唬 C-bet（{cbet_freq:.0%}頻率，均衡需要）'
            tips.append(f'3-bet底池空氣牌：維持{cbet_freq:.0%}詐唬頻率使範圍不被讀穿')
        else:
            action    = 'check_fold'
            action_zh = '過牌棄牌（詐唬頻率不足）'

    # ── Special tips ─────────────────────────────────────────────────────────
    if spr < 3.0:
        tips.append(f'SPR={spr:.1f}（極低）：幾乎每次下注都隱含承諾，謹慎面對加注')
    if board_type == 'wet' and hero_was_3better:
        tips.append('濕潤板面3-bet底池：保護需求高，同時詐唬代表性強（有很多強聽牌）')
    if board_type == 'dry' and hero_was_3better:
        tips.append('乾燥板面：3-bet範圍優勢最大，積極C-bet')
    if not hero_was_3better and hero_is_ip:
        tips.append('IP跟注者：可以用浮注戰略，但3-bet底池中詐唬機會較少')
    if villain_type == 'fish':
        tips.append('對魚：避免詐唬，只用強手牌大注碼建底池')

    # ── Reasoning ─────────────────────────────────────────────────────────────
    board_zh = _classify_board(board_type)
    reasoning = (
        f'3-bet底池（{pot_bb:.0f}BB），SPR={spr:.1f}，'
        f'{"IP " if hero_is_ip else "OOP "}'
        f'{"3-bet者" if hero_was_3better else "跟注者"}，'
        f'{board_zh}板面，'
        f'{hand_zh}（{hero_hand_pct:.0%}），'
        f'C-bet頻率{cbet_freq:.0%}，'
        f'→ {action_zh}'
    )

    # ── Summary ─────────────────────────────────────────────────────────────
    summary_zh = (
        f'[3-bet底池] {action_zh[:20]}  '
        f'SPR={spr:.1f}  '
        f'C-bet{cbet_freq:.0%}  '
        f'{size_pct:.0%}pot={size_bb:.0f}BB'
    )[:85]

    return ThreeBetPotResult(
        action           = action,
        action_zh        = action_zh,
        cbet_frequency   = cbet_freq,
        cbet_size_pct    = size_pct,
        cbet_size_bb     = size_bb,
        spr              = spr,
        commitment_pct   = commit_pct,
        hero_can_commit  = hero_can_commit,
        commit_threshold = commit_desc,
        hero_hand_pct    = hero_hand_pct,
        hand_category    = hand_cat,
        hand_zh          = hand_zh,
        pot_bb           = pot_bb,
        stack_bb         = stack_bb,
        hero_is_ip       = hero_is_ip,
        board_type       = board_type,
        hero_was_3better = hero_was_3better,
        villain_type     = villain_type,
        villain_vpip     = villain_vpip,
        reasoning        = reasoning,
        tips             = tips,
        summary_zh       = summary_zh,
    )


def threebet_pot_summary(r: ThreeBetPotResult) -> str:
    """Single-line overlay summary (<=85 chars)."""
    return r.summary_zh[:85]
