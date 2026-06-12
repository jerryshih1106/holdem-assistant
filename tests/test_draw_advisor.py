"""Tests for poker/draw_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.draw_advisor import analyze_draw, draw_one_liner, DrawAdvice, DRAW_OUTS


def _draw(outs, pot=15.0, bet=8.0, streets=1, stack=80.0, tendency='avg',
          draw_type='flush', fold_to_raise=0.50):
    return analyze_draw(
        outs=outs, pot_bb=pot, villain_bet_bb=bet,
        streets_remaining=streets, eff_stack_bb=stack,
        villain_stack_bb=stack, villain_tendency=tendency,
        draw_type=draw_type, villain_fold_to_raise=fold_to_raise,
    )


def test_returns_draw_advice():
    """analyze_draw should return a DrawAdvice dataclass."""
    r = _draw(9)
    assert isinstance(r, DrawAdvice), f'Expected DrawAdvice: {type(r)}'
    print(f'type: {type(r).__name__}')


def test_required_fields():
    """DrawAdvice should have all documented fields."""
    r = _draw(9)
    fields = ['draw_type', 'outs', 'streets_remaining', 'hit_prob', 'miss_prob',
              'pot_odds', 'has_raw_pot_odds', 'required_implied_bb',
              'realistic_implied_bb', 'implied_sufficient', 'ev_call',
              'ev_raise', 'ev_fold', 'action', 'raise_ok', 'call_ok',
              'villain_tendency', 'reasoning', 'tips']
    for f in fields:
        assert hasattr(r, f), f'DrawAdvice missing field: {f}'
    print(f'All {len(fields)} fields present')


def test_flush_draw_9_outs():
    """Flush draw (9 outs) hit_prob should be ~20% on 1 street."""
    r = _draw(9, streets=1)
    assert 0.18 <= r.hit_prob <= 0.22, \
        f'FD 1-street hit_prob should be ~20%: {r.hit_prob}'
    print(f'FD 1-street hit_prob: {r.hit_prob:.3f}')


def test_two_streets_higher_hit_prob():
    """Two streets should give higher hit probability than one."""
    r1 = _draw(9, streets=1)
    r2 = _draw(9, streets=2)
    assert r2.hit_prob > r1.hit_prob, \
        f'2 streets > 1 street: {r2.hit_prob} vs {r1.hit_prob}'
    print(f'hit_prob: 1-street={r1.hit_prob:.3f}  2-street={r2.hit_prob:.3f}')


def test_hit_plus_miss_equals_one():
    """hit_prob + miss_prob should equal 1.0."""
    r = _draw(9)
    assert abs(r.hit_prob + r.miss_prob - 1.0) < 0.001, \
        f'hit+miss should = 1: {r.hit_prob + r.miss_prob}'
    print(f'hit+miss: {r.hit_prob:.3f}+{r.miss_prob:.3f}={r.hit_prob+r.miss_prob:.3f}')


def test_ev_fold_is_zero():
    """ev_fold should always be 0.0."""
    r = _draw(9)
    assert r.ev_fold == 0.0, f'ev_fold should be 0: {r.ev_fold}'
    print(f'ev_fold: {r.ev_fold}')


def test_pot_odds_formula():
    """pot_odds = villain_bet / (pot + villain_bet)."""
    r = _draw(9, pot=15.0, bet=8.0)
    expected = 8.0 / (15.0 + 8.0)
    assert abs(r.pot_odds - expected) < 0.001, \
        f'pot_odds should be {expected:.3f}: {r.pot_odds:.3f}'
    print(f'pot_odds: {r.pot_odds:.3f} (expected {expected:.3f})')


def test_flush_draw_2_streets_has_raw_pot_odds():
    """Flush draw with 2 streets vs small bet should have raw pot odds."""
    r = _draw(9, pot=15.0, bet=5.0, streets=2)  # 36% equity vs 25% pot odds
    assert r.has_raw_pot_odds is True, \
        f'FD 2-streets vs small bet should have raw pot odds: {r.has_raw_pot_odds}'
    print(f'FD 2-streets: has_raw_pot_odds={r.has_raw_pot_odds} '
          f'hit={r.hit_prob:.2f} pot_odds={r.pot_odds:.2f}')


def test_gutshot_low_hit_prob():
    """Gutshot (4 outs, 1 street) should have hit_prob ~9%."""
    r = _draw(4, streets=1)
    assert 0.08 <= r.hit_prob <= 0.11, \
        f'Gutshot 1-street hit_prob should be ~9%: {r.hit_prob}'
    print(f'Gutshot 1-street hit_prob: {r.hit_prob:.3f}')


def test_gutshot_needs_large_implied():
    """Gutshot with 4 outs facing big bet should need large implied odds."""
    r = _draw(4, pot=20, bet=15, streets=1)
    assert r.required_implied_bb > 20, \
        f'Gutshot vs large bet needs lots of implied: {r.required_implied_bb}'
    print(f'Gutshot required_implied: {r.required_implied_bb:.1f}BB')


def test_payoff_villain_more_realistic_implied():
    """Payoff station should produce higher realistic_implied than tight villain."""
    r_station = _draw(9, tendency='payoff')
    r_tight   = _draw(9, tendency='tight')
    assert r_station.realistic_implied_bb > r_tight.realistic_implied_bb, \
        f'Station implied > tight: {r_station.realistic_implied_bb} vs {r_tight.realistic_implied_bb}'
    print(f'realistic_implied: station={r_station.realistic_implied_bb:.1f} '
          f'tight={r_tight.realistic_implied_bb:.1f}')


def test_oesd_vs_station_profitable():
    """Open-ended straight draw vs calling station should be call or raise (not fold)."""
    # Station: high implied odds (payoff tendency) — calling is at minimum profitable
    r = _draw(8, pot=12, bet=6, streets=1, tendency='payoff', draw_type='oesd',
              fold_to_raise=0.15)   # true station: barely folds to raises
    assert r.action in ('call', 'raise'), \
        f'OESD vs station should call or raise: {r.action}'
    assert r.ev_call > 0, f'OESD vs station call should be +EV: {r.ev_call}'
    print(f'OESD vs station: action={r.action} ev_call={r.ev_call:.2f}')


def test_flush_draw_2_streets_raises():
    """Flush draw with 2 streets and fold equity should prefer raise."""
    r = _draw(9, streets=2, fold_to_raise=0.55)
    assert r.action == 'raise', f'FD 2-streets should raise: {r.action}'
    print(f'FD 2-streets: action={r.action} ev_raise={r.ev_raise:.2f}')


def test_raise_ev_higher_than_call_when_raise():
    """When action is raise, ev_raise should exceed ev_call."""
    r = _draw(9, streets=2, fold_to_raise=0.55)
    if r.action == 'raise':
        assert r.ev_raise > r.ev_call, \
            f'EV(raise)={r.ev_raise:.2f} should > EV(call)={r.ev_call:.2f}'
    print(f'EV: raise={r.ev_raise:.2f} call={r.ev_call:.2f}')


def test_draw_outs_reference():
    """DRAW_OUTS should contain flush and gutshot keys."""
    assert 'flush' in DRAW_OUTS, 'DRAW_OUTS should have flush'
    assert 'gutshot' in DRAW_OUTS, 'DRAW_OUTS should have gutshot'
    assert DRAW_OUTS['flush'] == 9, f'Flush should be 9 outs: {DRAW_OUTS["flush"]}'
    assert DRAW_OUTS['gutshot'] == 4, f'Gutshot should be 4 outs: {DRAW_OUTS["gutshot"]}'
    print(f'DRAW_OUTS: flush={DRAW_OUTS["flush"]} gutshot={DRAW_OUTS["gutshot"]}')


def test_more_outs_higher_hit_prob():
    """More outs should give higher hit probability."""
    r4  = _draw(4, streets=1)
    r9  = _draw(9, streets=1)
    r15 = _draw(15, streets=1)
    assert r4.hit_prob < r9.hit_prob < r15.hit_prob, \
        f'4<9<15 outs: {r4.hit_prob:.3f} {r9.hit_prob:.3f} {r15.hit_prob:.3f}'
    print(f'hit_prob: 4={r4.hit_prob:.3f} 9={r9.hit_prob:.3f} 15={r15.hit_prob:.3f}')


def test_reasoning_is_string():
    """reasoning should be a non-empty string."""
    r = _draw(9)
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10, \
        f'reasoning should be non-empty: {repr(r.reasoning[:40])}'
    print(f'reasoning: {r.reasoning[:60]}')


def test_tips_list():
    """tips should be a non-empty list of strings."""
    r = _draw(9)
    assert isinstance(r.tips, list) and len(r.tips) > 0, \
        f'tips should be non-empty list: {r.tips}'
    print(f'tips: {r.tips[0][:50]}')


def test_draw_one_liner():
    """draw_one_liner should return non-empty string."""
    r = _draw(9)
    line = draw_one_liner(r)
    assert isinstance(line, str) and len(line) > 5, \
        f'one_liner should be non-empty: {repr(line)}'
    print(f'one_liner: {line[:70]}')


def test_tiny_bet_has_raw_pot_odds():
    """Very small bet into large pot gives raw pot odds for flush draw."""
    r = _draw(9, pot=30, bet=2, streets=1)  # bet is tiny fraction
    assert r.has_raw_pot_odds is True, \
        f'Tiny bet should give raw pot odds: {r.has_raw_pot_odds}'
    print(f'Tiny bet: hit={r.hit_prob:.3f} pot_odds={r.pot_odds:.3f}')


def test_fold_gutshot_vs_large_bet_tight_villain():
    """Gutshot on turn facing large bet from tight villain should fold."""
    r = _draw(4, pot=20, bet=16, streets=1, tendency='nitty', draw_type='gutshot')
    assert r.action == 'fold', \
        f'Gutshot vs large bet tight villain should fold: {r.action}'
    print(f'Gutshot vs nitty large bet: action={r.action}')


if __name__ == '__main__':
    tests = [
        test_returns_draw_advice,
        test_required_fields,
        test_flush_draw_9_outs,
        test_two_streets_higher_hit_prob,
        test_hit_plus_miss_equals_one,
        test_ev_fold_is_zero,
        test_pot_odds_formula,
        test_flush_draw_2_streets_has_raw_pot_odds,
        test_gutshot_low_hit_prob,
        test_gutshot_needs_large_implied,
        test_payoff_villain_more_realistic_implied,
        test_oesd_vs_station_calls,
        test_flush_draw_2_streets_raises,
        test_raise_ev_higher_than_call_when_raise,
        test_draw_outs_reference,
        test_more_outs_higher_hit_prob,
        test_reasoning_is_string,
        test_tips_list,
        test_draw_one_liner,
        test_tiny_bet_has_raw_pot_odds,
        test_fold_gutshot_vs_large_bet_tight_villain,
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
