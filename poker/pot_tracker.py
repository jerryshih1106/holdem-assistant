"""
底池跟蹤器：逐街自動計算底池大小。

使用方式：
  tracker = PotTracker(big_blind=20, small_blind=10)
  tracker.new_hand(num_players=6)

  # 翻前：所有行動（會自動加到底池）
  tracker.post_blind('bb', 20)
  tracker.post_blind('sb', 10)
  tracker.action('open', 60)      # UTG 開牌到 60
  tracker.action('call', 60)      # BTN 跟注
  tracker.action('fold')          # 其他人棄牌
  tracker.fold_blind('sb', 10)    # SB 棄牌（退回多放的部分）

  # 進入翻牌
  tracker.next_street()           # street = 'flop'，pot 自動確認
  print(tracker.pot)              # 底池大小

  # 翻牌行動
  tracker.action('bet', 80)
  tracker.action('call', 80)
  tracker.next_street()           # 進入轉牌

  # 快速查詢
  print(tracker.pot)
  print(tracker.street)
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional


@dataclass
class StreetLog:
    street: str
    action: str
    amount: int


class PotTracker:
    """
    逐街底池計算器。

    每個行動（bet/call/raise）都計入底池，
    next_street() 推進到下一街並清空本街的 call-amount。
    """

    STREETS = ['preflop', 'flop', 'turn', 'river']

    def __init__(self, big_blind: int = 20, small_blind: int = 10):
        self.big_blind   = big_blind
        self.small_blind = small_blind
        self._pot        = 0
        self._street_idx = 0
        self._call_size  = 0     # 本街最高下注（需要跟多少）
        self._log: List[StreetLog] = []

    # ── 屬性 ──────────────────────────────────────────────────────────

    @property
    def pot(self) -> int:
        return self._pot

    @property
    def street(self) -> str:
        return self.STREETS[min(self._street_idx, len(self.STREETS)-1)]

    @property
    def street_zh(self) -> str:
        return {'preflop':'翻前','flop':'翻牌','turn':'轉牌','river':'河牌'}.get(self.street, self.street)

    @property
    def call_size(self) -> int:
        """當前需要跟注的金額（0=可以過牌）。"""
        return self._call_size

    # ── 手牌控制 ──────────────────────────────────────────────────────

    def new_hand(self, num_players: int = 6):
        """開始新的一手，盲注自動入底池。"""
        self._pot        = self.big_blind + self.small_blind
        self._street_idx = 0
        self._call_size  = self.big_blind   # BB 算入，其他人需要跟到 BB
        self._log        = []
        self._log.append(StreetLog('preflop', 'blind', self.big_blind + self.small_blind))

    def set_pot(self, amount: int):
        """手動設定底池（覆蓋自動計算）。"""
        self._pot = amount

    def set_call(self, amount: int):
        """手動設定跟注額。"""
        self._call_size = amount

    # ── 行動記錄 ──────────────────────────────────────────────────────

    def action(self, action_type: str, amount: int = 0):
        """
        記錄一個玩家的行動並更新底池。

        action_type:
          'limp'   — 平跟（= call BB）
          'open'   — 開牌加注，amount = 總加注額
          'call'   — 跟注，amount = 跟注額
          'raise'  — 加注，amount = 總加注額（非加注差額）
          '3bet'   — 三倍注
          'bet'    — 下注（翻後）
          'check'  — 過牌
          'fold'   — 棄牌
        """
        if action_type in ('fold', 'check'):
            self._log.append(StreetLog(self.street, action_type, 0))
            return

        if action_type == 'limp':
            amount = self.big_blind
        elif action_type in ('open', '3bet', 'raise') and amount > 0:
            # 加注：只有「超過當前 call size 的部分」算新資金
            # 整個加注額進底池（簡化）
            pass

        if amount > 0:
            self._pot += amount
            self._log.append(StreetLog(self.street, action_type, amount))
            if action_type in ('open', 'raise', '3bet', 'bet'):
                self._call_size = amount

    def hero_call(self):
        """英雄跟注（跟注額 = call_size）。"""
        self.action('call', self._call_size)

    def hero_raise(self, to_amount: int):
        """英雄加注到 to_amount。"""
        self.action('raise', to_amount)
        self._call_size = to_amount

    def next_street(self):
        """推進到下一街，重置跟注額。"""
        if self._street_idx < len(self.STREETS) - 1:
            self._street_idx += 1
            self._call_size = 0

    def go_to_street(self, street: str):
        """直接跳到指定街道。"""
        if street in self.STREETS:
            self._street_idx = self.STREETS.index(street)
            self._call_size = 0

    # ── 快捷計算 ──────────────────────────────────────────────────────

    def pot_after_call(self) -> int:
        """跟注後的底池大小。"""
        return self._pot + self._call_size

    def bet_size_pct(self, pct: float) -> int:
        """底池百分比注碼（常用：0.33, 0.5, 0.75, 1.0）。"""
        return max(1, int(self._pot * pct))

    def common_sizes(self) -> dict:
        """常用注碼大小。"""
        return {
            '1/3底池': self.bet_size_pct(0.33),
            '1/2底池': self.bet_size_pct(0.50),
            '2/3底池': self.bet_size_pct(0.67),
            '底池大小': self.bet_size_pct(1.00),
        }

    def log_summary(self) -> str:
        parts = []
        for log in self._log[-8:]:
            parts.append(f'{log.street[:3]}:{log.action}{"="+str(log.amount) if log.amount else ""}')
        return '  '.join(parts)
