"""Tests for squeeze_spot_detector.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.squeeze_spot_detector import (
    detect_squeeze, SqueezeOpportunity, sqz_one_liner,
    _dead_money_factor, _squeeze_size, _fold_probability,
    _hand_suitability, _squeeze_ev, _squeeze_decision,
)


def _sqz(**kw):
    defaults = dict(
        hero_hand_category='suited_connector',
        hero_position='btn',
        open_size_bb=3.0,
        caller_count=1,
        opener_vpip=0.28,
        opener_fold_to_3bet=0.58,
        caller_avg_vpip=0.35,
        caller_avg_fold_to_3bet=0.70,
        hero_stack_bb=100.0,
        pot_bb=7.5,
    )
    defaults.update(kw)
    return detect_squeeze(**defaults)


def test_returns_squeeze_opportunity():
    r = _sqz()
    assert isinstance(r, SqueezeOpportunity)


def test_squeeze_size_1_caller():
    size = _squeeze_size(3.0, 1)
    assert abs(size - 12.0) < 0.1  # 3*3 + 1*3 = 12


def test_squeeze_size_2_callers():
    size = _squeeze_size(3.0, 2)
    assert abs(size - 15.0) < 0.1  # 3*3 + 2*3 = 15


def test_dead_money_factor_increases_with_callers():
    dm1 = _dead_money_factor(3.0, 1)
    dm2 = _dead_money_factor(3.0, 2)
    assert dm2 > dm1


def test_fold_probability_decreases_with_callers():
    p1 = _fold_probability(0.60, 0.70, 1, 'btn')
    p2 = _fold_probability(0.60, 0.70, 2, 'btn')
    assert p1 > p2


def test_fold_probability_ip_bonus():
    p_ip  = _fold_probability(0.60, 0.70, 1, 'btn')
    p_oop = _fold_probability(0.60, 0.70, 1, 'bb')
    assert p_ip >= p_oop


def test_hand_suitability_premium_pair():
    suited, eq, note = _hand_suitability('premium_pair')
    assert suited is True
    assert eq >= 0.75
    assert 'value' in note.lower()


def test_hand_suitability_trash():
    suited, eq, note = _hand_suitability('trash')
    assert suited is False
    assert eq <= 0.35


def test_hand_suitability_suited_ace():
    suited, eq, note = _hand_suitability('suited_ace')
    assert suited is True
    assert 'blocker' in note.lower() or 'fold' in note.lower()


def test_squeeze_decision_high_fold_eq_squeezes():
    decision = _squeeze_decision(
        ev=3.0, p_all_fold=0.65, hand_suited=True,
        caller_count=1, opener_fold_to_3bet=0.70, hero_stack_bb=100.0
    )
    assert decision == 'squeeze'


def test_squeeze_decision_low_fold_eq_folds():
    decision = _squeeze_decision(
        ev=-2.0, p_all_fold=0.15, hand_suited=False,
        caller_count=2, opener_fold_to_3bet=0.30, hero_stack_bb=100.0
    )
    assert decision == 'fold'


def test_squeeze_decision_short_stack_jams():
    decision = _squeeze_decision(
        ev=1.0, p_all_fold=0.50, hand_suited=True,
        caller_count=1, opener_fold_to_3bet=0.60, hero_stack_bb=15.0
    )
    assert decision == 'jam'


def test_premium_pair_squeezes():
    r = _sqz(hero_hand_category='premium_pair', opener_fold_to_3bet=0.55)
    assert r.action in ('squeeze', 'jam')


def test_trash_hand_folds_vs_sticky_opener():
    r = _sqz(hero_hand_category='trash', opener_fold_to_3bet=0.30,
             caller_avg_fold_to_3bet=0.40)
    assert r.action in ('fold', 'flat_call')


def test_squeeze_size_in_result():
    r = _sqz(open_size_bb=3.0, caller_count=1)
    assert abs(r.squeeze_size_bb - 12.0) < 0.1


def test_fold_probability_in_result():
    r = _sqz()
    assert 0.0 < r.fold_probability < 1.0


def test_ev_computed():
    r = _sqz()
    assert isinstance(r.squeeze_ev, float)


def test_tips_populated():
    r = _sqz()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _sqz()
    line = sqz_one_liner(r)
    assert '[SQZ' in line
    assert 'ev=' in line
    assert 'fold=' in line


def test_more_callers_more_dead_money():
    r1 = _sqz(caller_count=1)
    r2 = _sqz(caller_count=2)
    dm1 = 1 * r1.open_size_bb
    dm2 = 2 * r2.open_size_bb
    assert dm2 > dm1


def test_suited_connector_btns_high_fold_eq():
    r = _sqz(
        hero_hand_category='suited_connector',
        opener_fold_to_3bet=0.75,
        caller_avg_fold_to_3bet=0.80,
    )
    assert r.action in ('squeeze', 'flat_call')


def test_hand_suitable_stored():
    r = _sqz(hero_hand_category='premium_pair')
    assert r.hand_suitable is True


def test_dead_money_factor_stored():
    r = _sqz()
    assert r.dead_money_factor > 0.0


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
