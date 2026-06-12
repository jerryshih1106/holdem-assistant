"""
Session EV 漏洞追蹤器 (Session EV Leak Tracker)

每手記錄決策 vs 建議行動的差異，量化每種錯誤類別的 EV 損失。
Session 結束後輸出漏洞排名，讓玩家知道在哪裡虧錢。

漏洞類別：
  over_fold      — 應該跟注/加注卻棄牌（丟棄正EV牌）
  over_call      — 應該棄牌/加注卻跟注（跟注負EV牌）
  miss_valuebet  — 應該加注取值卻過牌/跟注
  bad_bluff      — 應該棄牌/跟注卻加注（詐唬不佳）
  miss_cbet      — 翻牌後應C-bet卻過牌
  bad_sizing     — 尺寸偏差（過大/過小）
  correct        — 決策正確
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import time


# ── 決策記錄 ──────────────────────────────────────────────────────────────────

@dataclass
class HandDecision:
    hand_id:          str          # 唯一局 ID（時間戳）
    street:           str          # preflop/flop/turn/river
    position:         str          # BTN/CO/SB/BB/...
    situation:        str          # 描述性情境
    action_taken:     str          # 實際行動：棄牌/過牌/跟注/加注/全下
    recommended:      str          # 建議行動
    ev_taken:         float        # 實際行動的 EV（chips/BB）
    ev_recommended:   float        # 建議行動的 EV
    ev_loss:          float        # ev_taken - ev_recommended（負數=虧損）
    leak_category:    str          # 漏洞類別
    equity:           float        # 手牌勝率（0-1）
    pot_bb:           float        # 底池大小
    note:             str = ''     # 額外備注


@dataclass
class LeakSummary:
    category:         str
    category_zh:      str
    count:            int
    total_ev_loss:    float        # 累積 EV 損失（BB）
    avg_ev_loss:      float        # 平均每次 EV 損失
    worst_hand:       Optional[str]  # 最嚴重的單手 ID
    advice:           str


@dataclass
class SessionReport:
    session_id:       str
    hands_played:     int
    total_decisions:  int
    correct_count:    int
    accuracy_rate:    float        # 正確決策率
    total_ev_loss:    float        # 本 session 總 EV 損失
    ev_loss_per_100:  float        # 每100手 EV 損失
    leaks:            List[LeakSummary]   # 按嚴重程度排序
    worst_street:     str          # 損失最多的街道
    best_position:    str          # 表現最好的位置
    worst_position:   str          # 表現最差的位置
    summary_line:     str


# ── 漏洞分類器 ────────────────────────────────────────────────────────────────

_LEAK_ZH = {
    'over_fold':     '過度棄牌',
    'over_call':     '過度跟注',
    'miss_valuebet': '漏掉加注取值',
    'bad_bluff':     '不當詐唬',
    'miss_cbet':     '漏掉C-bet',
    'bad_sizing':    '注碼偏差',
    'correct':       '正確決策',
}

_LEAK_ADVICE = {
    'over_fold':     '你丟棄了正EV的牌局。複查底池賠率，並相信手牌勝率數字。',
    'over_call':     '你在底池賠率不足時跟注。嚴格對照勝率 vs 底池賠率再行動。',
    'miss_valuebet': '你的強牌沒有最大化取值。勝率高時積極加注而非過牌/跟注。',
    'bad_bluff':     '你的詐唬對手未必棄牌。減少無折疊勝算的詐唬頻率。',
    'miss_cbet':     '翻牌後未充分利用範圍優勢C-bet。乾燥牌面可高頻小注。',
    'bad_sizing':    '注碼偏離最優。參考bet_sizing模組的街道/板面建議。',
    'correct':       '繼續保持！',
}


def classify_leak(
    action_taken: str,
    recommended:  str,
    ev_taken:     float,
    ev_rec:       float,
    equity:       float,
    pot_odds:     float,
    street:       str,
) -> Tuple[str, float]:
    """
    分類漏洞類型，回傳 (leak_category, ev_loss)。
    ev_loss = ev_taken - ev_recommended（負數=這次決策損失EV）
    """
    ev_loss = ev_taken - ev_rec

    # 完全匹配 → 正確
    if action_taken == recommended or abs(ev_loss) < 0.05:
        return 'correct', ev_loss

    taken = action_taken.lower()
    rec   = recommended.lower()

    # 應加注卻跟注/過牌 → 漏掉取值
    if rec in ('加注', 'raise', '全下') and taken in ('跟注', '過牌', 'call', 'check'):
        return 'miss_valuebet', ev_loss

    # 應跟注/加注卻棄牌 → 過度棄牌
    if taken in ('棄牌', 'fold') and rec in ('跟注', '加注', 'call', 'raise', '過牌', 'check'):
        return 'over_fold', ev_loss

    # 應棄牌卻跟注 → 過度跟注
    if rec in ('棄牌', 'fold') and taken in ('跟注', 'call'):
        return 'over_call', ev_loss

    # 應棄牌/跟注卻加注 → 不當詐唬
    if taken in ('加注', 'raise', '全下') and rec in ('棄牌', '跟注', 'fold', 'call'):
        return 'bad_bluff', ev_loss

    # 翻牌有機會C-bet但過牌
    if street == 'flop' and taken in ('過牌', 'check') and rec not in ('過牌', 'check'):
        return 'miss_cbet', ev_loss

    return 'bad_sizing', ev_loss


# ── 主追蹤器 ─────────────────────────────────────────────────────────────────

class SessionTracker:
    """
    Session EV 漏洞追蹤器。

    使用方式：
        tracker = SessionTracker()
        tracker.record_decision(
            street='flop', position='BTN',
            situation='翻牌有位置面對過牌',
            action_taken='過牌', recommended='加注',
            ev_taken=2.1, ev_recommended=4.8,
            equity=0.72, pot_bb=8.0,
        )
        report = tracker.get_report()
    """

    def __init__(self, session_id: str = ''):
        self.session_id  = session_id or f'sess_{int(time.time())}'
        self.decisions:  List[HandDecision] = []
        self._hand_count = 0
        self._current_hand_id = self._new_hand_id()

    def _new_hand_id(self) -> str:
        self._hand_count += 1
        return f'H{self._hand_count:04d}'

    def new_hand(self):
        """開始新一手牌，重置手牌ID。"""
        self._current_hand_id = self._new_hand_id()

    def record_decision(
        self,
        street:        str,
        position:      str,
        situation:     str,
        action_taken:  str,
        recommended:   str,
        ev_taken:      float,
        ev_recommended: float,
        equity:        float = 0.5,
        pot_bb:        float = 10.0,
        pot_odds:      float = 0.0,
        note:          str = '',
    ) -> HandDecision:
        """記錄一次決策。"""
        leak, ev_loss = classify_leak(
            action_taken, recommended,
            ev_taken, ev_recommended,
            equity, pot_odds, street,
        )
        dec = HandDecision(
            hand_id        = self._current_hand_id,
            street         = street,
            position       = position,
            situation      = situation,
            action_taken   = action_taken,
            recommended    = recommended,
            ev_taken       = round(ev_taken, 2),
            ev_recommended = round(ev_recommended, 2),
            ev_loss        = round(ev_loss, 2),
            leak_category  = leak,
            equity         = equity,
            pot_bb         = pot_bb,
            note           = note,
        )
        self.decisions.append(dec)
        return dec

    def quick_record(
        self,
        ev_breakdown: Dict[str, float],   # 來自 decision.py 的 ev_breakdown
        action_taken: str,
        recommended:  str,
        street:       str,
        position:     str,
        equity:       float = 0.5,
        pot_bb:       float = 10.0,
    ) -> HandDecision:
        """
        從 decision.py 的 ev_breakdown 直接記錄。

        ev_breakdown 格式: {'fold': 0, 'check': 2.1, 'call': 3.4, 'raise': 5.2, 'allin': 4.8}
        """
        action_map = {
            '棄牌': 'fold', '過牌': 'check', '跟注': 'call',
            '加注': 'raise', '全下': 'allin',
            'fold': 'fold', 'check': 'check', 'call': 'call',
            'raise': 'raise', 'allin': 'allin',
        }
        taken_key = action_map.get(action_taken.lower(), 'fold')
        rec_key   = action_map.get(recommended.lower(), 'fold')
        ev_taken  = ev_breakdown.get(taken_key, 0.0)
        ev_rec    = ev_breakdown.get(rec_key, 0.0)

        return self.record_decision(
            street=street, position=position,
            situation=f'{street} {action_taken} vs rec={recommended}',
            action_taken=action_taken, recommended=recommended,
            ev_taken=ev_taken, ev_recommended=ev_rec,
            equity=equity, pot_bb=pot_bb,
        )

    def get_report(self) -> SessionReport:
        """生成本 session 的漏洞報告。"""
        if not self.decisions:
            return self._empty_report()

        total = len(self.decisions)
        correct = sum(1 for d in self.decisions if d.leak_category == 'correct')
        total_ev_loss = sum(d.ev_loss for d in self.decisions)

        # 按漏洞類別統計
        by_cat: Dict[str, List[HandDecision]] = defaultdict(list)
        for d in self.decisions:
            by_cat[d.leak_category].append(d)

        leaks: List[LeakSummary] = []
        for cat, decs in by_cat.items():
            if cat == 'correct':
                continue
            cat_ev_loss = sum(d.ev_loss for d in decs)
            worst = min(decs, key=lambda x: x.ev_loss, default=None)
            leaks.append(LeakSummary(
                category     = cat,
                category_zh  = _LEAK_ZH.get(cat, cat),
                count        = len(decs),
                total_ev_loss = round(cat_ev_loss, 2),
                avg_ev_loss  = round(cat_ev_loss / len(decs), 2),
                worst_hand   = worst.hand_id if worst else None,
                advice       = _LEAK_ADVICE.get(cat, ''),
            ))
        leaks.sort(key=lambda x: x.total_ev_loss)

        # 按街道統計損失
        street_loss: Dict[str, float] = defaultdict(float)
        for d in self.decisions:
            street_loss[d.street] += d.ev_loss
        worst_street = min(street_loss, key=street_loss.get, default='unknown')

        # 按位置統計
        pos_loss: Dict[str, float] = defaultdict(float)
        pos_count: Dict[str, int] = defaultdict(int)
        for d in self.decisions:
            pos_loss[d.position] += d.ev_loss
            pos_count[d.position] += 1
        if pos_loss:
            worst_pos = min(pos_loss, key=lambda p: pos_loss[p] / pos_count[p])
            best_pos  = max(pos_loss, key=lambda p: pos_loss[p] / pos_count[p])
        else:
            worst_pos = best_pos = 'N/A'

        hands = max(self._hand_count, 1)
        ev_per_100 = round(total_ev_loss / hands * 100, 1)
        accuracy   = round(correct / total, 3)

        summary = (f'{total}次決策  正確率{accuracy:.0%}  '
                   f'總EV損失{total_ev_loss:.1f}BB  '
                   f'每100手{ev_per_100:.1f}BB')

        return SessionReport(
            session_id      = self.session_id,
            hands_played    = hands,
            total_decisions = total,
            correct_count   = correct,
            accuracy_rate   = accuracy,
            total_ev_loss   = round(total_ev_loss, 2),
            ev_loss_per_100 = ev_per_100,
            leaks           = leaks,
            worst_street    = worst_street,
            best_position   = best_pos,
            worst_position  = worst_pos,
            summary_line    = summary,
        )

    def _empty_report(self) -> SessionReport:
        return SessionReport(
            session_id='', hands_played=0, total_decisions=0,
            correct_count=0, accuracy_rate=1.0, total_ev_loss=0.0,
            ev_loss_per_100=0.0, leaks=[], worst_street='N/A',
            best_position='N/A', worst_position='N/A',
            summary_line='尚無決策記錄',
        )

    def print_report(self, report: Optional[SessionReport] = None):
        """列印本 session 漏洞報告。"""
        r = report or self.get_report()
        print(f'\n=== Session 漏洞報告 [{r.session_id}] ===')
        print(f'{r.summary_line}')
        print(f'每100手 EV 損失: {r.ev_loss_per_100:.1f}BB/100  '
              f'(正確率 {r.accuracy_rate:.0%})')
        print(f'最差街道: {r.worst_street}  最差位置: {r.worst_position}')
        print()
        if r.leaks:
            print('漏洞排行（最嚴重 → 最輕微）:')
            for i, leak in enumerate(r.leaks, 1):
                print(f'  {i}. [{leak.category_zh}] '
                      f'{leak.count}次  累積損失{leak.total_ev_loss:.1f}BB  '
                      f'均損{leak.avg_ev_loss:.1f}BB/次')
                print(f'     建議: {leak.advice}')
        else:
            print('本 session 無可識別漏洞！')
        print()


# ── 全局 session 實例（可直接 import 使用）────────────────────────────────────

_global_tracker: Optional[SessionTracker] = None


def get_tracker() -> SessionTracker:
    """取得全局 session 追蹤器（若不存在則新建）。"""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = SessionTracker()
    return _global_tracker


def reset_tracker(session_id: str = '') -> SessionTracker:
    """重置為新 session。"""
    global _global_tracker
    _global_tracker = SessionTracker(session_id)
    return _global_tracker


def record(
    ev_breakdown:  Dict[str, float],
    action_taken:  str,
    recommended:   str,
    street:        str,
    position:      str,
    equity:        float = 0.5,
    pot_bb:        float = 10.0,
) -> HandDecision:
    """快速記錄介面，使用全局 tracker。"""
    return get_tracker().quick_record(
        ev_breakdown, action_taken, recommended,
        street, position, equity, pot_bb,
    )
