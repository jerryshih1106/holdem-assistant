"""Tests for multiway_stack_off_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.multiway_stack_off_guide import (
    analyze_multiway_stack_off, MultiwayStackOffResult, mso_one_liner,
    _stack_off_threshold, _stack_off_decision, _p_ahead_estimate,
    BASE_STACK_OFF_THRESHOLD_BY_PLAYERS, BOARD_STACK_OFF_MODIFIER,
)


def _mso(**kw):
    defaults = dict(n_players=3, board_texture='semi_wet', position='ip', villain_type='reg', hand_sdv=0.72, spr=4.0)
    defaults.update(kw)
    return analyze_multiway_stack_off(**defaults)


def test_returns_result():
    assert isinstance(_mso(), MultiwayStackOffResult)


def test_more_players_higher_threshold():
    t2 = BASE_STACK_OFF_THRESHOLD_BY_PLAYERS[2]
    t4 = BASE_STACK_OFF_THRESHOLD_BY_PLAYERS[4]
    assert t4 > t2


def test_wet_higher_threshold_than_dry():
    wet = BOARD_STACK_OFF_MODIFIER['wet']
    dry = BOARD_STACK_OFF_MODIFIER['dry']
    assert wet > dry


def test_4way_threshold_higher_than_2way():
    t2 = _stack_off_threshold(2, 'semi_wet', 'ip', 'reg')
    t4 = _stack_off_threshold(4, 'semi_wet', 'ip', 'reg')
    assert t4 > t2


def test_fish_lower_threshold():
    fish = _stack_off_threshold(3, 'semi_wet', 'ip', 'fish')
    nit  = _stack_off_threshold(3, 'semi_wet', 'ip', 'nit')
    assert fish < nit


def test_ip_lower_than_oop():
    ip  = _stack_off_threshold(3, 'semi_wet', 'ip',  'reg')
    oop = _stack_off_threshold(3, 'semi_wet', 'oop', 'reg')
    assert ip < oop


def test_stack_off_comfortably_strong_hand():
    decision = _stack_off_decision(0.90, 0.65, 4.0)
    assert decision == 'STACK_OFF_COMFORTABLY'


def test_fold_below_threshold():
    decision = _stack_off_decision(0.50, 0.78, 4.0)
    assert 'FOLD' in decision


def test_commit_low_spr():
    decision = _stack_off_decision(0.65, 0.70, 1.0)
    assert 'COMMIT' in decision or 'COMFORTABLY' in decision


def test_p_ahead_decreases_with_players():
    p2 = _p_ahead_estimate(0.70, 2)
    p4 = _p_ahead_estimate(0.70, 4)
    assert p2 > p4


def test_threshold_stored():
    r = _mso()
    assert 0.45 <= r.stack_off_threshold <= 0.92


def test_p_ahead_stored():
    r = _mso()
    assert 0.0 < r.p_ahead_estimate <= 1.0


def test_tips_populated():
    r = _mso()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _mso()
    line = mso_one_liner(r)
    assert '[MSO' in line and 'threshold=' in line


def test_4way_tip_present():
    r = _mso(n_players=4)
    assert any('4' in t or 'way' in t.lower() or 'players' in t.lower() for t in r.tips)


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
