"""
多街承諾計劃顧問 (Multi-street Commitment Plan Advisor)

核心問題：「我的三街計劃是什麼？」

把翻牌圈的手牌強度、SPR、勝率整合成一個完整的三街計劃：
  - 每一街的行動（下注/過牌/加注/棄牌）
  - 每一街的注碼（底池比例）
  - 是否應該三街全注（幾何注碼）
  - 條件式計劃（例如："轉牌空白再下注，打磚牌放棄"）

幾何注碼原理（Geometric Sizing）：
  若目標是三街入底，每次下注 X% 底池使得 SPR=1 恰好在河牌：
    3 streets: ~33% pot 每次
    2 streets: ~50% pot 每次
    1 street:  ~pot 每次 (PSB)

  考慮玩家跟注後底池增大：
    若每次注碼 = f × P，跟注後底池 = P + 2fP = P(1+2f)
    三街後籌碼/底池 = SPR / [(1+2f)^3]
    設等於 1：f = ((SPR)^(1/3) - 1) / 2
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class StreetAction:
    action:       str    # 'BET' / 'CHECK' / 'CHECK_RAISE' / 'ALL_IN' / 'GIVE_UP'
    action_zh:    str
    size_pct:     float  # 注碼佔底池比例（0 = 不下注）
    size_bb:      float  # 實際 BB 數
    condition:    str    # 何時觸發此行動（空字串=無條件）


@dataclass
class StreetPlan:
    # 計劃摘要
    hand_category:   str    # 'nuts'/'strong'/'tpgk'/'medium'/'draw'/'weak'
    equity:          float
    spr:             float
    streets_left:    int    # 翻牌=3, 轉牌=2, 河牌=1

    # 各街計劃
    current:         StreetAction
    next_street:     Optional[StreetAction]
    final_street:    Optional[StreetAction]

    # 承諾分析
    commit_threshold: float    # SPR 低於此值時全下（2.0 = pot-committed）
    is_committed:     bool     # 是否已達承諾門檻
    geometric_size_pct: float  # 幾何注碼建議（底池%）

    # 摘要文字
    plan_zh:          str      # 整個計劃的一句話摘要
    key_note:         str      # 最重要的決策提示
    tips:             List[str] = field(default_factory=list)


# ── 手牌類別定義 ────────────────────────────────────────────────────────────────
# equity ranges for each category
_CATEGORY_MAP = [
    (0.75, 'nuts'),    # 75%+ = 接近堅果
    (0.62, 'strong'),  # 62-75% = 強牌（頂對好踢腳+）
    (0.50, 'tpgk'),    # 50-62% = 頂對好踢腳
    (0.38, 'medium'),  # 38-50% = 中等牌力
    (0.25, 'draw'),    # 25-38% = 聽牌/弱牌
    (0.00, 'weak'),    # <25% = 弱牌/純詐唬
]

_CAT_ZH = {
    'nuts':   '近堅果',
    'strong': '強牌',
    'tpgk':   '頂對',
    'medium': '中等牌',
    'draw':   '聽牌/弱',
    'weak':   '弱牌',
}


def _equity_to_category(equity: float, has_draw: bool = False) -> str:
    for threshold, cat in _CATEGORY_MAP:
        if equity >= threshold:
            if has_draw and cat == 'medium':
                return 'draw'
            return cat
    return 'weak'


def _geometric_size(spr: float, streets_left: int) -> float:
    """
    計算幾何注碼（為了在 streets_left 街內剛好打完籌碼）。
    返回底池比例（0-1）。
    """
    if spr <= 1.0 or streets_left <= 0:
        return 1.0  # shove
    # f = (spr^(1/n) - 1) / 2  where n = streets_left
    ratio = spr ** (1.0 / streets_left)
    f = (ratio - 1.0) / 2.0
    return min(1.0, max(0.25, round(f, 2)))


def _make_action(
    action:    str,
    action_zh: str,
    size_pct:  float,
    pot_bb:    float,
    condition: str = '',
) -> StreetAction:
    return StreetAction(
        action    = action,
        action_zh = action_zh,
        size_pct  = size_pct,
        size_bb   = round(pot_bb * size_pct, 1),
        condition = condition,
    )


def plan_streets(
    equity:          float,
    pot_bb:          float,
    stack_bb:        float,
    community_len:   int,    # 3=flop, 4=turn, 5=river
    has_draw:        bool   = False,
    villain_vpip:    float  = 0.28,  # 影響注碼大小
    is_oop:          bool   = False,  # OOP 手牌計劃更保守
    hand_category:   Optional[str] = None,  # 可手動指定
) -> StreetPlan:
    """
    生成翻牌/轉牌/河牌的完整三街計劃。

    Args:
        equity:         當前勝率（0-1）
        pot_bb:         當前底池（BB）
        stack_bb:       有效籌碼（BB）
        community_len:  公牌數量（3/4/5）
        has_draw:       是否有重要聽牌
        villain_vpip:   對手 VPIP（影響取值注碼）
        is_oop:         英雄是否無位置
        hand_category:  手動指定手牌類別（預設自動判斷）
    """
    spr = stack_bb / max(pot_bb, 0.1)
    streets_left = max(1, 5 - community_len + 1)  # flop=3, turn=2, river=1

    cat = hand_category or _equity_to_category(equity, has_draw)
    geo_pct = _geometric_size(spr, streets_left)

    commit_threshold = 2.0  # SPR < 2 = pot-committed
    is_committed = spr <= commit_threshold

    # ── 選擇注碼風格：魚用大注，正規用幾何注 ──────────────────────────
    if villain_vpip >= 0.40:
        value_pct = min(1.0, geo_pct + 0.15)   # vs 魚加大
    elif villain_vpip <= 0.20:
        value_pct = max(0.30, geo_pct - 0.10)  # vs 緊玩家縮小
    else:
        value_pct = geo_pct

    if is_oop:
        value_pct = min(value_pct, 0.75)  # OOP 上限 75%

    # ── 依手牌類別和 SPR 建立計劃 ──────────────────────────────────────
    plan = _build_plan(
        cat         = cat,
        equity      = equity,
        spr         = spr,
        pot_bb      = pot_bb,
        value_pct   = value_pct,
        geo_pct     = geo_pct,
        community_len = community_len,
        streets_left  = streets_left,
        has_draw    = has_draw,
        is_oop      = is_oop,
        is_committed = is_committed,
    )

    return StreetPlan(
        hand_category      = cat,
        equity             = equity,
        spr                = spr,
        streets_left       = streets_left,
        current            = plan['current'],
        next_street        = plan.get('next'),
        final_street       = plan.get('final'),
        commit_threshold   = commit_threshold,
        is_committed       = is_committed,
        geometric_size_pct = geo_pct,
        plan_zh            = plan['plan_zh'],
        key_note           = plan['key_note'],
        tips               = plan.get('tips', []),
    )


def _build_plan(
    cat, equity, spr, pot_bb, value_pct, geo_pct,
    community_len, streets_left, has_draw, is_oop, is_committed,
) -> dict:
    P = pot_bb
    tips = []

    # ── NUTS 近堅果（75%+）───────────────────────────────────────────────
    if cat == 'nuts':
        if spr <= 1.5:
            curr = _make_action('ALL_IN', '全下（幾何完成）', 1.0, P)
            tips.append(f'SPR={spr:.1f}，全下是唯一選擇，最大化取值')
            return dict(current=curr, plan_zh=f'[堅果 SPR={spr:.1f}] 全下',
                        key_note='不要慢打，立刻全下', tips=tips)

        curr_size = min(value_pct, 0.80) if is_oop else value_pct
        curr = _make_action('BET', f'下注{curr_size:.0%}底池', curr_size, P)

        if streets_left >= 3:  # on flop
            nxt_pct = _geometric_size(spr / (1 + 2 * curr_size), streets_left - 1)
            nxt = _make_action('BET', f'繼續 barrel {nxt_pct:.0%}底池', nxt_pct,
                               P * (1 + 2 * curr_size))
            fin_pct = 1.0 if spr > 3 else nxt_pct + 0.2
            fin = _make_action('ALL_IN' if spr > 4 else 'BET',
                               '河牌全下' if spr > 4 else f'河牌{min(fin_pct,1.0):.0%}底池',
                               min(fin_pct, 1.0), P * (1 + 2 * nxt_pct))
            plan_zh = (f'[{_CAT_ZH[cat]} SPR={spr:.1f}] '
                       f'翻{curr_size:.0%}→轉{nxt_pct:.0%}→河全下（幾何注）')
            key_note = '三街幾何入底，不要過牌慢打失去主動權'
        elif streets_left == 2:  # on turn
            nxt_pct = _geometric_size(spr / (1 + 2 * curr_size), 1)
            fin = _make_action('ALL_IN', '河牌全下', 1.0,
                               P * (1 + 2 * curr_size))
            nxt = fin
            plan_zh = f'[{_CAT_ZH[cat]} SPR={spr:.1f}] 轉{curr_size:.0%}→河全下'
            key_note = '轉牌下注後河牌必須全下，不要猶豫'
        else:  # on river
            plan_zh = f'[{_CAT_ZH[cat]} SPR={spr:.1f}] 河牌全下取值'
            key_note = '河牌堅果，最大化取值'
            nxt = fin = None

        tips.append(f'幾何注碼建議 {geo_pct:.0%} 底池/街，確保三街打完籌碼')
        return dict(current=curr, next=nxt, final=fin,
                    plan_zh=plan_zh, key_note=key_note, tips=tips)

    # ── STRONG 強牌（62-75%）──────────────────────────────────────────────
    if cat == 'strong':
        if is_committed:
            curr = _make_action('BET', '全下（已承諾）', 1.0, P)
            return dict(current=curr, plan_zh=f'[強牌 SPR={spr:.1f}] 已承諾全下',
                        key_note='SPR<2 表示已底池承諾，全下即可', tips=tips)

        curr = _make_action('BET', f'下注{value_pct:.0%}', value_pct, P)
        if streets_left >= 3:
            nxt = _make_action('BET', f'轉牌 barrel {min(value_pct+0.1, 0.80):.0%}',
                               min(value_pct + 0.1, 0.80),
                               P * (1 + 2 * value_pct),
                               condition='空白轉牌')
            bad_nxt = _make_action('CHECK', '轉牌過牌（危險公牌）', 0, P * (1 + 2 * value_pct),
                                   condition='危險轉牌（對子/順/同花完成）')
            fin = _make_action('BET', '河牌繼續取值或全下', min(value_pct + 0.2, 1.0),
                               P * 2, condition='轉牌繼續且未改善')
            plan_zh = (f'[{_CAT_ZH[cat]} SPR={spr:.1f}] '
                       f'翻{value_pct:.0%}→轉barrel（空白）→河取值')
            key_note = '三街取值計劃；危險轉牌需過牌保護，河牌不蓋過牌'
        elif streets_left == 2:
            nxt = _make_action('BET', f'河牌{min(value_pct+0.15,1.0):.0%}取值',
                               min(value_pct + 0.15, 1.0), P * (1 + 2 * value_pct))
            fin = None
            plan_zh = f'[{_CAT_ZH[cat]} SPR={spr:.1f}] 轉{value_pct:.0%}→河取值'
            key_note = '轉牌下注計劃，河牌繼續取值'
        else:
            plan_zh = f'[{_CAT_ZH[cat]} SPR={spr:.1f}] 河牌取值下注'
            key_note = '強牌河牌，選擇有利注碼取值'
            nxt = fin = None

        tips.append(f'強牌取值：vs VPIP高對手加大注碼，vs 緊玩家保守')
        return dict(current=curr, next=nxt, final=fin,
                    plan_zh=plan_zh, key_note=key_note, tips=tips)

    # ── TPGK 頂對好踢腳（50-62%）─────────────────────────────────────────
    if cat == 'tpgk':
        if spr <= 3:
            curr = _make_action('BET', '下注（短碼承諾）', min(value_pct, 0.75), P)
            plan_zh = f'[頂對 SPR={spr:.1f}] 短碼，一次性注碼計劃'
            key_note = 'SPR低，一次取值後面對加注考慮全下或棄牌'
            tips.append('SPR<3：不要慢打頂對，一次下注建立底池')
            return dict(current=curr, plan_zh=plan_zh, key_note=key_note, tips=tips)

        curr = _make_action('BET', f'下注{min(value_pct, 0.60):.0%}（控底池）',
                            min(value_pct, 0.60), P)
        if streets_left >= 3:
            nxt = _make_action('BET', '轉牌控底池 45-55%',
                               0.50, P * (1 + 2 * min(value_pct, 0.60)),
                               condition='對手未加注且轉牌安全')
            nxt_fold = _make_action('CHECK', '轉牌過牌（面臨加注/危險公牌）',
                                    0, P, condition='轉牌加注或惡化')
            fin = _make_action('CHECK', '河牌謹慎（根據對手行動）', 0.40, P * 1.8,
                               condition='轉牌跟注後河牌謹慎取值')
            plan_zh = (f'[{_CAT_ZH[cat]} SPR={spr:.1f}] '
                       f'翻{min(value_pct,0.60):.0%}（控底池）→轉50%→河謹慎')
            key_note = '頂對：控底池策略，面臨大注要重新評估牌力'
        elif streets_left == 2:
            nxt = _make_action('BET', f'河牌取值{min(value_pct,0.55):.0%}',
                               min(value_pct, 0.55), P * 1.5,
                               condition='河牌未惡化')
            fin = None
            plan_zh = f'[{_CAT_ZH[cat]} SPR={spr:.1f}] 轉→河控底池取值'
            key_note = '頂對控底池，河牌注碼不要太大'
        else:
            plan_zh = f'[{_CAT_ZH[cat]} SPR={spr:.1f}] 河牌中等注碼取值'
            key_note = '頂對河牌：中等注碼取值，面臨加注保守'
            nxt = fin = None

        tips.append('頂對控底池：SPR>6 時不要強求三街全下，對手加注要重新評估')
        return dict(current=curr, next=nxt, final=fin,
                    plan_zh=plan_zh, key_note=key_note, tips=tips)

    # ── DRAW 聽牌（25-50%）───────────────────────────────────────────────
    if cat in ('draw', 'medium') and has_draw:
        geo_draw = _geometric_size(spr, streets_left)
        draw_bet_pct = min(0.65, geo_draw + 0.10)  # 聽牌稍大，增加折疊勝算

        curr = _make_action('BET', f'半詐唬{draw_bet_pct:.0%}', draw_bet_pct, P)
        if streets_left >= 3:
            nxt_hit = _make_action('BET', '轉牌命中繼續 barrel', 0.70,
                                   P * (1 + 2 * draw_bet_pct), condition='命中聽牌')
            nxt_miss = _make_action('CHECK', '轉牌未命中，過牌放棄', 0,
                                    P * (1 + 2 * draw_bet_pct), condition='轉牌未命中')
            fin = _make_action('BET', '河牌命中，大注取值', 0.85,
                               P * 2, condition='命中聽牌')
            plan_zh = (f'[聽牌 SPR={spr:.1f}] '
                       f'半詐唬{draw_bet_pct:.0%}→命中繼續/未命中棄牌')
            key_note = '聽牌計劃：命中就取值，未命中轉牌放棄（不要三街詐唬）'
            tips.append('聽牌最佳線路：翻牌半詐唬，轉牌命中大注，未命中棄牌')
        elif streets_left == 2:
            nxt = _make_action('BET', '河牌命中全取', 0.85,
                               P * (1 + 2 * draw_bet_pct), condition='命中')
            nxt_miss = _make_action('CHECK', '河牌未命中，放棄', 0, 0, condition='未命中')
            fin = None
            plan_zh = f'[聽牌 SPR={spr:.1f}] 半詐唬→命中取值/棄牌'
            key_note = '轉牌聽牌：命中河牌大注，未命中放棄'
        else:
            plan_zh = f'[聽牌 SPR={spr:.1f}] 命中全注取值，未命中棄牌'
            key_note = '河牌聽牌命中：大注（0.8-1.0x 底池）取值'
            nxt = fin = None

        return dict(current=curr, next=nxt_hit if streets_left >= 2 else None,
                    final=fin, plan_zh=plan_zh, key_note=key_note, tips=tips)

    # ── MEDIUM 中等牌（38-50%）──────────────────────────────────────────────
    if cat == 'medium':
        curr = _make_action('CHECK', '過牌（控底池）', 0, P)
        if community_len == 3:  # on flop
            nxt = _make_action('CHECK', '轉牌繼續過牌或小注取值', 0.35, P,
                               condition='對手未加注')
            fin = _make_action('CHECK', '河牌根據牌面決定', 0.35, P * 1.5)
            plan_zh = (f'[{_CAT_ZH[cat]} SPR={spr:.1f}] '
                       f'過牌→轉牌薄取值→河牌謹慎')
            key_note = '中等牌：控底池，不要三街取值，注意對手加注信號'
        else:
            plan_zh = f'[{_CAT_ZH[cat]} SPR={spr:.1f}] 謹慎過牌或小注薄取值'
            key_note = '中等牌：薄取值或過牌，面臨加注考慮棄牌'
            nxt = fin = None

        tips.append('中等牌避免多街大注：控制底池大小，讓對手詐唬')
        return dict(current=curr, next=nxt, final=fin,
                    plan_zh=plan_zh, key_note=key_note, tips=tips)

    # ── WEAK 弱牌（< 25%）────────────────────────────────────────────────
    # weak = only bluffing is viable
    if spr >= 8 and equity >= 0.15:  # some bluff equity
        bluff_pct = 0.50
        curr = _make_action('BET', f'詐唬{bluff_pct:.0%}（純詐唬）', bluff_pct, P)
        plan_zh = f'[弱牌 SPR={spr:.1f}] 純詐唬或棄牌'
        key_note = '弱牌：只有詐唬選擇，對手跟注則放棄'
        tips.append('弱牌下注只有折疊勝算，對手跟注後不要繼續barrel')
    else:
        curr = _make_action('CHECK', '過牌/棄牌', 0, P)
        plan_zh = f'[弱牌 SPR={spr:.1f}] 棄牌或過牌放棄'
        key_note = '弱牌面對下注棄牌，主動檢查等值'
        tips.append('弱牌：不要英雄跟注，避免損失更多籌碼')

    return dict(current=curr, plan_zh=plan_zh, key_note=key_note, tips=tips)


def street_plan_summary(plan: StreetPlan) -> str:
    """單行 overlay 摘要（最多 90 字）。"""
    cat_zh = _CAT_ZH.get(plan.hand_category, plan.hand_category)
    spr_str = f'{plan.spr:.1f}'
    curr = plan.current
    curr_str = (f'{curr.action_zh}'
                if curr.size_pct == 0
                else f'{curr.action_zh}({curr.size_bb:.0f}BB)')

    parts = [f'[三街] {cat_zh} SPR={spr_str}', curr_str]
    if plan.next_street and plan.next_street.size_pct > 0:
        parts.append(f'→{plan.next_street.action_zh}')
    if plan.final_street and plan.final_street.size_pct > 0:
        parts.append(f'→{plan.final_street.action_zh}')

    return '  '.join(parts)[:90]
