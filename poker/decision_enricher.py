"""
P1 決策豐富化模組 — 將基礎 Decision 接入四個進階模組：

  1. Range Advantage / Nut Advantage  (range_advantage_quantifier, nut_advantage_analyzer)
  2. ICM 壓力調整                      (icm_advisor)
  3. 精確注碼 + GTO 混合頻率            (bet_sizing_ev, mixed_strategy_advisor)
  4. SPR 承諾門檻文字結論               (spr_commitment)

用法（在 main.py 分析迴圈中）：
    from poker.decision_enricher import enrich, BoardContext, TournamentContext

    ctx = BoardContext(community_cards, hero_pos, villain_pos, hand_type_zh, equity)
    trn = TournamentContext(spots_from_money=2, hero_stack_bb=30, avg_stack_bb=55)
    decision = enrich(base_decision, state, ctx, trn)
"""

from dataclasses import dataclass, field
from typing import List, Optional

from poker.decision import Decision, GameState

# ── 卡牌解析工具 ──────────────────────────────────────────────────────────────

_RANK_INT = {
    '2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,
    '9':9,'T':10,'J':11,'Q':12,'K':13,'A':14,
}
_RANK_STR = {v:k for k,v in _RANK_INT.items()}

def _rank(card: str) -> int:
    return _RANK_INT.get(card[0].upper(), 0) if card else 0


def _parse_board(community: List[str]):
    """
    解析前三張公牌（翻牌），回傳 range/nut advantage 所需的參數 dict。
    community 少於 3 張時回傳 None。
    """
    valid = [c for c in (community or []) if c and len(c) >= 2]
    if len(valid) < 3:
        return None
    flop = valid[:3]
    ranks = sorted([_rank(c) for c in flop], reverse=True)
    suits = [c[-1].lower() for c in flop]

    is_paired    = len(set(ranks)) < 3
    is_monotone  = len(set(suits)) == 1
    flush_draw   = (not is_monotone) and (len(set(suits)) == 2)  # 2 同花色=聽 flush
    flush_poss   = is_monotone or flush_draw
    gap          = ranks[0] - ranks[2]
    str_poss     = gap <= 4 and not is_paired

    if is_monotone:       texture = 'monotone'
    elif is_paired:       texture = 'paired'
    elif gap <= 4:        texture = 'wet'
    elif gap <= 7:        texture = 'medium'
    else:                 texture = 'dry'

    return {
        'high':         ranks[0],
        'mid':          ranks[1],
        'low':          ranks[2],
        'high_str':     _RANK_STR.get(ranks[0], '?'),
        'texture':      texture,
        'is_paired':    is_paired,
        'is_monotone':  is_monotone,
        'flush_poss':   flush_poss,
        'str_poss':     str_poss,
    }


def _hand_class(hand_type_zh: str, equity: float) -> str:
    """將中文牌型標籤對應到 mixed_strategy_advisor 的 hand_class。"""
    t = hand_type_zh.lower()
    if '同花' in t or '葫蘆' in t or '四條' in t or '同花順' in t:
        return 'flush_plus'
    if '順子' in t:    return 'straight'
    if '三條' in t or 'set' in t:  return 'set'
    if '兩對' in t:    return 'two_pair'
    if equity >= 0.82: return 'monster'
    if equity >= 0.70: return 'overpair'
    if equity >= 0.58: return 'top_pair'
    if equity >= 0.47: return 'middle_pair'
    if equity >= 0.35: return 'draw'
    return 'air'


def _street(n_comm: int) -> str:
    if n_comm >= 5: return 'river'
    if n_comm >= 4: return 'turn'
    if n_comm >= 3: return 'flop'
    return 'preflop'


def _is_ip(hero_pos: str) -> bool:
    return hero_pos.upper() in {'BTN', 'CO', 'HJ', 'LP'}


# ── 輸入 Context ──────────────────────────────────────────────────────────────

@dataclass
class BoardContext:
    community_cards: List[str]
    hero_pos:        str   = 'BTN'
    villain_pos:     str   = 'BB'
    hand_type_zh:    str   = ''
    equity:          float = 0.5


@dataclass
class TournamentContext:
    enabled:           bool  = False
    spots_from_money:  int   = 0    # 0=不在泡沫圈
    hero_stack_bb:     float = 100.0
    avg_stack_bb:      float = 100.0
    total_players:     int   = 9


# ── 主整合函式 ────────────────────────────────────────────────────────────────

def enrich(
    base:   Decision,
    state:  GameState,
    board_ctx:   Optional[BoardContext]      = None,
    tourney_ctx: Optional[TournamentContext] = None,
) -> Decision:
    """
    豐富化 Decision：填入 P1 欄位後回傳同一物件。
    所有模組呼叫均有 try/except 保護，任一失敗不影響基礎決策。
    """
    ctx = board_ctx or BoardContext(state.community_cards)
    trn = tourney_ctx or TournamentContext()

    board = _parse_board(ctx.community_cards)
    n_comm = len([c for c in ctx.community_cards if c])
    street = _street(n_comm)
    in_pos = _is_ip(ctx.hero_pos)
    pot_bb = state.pot
    stack_bb = state.hero_stack

    # ── 1. Range Advantage ──────────────────────────────────────────
    try:
        if board and n_comm >= 3:
            from poker.range_advantage_quantifier import quantify_range_advantage
            ra = quantify_range_advantage(
                aggressor_position=ctx.hero_pos.lower(),
                defender_position=ctx.villain_pos.lower(),
                board_high_card=board['high'],
                board_mid_card=board['mid'],
                board_low_card=board['low'],
                board_texture=board['texture'],
                is_paired_board=board['is_paired'],
                is_monotone=board['is_monotone'],
            )
            who = ra.who_has_advantage.upper()
            hero_up = ctx.hero_pos.upper()
            if who == hero_up:
                adv_zh = f"我方範圍優勢 {ra.score_1_to_10}/10"
                agg_freq = ra.aggressor_bet_freq
            elif who == ctx.villain_pos.upper():
                adv_zh = f"對方範圍優勢 {10 - ra.score_1_to_10 + 1}/10"
                agg_freq = ra.aggressor_bet_freq
            else:
                adv_zh = "範圍均衡"
                agg_freq = ra.aggressor_bet_freq
            base.range_adv_label = adv_zh
            base.range_adv_score = ra.score_1_to_10
    except Exception:
        pass

    # ── 2. Nut Advantage ────────────────────────────────────────────
    try:
        if board and n_comm >= 3:
            from poker.nut_advantage_analyzer import analyze_nut_advantage
            na = analyze_nut_advantage(
                pfr_pos=ctx.hero_pos.lower(),
                caller_pos=ctx.villain_pos.lower(),
                board_high=board['high_str'],
                board_type=board['texture'],
                board_paired=board['is_paired'],
                flush_possible=board['flush_poss'],
                straight_possible=board['str_poss'],
            )
            hero_up = ctx.hero_pos.lower()
            if na.nut_advantage == 'pfr' and hero_up in ('btn','co','hj','sb','utg','hj','lj'):
                nut_zh = f"堅果優勢：我方（{na.pfr_nut_pct:.0%} vs {na.caller_nut_pct:.0%}）"
                if na.should_overbet:
                    nut_zh += f" → 可 overbet {na.overbet_size}"
            elif na.nut_advantage == 'caller':
                nut_zh = f"堅果優勢：對方（{na.caller_nut_pct:.0%} vs {na.pfr_nut_pct:.0%}）"
            else:
                nut_zh = "堅果均衡"
            base.nut_adv_label = nut_zh
    except Exception:
        pass

    # ── 3. 精確注碼 + GTO 混合頻率 ─────────────────────────────────
    try:
        if street != 'preflop' and pot_bb > 0:
            from poker.bet_sizing_ev import compare_bet_sizes
            bev = compare_bet_sizes(
                pot_bb=float(pot_bb),
                hero_equity=ctx.equity,
                street=street,
                eff_stack_bb=float(stack_bb),
            )
            opt = bev.optimal
            size_pct_disp = int(opt.pct * 100)
            base.precise_size_pct   = opt.pct
            base.precise_size_label = f"{size_pct_disp}% pot（{opt.bet_bb:.0f}bb）EV+{opt.ev_vs_check:.1f}bb"
    except Exception:
        pass

    try:
        if street != 'preflop' and pot_bb > 0:
            from poker.mixed_strategy_advisor import advise_mixed_strategy
            hclass = _hand_class(ctx.hand_type_zh, ctx.equity)
            mix = advise_mixed_strategy(
                hero_hand_class=hclass,
                board_type=board['texture'] if board else 'medium',
                hero_pos='IP' if in_pos else 'OOP',
                street=street,
                spot_type='cbet',
                pot_bb=float(pot_bb),
                hero_equity=ctx.equity,
                spr=state.hero_stack / state.pot if state.pot > 0 else 10.0,
            )
            base.gto_bet_freq   = mix.adj_bet_freq
            base.gto_check_freq = mix.gto_check_freq
            if mix.should_mix:
                base.gto_mix_note = (
                    f"GTO 混合：下注 {mix.adj_bet_freq:.0%} / 過牌 {mix.gto_check_freq:.0%}"
                    f"（{int(mix.bet_size_pct*100)}% pot）"
                )
            else:
                action_zh = "下注" if mix.recommended_action == 'bet' else "過牌"
                base.gto_mix_note = f"GTO：純{action_zh}（{mix.adj_bet_freq:.0%}）"
    except Exception:
        pass

    # ── 4. SPR 承諾門檻 ────────────────────────────────────────────
    try:
        if pot_bb > 0 and stack_bb > 0:
            # 手牌型別映射到 spr_commitment 的 hand_type key
            htype = _spr_hand_type(ctx.hand_type_zh, ctx.equity)
            from poker.spr_commitment import analyze_spr_commitment
            sc = analyze_spr_commitment(
                pot_bb=float(pot_bb),
                stack_bb=float(stack_bb),
                hand_type=htype,
                is_ip=in_pos,
            )
            verdict = sc.summary_zh
            if sc.should_commit:
                verdict += f" ✓（EV全下 +{sc.ev_commit:.0f}bb vs 控牌 +{sc.ev_no_commit:.0f}bb）"
            else:
                verdict += f" ✗（控牌 EV 較優）"
            base.spr_verdict = verdict
    except Exception:
        pass

    # ── 5. ICM 壓力 ─────────────────────────────────────────────────
    try:
        if trn.enabled and trn.spots_from_money > 0:
            from poker.icm_advisor import calc_bubble_advice
            icm = calc_bubble_advice(
                spots_from_money=trn.spots_from_money,
                hero_stack_bb=trn.hero_stack_bb,
                avg_stack_bb=trn.avg_stack_bb,
                total_players=trn.total_players,
            )
            premium_pct = int(icm.equity_premium * 100)
            rank_zh = {'big':'大籌碼','medium':'中籌碼','short':'短籌碼','micro':'極短'}.get(
                icm.hero_rank, icm.hero_rank)
            action_zh = {'survive':'生存優先','attack_short':'攻擊短碼','normal':'正常打牌',
                         'chip_lead':'積極擴大'}.get(icm.priority_action, icm.priority_action)
            base.icm_note = (
                f"ICM 壓力 {icm.icm_pressure:.0%}｜{rank_zh}｜{action_zh}"
                f"｜跟注需 {icm.call_threshold:.0%}+ 勝率（+{premium_pct}% 溢價）"
            )
            base.icm_equity_premium = icm.equity_premium
    except Exception:
        pass

    return base


# ── SPR hand_type 映射 ────────────────────────────────────────────────────────

_SPR_HAND_MAP = {
    '怪獸': 'full_house_plus', '強牌': 'flush', '中等': 'tpgk',
    '聽牌': 'tpwk', '弱牌': 'tpwk',
}

def _spr_hand_type(hand_type_zh: str, equity: float) -> str:
    for kw, ht in _SPR_HAND_MAP.items():
        if kw in hand_type_zh:
            return ht
    if equity >= 0.80: return 'full_house_plus'
    if equity >= 0.70: return 'flush'
    if equity >= 0.58: return 'tpgk'
    return 'tpwk'
