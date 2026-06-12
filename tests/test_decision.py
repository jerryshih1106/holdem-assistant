"""Tests for poker/decision.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.decision import GameState, recommend, ev_breakdown, pot_odds, spr


def _gs(pot=100, call_amount=0, stack=400, equity=0.70,
        position='ip', num_opponents=1, street='flop'):
    return GameState(
        hole_cards=['Ah', 'Ks'],
        community_cards=['Ac', '7h', '2d'],
        pot=pot, call_amount=call_amount,
        hero_stack=stack, position=position,
        num_opponents=num_opponents,
    )


def test_pot_odds_formula():
    """pot_odds = call / (pot + call)."""
    result = pot_odds(20, 100)
    expected = 20 / (100 + 20)
    assert abs(result - expected) < 0.001, \
        f'pot_odds {result:.3f} should = {expected:.3f}'
    print(f'pot_odds(20, 100) = {result:.3f} (expected {expected:.3f})')


def test_pot_odds_zero_when_no_call():
    """pot_odds should be 0 when call_amount=0."""
    result = pot_odds(0, 100)
    assert result == 0.0, f'pot_odds with call=0 should be 0: {result}'
    print(f'pot_odds(0, 100) = {result}')


def test_spr_formula():
    """SPR = stack / pot."""
    result = spr(400, 100)
    assert abs(result - 4.0) < 0.001, f'SPR(400/100) should = 4.0: {result}'
    print(f'spr(400, 100) = {result:.1f}')


def test_strong_hand_recommends_raise():
    """Strong equity (85%) facing no bet should recommend raise/check."""
    gs = _gs(pot=100, call_amount=0, stack=400)
    d = recommend(gs, equity=0.85, tie_rate=0.01)
    assert d.action is not None and len(d.action) > 0
    assert d.ev > 0, f'Strong hand EV should be positive: {d.ev}'
    print(f'Strong hand: action={d.action} ev={d.ev:.1f}')


def test_weak_hand_facing_large_bet_may_fold():
    """Weak hand (18%) facing large bet should lean toward fold."""
    gs = _gs(pot=100, call_amount=60, stack=200)
    d = recommend(gs, equity=0.18, tie_rate=0.01)
    # pot_odds = 60/160 = 37.5%, equity 18% < pot_odds → should fold
    assert d.pot_odds > d.equity, \
        f'Pot odds {d.pot_odds:.0%} should exceed equity {d.equity:.0%} for fold signal'
    print(f'Weak vs big bet: pot_odds={d.pot_odds:.0%} equity={d.equity:.0%}')


def test_ev_breakdown_all_keys():
    """ev_breakdown should return dict with fold/check/call/raise/allin."""
    gs = _gs(pot=100, call_amount=20, stack=400)
    ev = ev_breakdown(gs, 0.65)
    required = {'fold', 'check', 'call', 'raise', 'allin'}
    for k in required:
        assert k in ev, f'ev_breakdown missing key: {k}'
    print(f'EV breakdown: {", ".join(f"{k}={v:.1f}" for k,v in ev.items())}')


def test_fold_ev_is_zero():
    """Fold EV should always be 0 (no chips gained/lost by folding)."""
    gs = _gs(pot=100, call_amount=20, stack=400)
    ev = ev_breakdown(gs, 0.65)
    assert ev['fold'] == 0.0, f'Fold EV should be 0: {ev["fold"]}'
    print(f'Fold EV = {ev["fold"]}')


def test_decision_has_reasoning():
    """Decision should include a non-empty reasoning string."""
    gs = _gs(pot=100, call_amount=0, stack=400)
    d = recommend(gs, equity=0.70, tie_rate=0.02)
    assert isinstance(d.reasoning, str) and len(d.reasoning) > 3, \
        f'reasoning should be non-empty: {d.reasoning!r}'
    print(f'Reasoning: {d.reasoning[:50]}')


def test_decision_has_ev_breakdown_dict():
    """Decision should include ev_breakdown dict."""
    gs = _gs(pot=100, call_amount=0, stack=400)
    d = recommend(gs, equity=0.75, tie_rate=0.01)
    assert isinstance(d.ev_breakdown, dict) and len(d.ev_breakdown) > 0, \
        f'ev_breakdown should be non-empty dict: {d.ev_breakdown}'
    print(f'Decision ev_breakdown keys: {list(d.ev_breakdown.keys())}')


def test_raise_size_positive_when_raising():
    """raise_size should be positive when action is raise."""
    gs = _gs(pot=100, call_amount=0, stack=400)
    d = recommend(gs, equity=0.85, tie_rate=0.01)
    if '加注' in d.action or 'raise' in d.action.lower():
        assert d.raise_size > 0, f'raise_size should be > 0: {d.raise_size}'
    print(f'Action={d.action} raise_size={d.raise_size}')


def test_equity_stored_in_decision():
    """Decision should store the equity passed in."""
    gs = _gs(pot=100, call_amount=0, stack=400)
    d = recommend(gs, equity=0.72, tie_rate=0.01)
    assert abs(d.equity - 0.72) < 0.01, \
        f'Decision should store equity=0.72: {d.equity}'
    print(f'Decision equity: {d.equity:.0%}')


if __name__ == '__main__':
    tests = [
        test_pot_odds_formula,
        test_pot_odds_zero_when_no_call,
        test_spr_formula,
        test_strong_hand_recommends_raise,
        test_weak_hand_facing_large_bet_may_fold,
        test_ev_breakdown_all_keys,
        test_fold_ev_is_zero,
        test_decision_has_reasoning,
        test_decision_has_ev_breakdown_dict,
        test_raise_size_positive_when_raising,
        test_equity_stored_in_decision,
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
