"""Tests for river_range_construction_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.river_range_construction_guide import (
    analyze_river_range_construction, RiverRangeResult, rrc_one_liner,
    _alpha, _bluff_ratio, _value_threshold,
    HAND_CATEGORIES_RIVER, VALUE_RANGE_THRESHOLDS,
)


def _rrc(**kw):
    defaults = dict(bet_frac=0.67, position='oop', pot_bb=30.0, hands_in_range=None)
    defaults.update(kw)
    return analyze_river_range_construction(**defaults)


def test_returns_result():
    assert isinstance(_rrc(), RiverRangeResult)


def test_alpha_halfpot():
    a = _alpha(0.50)
    assert abs(a - (1.0/3.0)) < 0.01


def test_alpha_fullpot():
    a = _alpha(1.00)
    assert abs(a - 0.50) < 0.01


def test_bluff_ratio_decreases_with_larger_bet():
    small = _bluff_ratio(0.33)
    large = _bluff_ratio(1.00)
    assert small > large


def test_value_threshold_rises_with_size():
    small_t = _value_threshold(0.33)
    large_t = _value_threshold(1.00)
    assert large_t > small_t


def test_nuts_always_value():
    r = _rrc()
    assert r.range_assignments.get('nuts') == 'VALUE_BET'


def test_air_bluff_or_fold():
    r = _rrc()
    assert r.range_assignments.get('air') in ('BLUFF', 'CHECK_FOLD')


def test_middle_pair_check_call_or_fold():
    r = _rrc()
    assert r.range_assignments.get('middle_pair') in ('CHECK_CALL', 'CHECK_FOLD')


def test_missed_flush_ace_good_bluff():
    r = _rrc()
    assert r.range_assignments.get('missed_flush_ace') in ('BLUFF', 'CHECK_FOLD')


def test_bluffs_have_blockers():
    r = _rrc()
    for hand, assignment in r.range_assignments.items():
        if assignment == 'BLUFF':
            blocker = HAND_CATEGORIES_RIVER.get(hand, {}).get('bluff_blocker', 0)
            assert blocker >= 0.20


def test_value_count_positive():
    r = _rrc()
    assert r.n_value >= 1


def test_alpha_stored():
    r = _rrc()
    assert 0 < r.alpha < 1


def test_bluff_ratio_stored():
    r = _rrc()
    assert r.bluff_ratio > 0


def test_tips_populated():
    r = _rrc()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _rrc()
    line = rrc_one_liner(r)
    assert '[RRC' in line and 'ratio=' in line


def test_oop_tip_present():
    r = _rrc(position='oop')
    assert any('OOP' in t for t in r.tips)


def test_pot_bet_lower_bluff_ratio_than_small():
    small_r = _rrc(bet_frac=0.33)
    pot_r   = _rrc(bet_frac=1.00)
    assert pot_r.bluff_ratio < small_r.bluff_ratio


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
