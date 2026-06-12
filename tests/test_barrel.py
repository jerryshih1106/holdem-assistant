"""Tests for poker/barrel.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.barrel import analyze_barrel, barrel_summary, classify_runout


def test_strong_hand_should_barrel_turn():
    """Strong hand (equity 75%) on blank turn should barrel."""
    r = analyze_barrel(
        hole=['Ah', 'Kh'], flop=['Ac', '7h', '2d'], new_card='Ks',
        street='turn', pot_bb=12.0, eff_stack_bb=80.0,
        in_position=True, equity=0.75,
    )
    assert r.should_barrel is True, \
        f'Strong hand on blank turn should barrel: {r.should_barrel}'
    assert r.barrel_freq >= 0.5, f'Barrel freq should be high: {r.barrel_freq:.0%}'
    print(f'Strong turn barrel: freq={r.barrel_freq:.0%} sizing={r.sizing_pct:.0%}pot')


def test_barrel_freq_between_0_and_1():
    """barrel_freq should always be between 0 and 1."""
    r = analyze_barrel(
        hole=['Jh', 'Tc'], flop=['9h', '8c', '2d'], new_card='5s',
        street='turn', pot_bb=10.0, eff_stack_bb=60.0,
        in_position=True, equity=0.45,
    )
    assert 0.0 <= r.barrel_freq <= 1.0, \
        f'barrel_freq out of bounds: {r.barrel_freq}'
    print(f'Barrel freq: {r.barrel_freq:.0%}')


def test_sizing_pct_positive_when_should_barrel():
    """When should_barrel=True, sizing_pct should be positive."""
    r = analyze_barrel(
        hole=['Ah', 'Kh'], flop=['Ac', '7h', '2d'], new_card='Ks',
        street='turn', pot_bb=12.0, eff_stack_bb=80.0,
        in_position=True, equity=0.75,
    )
    if r.should_barrel:
        assert r.sizing_pct > 0, f'sizing_pct must be positive: {r.sizing_pct}'
        assert r.sizing_pct <= 1.5, f'sizing_pct unreasonably large: {r.sizing_pct}'
    print(f'Barrel size: {r.sizing_pct:.0%} pot')


def test_street_field_nonempty():
    """street field should be a non-empty string (localized)."""
    r = analyze_barrel(
        hole=['Ah', 'Kh'], flop=['Ac', '7h', '2d'], new_card='Ks',
        street='turn', pot_bb=12.0, eff_stack_bb=80.0,
        in_position=True, equity=0.70,
    )
    assert isinstance(r.street, str) and len(r.street) > 0, \
        f'street should be non-empty: {r.street!r}'
    print(f'Street field: {r.street!r}')


def test_runout_type_is_valid():
    """runout_type should be a known category string."""
    r = analyze_barrel(
        hole=['Ah', 'Kh'], flop=['Ac', '7h', '2d'], new_card='Ks',
        street='turn', pot_bb=12.0, eff_stack_bb=80.0,
        in_position=True, equity=0.60,
    )
    assert isinstance(r.runout_type, str) and len(r.runout_type) > 0, \
        f'runout_type should be non-empty: {r.runout_type!r}'
    print(f'Runout type: {r.runout_type!r}')


def test_river_barrel_possible():
    """River barrel analysis should also return a valid result."""
    r = analyze_barrel(
        hole=['Kh', 'Kd'], flop=['Ks', '7h', '2c'], new_card='5s',
        street='river', pot_bb=20.0, eff_stack_bb=60.0,
        in_position=True, equity=0.90,
    )
    assert isinstance(r.should_barrel, bool)
    assert 0.0 <= r.barrel_freq <= 1.0
    print(f'River barrel: should={r.should_barrel} freq={r.barrel_freq:.0%}')


def test_weak_equity_oop_lower_barrel_freq():
    """Weak equity OOP should produce lower barrel frequency than strong equity IP."""
    r_strong = analyze_barrel(
        hole=['Ah', 'Ac'], flop=['As', '7h', '2d'], new_card='Kc',
        street='turn', pot_bb=10.0, eff_stack_bb=80.0,
        in_position=True, equity=0.90,
    )
    r_weak = analyze_barrel(
        hole=['Jh', 'Tc'], flop=['9h', '8c', '2s'], new_card='3d',
        street='turn', pot_bb=10.0, eff_stack_bb=80.0,
        in_position=False, equity=0.30,
    )
    assert r_strong.barrel_freq >= r_weak.barrel_freq, \
        f'Strong IP {r_strong.barrel_freq:.0%} should >= weak OOP {r_weak.barrel_freq:.0%}'
    print(f'Barrel freq: strong-IP={r_strong.barrel_freq:.0%}  weak-OOP={r_weak.barrel_freq:.0%}')


def test_reasoning_is_string():
    """reasoning should be a non-empty string."""
    r = analyze_barrel(
        hole=['Ah', 'Kh'], flop=['Ac', '7h', '2d'], new_card='Ks',
        street='turn', pot_bb=12.0, eff_stack_bb=80.0,
        in_position=True, equity=0.70,
    )
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 3, \
        f'reasoning should be non-empty string: {r.reasoning!r}'
    print(f'Reasoning: {r.reasoning[:50]}')


def test_classify_runout_returns_string():
    """classify_runout should return a non-empty string."""
    result = classify_runout(
        flop=['Ac', '7h', '2d'], new_card='Ks',
    )
    # Returns (type_str, zh_str) tuple
    assert isinstance(result, tuple) and len(result) == 2, \
        f'classify_runout should return 2-tuple: {result!r}'
    assert len(result[0]) > 0, f'First element should be non-empty: {result[0]!r}'
    print(f'Classify runout: {result[0]!r}')


def test_barrel_summary_returns_string():
    """barrel_summary should return a non-empty string."""
    r = analyze_barrel(
        hole=['Ah', 'Kh'], flop=['Ac', '7h', '2d'], new_card='Ks',
        street='turn', pot_bb=12.0, eff_stack_bb=80.0,
        in_position=True, equity=0.75,
    )
    s = barrel_summary(r)
    assert isinstance(s, str) and len(s) > 5, \
        f'barrel_summary should return non-empty string: {s!r}'
    print(f'Barrel summary: {s[:60]}')


def test_high_cbet_pct_can_affect_barrel():
    """High historical cbet frequency should not crash and return valid result."""
    r = analyze_barrel(
        hole=['Ah', 'Kh'], flop=['Ac', '7h', '2d'], new_card='Ks',
        street='turn', pot_bb=12.0, eff_stack_bb=80.0,
        in_position=True, cbet_pct=0.85, equity=0.65,
    )
    assert isinstance(r.should_barrel, bool)
    assert 0.0 <= r.barrel_freq <= 1.0
    print(f'High-cbet barrel: freq={r.barrel_freq:.0%}')


if __name__ == '__main__':
    tests = [
        test_strong_hand_should_barrel_turn,
        test_barrel_freq_between_0_and_1,
        test_sizing_pct_positive_when_should_barrel,
        test_street_field_nonempty,
        test_runout_type_is_valid,
        test_river_barrel_possible,
        test_weak_equity_oop_lower_barrel_freq,
        test_reasoning_is_string,
        test_classify_runout_returns_string,
        test_barrel_summary_returns_string,
        test_high_cbet_pct_can_affect_barrel,
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
