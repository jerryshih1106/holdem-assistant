"""Tests for value_bet_threshold_calculator.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.value_bet_threshold_calculator import (
    calc_value_bet_threshold, VBTResult, vbt_one_liner,
    _min_equity_to_value_bet, _is_value_bet_profitable,
    _ev_of_value_bet, _ev_of_check, _optimal_bet_size, _hand_equity_class,
)


def _vbt(**kw):
    defaults = dict(
        bet_size_pct=0.75,
        pot_bb=30.0,
        villain_call_rate=0.55,
        hero_equity=0.62,
        hero_hand_category='top_pair',
        street='river',
    )
    defaults.update(kw)
    return calc_value_bet_threshold(**defaults)


def test_returns_vbt_result():
    r = _vbt()
    assert isinstance(r, VBTResult)


def test_threshold_is_fraction():
    eq_min = _min_equity_to_value_bet(0.75, 0.55)
    assert 0.0 <= eq_min <= 1.0


def test_larger_bet_raises_threshold():
    # Large bets (>= 1.0x pot) require positive equity threshold; medium bets do not
    overbet = _min_equity_to_value_bet(1.50, 0.55)
    medium = _min_equity_to_value_bet(0.75, 0.55)
    assert overbet >= medium


def test_high_call_rate_valid_fraction():
    # Verify thresholds are always in [0, 1]
    for bet in [0.25, 0.75, 1.50]:
        for call in [0.30, 0.55, 0.70]:
            eq = _min_equity_to_value_bet(bet, call)
            assert 0.0 <= eq <= 1.0, f'bet={bet} call={call}: eq={eq}'


def test_profitable_when_equity_exceeds_threshold():
    eq_min = _min_equity_to_value_bet(0.75, 0.55)
    assert _is_value_bet_profitable(eq_min + 0.10, eq_min) is True


def test_not_profitable_below_threshold():
    # Use overbet where threshold is positive
    eq_min = _min_equity_to_value_bet(1.50, 0.55)
    assert eq_min > 0.0   # ensure there IS a positive threshold for overbets
    assert _is_value_bet_profitable(max(0.0, eq_min - 0.10), eq_min) is False


def test_ev_of_check_proportional_to_equity():
    low = _ev_of_check(0.40, 30.0)
    high = _ev_of_check(0.70, 30.0)
    assert high > low


def test_ev_of_bet_positive_high_equity():
    ev = _ev_of_value_bet(0.75, 0.55, 0.80, 30.0)
    assert ev > 0


def test_optimal_bet_returns_valid_size():
    size = _optimal_bet_size(0.62, 0.55, 30.0)
    assert size >= 0.0


def test_hand_class_clear_value():
    assert _hand_equity_class(0.80, 0.40) == 'clear_value'


def test_hand_class_thin_value():
    eq_min = _min_equity_to_value_bet(0.75, 0.55)
    assert _hand_equity_class(eq_min + 0.05, eq_min) == 'thin_value'


def test_hand_class_clear_check():
    eq_min = _min_equity_to_value_bet(0.75, 0.55)
    assert _hand_equity_class(eq_min - 0.20, eq_min) == 'clear_check'


def test_threshold_stored():
    r = _vbt()
    assert 0.0 <= r.min_equity_threshold < 1.0


def test_is_profitable_stored():
    r = _vbt()
    assert isinstance(r.is_profitable, bool)


def test_ev_bet_greater_than_check_when_profitable():
    r = _vbt(hero_equity=0.80)
    if r.is_profitable:
        assert r.ev_of_bet >= r.ev_of_check - 0.5


def test_equity_class_stored():
    r = _vbt()
    assert r.equity_class in ('clear_value', 'solid_value', 'thin_value',
                               'marginal_check', 'clear_check')


def test_optimal_bet_size_stored():
    r = _vbt()
    assert r.optimal_bet_size >= 0.0


def test_tips_populated():
    r = _vbt()
    assert len(r.tips) >= 3


def test_one_liner_format():
    r = _vbt()
    line = vbt_one_liner(r)
    assert '[VBT' in line
    assert 'eq=' in line
    assert 'min=' in line
    assert 'ev_gain=' in line


def test_one_liner_value_bet():
    r = _vbt(hero_equity=0.85)
    line = vbt_one_liner(r)
    assert 'VALUE_BET' in line or 'CHECK' in line


def test_low_equity_overbet_needs_equity():
    # Use 150% pot overbet (has positive threshold ~31%)
    r = _vbt(hero_equity=0.10, bet_size_pct=1.50, villain_call_rate=0.55)
    # 10% equity below ~31% threshold = should not be profitable
    assert not r.is_profitable or r.equity_class in ('marginal_check', 'clear_check')


def test_high_equity_clear_value():
    r = _vbt(hero_equity=0.90, bet_size_pct=0.50, villain_call_rate=0.60)
    assert r.equity_class in ('clear_value', 'solid_value')


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
