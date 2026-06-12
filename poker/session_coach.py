"""
Session 教練（Session Coach）

分析 session_tracker 數據，量化每個 leak 的 BB/100 損失，
給出優先順序最高的修正建議和具體練習方法。

用法：
    from poker.session_coach import coach_session, CoachAdvice
    from poker.session_tracker import get_tracker
    advice = coach_session(get_tracker())
    print(advice.summary)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict


# ── 知識庫：每種 leak 的描述、修正方法、練習建議 ────────────────────────────

_LEAK_PLAYBOOK: Dict[str, Dict] = {
    'over_fold': {
        'name': '過度棄牌',
        'fix': '擴大跟注範圍：只要勝率 > 底池賠率就應跟注',
        'drill': '練習計算底池賠率，設定跟注下限（equity threshold）',
        'impact_mult': 1.2,
    },
    'over_call': {
        'name': '過度跟注',
        'fix': '縮緊跟注範圍：面對大下注需要更高勝率',
        'drill': '練習 MDF 計算，學習棄掉勝率不足的手牌',
        'impact_mult': 1.0,
    },
    'missed_bet': {
        'name': '漏失價值下注',
        'fix': '增加 value bet 頻率，尤其在 river 應三街下注',
        'drill': '覆盤每手過牌的河牌，判斷是否應該下注',
        'impact_mult': 1.5,
    },
    'bluff_too_much': {
        'name': '過度詐唬',
        'fix': '減少詐唬頻率，確認 fold equity 足夠再詐唬',
        'drill': '計算對手的 MDF，只在 bluff EV > 0 時詐唬',
        'impact_mult': 1.0,
    },
    'wrong_sizing': {
        'name': '下注尺寸錯誤',
        'fix': '使用 bet_sizing_ev 模組確認最優下注比例',
        'drill': '練習依牌面濕度和對手類型調整下注尺寸',
        'impact_mult': 0.8,
    },
    'default': {
        'name': '決策偏差',
        'fix': '對照 GTO 建議，找出偏差最大的情境',
        'drill': '針對最差位置的手牌進行覆盤',
        'impact_mult': 1.0,
    },
}

# 評分標準
_GRADE_THRESHOLDS = [
    (0,   'A', '優秀：幾乎無可利用的 leak'),
    (3,   'B', '良好：小幅調整即可改善'),
    (8,   'C', '一般：有明顯 leak 需要修正'),
    (15,  'D', '需加強：多個高代價 leak'),
    (float('inf'), 'F', '嚴重：基本決策需要重建'),
]


@dataclass
class LeakFix:
    """單一 leak 的診斷與修正建議。"""
    category: str
    category_name: str
    count: int
    ev_loss_per_100: float
    fix: str
    drill: str


@dataclass
class CoachAdvice:
    """完整 session 教練報告。"""
    total_decisions: int
    accuracy_rate: float
    total_ev_loss_per_100: float
    grade: str
    grade_desc: str
    top_leak: Optional[LeakFix]
    all_leaks: List[LeakFix]
    best_position: Optional[str]
    worst_position: Optional[str]
    worst_street: Optional[str]
    priority_fix: str
    summary: str


def coach_session(tracker) -> CoachAdvice:
    """
    分析 SessionTracker，返回量化的教練建議。

    Args:
        tracker: poker.session_tracker.SessionTracker 實例

    Returns:
        CoachAdvice 完整教練報告
    """
    report = tracker.get_report()

    total = report.total_decisions
    accuracy = report.accuracy_rate if report.accuracy_rate is not None else 1.0
    ev_loss_per_100 = report.ev_loss_per_100 if report.ev_loss_per_100 else 0.0

    # ── 整理 leak 列表 ─────────────────────────────────────────────────────
    leak_fixes: List[LeakFix] = []
    for leak in (report.leaks or []):
        playbook = _LEAK_PLAYBOOK.get(leak.category, _LEAK_PLAYBOOK['default'])
        # 換算為 BB/100（已有 total_ev_loss，除以手數×100）
        cost = (abs(leak.total_ev_loss) / max(total, 1)) * 100 * playbook['impact_mult']
        leak_fixes.append(LeakFix(
            category=leak.category,
            category_name=playbook['name'],
            count=leak.count,
            ev_loss_per_100=round(cost, 1),
            fix=playbook['fix'],
            drill=playbook['drill'],
        ))

    # 按 EV 損失排序
    leak_fixes.sort(key=lambda x: x.ev_loss_per_100, reverse=True)
    top_leak = leak_fixes[0] if leak_fixes else None

    # ── 評分 ───────────────────────────────────────────────────────────────
    abs_loss = abs(ev_loss_per_100)
    grade, grade_desc = 'A', _GRADE_THRESHOLDS[0][2]
    for threshold, g, desc in _GRADE_THRESHOLDS:
        if abs_loss >= threshold:
            grade, grade_desc = g, desc

    # ── 優先修正建議 ────────────────────────────────────────────────────────
    if top_leak:
        priority_fix = (
            f'【最高優先】{top_leak.category_name}（-{top_leak.ev_loss_per_100:.1f} BB/100）'
            f'\n  修正：{top_leak.fix}'
            f'\n  練習：{top_leak.drill}'
        )
    else:
        priority_fix = '無明顯 leak，繼續保持當前策略'

    # ── 摘要行 ─────────────────────────────────────────────────────────────
    summary = (
        f'Session 評分：{grade}  '
        f'準確率：{accuracy:.0%}  '
        f'EV 損失：{ev_loss_per_100:.1f} BB/100  '
        f'Leak 數：{len(leak_fixes)}'
    )

    return CoachAdvice(
        total_decisions=total,
        accuracy_rate=accuracy,
        total_ev_loss_per_100=ev_loss_per_100,
        grade=grade,
        grade_desc=grade_desc,
        top_leak=top_leak,
        all_leaks=leak_fixes,
        best_position=report.best_position,
        worst_position=report.worst_position,
        worst_street=report.worst_street,
        priority_fix=priority_fix,
        summary=summary,
    )


def coach_one_liner(advice: CoachAdvice) -> str:
    """單行摘要，用於 overlay。"""
    if advice.top_leak:
        return (f'[{advice.grade}] {advice.top_leak.category_name}'
                f' -{advice.top_leak.ev_loss_per_100:.1f}BB/100'
                f' | 準確率{advice.accuracy_rate:.0%}')
    return f'[{advice.grade}] 準確率{advice.accuracy_rate:.0%}  無顯著 leak'
