"""Tests for equity_share_calculator.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.equity_share_calculator import (
    calculate_equity_share, EquityShareResult, eqs_one_liner,
    _pot_odds_required, _equity_share_bb, _equity_share_after_call,
    _call_surplus, _implied_odds_needed, _call_decision,
)


def _eqs(**kw):
    defaults = dict(
        hero_equity=0.35,
        pot_bb=40.0,
        villain_bet_bb=20.0,
        hero_call_bb=20.0,
        street='flop',
        num_players=2,
        hero_hand_category='flush_draw',
        hero_stack_bb=80.0,
    )
    defaults.update(kw)
    return calculate_equity_share(**defaults)


def test_returns_equity_share_result():
    r = _eqs()
    assert isinstance(r, EquityShareResult)


def test_pot_odds_formula():
    # bet=20, pot=40 → required = 20 / (40 + 20 + 20) = 20/80 = 0.25
    odds = _pot_odds_required(20.0, 40.0)
    assert abs(odds - 0.25) < 0.001


def test_pot_odds_increases_with_bet_size():
    odds_small = _pot_odds_required(10.0, 40.0)
    odds_large = _pot_odds_required(40.0, 40.0)
    assert odds_small < odds_large


def test_equity_share_bb_formula():
    share = _equity_share_bb(0.35, 100.0)
    assert abs(share - 35.0) < 0.01


def test_equity_share_scales_with_equity():
    share_low  = _equity_share_bb(0.20, 100.0)
    share_high = _equity_share_bb(0.60, 100.0)
    assert share_high > share_low


def test_equity_share_after_call_formula():
    # pot=40, bet=20, hero calls 20 → new_pot=80; hero equity 35% → 28
    share = _equity_share_after_call(0.35, 40.0, 20.0)
    assert abs(share - 28.0) < 0.01


def test_call_surplus_positive_when_enough_equity():
    # hero 50% equity, pot=40, bet=20 → share_after=0.5*80=40; surplus=40-20=+20
    s = _call_surplus(0.50, 40.0, 20.0)
    assert s > 0


def test_call_surplus_negative_when_insufficient_equity():
    # hero 20% equity, pot=40, bet=20 → share_after=0.2*80=16; surplus=16-20=-4
    s = _call_surplus(0.20, 40.0, 20.0)
    assert s < 0


def test_implied_odds_zero_when_surplus_positive():
    implied = _implied_odds_needed(0.50, 40.0, 20.0, 80.0)
    assert implied == 0.0


def test_implied_odds_positive_when_negative_surplus():
    implied = _implied_odds_needed(0.20, 40.0, 20.0, 80.0)
    assert implied > 0


def test_clear_call_when_above_pot_odds():
    decision, _ = _call_decision(0.50, 0.25, 15.0, 0.0, 'flush_draw', 'flop')
    assert decision == 'call'


def test_fold_when_below_pot_odds_river():
    decision, _ = _call_decision(0.20, 0.30, -4.0, 4.0, 'top_pair', 'river')
    assert decision == 'fold'


def test_call_implied_for_draw_flop():
    decision, _ = _call_decision(0.25, 0.30, -2.0, 2.0, 'flush_draw', 'flop')
    assert decision in ('call_implied', 'call_marginal', 'call')


def test_decision_stored():
    r = _eqs()
    assert r.call_decision in ('call', 'call_implied', 'call_marginal', 'fold')


def test_equity_share_now_stored():
    r = _eqs(hero_equity=0.40, pot_bb=50.0)
    assert abs(r.equity_share_now_bb - 20.0) < 0.1


def test_pot_odds_stored():
    r = _eqs()
    assert 0 < r.pot_odds_required < 1.0


def test_call_surplus_stored():
    r = _eqs()
    # Should have a call_surplus value
    assert isinstance(r.call_surplus_bb, float)


def test_tips_populated():
    r = _eqs()
    assert len(r.tips) >= 2


def test_multiway_tip():
    r = _eqs(num_players=3)
    tips_lower = ' '.join(r.tips).lower()
    assert 'multiway' in tips_lower or 'multi' in tips_lower or 'player' in tips_lower


def test_overbet_tip():
    r = _eqs(villain_bet_bb=60.0, pot_bb=40.0)
    tips_lower = ' '.join(r.tips).lower()
    assert 'overbet' in tips_lower or 'large' in tips_lower or 'big' in tips_lower


def test_river_implied_odds_warning():
    r = _eqs(street='river', hero_equity=0.20, villain_bet_bb=25.0, pot_bb=40.0)
    tips_lower = ' '.join(r.tips).lower()
    assert 'river' in tips_lower or 'implied' in tips_lower or 'pot odds' in tips_lower


def test_one_liner_format():
    r = _eqs()
    line = eqs_one_liner(r)
    assert '[EQS' in line
    assert 'equity=' in line
    assert 'pot_odds=' in line
    assert 'surplus=' in line


def test_one_liner_contains_decision():
    r = _eqs()
    line = eqs_one_liner(r)
    assert r.call_decision.upper() in line


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
