"""
後門聽牌半詐唬顧問 (Backdoor Draw Semi-bluff Advisor)

場景：翻牌圈（Flop），英雄沒有成手牌也沒有主要聽牌（無花色聽牌/無順子聽牌），
但有「後門聽牌」（Backdoor Draw），即需要轉牌和河牌才能完成的聽牌。

為什麼重要？
  大多數玩家遇到後門聽牌會直接過牌-棄牌（check-fold），但這是錯誤的：
  - 後門花色聽牌（兩張同花色）≈ 4.2% 額外勝率
  - 後門順子聽牌（3連張）≈ 3-5% 額外勝率
  - 同時有兩個後門聽牌 ≈ 7-9% 額外勝率

  加上底牌的超張（overcard）勝率，很多看似只能棄牌的手牌實際上可以半詐唬。

後門花色聽牌計算（翻牌圈）：
  P(完成花色) = P(轉牌 suit) × P(河牌 suit)
             ≈ (10/47) × (9/46) ≈ 4.16%

後門順子聽牌（翻牌圈，3 張牌連接）：
  強後門順（3 連張，如 J-T-x 已有兩張）≈ 4-5%
  弱後門順（JT 結合一張離散牌）≈ 2-3%

情境判斷：
  - 對手 C-bet 很高（>65%）→ 對手有很多弱手牌在 bet，可以半詐唬
  - 牌面乾燥（dry board）→ 對手 check 不太可能有強牌，半詐唬效果好
  - 多人底池 → 不建議半詐唬，後門勝算稀釋

推薦情境（可考慮半詐唬）：
  1. 後門花色聽牌 + 超張（>44% adjusted equity）
  2. 雙後門聽牌（花色 + 順子）
  3. 對手 C-bet 高（>70%）且牌面相對乾燥
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class BackdoorDrawResult:
    # 後門聽牌偵測
    has_backdoor_flush:    bool
    has_backdoor_straight: bool
    backdoor_type:         str   # 'strong'/'medium'/'weak'/'none'
    n_backdoor_draws:      int   # 0, 1, or 2

    # 勝率分析
    backdoor_equity_pct:   float  # 後門聽牌的額外勝率貢獻（%，非 0-1）
    raw_equity:            float  # MC 原始勝率（0-1）
    adjusted_equity:       float  # raw_equity + backdoor contribution
    primary_draw_outs:     int    # 主要聽牌出張（0 if no primary draw）

    # 建議
    should_semi_bluff:     bool
    bet_frequency:         float  # 推薦下注頻率（0-1）
    sizing_pct:            float  # 推薦注碼（佔底池比例）
    sizing_bb:             float  # 推薦注碼（BB）
    continuation_type:     str    # 'semibluff'/'thin_value'/'check_call'/'check_fold'
    continuation_zh:       str

    # 情境
    pot_bb:                float
    board_is_wet:          bool
    villain_cbet_pct:      float
    n_opponents:           int

    # 說明
    reasoning:             str
    tips:                  List[str]
    summary_zh:            str


def _detect_backdoor_flush(hole: List[str], board: List[str]) -> bool:
    """
    True if hero has two hole cards of the same suit that matches AT LEAST one board card
    (runner-runner flush possible).
    """
    if len(hole) < 2:
        return False
    s0 = hole[0][-1].lower()
    s1 = hole[1][-1].lower()
    if s0 != s1:
        return False   # hole cards not same suit

    board_suits = [c[-1].lower() for c in board]
    matching = board_suits.count(s0)
    # For runner-runner: need exactly 2 (hero has 2, board has 1 = 3 total, need 2 more)
    # OR need 0 board cards of that suit (pure runner-runner)
    # Standard: hero has 2 of same suit, board has 0 or 1 matching = backdoor
    return matching <= 1   # 0 or 1 matching board card = backdoor flush possible


def _rank_val(r: str) -> int:
    return {'2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,
            'T':10,'J':11,'Q':12,'K':13,'A':14}.get(r.upper(), 0)


def _detect_backdoor_straight(hole: List[str], board: List[str]) -> str:
    """
    Detect backdoor straight draws where hero's hole cards contribute to the draw.

    Returns: 'strong' (3 ranks in a 5-wide window, at least 1 from hero)
             'medium' (2 ranks in window including 1 hero card)
             'none'

    Requires at least one hole card in the window so we don't flag board-only draws.
    """
    if len(hole) < 2:
        return 'none'

    hole_ranks = {_rank_val(c[:-1]) for c in hole}
    all_ranks  = hole_ranks | {_rank_val(c[:-1]) for c in board}

    for lo in range(2, 15):
        hi = lo + 4
        in_window      = {r for r in all_ranks  if lo <= r <= hi}
        hole_in_window = {r for r in hole_ranks if lo <= r <= hi}
        if len(hole_in_window) >= 1 and len(in_window) >= 3:
            return 'strong'

    for lo in range(2, 15):
        hi = lo + 4
        in_window      = {r for r in all_ranks  if lo <= r <= hi}
        hole_in_window = {r for r in hole_ranks if lo <= r <= hi}
        if len(hole_in_window) >= 1 and len(in_window) >= 2:
            return 'medium'

    return 'none'


def _backdoor_equity_pct(has_bf: bool, str_type: str) -> float:
    """
    Approximate equity % contributed by backdoor draws (on flop, 2 cards to come).

    Backdoor flush: (10/47)*(9/46) ≈ 4.16%
    Strong backdoor straight: ~4.5% (connects and then fills)
    Medium backdoor straight: ~2.5%
    """
    total = 0.0
    if has_bf:
        total += 4.2
    if str_type == 'strong':
        total += 4.5
    elif str_type == 'medium':
        total += 2.5
    return round(total, 1)


def analyze_backdoor_draw(
    hole_cards:         List[str],
    community:          List[str],   # exactly 3 cards (flop)
    raw_equity:         float = 0.35,
    primary_draw_outs:  int   = 0,   # from outs.py (flush/OESD/gutshot)
    pot_bb:             float = 10.0,
    villain_cbet_pct:   float = 0.60,
    n_opponents:        int   = 1,
    board_is_wet:       bool  = False,
) -> BackdoorDrawResult:
    """
    Analyze whether backdoor draws justify a semi-bluff bet on the flop.

    Args:
        hole_cards:        Hero's 2 hole cards
        community:         3 flop cards
        raw_equity:        Hero's MC equity (0-1)
        primary_draw_outs: Direct draw outs (from outs.py). 0 = no primary draw.
        pot_bb:            Pot size in BB
        villain_cbet_pct:  Villain's c-bet percentage (from HUD)
        n_opponents:       Number of opponents
        board_is_wet:      True if many draws possible
    """
    tips: List[str] = []

    # ── Detect backdoor draws ─────────────────────────────────────────────────
    hole  = [c.strip() for c in hole_cards if c.strip()]
    board = [c.strip() for c in community if c.strip()]

    has_bf     = _detect_backdoor_flush(hole, board) if len(board) >= 3 else False
    str_type   = _detect_backdoor_straight(hole, board) if len(board) >= 3 else 'none'
    has_bs     = str_type != 'none'
    n_draws    = int(has_bf) + int(has_bs)

    backdoor_pct = _backdoor_equity_pct(has_bf, str_type)

    # ── Adjusted equity ──────────────────────────────────────────────────────
    adjusted_eq = min(0.80, raw_equity + backdoor_pct / 100.0)

    # ── Backdoor type label ───────────────────────────────────────────────────
    if n_draws == 0:
        bdr_type = 'none'
    elif n_draws == 2:
        bdr_type = 'strong'
    elif has_bf:
        bdr_type = 'medium'
    else:
        bdr_type = str_type   # 'strong'/'medium'

    # ── Semi-bluff decision ───────────────────────────────────────────────────
    # Conditions favoring semi-bluff:
    # 1. Adjusted equity >= 35% (after backdoor bonus)
    # 2. Single opponent (bluff loses value multiway)
    # 3. Villain c-bets high (their check range is weak = good to attack)
    # 4. Dry board (our bluff has fewer competitors)

    villain_check_is_weak = villain_cbet_pct >= 0.65   # checks less on dry boards
    multiway = n_opponents >= 2

    base_freq = 0.0
    if multiway:
        should_semi_bluff = False
        base_freq = 0.0
        tips.append(f'多人底池（{n_opponents}人）：不建議純後門半詐唬')
    elif primary_draw_outs >= 8:
        # Strong primary draw → this module isn't needed (handle in outs.py)
        should_semi_bluff = True
        base_freq = 0.70
        tips.append('已有強主要聽牌，後門聽牌為額外保險')
    elif adjusted_eq >= 0.45:
        should_semi_bluff = True
        base_freq = 0.65 if villain_check_is_weak else 0.45
        if villain_check_is_weak:
            tips.append(f'對手 C-bet {villain_cbet_pct:.0%}（高）：過牌範圍弱，好機會詐唬')
    elif adjusted_eq >= 0.38 and n_draws >= 1:
        should_semi_bluff = True
        base_freq = 0.40 if villain_check_is_weak else 0.25
        tips.append(f'後門勝率 {backdoor_pct:.1f}% 使此手牌調整後勝率 {adjusted_eq:.0%}，邊緣半詐唬')
    elif adjusted_eq >= 0.33 and n_draws == 2:
        should_semi_bluff = True
        base_freq = 0.30
        tips.append('雙後門聽牌提供足夠折疊勝算')
    else:
        should_semi_bluff = False
        base_freq = 0.0

    # Wet board reduces pure bluff frequency (villain likely to c-bet strong)
    if board_is_wet and should_semi_bluff:
        base_freq *= 0.75
        tips.append('牌面潮濕：降低半詐唬頻率（對手 C-bet 範圍更強）')

    bet_frequency = round(min(1.0, base_freq), 2)

    # ── Sizing ───────────────────────────────────────────────────────────────
    # Small sizing for backdoor draws: charges a little, doesn't over-commit
    if adjusted_eq >= 0.45:
        sizing_pct = 0.50   # half pot
    elif adjusted_eq >= 0.38:
        sizing_pct = 0.33   # 1/3 pot
    else:
        sizing_pct = 0.25

    sizing_bb = round(pot_bb * sizing_pct, 1)

    # ── Continuation type ─────────────────────────────────────────────────────
    if not should_semi_bluff:
        if primary_draw_outs >= 4:
            cont_type = 'check_call'
            cont_zh   = '過牌跟注（有直接聽牌）'
        else:
            cont_type = 'check_fold'
            cont_zh   = '過牌棄牌'
    elif adjusted_eq >= 0.50:
        cont_type = 'thin_value'
        cont_zh   = '薄價值下注（兼顧保護）'
    else:
        cont_type = 'semibluff'
        cont_zh   = '半詐唬'

    # ── Reasoning ─────────────────────────────────────────────────────────────
    draw_parts = []
    if has_bf:
        draw_parts.append('後門花色聽牌(+4.2%)')
    if has_bs:
        draw_parts.append(f'後門順子({str_type})(+{4.5 if str_type=="strong" else 2.5:.1f}%)')
    if not draw_parts:
        draw_parts = ['無後門聽牌']

    reasoning = (
        f'{" + ".join(draw_parts)}，調整後勝率 {raw_equity:.0%}→{adjusted_eq:.0%}'
        f'，{"建議" if should_semi_bluff else "不建議"}半詐唬'
        f'（{cont_zh}）'
    )

    # ── Summary ────────────────────────────────────────────────────────────────
    if n_draws == 0:
        summary_zh = f'[後門] 無後門聽牌→{cont_zh[:10]}'
    elif should_semi_bluff:
        draw_txt = '花+順後門' if n_draws == 2 else ('後門花色' if has_bf else f'後門順子({str_type})')
        summary_zh = (
            f'[後門] {draw_txt}  '
            f'勝率{raw_equity:.0%}+{backdoor_pct:.1f}%={adjusted_eq:.0%}  '
            f'{cont_zh[:6]}  '
            f'{sizing_pct:.0%}pot={sizing_bb:.0f}BB'
        )[:85]
    else:
        summary_zh = f'[後門] +{backdoor_pct:.1f}%  調整勝率{adjusted_eq:.0%}→{cont_zh[:8]}'

    return BackdoorDrawResult(
        has_backdoor_flush    = has_bf,
        has_backdoor_straight = has_bs,
        backdoor_type         = bdr_type,
        n_backdoor_draws      = n_draws,
        backdoor_equity_pct   = backdoor_pct,
        raw_equity            = raw_equity,
        adjusted_equity       = adjusted_eq,
        primary_draw_outs     = primary_draw_outs,
        should_semi_bluff     = should_semi_bluff,
        bet_frequency         = bet_frequency,
        sizing_pct            = sizing_pct,
        sizing_bb             = sizing_bb,
        continuation_type     = cont_type,
        continuation_zh       = cont_zh,
        pot_bb                = pot_bb,
        board_is_wet          = board_is_wet,
        villain_cbet_pct      = villain_cbet_pct,
        n_opponents           = n_opponents,
        reasoning             = reasoning,
        tips                  = tips,
        summary_zh            = summary_zh,
    )


def backdoor_draw_summary(r: BackdoorDrawResult) -> str:
    """Single-line overlay summary (<=85 chars)."""
    return r.summary_zh[:85]
