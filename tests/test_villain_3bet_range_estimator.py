"""Tests for poker/villain_3bet_range_estimator.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.villain_3bet_range_estimator import estimate_3bet_range, ThreeBetRangeResult, tbre_one_liner


def _tbre(**kw):
    defaults = dict(
        villain_3bet_pct=0.09, villain_position='BB',
        hero_position='BTN', hero_hand_rank_pct=0.75,
        hero_open_bb=2.5, villain_3bet_size_bb=8.5,
        effective_stack_bb=100.0, villain_fold_to_4b=0.55,
    )
    defaults.update(kw)
    return estimate_3bet_range(**defaults)


def test_returns_correct_type():
    r = _tbre()
    assert isinstance(r, ThreeBetRangeResult)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _tbre()
    fields = [
        'villain_3bet_pct', 'villain_position', 'hero_position',
        'hero_hand_rank_pct', 'hero_open_bb', 'villain_3bet_size_bb',
        'effective_stack_bb', 'value_combos', 'semibluff_combos', 'bluff_combos',
        'total_combos', 'value_pct', 'bluff_pct', 'range_type',
        'hero_equity_vs_range', 'breakeven_equity', 'equity_margin',
        'fourbet_size_bb', 'fourbet_ev', 'call_ev', 'fold_to_4b_estimate',
        'recommended_action', 'action_reasoning', 'verdict', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_tight_3bet_is_value_heavy():
    """4% 3-bet range should be value-heavy."""
    r = _tbre(villain_3bet_pct=0.04)
    assert r.range_type == 'value_heavy', f'Tight 3bet should be value_heavy: {r.range_type}'
    print(f'4% 3-bet range type: {r.range_type} ({r.value_pct:.0%} value)')


def test_wide_3bet_has_more_bluffs():
    """20% 3-bet range should have more bluffs."""
    r_tight = _tbre(villain_3bet_pct=0.04)
    r_wide = _tbre(villain_3bet_pct=0.20)
    assert r_wide.bluff_pct > r_tight.bluff_pct, \
        f'Wide 3-bet should have more bluffs: {r_wide.bluff_pct:.0%} vs {r_tight.bluff_pct:.0%}'
    print(f'Bluff pct: tight={r_tight.bluff_pct:.0%} wide={r_wide.bluff_pct:.0%}')


def test_equity_higher_for_premium_hand():
    """AA (rank 0.99) should have higher equity than 76s (rank 0.55)."""
    r_premium = _tbre(hero_hand_rank_pct=0.99)
    r_weak = _tbre(hero_hand_rank_pct=0.55)
    assert r_premium.hero_equity_vs_range > r_weak.hero_equity_vs_range, \
        f'Premium should have higher equity: {r_premium.hero_equity_vs_range:.0%} vs {r_weak.hero_equity_vs_range:.0%}'
    print(f'Equity: premium={r_premium.hero_equity_vs_range:.0%} weak={r_weak.hero_equity_vs_range:.0%}')


def test_premium_hand_recommends_fourbet():
    """Very strong hand should 4-bet for value."""
    r = _tbre(hero_hand_rank_pct=0.99)  # AA
    assert r.recommended_action == 'fourbet_value', \
        f'AA should 4-bet value: {r.recommended_action}'
    print(f'AA action: {r.recommended_action}')


def test_weak_hand_vs_tight_range_folds():
    """Weak hand vs value-heavy 3-bet range should fold."""
    r = _tbre(villain_3bet_pct=0.04, hero_hand_rank_pct=0.40)
    assert r.recommended_action in ('fold', 'fold_marginal'), \
        f'Weak hand vs tight 3-bet should fold: {r.recommended_action}'
    print(f'Weak hand vs 4% 3-bet: {r.recommended_action}')


def test_breakeven_equity_formula():
    """BE equity = call_cost / (pot + call_cost)."""
    r = _tbre(hero_open_bb=2.5, villain_3bet_size_bb=8.5)
    call_cost = 8.5 - 2.5
    pot = 8.5 + 2.5
    expected_be = call_cost / (pot + call_cost)
    assert abs(r.breakeven_equity - expected_be) < 0.02, \
        f'BE: {r.breakeven_equity:.3f} vs expected {expected_be:.3f}'
    print(f'Breakeven equity: {r.breakeven_equity:.3f}')


def test_equity_margin_consistent():
    """equity_margin = hero_equity - breakeven_equity."""
    r = _tbre()
    expected = round(r.hero_equity_vs_range - r.breakeven_equity, 3)
    assert abs(r.equity_margin - expected) < 0.01, \
        f'Margin: {r.equity_margin:.3f} vs computed {expected:.3f}'
    print(f'Equity margin: {r.equity_margin:+.3f}')


def test_oop_3bet_has_more_bluffs_than_ip():
    """BB 3-bet (OOP) should have more bluffs than CO 3-bet (IP)."""
    r_oop = _tbre(villain_position='BB')
    r_ip = _tbre(villain_position='CO')
    assert r_oop.bluff_pct >= r_ip.bluff_pct, \
        f'OOP should have more bluffs: BB={r_oop.bluff_pct:.0%} CO={r_ip.bluff_pct:.0%}'
    print(f'Bluff pct: BB(OOP)={r_oop.bluff_pct:.0%} CO(IP)={r_ip.bluff_pct:.0%}')


def test_total_combos_positive():
    r = _tbre()
    assert r.total_combos > 0
    print(f'Total combos: {r.total_combos}')


def test_4bet_size_larger_than_3bet():
    """4-bet size should be larger than the 3-bet."""
    r = _tbre()
    assert r.fourbet_size_bb > r.villain_3bet_size_bb, \
        f'4-bet {r.fourbet_size_bb} should > 3-bet {r.villain_3bet_size_bb}'
    print(f'4-bet size: {r.fourbet_size_bb:.1f}BB vs 3-bet {r.villain_3bet_size_bb:.1f}BB')


def test_range_type_valid():
    valid = {'value_heavy', 'balanced', 'bluff_heavy'}
    r = _tbre()
    assert r.range_type in valid, f'Invalid range type: {r.range_type}'
    print(f'Range type: {r.range_type}')


def test_action_valid():
    valid = {'fourbet_value', 'fourbet_bluff', 'call', 'fold', 'fold_marginal'}
    r = _tbre()
    assert r.recommended_action in valid, f'Invalid action: {r.recommended_action}'
    print(f'Action: {r.recommended_action}')


def test_tips_not_empty():
    r = _tbre()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips count: {len(r.tips)}')


def test_verdict_contains_range_type():
    r = _tbre()
    assert r.range_type in r.verdict
    print(f'Verdict: {r.verdict[:80]}')


def test_reasoning_not_empty():
    r = _tbre()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'Reasoning: {r.reasoning[:80]}')


def test_all_positions_work():
    for pos in ['BB', 'SB', 'CO', 'BTN', 'HJ', 'UTG']:
        r = _tbre(villain_position=pos)
        assert isinstance(r, ThreeBetRangeResult)
    print('All positions work')


def test_equity_in_valid_range():
    r = _tbre()
    assert 0.15 <= r.hero_equity_vs_range <= 0.85, \
        f'Equity out of range: {r.hero_equity_vs_range}'
    print(f'Equity: {r.hero_equity_vs_range:.0%}')


def test_one_liner():
    r = _tbre()
    line = tbre_one_liner(r)
    assert '3BET' in line and 'eq=' in line and '4b_ev=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_tight_3bet_is_value_heavy, test_wide_3bet_has_more_bluffs,
        test_equity_higher_for_premium_hand, test_premium_hand_recommends_fourbet,
        test_weak_hand_vs_tight_range_folds, test_breakeven_equity_formula,
        test_equity_margin_consistent, test_oop_3bet_has_more_bluffs_than_ip,
        test_total_combos_positive, test_4bet_size_larger_than_3bet,
        test_range_type_valid, test_action_valid, test_tips_not_empty,
        test_verdict_contains_range_type, test_reasoning_not_empty,
        test_all_positions_work, test_equity_in_valid_range, test_one_liner,
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
