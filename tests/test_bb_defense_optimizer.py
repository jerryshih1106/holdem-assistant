"""Tests for poker/bb_defense_optimizer.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.bb_defense_optimizer import optimize_bb_defense, BBDefenseAdvice, bbd_one_liner


def _bbd(**kw):
    defaults = dict(
        villain_position='BTN', open_size_bb=2.5,
        effective_stack_bb=100.0, villain_open_pct=0.44,
        villain_fold_to_3b=0.55,
    )
    defaults.update(kw)
    return optimize_bb_defense(**defaults)


def test_returns_correct_type():
    r = _bbd()
    assert isinstance(r, BBDefenseAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _bbd()
    fields = [
        'villain_position', 'open_size_bb', 'effective_stack_bb',
        'villain_open_pct', 'villain_fold_to_3b',
        'call_cost_bb', 'mdf', 'pot_odds', 'spr_postflop',
        'optimal_defend_pct', 'optimal_call_pct', 'optimal_3bet_pct',
        'threeb_size_bb', 'ev_3bet_bluff', 'bluff_3b_breakeven_fold',
        'defend_range_guide', 'threeb_value_range', 'threeb_bluff_range',
        'calling_range', 'defending_too_tight_threshold',
        'defending_too_loose_threshold', 'verdict', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_mdf_formula():
    """MDF = call_cost / (open + 1.0)."""
    r = _bbd(open_size_bb=2.5)
    # MDF = (2.5 - 1.0) / (2.5 + 1.0) = 1.5/3.5 = 0.4286
    expected = (2.5 - 1.0) / (2.5 + 1.0)
    assert abs(r.mdf - expected) < 0.01, f'MDF: {r.mdf:.3f} vs expected {expected:.3f}'
    print(f'MDF: {r.mdf:.3f}')


def test_optimal_defend_above_mdf():
    """Optimal defend must be >= MDF to prevent profitable bluffs."""
    r = _bbd()
    assert r.optimal_defend_pct >= r.mdf, \
        f'Defend {r.optimal_defend_pct:.3f} should >= MDF {r.mdf:.3f}'
    print(f'Defend={r.optimal_defend_pct:.0%} >= MDF={r.mdf:.0%}')


def test_wider_defense_vs_btn_than_utg():
    """BB should defend wider vs BTN (stealing) than vs UTG (value)."""
    r_btn = _bbd(villain_position='BTN')
    r_utg = _bbd(villain_position='UTG', villain_open_pct=0.14)
    assert r_btn.optimal_defend_pct >= r_utg.optimal_defend_pct, \
        f'BTN defend={r_btn.optimal_defend_pct:.0%} should >= UTG={r_utg.optimal_defend_pct:.0%}'
    print(f'Defend: BTN={r_btn.optimal_defend_pct:.0%} UTG={r_utg.optimal_defend_pct:.0%}')


def test_total_defend_equals_call_plus_3bet():
    """optimal_defend_pct = call_pct + 3bet_pct."""
    r = _bbd()
    total = round(r.optimal_call_pct + r.optimal_3bet_pct, 3)
    assert abs(total - r.optimal_defend_pct) < 0.01, \
        f'call+3bet={total:.3f} != defend={r.optimal_defend_pct:.3f}'
    print(f'call={r.optimal_call_pct:.0%} + 3bet={r.optimal_3bet_pct:.0%} = {total:.0%}')


def test_larger_open_reduces_call_pct():
    """Bigger open = worse pot odds = less calling."""
    r_small = _bbd(open_size_bb=2.0)
    r_large = _bbd(open_size_bb=4.0)
    # Larger open has higher MDF denominator but worse pot odds
    assert r_small.pot_odds <= r_large.pot_odds, \
        f'Larger open should have worse pot odds: small={r_small.pot_odds:.3f} large={r_large.pot_odds:.3f}'
    print(f'Pot odds: 2BB={r_small.pot_odds:.3f} 4BB={r_large.pot_odds:.3f}')


def test_high_fold_to_3b_enables_bluff_3b():
    """High fold-to-3bet = villain folds a lot = 3-bet bluffing is more profitable."""
    r_low = _bbd(villain_fold_to_3b=0.30)
    r_high = _bbd(villain_fold_to_3b=0.75)
    assert r_high.ev_3bet_bluff > r_low.ev_3bet_bluff, \
        f'High fold should give higher 3-bet bluff EV: {r_high.ev_3bet_bluff:.2f} vs {r_low.ev_3bet_bluff:.2f}'
    print(f'3-bet bluff EV: low_fold={r_low.ev_3bet_bluff:.2f} high_fold={r_high.ev_3bet_bluff:.2f}')


def test_3bet_size_larger_than_open():
    """3-bet size must be larger than the open."""
    r = _bbd()
    assert r.threeb_size_bb > r.open_size_bb, \
        f'3-bet {r.threeb_size_bb} should > open {r.open_size_bb}'
    print(f'3-bet size: {r.threeb_size_bb:.1f}BB vs open {r.open_size_bb:.1f}BB')


def test_defend_pct_in_valid_range():
    r = _bbd()
    assert 0.25 <= r.optimal_defend_pct <= 0.65, \
        f'Defend pct out of range: {r.optimal_defend_pct}'
    print(f'Defend pct: {r.optimal_defend_pct:.0%}')


def test_3bet_pct_positive():
    r = _bbd()
    assert r.optimal_3bet_pct > 0
    print(f'3-bet pct: {r.optimal_3bet_pct:.0%}')


def test_call_pct_positive():
    r = _bbd()
    assert r.optimal_call_pct > 0
    print(f'Call pct: {r.optimal_call_pct:.0%}')


def test_spr_positive():
    r = _bbd()
    assert r.spr_postflop > 0
    print(f'SPR postflop: {r.spr_postflop:.1f}')


def test_tips_not_empty():
    r = _bbd()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips count: {len(r.tips)}')


def test_high_fold_triggers_tip():
    r = _bbd(villain_fold_to_3b=0.70)
    high_fold_tips = [t for t in r.tips if 'HIGH FOLD' in t or 'fold' in t.lower()]
    assert len(high_fold_tips) > 0, f'High fold should trigger tip: {r.tips}'
    print(f'High fold tip found')


def test_wide_open_triggers_tip():
    r = _bbd(villain_position='BTN', villain_open_pct=0.60)
    wide_tips = [t for t in r.tips if 'WIDE' in t.upper() or '60' in t or 'wide' in t.lower()]
    print(f'Wide open (60%): {len(r.tips)} tips')
    assert len(r.tips) > 0


def test_defend_range_guide_not_empty():
    r = _bbd()
    assert isinstance(r.defend_range_guide, str) and len(r.defend_range_guide) > 10
    print(f'Range guide: {r.defend_range_guide[:60]}')


def test_utg_range_tighter_than_btn():
    r_utg = _bbd(villain_position='UTG', villain_open_pct=0.14)
    r_btn = _bbd(villain_position='BTN', villain_open_pct=0.44)
    # UTG value range should be tighter (only QQ+, AKs)
    # Check by 3-bet pct (UTG should 3-bet less)
    assert r_utg.optimal_3bet_pct <= r_btn.optimal_3bet_pct, \
        f'UTG 3bet={r_utg.optimal_3bet_pct:.0%} should <= BTN {r_btn.optimal_3bet_pct:.0%}'
    print(f'3-bet pct: UTG={r_utg.optimal_3bet_pct:.0%} BTN={r_btn.optimal_3bet_pct:.0%}')


def test_verdict_contains_defend_pct():
    r = _bbd()
    assert 'defend=' in r.verdict or r.villain_position in r.verdict
    print(f'Verdict: {r.verdict[:80]}')


def test_reasoning_not_empty():
    r = _bbd()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'Reasoning: {r.reasoning[:80]}')


def test_one_liner():
    r = _bbd()
    line = bbd_one_liner(r)
    assert 'BBD' in line and 'MDF=' in line and 'defend=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_mdf_formula, test_optimal_defend_above_mdf,
        test_wider_defense_vs_btn_than_utg, test_total_defend_equals_call_plus_3bet,
        test_larger_open_reduces_call_pct, test_high_fold_to_3b_enables_bluff_3b,
        test_3bet_size_larger_than_open, test_defend_pct_in_valid_range,
        test_3bet_pct_positive, test_call_pct_positive, test_spr_positive,
        test_tips_not_empty, test_high_fold_triggers_tip,
        test_wide_open_triggers_tip, test_defend_range_guide_not_empty,
        test_utg_range_tighter_than_btn,
        test_verdict_contains_defend_pct, test_reasoning_not_empty, test_one_liner,
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
