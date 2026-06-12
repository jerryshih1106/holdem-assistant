"""Tests for range_disadvantage_response.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.range_disadvantage_response import (
    respond_to_range_disadvantage, RangeDisadvantageResponse, rdr_one_liner,
    _get_range_disadvantage, _disadvantage_level, _adjusted_cbet_frequency,
    _check_raise_frequency, _recommended_action,
    RANGE_DISADVANTAGE,
)


def _rdr(**kw):
    defaults = dict(
        hero_role='pfr',
        hero_opening_position='utg',
        villain_position='btn',
        board_type='low_connected',
        street='flop',
        hero_hand_category='overcards',
        hero_equity=0.30,
        pot_bb=12.0,
        hero_stack_bb=90.0,
        villain_vpip=0.35,
        villain_af=2.2,
    )
    defaults.update(kw)
    return respond_to_range_disadvantage(**defaults)


def test_returns_range_disadvantage_response():
    r = _rdr()
    assert isinstance(r, RangeDisadvantageResponse)


def test_utg_low_connected_severe():
    d = _get_range_disadvantage('utg', 'low_connected')
    assert d >= 0.65   # UTG on low connected = severe disadvantage


def test_btn_low_connected_mild():
    d = _get_range_disadvantage('btn', 'low_connected')
    assert d < 0.45   # BTN has wide range; less disadvantaged


def test_utg_high_connected_lower():
    d = _get_range_disadvantage('utg', 'high_connected')
    assert d < _get_range_disadvantage('utg', 'low_connected')


def test_disadvantage_level_severe():
    assert _disadvantage_level(0.70) == 'severe'


def test_disadvantage_level_moderate():
    assert _disadvantage_level(0.55) == 'moderate'


def test_disadvantage_level_mild():
    assert _disadvantage_level(0.35) == 'mild'


def test_disadvantage_level_minimal():
    assert _disadvantage_level(0.15) == 'minimal'


def test_cbet_reduced_on_disadvantage():
    base = 0.58
    adj = _adjusted_cbet_frequency(base, 0.70, 'low_connected', 'overcards')
    assert adj < base


def test_strong_hand_still_bets():
    adj = _adjusted_cbet_frequency(0.58, 0.70, 'low_connected', 'set')
    assert adj >= 0.75


def test_air_cbet_low():
    adj = _adjusted_cbet_frequency(0.58, 0.70, 'low_connected', 'air')
    assert adj <= 0.30


def test_check_raise_freq_higher_when_disadvantaged():
    low = _check_raise_frequency(0.20, 'low_connected')
    high = _check_raise_frequency(0.70, 'low_connected')
    assert high > low


def test_check_raise_freq_capped():
    freq = _check_raise_frequency(0.95, 'low_connected')
    assert freq <= 0.30


def test_air_severe_check_fold():
    action, _ = _recommended_action('air', 0.20, 0.70, 'pfr', 'flop', 2.0)
    assert action == 'check_fold'


def test_strong_hand_aggressive_villain_check_raise():
    action, _ = _recommended_action('set', 0.85, 0.70, 'pfr', 'flop', 3.0)
    assert action == 'check_raise'


def test_strong_hand_passive_villain_bet():
    action, _ = _recommended_action('set', 0.85, 0.70, 'pfr', 'flop', 1.5)
    assert action == 'bet_value'


def test_overpair_severe_check_call():
    action, _ = _recommended_action('overpair', 0.65, 0.70, 'pfr', 'flop', 2.0)
    assert action == 'check_call'


def test_draw_with_equity_semi_bluff():
    action, _ = _recommended_action('flush_draw', 0.40, 0.50, 'pfr', 'flop', 2.0)
    assert action == 'bet_semi_bluff'


def test_disadvantage_score_stored():
    r = _rdr()
    assert 0 < r.disadvantage_score <= 1.0


def test_disadvantage_level_stored():
    r = _rdr()
    assert r.disadvantage_level in ('severe', 'moderate', 'mild', 'minimal')


def test_utg_low_connected_severe_level():
    r = _rdr(hero_opening_position='utg', board_type='low_connected')
    assert r.disadvantage_level == 'severe'


def test_adjusted_cbet_in_result():
    r = _rdr()
    assert 0 < r.adjusted_cbet_freq <= 1.0


def test_check_raise_freq_in_result():
    r = _rdr()
    assert 0 < r.check_raise_freq <= 0.30


def test_tips_populated():
    r = _rdr()
    assert len(r.tips) >= 2


def test_aggressive_villain_tip():
    r = _rdr(villain_af=3.5)
    tips_lower = ' '.join(r.tips).lower()
    assert 'af' in tips_lower or 'aggress' in tips_lower


def test_one_liner_format():
    r = _rdr()
    line = rdr_one_liner(r)
    assert '[RDR' in line
    assert 'd=' in line
    assert 'cbet=' in line
    assert 'cr=' in line


def test_one_liner_uppercase_level():
    r = _rdr()
    line = rdr_one_liner(r)
    assert r.disadvantage_level.upper() in line


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
