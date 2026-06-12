"""Tests for tournament_payjump_advisor.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.tournament_payjump_advisor import (
    advise_payjump, PayJumpAdvice, pj_one_liner,
    _jump_category, _bubble_factor, _equity_adjustment,
)


def _pj(**kw):
    defaults = dict(
        hero_chips=35000,
        avg_chips=42000,
        players_left=18,
        spots_to_jump=3,
        current_prize=1200.0,
        target_prize=2000.0,
        hero_hand_rank_pct=0.72,
        situation='normal',
    )
    defaults.update(kw)
    return advise_payjump(**defaults)


def test_returns_payjump_advice():
    r = _pj()
    assert isinstance(r, PayJumpAdvice)


def test_jump_category_min_cash():
    cat = _jump_category(0.0, 1200.0)
    assert cat == 'min_cash'


def test_jump_category_winner_takes_most():
    cat = _jump_category(2000.0, 10000.0)
    assert cat == 'winner_takes_most'


def test_jump_category_significant_jump():
    cat = _jump_category(1200.0, 2200.0)  # ratio ~1.83
    assert cat == 'significant_jump'


def test_jump_category_major_jump():
    cat = _jump_category(1200.0, 3600.0)  # ratio 3.0
    assert cat == 'major_jump'


def test_jump_category_next_step():
    cat = _jump_category(1200.0, 1600.0)  # ratio ~1.33
    assert cat == 'next_step'


def test_bubble_factor_min_cash_high():
    bf = _bubble_factor(1, 'min_cash', 40000, 40000)
    assert bf >= 2.5


def test_bubble_factor_winner_takes_most_low():
    bf = _bubble_factor(2, 'winner_takes_most', 40000, 40000)
    assert bf <= 1.5


def test_bubble_factor_short_stack_lower():
    bf_normal = _bubble_factor(1, 'significant_jump', 42000, 42000)
    bf_short = _bubble_factor(1, 'significant_jump', 15000, 42000)
    assert bf_short < bf_normal


def test_equity_adjustment_high_bf():
    adj = _equity_adjustment(2.5)
    assert adj >= 0.08


def test_equity_adjustment_low_bf():
    adj = _equity_adjustment(0.7)
    assert adj <= 0.0


def test_call_threshold_increases_with_icm():
    r = _pj(current_prize=0.0, target_prize=1200.0, spots_to_jump=1)
    assert r.adjusted_call_threshold >= 0.55


def test_push_threshold_reasonable():
    r = _pj()
    assert 0.30 <= r.adjusted_push_threshold <= 0.70


def test_facing_shove_good_hand_calls():
    r = _pj(
        current_prize=1200.0, target_prize=1800.0,
        spots_to_jump=5, hero_hand_rank_pct=0.95,
        situation='facing_shove',
    )
    assert r.action_recommendation == 'call'


def test_facing_shove_near_min_cash_folds():
    r = _pj(
        current_prize=0.0, target_prize=1200.0,
        spots_to_jump=1, hero_hand_rank_pct=0.50,
        situation='facing_shove',
    )
    assert r.action_recommendation == 'fold'


def test_considering_push_good_hand_pushes():
    r = _pj(
        hero_hand_rank_pct=0.90,
        situation='considering_push',
    )
    assert r.action_recommendation == 'push'


def test_considering_push_bad_hand_folds():
    r = _pj(
        hero_hand_rank_pct=0.05,
        situation='considering_push',
    )
    assert r.action_recommendation == 'fold'


def test_prize_ratio_computed():
    r = _pj(current_prize=1000.0, target_prize=2500.0)
    assert abs(r.prize_ratio - 2.5) < 0.01


def test_jump_category_in_result():
    r = _pj()
    assert r.jump_category in ('min_cash', 'next_step', 'significant_jump', 'major_jump', 'winner_takes_most', 'small_step')


def test_one_liner_format():
    r = _pj()
    line = pj_one_liner(r)
    assert '[PJ' in line
    assert 'bf=' in line
    assert '->' in line or '$' in line


def test_tips_populated():
    r = _pj()
    assert len(r.tips) >= 2


def test_steal_advice_chip_leader():
    r = _pj(hero_chips=80000, avg_chips=42000)
    assert 'steal aggressively' in r.steal_advice.lower() or 'chip leader' in r.steal_advice.lower()


def test_steal_advice_short_stack():
    r = _pj(hero_chips=10000, avg_chips=42000)
    assert 'push' in r.steal_advice.lower() or 'short' in r.steal_advice.lower()


def test_min_cash_tip_appears():
    r = _pj(current_prize=0.0, target_prize=1200.0, spots_to_jump=2)
    has_cash_tip = any('money' in t.lower() or 'min' in t.lower() for t in r.tips)
    assert has_cash_tip


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t()
            print(f'[OK] {t.__name__}')
        except Exception as e:
            print(f'[FAIL] {t.__name__}: {e}')
            failed += 1
    print(f'\n{len(tests)-failed}/{len(tests)} passed')
    sys.exit(failed)
