"""Tests for poker/bet_sizing.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.bet_sizing import suggest_bet_sizing, sizing_summary, BetSizingResult


def test_result_has_all_fields():
    """BetSizingResult should have all expected fields."""
    r = suggest_bet_sizing('flop', pot_bb=10, eff_stack_bb=90, in_position=True)
    required = ['recommended', 'alternatives', 'cbet_freq', 'reasoning', 'street']
    for field in required:
        assert hasattr(r, field), f'BetSizingResult missing field: {field}'
    print(f'All fields present')


def test_recommended_has_sizing_option_fields():
    """recommended should be a SizingOption with pct and chips."""
    r = suggest_bet_sizing('flop', pot_bb=10, eff_stack_bb=90, in_position=True)
    rec = r.recommended
    assert hasattr(rec, 'pct') and hasattr(rec, 'chips'), \
        f'SizingOption should have pct and chips: {dir(rec)}'
    assert 0.0 < rec.pct < 2.0, f'pct should be a pot fraction: {rec.pct}'
    assert rec.chips > 0, f'chips should be > 0: {rec.chips}'
    print(f'Recommended: pct={rec.pct:.0%} chips={rec.chips:.1f}')


def test_wet_board_larger_sizing_than_dry():
    """Wet board should recommend larger bet size than dry board."""
    r_dry = suggest_bet_sizing('flop', pot_bb=10, eff_stack_bb=90, in_position=True, texture='dry')
    r_wet = suggest_bet_sizing('flop', pot_bb=10, eff_stack_bb=90, in_position=True, texture='wet')
    assert r_wet.recommended.pct >= r_dry.recommended.pct, \
        f'Wet {r_wet.recommended.pct:.0%} should >= dry {r_dry.recommended.pct:.0%}'
    print(f'Sizing: dry={r_dry.recommended.pct:.0%} wet={r_wet.recommended.pct:.0%}')


def test_river_larger_than_flop_sizing():
    """River should recommend a larger fraction than flop (polar range)."""
    r_flop  = suggest_bet_sizing('flop',  pot_bb=10, eff_stack_bb=90, in_position=True)
    r_river = suggest_bet_sizing('river', pot_bb=10, eff_stack_bb=90, in_position=True)
    assert r_river.recommended.pct >= r_flop.recommended.pct, \
        f'River {r_river.recommended.pct:.0%} should >= flop {r_flop.recommended.pct:.0%}'
    print(f'Sizing: flop={r_flop.recommended.pct:.0%} river={r_river.recommended.pct:.0%}')


def test_chips_proportional_to_pot():
    """chips = pct * pot_bb should hold."""
    pot = 20.0
    r = suggest_bet_sizing('flop', pot_bb=pot, eff_stack_bb=180, in_position=True, texture='dry')
    rec = r.recommended
    expected_chips = rec.pct * pot
    assert abs(rec.chips - expected_chips) < 0.5, \
        f'chips {rec.chips:.1f} should = pct*pot {expected_chips:.1f}'
    print(f'chips={rec.chips:.1f} pct*pot={expected_chips:.1f}')


def test_cbet_freq_in_range():
    """cbet_freq should be a float in [0, 1]."""
    r = suggest_bet_sizing('flop', pot_bb=10, eff_stack_bb=90, in_position=True)
    assert 0.0 <= r.cbet_freq <= 1.0, \
        f'cbet_freq should be in [0,1]: {r.cbet_freq}'
    print(f'cbet_freq: {r.cbet_freq:.0%}')


def test_alternatives_is_list():
    """alternatives should be a list (possibly empty)."""
    r = suggest_bet_sizing('flop', pot_bb=10, eff_stack_bb=90, in_position=True)
    assert isinstance(r.alternatives, list), \
        f'alternatives should be list: {type(r.alternatives)}'
    print(f'alternatives count: {len(r.alternatives)}')


def test_reasoning_is_string():
    """reasoning should be a non-empty string."""
    r = suggest_bet_sizing('flop', pot_bb=10, eff_stack_bb=90, in_position=True)
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 3, \
        f'reasoning should be non-empty string: {repr(r.reasoning)[:50]}'
    print(f'reasoning length: {len(r.reasoning)}')


def test_sizing_summary_returns_string():
    """sizing_summary should return a non-empty string."""
    r = suggest_bet_sizing('flop', pot_bb=10, eff_stack_bb=90, in_position=True)
    s = sizing_summary(r)
    assert isinstance(s, str) and len(s) > 5, \
        f'sizing_summary should be non-empty: {repr(s)[:50]}'
    print(f'sizing_summary length: {len(s)}')


def test_oop_vs_ip_sizing():
    """OOP (out of position) should work and return a valid result."""
    r = suggest_bet_sizing('flop', pot_bb=10, eff_stack_bb=90, in_position=False)
    assert r.recommended.pct > 0, \
        f'OOP sizing should have pct > 0: {r.recommended.pct}'
    print(f'OOP flop sizing: {r.recommended.pct:.0%}')


if __name__ == '__main__':
    tests = [
        test_result_has_all_fields,
        test_recommended_has_sizing_option_fields,
        test_wet_board_larger_sizing_than_dry,
        test_river_larger_than_flop_sizing,
        test_chips_proportional_to_pot,
        test_cbet_freq_in_range,
        test_alternatives_is_list,
        test_reasoning_is_string,
        test_sizing_summary_returns_string,
        test_oop_vs_ip_sizing,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f'  PASS  {t.__name__}')
        except Exception as e:
            print(f'  FAIL  {t.__name__}: {e}')
            import traceback; traceback.print_exc()
            failed += 1
    print(f'\n{len(tests)-failed}/{len(tests)} passed')
    sys.exit(failed)
