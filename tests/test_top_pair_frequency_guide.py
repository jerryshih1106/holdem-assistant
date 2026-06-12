"""Tests for top_pair_frequency_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.top_pair_frequency_guide import (
    analyze_top_pair, TopPairResult, tp_one_liner,
    _tp_bet_freq, _tp_size_pct, _tp_action,
    TP_BET_FREQ_BY_STREET, KICKER_QUALITY_MODIFIER,
    VILLAIN_TP_MODIFIER, TP_SIZE_BY_STREET,
)


def _tp(**kw):
    defaults = dict(street='flop', kicker_quality='top', villain_type='reg',
                    board_texture='dry')
    defaults.update(kw)
    return analyze_top_pair(**defaults)


def test_returns_result():
    assert isinstance(_tp(), TopPairResult)


def test_flop_freq_higher_than_river():
    assert TP_BET_FREQ_BY_STREET['flop'] > TP_BET_FREQ_BY_STREET['river']


def test_top_kicker_higher_freq_than_bottom():
    top_freq = _tp_bet_freq('flop', 'top', 'reg', 'dry')
    bot_freq = _tp_bet_freq('flop', 'bottom', 'reg', 'dry')
    assert top_freq > bot_freq


def test_calling_station_increases_freq():
    cs = _tp_bet_freq('flop', 'top', 'calling_station', 'dry')
    reg = _tp_bet_freq('flop', 'top', 'reg', 'dry')
    assert cs > reg


def test_lag_decreases_freq():
    lag = _tp_bet_freq('flop', 'top', 'lag', 'dry')
    reg = _tp_bet_freq('flop', 'top', 'reg', 'dry')
    assert lag < reg


def test_dry_higher_than_wet():
    dry = _tp_bet_freq('flop', 'top', 'reg', 'dry')
    wet = _tp_bet_freq('flop', 'top', 'reg', 'wet')
    assert dry > wet


def test_action_bet_value():
    action = _tp_action(0.75)
    assert action == 'BET_VALUE'


def test_action_check_call():
    action = _tp_action(0.40)
    assert action == 'CHECK_CALL'


def test_action_check_fold():
    action = _tp_action(0.20)
    assert action == 'CHECK_FOLD'


def test_calling_station_larger_size():
    cs_size = _tp_size_pct('flop', 'calling_station')
    reg_size = _tp_size_pct('flop', 'reg')
    assert cs_size > reg_size


def test_tips_populated():
    r = _tp()
    assert len(r.tips) >= 2


def test_tptk_tip():
    r = _tp(kicker_quality='top')
    assert any('TPTK' in t or 'top kicker' in t.lower() for t in r.tips)


def test_lag_tip():
    r = _tp(villain_type='lag')
    assert any('LAG' in t for t in r.tips)


def test_one_liner_format():
    r = _tp()
    line = tp_one_liner(r)
    assert '[TP' in line and 'freq=' in line and 'action=' in line


def test_verdict_contains_kicker():
    r = _tp(kicker_quality='weak')
    assert 'weak' in r.verdict


def test_river_sizing_largest():
    assert TP_SIZE_BY_STREET['river'] > TP_SIZE_BY_STREET['flop']


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
