"""Tests for final_table_icm_strategy.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.final_table_icm_strategy import (
    advise_final_table, FinalTableAdvice, ft_one_liner, _icm_equity,
    _stack_regime, _push_equity_threshold, _call_equity_threshold,
)


def _ft(**kw):
    defaults = dict(
        hero_chips=45000,
        all_chips=[45000, 80000, 30000, 25000, 20000],
        payouts=[5000, 3000, 1800, 1200, 800],
        hero_index=0,
        blinds_bb=2000,
        hero_hand_rank_pct=0.75,
        situation='push_fold',
    )
    defaults.update(kw)
    return advise_final_table(**defaults)


def test_returns_final_table_advice():
    r = _ft()
    assert isinstance(r, FinalTableAdvice)


def test_icm_equity_sums_to_total_prize():
    chips = [100000, 80000, 60000, 40000]
    prizes = [5000, 3000, 1500, 800]
    equities = _icm_equity(chips, prizes)
    assert abs(sum(equities) - sum(prizes)) < 0.01


def test_icm_equity_largest_stack_has_most():
    chips = [100000, 80000, 60000, 40000]
    prizes = [5000, 3000, 1500, 800]
    equities = _icm_equity(chips, prizes)
    assert equities[0] > equities[1] > equities[2] > equities[3]


def test_icm_equity_computed():
    r = _ft()
    assert r.hero_icm_equity > 0
    assert r.hero_icm_equity < r.payouts[0]


def test_stack_regime_chip_leader():
    regime = _stack_regime(160000, 80000, 3000)
    assert regime == 'chip_leader'


def test_stack_regime_short_stack():
    regime = _stack_regime(12000, 80000, 3000)
    assert regime in ('short_stack', 'micro_stack')


def test_stack_regime_medium_stack():
    # stack_ratio=1.0, m_ratio=50000/(3*2000)=8.3 → medium_stack condition needs ratio>=0.7 and M>=15
    # Use M=25 to satisfy both conditions
    regime = _stack_regime(75000, 75000, 1000)   # ratio=1.0, M=25
    assert regime in ('medium_stack', 'healthy_stack')


def test_chip_leader_has_lower_push_threshold():
    chips = [100000, 80000, 60000]
    prizes = [5000, 3000, 1500]
    push_leader = _push_equity_threshold('chip_leader', 100000, 80000, 240000, prizes, 0, 3)
    push_medium = _push_equity_threshold('medium_stack', 60000, 80000, 240000, prizes, 2, 3)
    assert push_leader < push_medium


def test_call_threshold_higher_than_push():
    prizes = [5000, 3000, 1500]
    push = _push_equity_threshold('medium_stack', 60000, 80000, 240000, prizes, 2, 5)
    call = _call_equity_threshold('medium_stack', 5, prizes)
    assert call >= push


def test_call_threshold_reasonable_range():
    prizes = [5000, 3000, 1500, 800]
    call = _call_equity_threshold('healthy_stack', 4, prizes)
    assert 0.50 <= call <= 0.68


def test_push_fold_situation():
    r = _ft(situation='push_fold')
    assert r.situation == 'push_fold'
    assert r.action_recommendation in ('push', 'fold')


def test_call_decision_situation():
    r = _ft(situation='call_decision', hero_hand_rank_pct=0.90)
    assert r.situation == 'call_decision'
    assert r.action_recommendation in ('call', 'fold')


def test_premium_hand_pushes():
    r = _ft(hero_hand_rank_pct=0.95, situation='push_fold')
    assert r.action_recommendation == 'push'


def test_weak_hand_folds():
    r = _ft(hero_hand_rank_pct=0.15, situation='push_fold')
    assert r.action_recommendation == 'fold'


def test_stack_regime_in_result():
    r = _ft()
    assert r.stack_regime in ('chip_leader', 'healthy_stack', 'medium_stack', 'short_stack', 'micro_stack')


def test_five_player_final_table():
    r = _ft(
        hero_chips=20000,
        all_chips=[80000, 60000, 50000, 40000, 20000],
        payouts=[10000, 6000, 3500, 2000, 1200],
        hero_index=4,
        blinds_bb=2000,
    )
    assert r.stack_regime in ('short_stack', 'micro_stack')


def test_short_stack_low_push_threshold():
    r = _ft(
        hero_chips=10000,
        all_chips=[100000, 80000, 60000, 10000],
        payouts=[5000, 3000, 1500, 800],
        hero_index=3,
        blinds_bb=2000,
        situation='push_fold',
        hero_hand_rank_pct=0.50,
    )
    # Short stack with moderate hand should push (desperation)
    assert r.push_equity_threshold <= 0.55


def test_chip_stack_pct():
    r = _ft()
    # hero_chips=45000, total=200000 => 22.5%
    assert 0.15 <= r.hero_stack_pct <= 0.40


def test_one_liner_format():
    r = _ft()
    line = ft_one_liner(r)
    assert '[FT' in line
    assert 'icm=' in line or 'stack=' in line


def test_tips_populated():
    r = _ft()
    assert len(r.tips) > 0


def test_payouts_list_stored():
    r = _ft()
    assert r.payouts == [5000, 3000, 1800, 1200, 800]


def test_blinds_bb_stored():
    r = _ft(blinds_bb=3000)
    assert r.blinds_bb == 3000


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
