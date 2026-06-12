"""Tests for poker/river_decision.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.river_decision import analyze_river, river_summary


def test_strong_hand_bets_river():
    """Strong hand (equity 80%+) IP should recommend value betting."""
    r = analyze_river(equity=0.82, pot_bb=20.0, position='ip',
                      villain_bet=0.0, stack_bb=80.0)
    assert r.situation == 'hero_acts_first'
    assert r.thin_value_ok is True, \
        f'Strong hand should allow value bet: {r.thin_value_ok}'
    assert r.sizing_bb > 0, f'Should recommend a positive bet size: {r.sizing_bb}'
    print(f'Strong river: action={r.action[:8]} size={r.sizing_bb:.1f}BB')


def test_facing_bet_situation():
    """When villain bets, situation should be facing_bet."""
    r = analyze_river(equity=0.55, pot_bb=15.0, position='ip',
                      villain_bet=10.0, stack_bb=60.0)
    assert r.situation == 'facing_bet', \
        f'Should be facing_bet when villain_bet>0: {r.situation}'
    print(f'Facing bet: situation={r.situation} equity_needed={r.equity_needed:.0%}')


def test_weak_hand_facing_large_bet_folds():
    """Very weak hand facing large overbet should fold."""
    r = analyze_river(equity=0.15, pot_bb=20.0, position='oop',
                      villain_bet=30.0, stack_bb=80.0,
                      villain_bluff_pct=0.15, villain_af=0.8)
    assert r.situation == 'facing_bet'
    assert r.equity_needed > 0.15, \
        f'Equity needed should exceed hero equity for fold: {r.equity_needed:.0%}'
    print(f'Weak vs overbet: equity_needed={r.equity_needed:.0%} hero={0.15:.0%}')


def test_alpha_between_0_and_1():
    """alpha (pot odds fraction) should be between 0 and 1."""
    r = analyze_river(equity=0.60, pot_bb=20.0, position='ip',
                      villain_bet=0.0, stack_bb=80.0)
    assert 0.0 <= r.alpha <= 1.0, f'alpha out of bounds: {r.alpha}'
    print(f'Alpha: {r.alpha:.0%}')


def test_sizing_pct_between_0_and_1_point_5():
    """sizing_pct should be a reasonable pot fraction (0..1.5)."""
    r = analyze_river(equity=0.75, pot_bb=20.0, position='ip',
                      villain_bet=0.0, stack_bb=80.0)
    assert 0.0 <= r.sizing_pct <= 1.5, \
        f'sizing_pct out of bounds: {r.sizing_pct}'
    print(f'Sizing: {r.sizing_pct:.0%} pot = {r.sizing_bb:.1f}BB')


def test_sizing_bb_matches_pct():
    """sizing_bb should approximately equal sizing_pct * pot_bb."""
    pot = 20.0
    r = analyze_river(equity=0.72, pot_bb=pot, position='ip',
                      villain_bet=0.0, stack_bb=80.0)
    expected = r.sizing_pct * pot
    assert abs(r.sizing_bb - expected) < 1.0, \
        f'sizing_bb {r.sizing_bb:.1f} should ~= pct×pot {expected:.1f}'
    print(f'Sizing: {r.sizing_bb:.1f}BB (pct×pot={expected:.1f}BB)')


def test_bluff_catcher_equity_needed_matches_alpha():
    """For facing a bet, equity_needed should reflect pot odds (alpha)."""
    villain_bet = 10.0
    pot = 20.0
    r = analyze_river(equity=0.40, pot_bb=pot, position='ip',
                      villain_bet=villain_bet, stack_bb=60.0)
    expected_alpha = villain_bet / (pot + villain_bet)
    assert abs(r.equity_needed - expected_alpha) < 0.05, \
        f'equity_needed {r.equity_needed:.0%} should ~= alpha {expected_alpha:.0%}'
    print(f'Bluff catch threshold: {r.equity_needed:.0%} (alpha={expected_alpha:.0%})')


def test_high_blocker_score_improves_bluff():
    """High blocker score should not crash and produce valid result."""
    r = analyze_river(equity=0.25, pot_bb=20.0, position='ip',
                      villain_bet=0.0, stack_bb=60.0,
                      blocker_bluff=0.90, blocker_call=0.40)
    assert isinstance(r.action, str) and len(r.action) > 0
    assert 0.0 <= r.sizing_pct <= 1.5
    print(f'High blocker bluff: action={r.action[:8]} sizing={r.sizing_pct:.0%}')


def test_reasoning_is_string():
    """reasoning should be a non-empty string."""
    r = analyze_river(equity=0.65, pot_bb=18.0, position='ip',
                      villain_bet=0.0, stack_bb=60.0)
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 3, \
        f'reasoning should be non-empty: {r.reasoning!r}'
    print(f'Reasoning: {r.reasoning[:50]}')


def test_tips_is_list():
    """tips should be a list."""
    r = analyze_river(equity=0.65, pot_bb=18.0, position='ip',
                      villain_bet=0.0, stack_bb=60.0)
    assert isinstance(r.tips, list), f'tips should be list: {type(r.tips)}'
    print(f'Tips count: {len(r.tips)}')


def test_river_summary_returns_string():
    """river_summary should return a non-empty string."""
    r = analyze_river(equity=0.70, pot_bb=20.0, position='ip',
                      villain_bet=0.0, stack_bb=60.0)
    s = river_summary(r)
    assert isinstance(s, str) and len(s) > 5, \
        f'river_summary should be non-empty: {s!r}'
    print(f'River summary: {s[:60]}')


if __name__ == '__main__':
    tests = [
        test_strong_hand_bets_river,
        test_facing_bet_situation,
        test_weak_hand_facing_large_bet_folds,
        test_alpha_between_0_and_1,
        test_sizing_pct_between_0_and_1_point_5,
        test_sizing_bb_matches_pct,
        test_bluff_catcher_equity_needed_matches_alpha,
        test_high_blocker_score_improves_bluff,
        test_reasoning_is_string,
        test_tips_is_list,
        test_river_summary_returns_string,
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
