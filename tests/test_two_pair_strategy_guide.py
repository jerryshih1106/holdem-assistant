"""Tests for two_pair_strategy_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.two_pair_strategy_guide import (
    analyze_two_pair, TwoPairResult, tp2_one_liner,
    _two_pair_freq, _two_pair_size, _two_pair_action,
    TWO_PAIR_BET_FREQ, BOARD_TP2_MODIFIER, N_OPPONENTS_MODIFIER,
    TWO_PAIR_SIZE, STACK_OFF_THRESHOLD_TP2,
)


def _tp2(**kw):
    defaults = dict(street='flop', board_texture='wet', n_opponents=1,
                    hand_type='top_two', spr=4.0)
    defaults.update(kw)
    return analyze_two_pair(**defaults)


def test_returns_result():
    assert isinstance(_tp2(), TwoPairResult)


def test_flop_freq_higher_than_river():
    assert TWO_PAIR_BET_FREQ['flop'] > TWO_PAIR_BET_FREQ['river']


def test_wet_increases_freq():
    wet = _two_pair_freq('flop', 'wet', 1)
    dry = _two_pair_freq('flop', 'dry', 1)
    assert wet > dry


def test_more_opponents_lower_freq():
    hu = _two_pair_freq('flop', 'wet', 1)
    mw = _two_pair_freq('flop', 'wet', 3)
    assert hu > mw


def test_river_size_largest():
    assert TWO_PAIR_SIZE['river'] > TWO_PAIR_SIZE['flop']


def test_wet_board_larger_size():
    wet = _two_pair_size('flop', 'wet')
    dry = _two_pair_size('flop', 'dry')
    assert wet > dry


def test_action_bet_value_protection():
    action = _two_pair_action(0.90, 'top_two')
    assert 'BET' in action


def test_action_check_call():
    action = _two_pair_action(0.40, 'bottom_two')
    assert 'CHECK' in action or 'BET' in action


def test_stack_off_threshold():
    assert 0.50 <= STACK_OFF_THRESHOLD_TP2 <= 0.80


def test_tips_populated():
    r = _tp2()
    assert len(r.tips) >= 2


def test_multiway_tip():
    r = _tp2(n_opponents=3)
    assert any('multiway' in t.lower() or 'MULTIWAY' in t or str(3) in t for t in r.tips)


def test_paired_board_tip():
    r = _tp2(board_texture='paired')
    assert any('PAIRED' in t or 'paired' in t for t in r.tips)


def test_wet_board_tip():
    r = _tp2(board_texture='wet')
    assert any('WET' in t or 'wet' in t for t in r.tips)


def test_one_liner_format():
    r = _tp2()
    line = tp2_one_liner(r)
    assert '[2PR' in line and 'freq=' in line and 'action=' in line


def test_verdict_contains_hand_type():
    r = _tp2(hand_type='bottom_two')
    assert 'bottom_two' in r.verdict


def test_n_opponents_modifier_exists():
    assert 2 in N_OPPONENTS_MODIFIER and 4 in N_OPPONENTS_MODIFIER


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t(); print(f'[OK] {t.__name__}')
        except Exception as e:
            print(f'[FAIL] {t.__name__}: {e}'); failed += 1
    print(f'\n{len(tests)-failed}/{len(tests)} passed')
    sys.exit(failed)
