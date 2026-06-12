"""
傾斜/動量警報系統 (Tilt / Decision Quality Monitor)

核心概念：
  傾斜（Tilt）是撲克中最昂貴的行為問題。
  研究顯示：處於傾斜狀態的玩家 winrate 下降 40-80%。

偵測方法：
  1. 連續負 EV 決策（連續 3+ 次）
  2. 決策質量趨勢：最後 5 手 vs 前 10 手的準確率差異
  3. EV 崩潰速率：過去 X 手的 EV 損失超過閾值

傾斜等級：
  無      — 決策質量穩定
  警告    — 輕微傾斜信號（2個連續壞決策 或 準確率下降 15%+）
  傾斜    — 中度傾斜（3個連續壞決策 或 準確率下降 25%+）
  嚴重    — 嚴重傾斜（4+ 連續壞決策 或 EV 損失加速）

動量分析：
  正向動量 — 最近比基線打得更好
  負向動量 — 最近比基線打得更差
  無動量   — 穩定

應對建議：
  警告    — 「注意：最近決策略有下滑，保持紀律」
  傾斜    — 「建議：暫停 5 分鐘，深呼吸，回到基礎策略」
  嚴重    — 「強烈建議：立即離桌。等情緒穩定後再回來。」
"""

from dataclasses import dataclass, field
from typing import List, Optional, Deque
from collections import deque
import time


@dataclass
class DecisionRecord:
    timestamp:  float
    ev_loss:    float       # 負 = 此決策比建議差（越負越壞）
    is_correct: bool        # 是否符合建議
    street:     str
    position:   str
    action:     str


@dataclass
class TiltResult:
    # 狀態
    tilt_level:        str      # 'none'/'warning'/'tilt'/'severe'
    tilt_level_zh:     str
    tilt_score:        float    # 0-1（越高傾斜越嚴重）

    # 近期決策質量
    recent_accuracy:   float    # 最近 5 手的正確率（0-1）
    baseline_accuracy: float    # 基準正確率（全 session，0-1）
    accuracy_drop:     float    # 正確率下降幅度（負 = 下滑）

    # 動量
    momentum:          str      # 'positive'/'negative'/'neutral'
    momentum_zh:       str
    recent_ev_loss:    float    # 最近 5 手的總 EV 損失
    baseline_ev_loss:  float    # 每手平均 EV 損失（session 基準）

    # 連續壞決策
    consecutive_bad:   int      # 連續壞決策次數

    # 建議
    advice:            str
    should_pause:      bool     # 是否建議暫停
    summary_zh:        str


class TiltMonitor:
    """
    實時追蹤決策質量，偵測傾斜信號。

    使用方式：
        monitor = TiltMonitor()
        monitor.record_decision(ev_loss=-2.5, is_correct=False, ...)
        result = monitor.analyze()
    """

    def __init__(self, window_size: int = 5, history_size: int = 50):
        self._window_size   = window_size      # 近期窗口
        self._history_size  = history_size     # 總歷史保留
        self._decisions: Deque[DecisionRecord] = deque(maxlen=history_size)
        self._session_start = time.time()

    def record(
        self,
        ev_loss:    float,
        is_correct: bool,
        street:     str = 'unknown',
        position:   str = 'unknown',
        action:     str = 'unknown',
    ) -> None:
        self._decisions.append(DecisionRecord(
            timestamp  = time.time(),
            ev_loss    = ev_loss,
            is_correct = is_correct,
            street     = street,
            position   = position,
            action     = action,
        ))

    def analyze(self) -> TiltResult:
        """分析當前傾斜狀態。"""
        decisions = list(self._decisions)
        n = len(decisions)

        if n == 0:
            return _neutral_result()

        # ── 近期窗口（最後 N 手）────────────────────────────────────────────────
        recent = decisions[-self._window_size:]
        recent_n = len(recent)

        recent_accuracy  = sum(1 for d in recent if d.is_correct) / max(recent_n, 1)
        recent_ev_loss   = sum(d.ev_loss for d in recent)

        # ── 基準（全 session）────────────────────────────────────────────────────
        baseline_accuracy = sum(1 for d in decisions if d.is_correct) / max(n, 1)
        if n > 0:
            baseline_ev_loss = sum(d.ev_loss for d in decisions) / max(n, 1)
        else:
            baseline_ev_loss = 0.0

        # ── 準確率下降 ────────────────────────────────────────────────────────────
        accuracy_drop = recent_accuracy - baseline_accuracy  # 負 = 近期更差

        # ── 連續壞決策 ────────────────────────────────────────────────────────────
        consecutive_bad = 0
        for d in reversed(decisions):
            if not d.is_correct:
                consecutive_bad += 1
            else:
                break

        # ── 傾斜分數 ─────────────────────────────────────────────────────────────
        tilt_score = 0.0

        # 連續壞決策貢獻
        tilt_score += min(0.4, consecutive_bad * 0.12)

        # 準確率下降貢獻
        if accuracy_drop < -0.25:
            tilt_score += 0.35
        elif accuracy_drop < -0.15:
            tilt_score += 0.20
        elif accuracy_drop < -0.05:
            tilt_score += 0.08

        # 近期 EV 損失加速
        if n >= self._window_size and recent_n >= 3:
            recent_per_hand = recent_ev_loss / max(recent_n, 1)
            if recent_per_hand < baseline_ev_loss - 1.5:
                tilt_score += 0.25   # EV 損失明顯加速
            elif recent_per_hand < baseline_ev_loss - 0.5:
                tilt_score += 0.10

        tilt_score = min(1.0, tilt_score)

        # ── 等級判定 ──────────────────────────────────────────────────────────────
        if tilt_score >= 0.65 or consecutive_bad >= 4:
            tilt_level    = 'severe'
            tilt_level_zh = '嚴重傾斜'
            should_pause  = True
            advice = '強烈建議：立即離桌。清空情緒後再回來，避免更大損失。'
        elif tilt_score >= 0.40 or consecutive_bad >= 3:
            tilt_level    = 'tilt'
            tilt_level_zh = '傾斜中'
            should_pause  = True
            advice = '建議暫停 5 分鐘。深呼吸，回到基礎策略，不要追虧。'
        elif tilt_score >= 0.20 or consecutive_bad >= 2:
            tilt_level    = 'warning'
            tilt_level_zh = '傾斜警告'
            should_pause  = False
            advice = '注意：最近決策質量下滑。放慢節奏，只打清晰的牌局。'
        else:
            tilt_level    = 'none'
            tilt_level_zh = '狀態正常'
            should_pause  = False
            advice = '決策質量穩定，繼續保持當前節奏。'

        # ── 動量 ─────────────────────────────────────────────────────────────────
        if accuracy_drop >= 0.10:
            momentum    = 'positive'
            momentum_zh = '正向動量（近期打得更好）'
        elif accuracy_drop <= -0.10:
            momentum    = 'negative'
            momentum_zh = '負向動量（近期打得更差）'
        else:
            momentum    = 'neutral'
            momentum_zh = '穩定'

        # ── 摘要行 ────────────────────────────────────────────────────────────────
        if tilt_level == 'none':
            summary_zh = (f'[狀態] {tilt_level_zh}  '
                          f'準確率 {recent_accuracy:.0%}  '
                          f'近期EV {recent_ev_loss:+.1f}BB')
        else:
            summary_zh = (f'[傾斜] {tilt_level_zh}  '
                          f'連續{consecutive_bad}次壞決策  '
                          f'{advice[:20]}')

        return TiltResult(
            tilt_level        = tilt_level,
            tilt_level_zh     = tilt_level_zh,
            tilt_score        = round(tilt_score, 2),
            recent_accuracy   = round(recent_accuracy, 2),
            baseline_accuracy = round(baseline_accuracy, 2),
            accuracy_drop     = round(accuracy_drop, 2),
            momentum          = momentum,
            momentum_zh       = momentum_zh,
            recent_ev_loss    = round(recent_ev_loss, 2),
            baseline_ev_loss  = round(baseline_ev_loss, 2),
            consecutive_bad   = consecutive_bad,
            advice            = advice,
            should_pause      = should_pause,
            summary_zh        = summary_zh[:80],
        )

    def reset(self) -> None:
        self._decisions.clear()
        self._session_start = time.time()

    @property
    def decision_count(self) -> int:
        return len(self._decisions)


def _neutral_result() -> TiltResult:
    return TiltResult(
        tilt_level        = 'none',
        tilt_level_zh     = '資料不足',
        tilt_score        = 0.0,
        recent_accuracy   = 1.0,
        baseline_accuracy = 1.0,
        accuracy_drop     = 0.0,
        momentum          = 'neutral',
        momentum_zh       = '穩定',
        recent_ev_loss    = 0.0,
        baseline_ev_loss  = 0.0,
        consecutive_bad   = 0,
        advice            = '繼續記錄決策...',
        should_pause      = False,
        summary_zh        = '[狀態] 資料蒐集中...',
    )


def tilt_summary(r: TiltResult) -> str:
    """單行 overlay 摘要（最多 80 字）。"""
    return r.summary_zh[:80]
