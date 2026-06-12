"""Tests for middle_pair_frequency_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.middle_pair_frequency_guide import (
    analyze_middle_pair, MiddlePairResult, mp_one_liner,
    _middle_pair_bet_freq, _middle_pair_action, _bet_size_pct,
    MIDDLE_PAIR_BET_FREQ_BY_STREET, VILLAIN_MP_MODIFIER,
    BOARD_MP_MODIFIER, MP_VALUE_THRESHOLD,
)


def _mp(**kw):
    defaults = dict(street='flop', villain_type='reg', board_texture='dry',
                    kicker_quality='middle')
    defaults.update(kw)
    return analyze_middle_pair(**defaults)


def test_returns_result():
    assert isinstance(_mp(), MiddlePairResult)


def test_flop_freq_higher_than_river():
    flop_freq = MIDDLE_PAIR_BET_FREQ_BY_STREET['flop']
    river_freq = MIDDLE_PAIR_BET_FREQ_BY_STREET['river']
    assert flop_freq > river_freq


def test_calling_station_increases_freq():
    cs = _middle_pair_bet_freq('flop', 'calling_station', 'dry')
    reg = _middle_pair_bet_freq('flop', 'reg', 'dry')
    assert cs > reg


def test_lag_decreases_freq():
    lag = _middle_pair_bet_freq('flop', 'lag', 'dry')
    reg = _middle_pair_bet_freq('flop', 'reg', 'dry')
    assert lag < reg


def test_dry_board_increases_freq():
    dry = _middle_pair_bet_freq('flop', 'reg', 'dry')
    wet = _middle_pair_bet_freq('flop', 'reg', 'wet')
    assert dry > wet


def test_action_above_threshold():
    action = _middle_pair_action(0.60)
    assert action == 'BET_THIN_VALUE'


def test_action_middle_range():
    action = _middle_pair_action(0.35)
    assert action == 'CHECK_CALL'


def test_action_below_threshold():
    action = _middle_pair_action(0.10)
    assert action == 'CHECK_FOLD'


def test_mp_value_threshold():
    assert 0.30 <= MP_VALUE_THRESHOLD <= 0.60


def test_fish_vs_reg_bet_size():
    fish_size = _bet_size_pct('flop', 'fish')
    lag_size = _bet_size_pct('flop', 'lag')
    assert fish_size > lag_size


def test_tips_populated():
    r = _mp()
    assert len(r.tips) >= 2


def test_lag_tip():
    r = _mp(villain_type='lag')
    assert any('LAG' in t for t in r.tips)


def test_wet_board_tip():
    r = _mp(board_texture='wet')
    assert any('WET' in t or 'wet' in t for t in r.tips)


def test_one_liner_format():
    r = _mp()
    line = mp_one_liner(r)
    assert '[MP' in line and 'freq=' in line and 'action=' in line


def test_verdict_contains_street():
    r = _mp(street='turn')
    assert 'turn' in r.verdict


def test_river_freq_low():
    r = _mp(street='river', villain_type='nit')
    assert r.bet_freq < 0.50


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
