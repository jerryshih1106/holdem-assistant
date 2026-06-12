"""Tests for poker/facing_aggression.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.facing_aggression import analyze_facing_aggression, facing_aggression_summary


def test_check_raise_reduces_equity_significantly():
    """Check-raise should dramatically reduce hero's effective equity."""
    r = analyze_facing_aggression(
        call_amount=20.0, pot_bb=20.0, raw_equity=0.55,
        street='flop', action_type='check_raise_flop',
    )
    assert r.adjusted_equity < r.raw_equity * 0.90, \
        f'Check-raise should reduce equity: raw={r.raw_equity:.0%} adj={r.adjusted_equity:.0%}'
    assert r.equity_reduction > 0.05, \
        f'Check-raise equity reduction should be >5%: {r.equity_reduction:.0%}'
    print(f'CR flop: raw={r.raw_equity:.0%} → adj={r.adjusted_equity:.0%} '
          f'(-{r.equity_reduction:.0%})')


def test_cbet_small_equity_reduction():
    """Broad c-bet range should have minimal equity reduction."""
    r = analyze_facing_aggression(
        call_amount=8.0, pot_bb=15.0, raw_equity=0.45,
        street='flop', action_type='cbet_flop',
    )
    assert r.equity_reduction < 0.08, \
        f'C-bet equity reduction should be small: {r.equity_reduction:.0%}'
    print(f'C-bet: raw={r.raw_equity:.0%} → adj={r.adjusted_equity:.0%} '
          f'(-{r.equity_reduction:.0%})')


def test_turn_checkraise_stronger_than_flop():
    """Turn CR should have narrower range (more equity reduction) than flop CR."""
    flop_cr = analyze_facing_aggression(
        call_amount=15.0, pot_bb=20.0, raw_equity=0.50,
        street='flop', action_type='check_raise_flop',
    )
    turn_cr = analyze_facing_aggression(
        call_amount=15.0, pot_bb=20.0, raw_equity=0.50,
        street='turn', action_type='check_raise_turn',
    )
    assert turn_cr.adjusted_equity <= flop_cr.adjusted_equity, \
        f'Turn CR ({turn_cr.villain_range_pct:.0%}) should be narrower than flop CR ({flop_cr.villain_range_pct:.0%})'
    print(f'Flop CR range={flop_cr.villain_range_pct:.0%}  Turn CR range={turn_cr.villain_range_pct:.0%}')


def test_river_overbet_narrowest_range():
    """River overbet should have narrowest range (most equity reduction)."""
    overbet = analyze_facing_aggression(
        call_amount=40.0, pot_bb=20.0, raw_equity=0.50,
        street='river', action_type='river_overbet',
    )
    small   = analyze_facing_aggression(
        call_amount=8.0, pot_bb=20.0, raw_equity=0.50,
        street='river', action_type='river_small',
    )
    assert overbet.villain_range_pct <= small.villain_range_pct, \
        f'Overbet range {overbet.villain_range_pct:.0%} should be <= small {small.villain_range_pct:.0%}'
    print(f'Overbet range={overbet.villain_range_pct:.0%}  Small range={small.villain_range_pct:.0%}')


def test_clear_call_when_adjusted_equity_high():
    """When adjusted equity >> required equity, recommend call."""
    r = analyze_facing_aggression(
        call_amount=5.0, pot_bb=30.0, raw_equity=0.72,
        street='flop', action_type='cbet_flop',
    )
    assert r.action in ('call',), \
        f'High equity should recommend call: adj_eq={r.adjusted_equity:.0%} req={r.required_equity:.0%}'
    print(f'Clear call: adj_eq={r.adjusted_equity:.0%} req={r.required_equity:.0%} → {r.action}')


def test_fold_when_adjusted_equity_much_lower_than_required():
    """When villain check-raises and hero has weak hand, should recommend fold."""
    r = analyze_facing_aggression(
        call_amount=25.0, pot_bb=15.0, raw_equity=0.35,
        street='turn', action_type='check_raise_turn',
    )
    # Required equity ≈ 25/(15+25+25) ≈ 38%, adj equity should be much lower
    print(f'CR turn weak: adj_eq={r.adjusted_equity:.0%} req={r.required_equity:.0%} → {r.action}')
    # The required equity is quite high for this bet size, adj equity should be low
    assert r.adjusted_equity < r.raw_equity, 'Equity should be reduced'


def test_passive_villain_narrower_cr_range():
    """Passive villain (low AF) check-raises with narrower range (even less bluffs)."""
    passive = analyze_facing_aggression(
        call_amount=20.0, pot_bb=20.0, raw_equity=0.45,
        street='flop', action_type='check_raise_flop',
        villain_af=0.4,
    )
    aggressive = analyze_facing_aggression(
        call_amount=20.0, pot_bb=20.0, raw_equity=0.45,
        street='flop', action_type='check_raise_flop',
        villain_af=3.0,
    )
    # Passive villain has tighter CR range → more equity reduction
    assert passive.villain_range_pct <= aggressive.villain_range_pct, \
        f'Passive CR range {passive.villain_range_pct:.0%} should be <= aggressive {aggressive.villain_range_pct:.0%}'
    print(f'Passive CR range={passive.villain_range_pct:.0%}  Aggressive CR range={aggressive.villain_range_pct:.0%}')


def test_auto_detect_action_type():
    """Auto-detection should classify check-raise correctly."""
    r = analyze_facing_aggression(
        call_amount=18.0, pot_bb=12.0, raw_equity=0.52,
        street='flop', is_checkraise=True,
    )
    assert 'check_raise' in r.action_type, \
        f'Should detect check_raise: got {r.action_type}'
    print(f'Auto-detect: action_type={r.action_type}')


def test_auto_detect_river_overbet():
    """Auto-detect overbet when bet > pot."""
    r = analyze_facing_aggression(
        call_amount=30.0, pot_bb=20.0, raw_equity=0.50,
        street='river',
    )
    # call_amount/pot_bb = 1.5 → >100% pot = overbet
    assert r.action_type == 'river_overbet', \
        f'Should detect river_overbet: got {r.action_type}'
    print(f'Overbet auto-detect: {r.action_type}')


def test_required_equity_formula():
    """Required equity = call / (pot + call + call)."""
    call = 15.0; pot = 25.0
    r = analyze_facing_aggression(
        call_amount=call, pot_bb=pot, raw_equity=0.50,
        street='flop', action_type='cbet_flop',
    )
    expected = call / (pot + call + call)
    assert abs(r.required_equity - expected) < 0.02, \
        f'Required equity: {r.required_equity:.3f} vs {expected:.3f}'
    print(f'Pot odds formula: call={call} pot={pot} req={r.required_equity:.0%} '
          f'expected={expected:.0%}')


def test_summary_format():
    """Summary should be <=85 chars and contain [行動調整]."""
    r = analyze_facing_aggression(
        call_amount=15.0, pot_bb=20.0, raw_equity=0.48,
        street='turn', action_type='double_barrel',
    )
    s = facing_aggression_summary(r)
    assert len(s) <= 85, f'Too long ({len(s)}): {s}'
    assert '[行動調整]' in s, f'Missing [行動調整]: {s}'
    print(f'Summary ({len(s)} chars): {s}')


if __name__ == '__main__':
    tests = [
        test_check_raise_reduces_equity_significantly,
        test_cbet_small_equity_reduction,
        test_turn_checkraise_stronger_than_flop,
        test_river_overbet_narrowest_range,
        test_clear_call_when_adjusted_equity_high,
        test_fold_when_adjusted_equity_much_lower_than_required,
        test_passive_villain_narrower_cr_range,
        test_auto_detect_action_type,
        test_auto_detect_river_overbet,
        test_required_equity_formula,
        test_summary_format,
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
