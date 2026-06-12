"""Tests for poker/probe_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.probe_advisor import analyze_probe, probe_one_liner, ProbeAdvice


def _probe(equity, pot=12.0, stack=70.0, check_freq=0.55, fold_to_probe=0.50,
           wetness=0.30, street='turn', ip=True, draw=False, cbet=0.60):
    return analyze_probe(
        hero_equity=equity, pot_bb=pot, eff_stack_bb=stack,
        villain_turn_check_freq=check_freq, villain_fold_to_probe=fold_to_probe,
        board_wetness=wetness, street=street, in_position=ip,
        hero_has_draw=draw, villain_cbet_flop_freq=cbet,
    )


def test_returns_probe_advice():
    """analyze_probe should return a ProbeAdvice dataclass."""
    r = _probe(0.55)
    assert isinstance(r, ProbeAdvice), f'Expected ProbeAdvice: {type(r)}'
    print(f'type: {type(r).__name__}')


def test_required_fields():
    """ProbeAdvice should have all documented fields."""
    r = _probe(0.55)
    fields = ['street', 'hero_equity', 'pot_bb', 'villain_check_freq',
              'villain_fold_to_probe', 'bet_size_bb', 'bet_size_pct',
              'ev_bet', 'ev_check', 'action', 'probe_type',
              'fold_equity_gained', 'reasoning', 'tips']
    for f in fields:
        assert hasattr(r, f), f'ProbeAdvice missing field: {f}'
    print(f'All {len(fields)} fields present')


def test_value_probe_bets():
    """High equity should produce value probe and bet action."""
    r = _probe(0.75)
    assert r.probe_type == 'value', f'75% equity should be value probe: {r.probe_type}'
    assert r.action == 'bet', f'Value probe should bet: {r.action}'
    print(f'75% equity: probe_type={r.probe_type} action={r.action}')


def test_semi_bluff_probe():
    """Medium equity with good fold equity should semi-bluff probe."""
    r = _probe(0.48, check_freq=0.65, fold_to_probe=0.55)
    assert r.probe_type == 'semi-bluff', \
        f'48% eq high fold should semi-bluff: {r.probe_type}'
    assert r.action == 'bet', f'Semi-bluff should bet: {r.action}'
    print(f'Semi-bluff probe: type={r.probe_type} action={r.action}')


def test_low_equity_low_fold_checks():
    """Low equity with low fold equity should check."""
    r = _probe(0.25, fold_to_probe=0.30, check_freq=0.40)
    assert r.action == 'check', \
        f'Low equity low fold eq should check: {r.action}'
    print(f'Low equity low fold: action={r.action} probe_type={r.probe_type}')


def test_ev_bet_higher_than_check_when_betting():
    """When action is bet, ev_bet should exceed ev_check."""
    r = _probe(0.75)
    if r.action == 'bet':
        assert r.ev_bet > r.ev_check, \
            f'EV(bet)={r.ev_bet:.2f} should > EV(check)={r.ev_check:.2f}'
    print(f'EV: bet={r.ev_bet:.2f} check={r.ev_check:.2f}')


def test_ev_check_formula():
    """ev_check = equity * pot_bb."""
    r = _probe(0.55, pot=12.0)
    expected = 0.55 * 12.0
    assert abs(r.ev_check - expected) < 0.5, \
        f'ev_check should be ~{expected:.2f}: {r.ev_check:.2f}'
    print(f'ev_check: {r.ev_check:.2f} (expected {expected:.2f})')


def test_bet_size_scales_with_pot():
    """Larger pot should give larger bet size."""
    r_small = _probe(0.55, pot=10.0)
    r_large = _probe(0.55, pot=30.0)
    assert r_large.bet_size_bb > r_small.bet_size_bb, \
        f'Larger pot → larger bet: {r_large.bet_size_bb} vs {r_small.bet_size_bb}'
    print(f'bet_size: pot=10→{r_small.bet_size_bb:.1f}  pot=30→{r_large.bet_size_bb:.1f}')


def test_river_bet_size_pct_larger():
    """River probe should have larger bet_size_pct than flop."""
    r_flop  = _probe(0.55, street='flop')
    r_river = _probe(0.55, street='river')
    assert r_river.bet_size_pct >= r_flop.bet_size_pct, \
        f'River pct >= flop pct: {r_river.bet_size_pct} vs {r_flop.bet_size_pct}'
    print(f'bet_size_pct: flop={r_flop.bet_size_pct:.2f} river={r_river.bet_size_pct:.2f}')


def test_wet_board_larger_probe():
    """Wet board should produce larger bet size than dry board."""
    r_dry = _probe(0.55, wetness=0.10)
    r_wet = _probe(0.55, wetness=0.80)
    assert r_wet.bet_size_pct >= r_dry.bet_size_pct, \
        f'Wet >= dry bet: {r_wet.bet_size_pct} vs {r_dry.bet_size_pct}'
    print(f'bet_size_pct: dry={r_dry.bet_size_pct:.2f} wet={r_wet.bet_size_pct:.2f}')


def test_fold_equity_gained_positive():
    """fold_equity_gained should be positive when betting."""
    r = _probe(0.50, fold_to_probe=0.55)
    assert r.fold_equity_gained >= 0, \
        f'fold_equity_gained should be >= 0: {r.fold_equity_gained}'
    print(f'fold_equity_gained: {r.fold_equity_gained:.2f}BB')


def test_high_villain_check_freq_probe_tip():
    """High villain check frequency should mention it in tips."""
    r = _probe(0.48, check_freq=0.70, fold_to_probe=0.55)
    tip_text = ' '.join(r.tips)
    assert 'check' in tip_text.lower() or 'up' in tip_text.lower() or '70' in tip_text, \
        f'Tips should mention villain giving up: {r.tips}'
    print(f'High check freq tips: {r.tips[0][:60]}')


def test_probe_type_value_for_high_equity():
    """Equity > 60% should be classified as value probe."""
    r = _probe(0.70)
    assert r.probe_type == 'value', \
        f'70% equity should be value probe: {r.probe_type}'
    print(f'70% equity: probe_type={r.probe_type}')


def test_probe_type_none_for_low_equity_low_fold():
    """Low equity with low fold-to-probe should be none type."""
    r = _probe(0.20, fold_to_probe=0.30, check_freq=0.35)
    assert r.probe_type in ('none', 'pure-bluff') or r.action == 'check', \
        f'Low equity low fold: {r.probe_type} / {r.action}'
    print(f'Low equity low fold: probe_type={r.probe_type} action={r.action}')


def test_reasoning_is_string():
    """reasoning should be a non-empty string."""
    r = _probe(0.55)
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10, \
        f'reasoning should be non-empty: {repr(r.reasoning[:40])}'
    print(f'reasoning: {r.reasoning[:60]}')


def test_tips_is_list():
    """tips should be a list of strings."""
    r = _probe(0.55)
    assert isinstance(r.tips, list) and len(r.tips) > 0, \
        f'tips should be non-empty list: {r.tips}'
    print(f'tips count: {len(r.tips)}')


def test_probe_one_liner():
    """probe_one_liner should return non-empty string."""
    r = _probe(0.55)
    line = probe_one_liner(r)
    assert isinstance(line, str) and len(line) > 5, \
        f'one_liner should be non-empty: {repr(line)}'
    print(f'one_liner: {line}')


def test_pure_bluff_probe():
    """Very low equity with high fold equity should be pure-bluff probe."""
    r = _probe(0.20, fold_to_probe=0.65, check_freq=0.70)
    assert r.probe_type in ('pure-bluff', 'semi-bluff'), \
        f'Low equity high fold should bluff probe: {r.probe_type}'
    print(f'Pure bluff: probe_type={r.probe_type} action={r.action}')


def test_draw_increases_bet_size():
    """Having a draw on wet board should increase bet size pct."""
    r_no_draw = _probe(0.45, wetness=0.60, draw=False)
    r_draw    = _probe(0.45, wetness=0.60, draw=True)
    assert r_draw.bet_size_pct >= r_no_draw.bet_size_pct, \
        f'Draw should >= no draw bet size: {r_draw.bet_size_pct} vs {r_no_draw.bet_size_pct}'
    print(f'bet_size_pct: no_draw={r_no_draw.bet_size_pct:.2f} draw={r_draw.bet_size_pct:.2f}')


def test_bet_capped_by_stack():
    """bet_size_bb should not exceed 60% of effective stack."""
    r = _probe(0.55, pot=100.0, stack=20.0)   # large pot relative to stack
    assert r.bet_size_bb <= 20.0 * 0.60 + 0.1, \
        f'bet_size should be capped by stack: {r.bet_size_bb}'
    print(f'bet_size_bb (capped): {r.bet_size_bb:.1f} (stack={20.0})')


if __name__ == '__main__':
    tests = [
        test_returns_probe_advice,
        test_required_fields,
        test_value_probe_bets,
        test_semi_bluff_probe,
        test_low_equity_low_fold_checks,
        test_ev_bet_higher_than_check_when_betting,
        test_ev_check_formula,
        test_bet_size_scales_with_pot,
        test_river_bet_size_pct_larger,
        test_wet_board_larger_probe,
        test_fold_equity_gained_positive,
        test_high_villain_check_freq_probe_tip,
        test_probe_type_value_for_high_equity,
        test_probe_type_none_for_low_equity_low_fold,
        test_reasoning_is_string,
        test_tips_is_list,
        test_probe_one_liner,
        test_pure_bluff_probe,
        test_draw_increases_bet_size,
        test_bet_capped_by_stack,
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
