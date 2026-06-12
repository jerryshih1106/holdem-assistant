"""Tests for overpair_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.overpair_guide import (
    analyze_overpair, OverpairResult, op_one_liner,
    _op_bet_freq, _op_size, _should_stack_off,
    OVERPAIR_BET_FREQ, BOARD_OP_MODIFIER, VILLAIN_OP_MODIFIER,
    STACK_OFF_THRESHOLD, OP_SIZE_BY_BOARD,
)


def _op(**kw):
    defaults = dict(pair_rank='qq', board_texture='dry', villain_type='reg',
                    street='flop', spr=4.0)
    defaults.update(kw)
    return analyze_overpair(**defaults)


def test_returns_result():
    assert isinstance(_op(), OverpairResult)


def test_flop_freq_higher_than_river():
    assert OVERPAIR_BET_FREQ['flop'] > OVERPAIR_BET_FREQ['river']


def test_dry_higher_freq_than_paired():
    dry = _op_bet_freq('flop', 'dry', 'reg')
    paired = _op_bet_freq('flop', 'paired', 'reg')
    assert dry > paired


def test_fish_increases_freq():
    fish = _op_bet_freq('flop', 'dry', 'fish')
    reg = _op_bet_freq('flop', 'dry', 'reg')
    assert fish > reg


def test_lag_decreases_freq():
    lag = _op_bet_freq('flop', 'dry', 'lag')
    reg = _op_bet_freq('flop', 'dry', 'reg')
    assert lag < reg


def test_wet_board_larger_size():
    wet_size = _op_size('wet', 'reg')
    dry_size = _op_size('dry', 'reg')
    assert wet_size > dry_size


def test_paired_board_smallest_size():
    paired_size = _op_size('paired', 'reg')
    wet_size = _op_size('wet', 'reg')
    assert paired_size < wet_size


def test_aa_stack_off_threshold_lower_than_jj():
    assert STACK_OFF_THRESHOLD['aa'] < STACK_OFF_THRESHOLD['jj']


def test_should_stack_off_aa_dry():
    assert _should_stack_off('aa', 'dry', 'reg') is True


def test_no_stack_off_lag_wet():
    assert _should_stack_off('qq', 'wet', 'lag') is False


def test_tips_populated():
    r = _op()
    assert len(r.tips) >= 2


def test_paired_board_tip():
    r = _op(board_texture='paired')
    assert any('PAIRED' in t or 'paired' in t for t in r.tips)


def test_lag_tip():
    r = _op(villain_type='lag')
    assert any('LAG' in t for t in r.tips)


def test_one_liner_format():
    r = _op()
    line = op_one_liner(r)
    assert '[OP' in line and 'freq=' in line and 'stack_off=' in line


def test_verdict_contains_board():
    r = _op(board_texture='wet')
    assert 'wet' in r.verdict


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
