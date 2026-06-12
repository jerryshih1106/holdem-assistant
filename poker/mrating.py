"""
M-Ratio 錦標賽壓力計。

M = 籌碼 / 每手成本（BB + SB + 前注）

M 區間與策略：
  M ≥ 20  綠區 — 全遊戲策略，無限制
  M 10-19 黃區 — 收緊開牌範圍，避免邊緣情況
  M  5-9  橘區 — 推折模式，幾乎只推或棄牌
  M  1-4  紅區 — 緊急：任何合理的手牌都應全推
  M < 1   死亡 — 下一手必推

Harrington's M（原始定義）：
  M_effective（多人桌調整）= M × (玩家數 / 最大玩家數)
  例：6人桌但只剩4人 → M_eff = M × (4/6)
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class MRating:
    stack:      int
    big_blind:  int
    small_blind: int
    ante:       int        # 前注（通常在錦標賽中後期）
    players:    int        # 目前桌上人數
    max_players: int       # 最大人數（6-max=6, full ring=9）

    @property
    def cost_per_orbit(self) -> int:
        return self.big_blind + self.small_blind + self.ante * self.players

    @property
    def m(self) -> float:
        cost = self.cost_per_orbit
        return self.stack / cost if cost > 0 else 999.0

    @property
    def m_effective(self) -> float:
        """Harrington 有效 M：多人桌人數調整。"""
        raw = self.m
        if self.max_players > 0:
            return raw * (self.players / self.max_players)
        return raw

    @property
    def zone(self) -> str:
        m = self.m_effective
        if m >= 20:  return '綠區'
        if m >= 10:  return '黃區'
        if m >= 5:   return '橘區'
        if m >= 1:   return '紅區'
        return '死亡區'

    @property
    def zone_color(self) -> str:
        m = self.m_effective
        if m >= 20:  return '#56D364'
        if m >= 10:  return '#E3B341'
        if m >= 5:   return '#FF9F43'
        return '#FF4444'

    @property
    def strategy(self) -> str:
        m = self.m_effective
        if m >= 20:
            return '全遊戲策略，可自由翻後操作'
        if m >= 10:
            return '收緊開牌範圍；避免翻後複雜局面；減少跟注寬度'
        if m >= 5:
            return '推折模式：只推牌或棄牌；stop-and-go 策略'
        if m >= 1:
            return '緊急推牌：幾乎任何合理起手牌都全推'
        return '下一手必推，任何牌都推'

    @property
    def push_threshold(self) -> str:
        """本 M 值下建議的推牌範圍描述。"""
        m = self.m_effective
        if m >= 15:  return '參考正常 push/fold 表（≥15bb）'
        if m >= 10:  return '約前 35-45% 的手牌'
        if m >= 7:   return '約前 55-65% 的手牌'
        if m >= 4:   return '約前 75% 的手牌'
        return '幾乎所有手牌（前 90%+）'

    @property
    def m_bar(self) -> str:
        """視覺化壓力條（20個字元寬）。"""
        m = min(self.m_effective, 20)
        filled = int(m / 20 * 20)
        return '|' * filled + '.' * (20 - filled)

    def summary(self) -> str:
        return (f'M={self.m_effective:.1f}  [{self.zone}]  '
                f'{self.strategy[:30]}...')


def calculate_m(
    stack:      int,
    big_blind:  int,
    small_blind: int = 0,
    ante:       int  = 0,
    players:    int  = 6,
    max_players: int = 6,
) -> MRating:
    if small_blind == 0:
        small_blind = big_blind // 2
    return MRating(
        stack=stack, big_blind=big_blind,
        small_blind=small_blind, ante=ante,
        players=players, max_players=max_players,
    )


def m_from_bb(stack_in_bb: float, players: int = 6, max_players: int = 6) -> float:
    """快速估算：以 bb 為單位的籌碼換算成 M。"""
    cost = 1.5   # BB + SB ≈ 1.5bb（不含前注）
    return stack_in_bb / cost * (players / max_players)


def zone_advice(m_eff: float) -> dict:
    """回傳詳細的區間建議。"""
    if m_eff >= 20:
        return {
            'zone': '綠區', 'color': '#56D364',
            'open_range': '正常 GTO 開牌範圍',
            'three_bet':  '正常三倍注範圍',
            'postflop':   '可充分利用翻後技巧',
            'avoid':      '無特別限制',
        }
    if m_eff >= 10:
        return {
            'zone': '黃區', 'color': '#E3B341',
            'open_range': '收緊 10-15%，避免邊緣手牌',
            'three_bet':  '只三倍注強牌；減少輕三倍注',
            'postflop':   '避免建立超過 2-3 個籌碼的底池',
            'avoid':      '避免邊緣跟注（隱含賠率不夠）',
        }
    if m_eff >= 5:
        return {
            'zone': '橘區', 'color': '#FF9F43',
            'open_range': '只推牌或棄牌；不平跟',
            'three_bet':  '全下或棄牌，不標準三倍注',
            'postflop':   '翻前推進，避免建鍋後折疊',
            'avoid':      '避免任何翻後的靈活空間消耗',
        }
    return {
        'zone': '紅區', 'color': '#FF4444',
        'open_range': '幾乎所有合理手牌都推',
        'three_bet':  '必推，不考慮三倍注',
        'postflop':   '無翻後策略空間',
        'avoid':      '不要等待「好牌」，籌碼在流失',
    }
