"""Tests for poker/river_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.river_advisor import (
    analyze_river_call, river_one_liner, analyze_sizing_tell, RiverCallResult
)

_BOARD = ['Ah', '7c', '2d', 'Jh', '5s']   # dry river board


def _call(hole_cards, villain_bet_bb=10.0, pot_bb=20.0, equity=0.60,
          freq=0.35, vpip=0.28):
    return analyze_river_call(
        hole_cards=hole_cards, community=_BOARD,
        pot_bb=pot_bb, villain_bet_bb=villain_bet_bb,
        villain_river_bet_freq=freq, villain_vpip=vpip,
        hero_equity=equity,
    )


def test_returns_river_call_result():
    """analyze_river_call should return a RiverCallResult dataclass."""
    r = _call(['Ah', 'Kd'], equity=0.70)
    assert isinstance(r, RiverCallResult), f'Expected RiverCallResult: {type(r)}'
    print(f'type: {type(r).__name__}')


def test_required_fields():
    """RiverCallResult should have all documented fields."""
    r = _call(['Ah', 'Kd'], equity=0.70)
    fields = ['pot_bb', 'villain_bet_bb', 'total_pot_bb', 'pot_odds', 'bet_fraction',
              'mdf', 'hero_call_freq', 'blocker_score', 'blocking_combos',
              'unblocking_combos', 'villain_bet_freq', 'adjusted_call_threshold',
              'ev_call', 'ev_fold', 'action', 'confidence', 'edge',
              'reasoning', 'key_factors']
    for f in fields:
        assert hasattr(r, f), f'RiverCallResult missing field: {f}'
    print(f'All {len(fields)} fields present')


def test_pot_odds_formula():
    """pot_odds should equal villain_bet / (pot + villain_bet)."""
    r = _call(['Ah', 'Kd'], pot_bb=20.0, villain_bet_bb=10.0, equity=0.60)
    expected = 10.0 / (20.0 + 10.0)
    assert abs(r.pot_odds - expected) < 0.001, \
        f'pot_odds should be {expected:.3f}: {r.pot_odds:.3f}'
    print(f'pot_odds: {r.pot_odds:.3f} (expected {expected:.3f})')


def test_mdf_formula():
    """mdf should equal pot / (pot + villain_bet)."""
    r = _call(['Ah', 'Kd'], pot_bb=20.0, villain_bet_bb=10.0, equity=0.60)
    expected = 20.0 / (20.0 + 10.0)
    assert abs(r.mdf - expected) < 0.001, \
        f'mdf should be {expected:.3f}: {r.mdf:.3f}'
    print(f'mdf: {r.mdf:.3f} (expected {expected:.3f})')


def test_pot_odds_plus_mdf_equals_one():
    """pot_odds + mdf should equal 1.0."""
    r = _call(['Ah', 'Kd'], equity=0.60)
    assert abs(r.pot_odds + r.mdf - 1.0) < 0.001, \
        f'pot_odds + mdf should = 1: {r.pot_odds + r.mdf}'
    print(f'pot_odds + mdf = {r.pot_odds + r.mdf:.3f}')


def test_ev_fold_is_zero():
    """ev_fold should always be 0.0."""
    r = _call(['Ah', 'Kd'], equity=0.60)
    assert r.ev_fold == 0.0, f'ev_fold should be 0: {r.ev_fold}'
    print(f'ev_fold: {r.ev_fold}')


def test_high_equity_call():
    """Hero with 80% equity should call."""
    r = _call(['Ah', 'Ad'], equity=0.80)
    assert r.action == 'call', f'80% equity should call: {r.action}'
    print(f'80% equity action: {r.action}  ev={r.ev_call:.2f}')


def test_low_equity_fold():
    """Hero with 10% equity facing half-pot bet should fold."""
    r = _call(['2h', '3c'], equity=0.10, villain_bet_bb=10.0, pot_bb=20.0)
    assert r.action == 'fold', f'10% equity should fold: {r.action}'
    print(f'10% equity action: {r.action}  ev={r.ev_call:.2f}')


def test_ev_call_formula():
    """ev_call = equity * total_pot - (1-equity) * villain_bet."""
    r = _call(['Ah', 'Kd'], pot_bb=20.0, villain_bet_bb=10.0, equity=0.60)
    total = 20.0 + 10.0
    expected = 0.60 * total - (1 - 0.60) * 10.0
    assert abs(r.ev_call - expected) < 0.1, \
        f'ev_call should be {expected:.2f}: {r.ev_call:.2f}'
    print(f'ev_call: {r.ev_call:.2f} (expected {expected:.2f})')


def test_large_bet_high_pot_odds():
    """Large bet (overbet) should require higher equity (higher pot_odds)."""
    r_half = _call(['Ah', 'Kd'], pot_bb=20.0, villain_bet_bb=10.0, equity=0.60)
    r_over = _call(['Ah', 'Kd'], pot_bb=20.0, villain_bet_bb=30.0, equity=0.60)
    assert r_over.pot_odds > r_half.pot_odds, \
        f'Overbet needs more equity: {r_over.pot_odds:.2f} vs {r_half.pot_odds:.2f}'
    print(f'pot_odds: half={r_half.pot_odds:.2f}  over={r_over.pot_odds:.2f}')


def test_small_bet_low_pot_odds():
    """Small bet should require less equity (lower pot_odds)."""
    r_small = _call(['Ah', 'Kd'], pot_bb=20.0, villain_bet_bb=4.0, equity=0.60)
    r_full  = _call(['Ah', 'Kd'], pot_bb=20.0, villain_bet_bb=20.0, equity=0.60)
    assert r_small.pot_odds < r_full.pot_odds, \
        f'Small bet lower pot_odds: {r_small.pot_odds:.2f} vs {r_full.pot_odds:.2f}'
    print(f'pot_odds: small={r_small.pot_odds:.2f}  full={r_full.pot_odds:.2f}')


def test_blocker_score_ace_on_board():
    """Holding an ace when board has ace should give positive blocker score."""
    r = analyze_river_call(
        hole_cards=['Ah', 'Kd'],
        community=['As', '7h', '2d', 'Jh', '5s'],  # Ace on board
        pot_bb=20.0, villain_bet_bb=10.0,
        hero_equity=0.70,
    )
    assert r.blocker_score > 0, f'Ace blocker should > 0: {r.blocker_score}'
    print(f'blocker_score (Ace): {r.blocker_score:.2f}')


def test_flush_board_suit_blocker():
    """Holding a flush-suit card on 3-suited board should give blocker score."""
    # 3 hearts on board, hero has heart
    r = analyze_river_call(
        hole_cards=['Kh', 'Qd'],
        community=['Ah', '7h', '2h', 'Jc', '5s'],
        pot_bb=20.0, villain_bet_bb=10.0,
        hero_equity=0.50,
    )
    assert r.blocker_score > 0, f'Flush blocker should > 0: {r.blocker_score}'
    print(f'blocker_score (flush suit): {r.blocker_score:.2f}')


def test_high_villain_bet_freq_lowers_threshold():
    """When villain bets river often, adjusted threshold should be lower (call more)."""
    r_rare = _call(['Ah', 'Kd'], equity=0.55, freq=0.15)
    r_freq = _call(['Ah', 'Kd'], equity=0.55, freq=0.60)
    assert r_freq.adjusted_call_threshold <= r_rare.adjusted_call_threshold, \
        f'High freq lowers threshold: {r_freq.adjusted_call_threshold:.2f} vs ' \
        f'{r_rare.adjusted_call_threshold:.2f}'
    print(f'threshold: rare={r_rare.adjusted_call_threshold:.2f} '
          f'freq={r_freq.adjusted_call_threshold:.2f}')


def test_total_pot_is_pot_plus_bet():
    """total_pot_bb should equal pot_bb + villain_bet_bb."""
    r = _call(['Ah', 'Kd'], pot_bb=20.0, villain_bet_bb=10.0, equity=0.60)
    assert abs(r.total_pot_bb - 30.0) < 0.001, \
        f'total_pot should be 30: {r.total_pot_bb}'
    print(f'total_pot_bb: {r.total_pot_bb}')


def test_reasoning_is_nonempty_string():
    """reasoning should be a non-empty string."""
    r = _call(['Ah', 'Kd'], equity=0.60)
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10, \
        f'reasoning should be non-empty: {repr(r.reasoning[:40])}'
    print(f'reasoning (first 60): {r.reasoning[:60]}')


def test_key_factors_is_list():
    """key_factors should be a list of strings."""
    r = _call(['Ah', 'Kd'], equity=0.60)
    assert isinstance(r.key_factors, list), f'key_factors should be list: {type(r.key_factors)}'
    assert all(isinstance(f, str) for f in r.key_factors), 'All factors should be strings'
    print(f'key_factors: {r.key_factors[:1]}')


def test_river_one_liner():
    """river_one_liner should return a non-empty string with action."""
    r = _call(['Ah', 'Kd'], equity=0.70)
    line = river_one_liner(r)
    assert isinstance(line, str) and len(line) > 5, \
        f'one_liner should be non-empty: {repr(line)}'
    assert r.action.upper() in line, f'action should appear in one_liner: {line}'
    print(f'one_liner: {line}')


def test_analyze_sizing_tell_overbet():
    """Overbet sizing tell should mention polarised."""
    msg = analyze_sizing_tell(20, 30)  # 150% pot
    assert isinstance(msg, str) and len(msg) > 5
    assert 'overbet' in msg.lower() or 'polarised' in msg.lower(), \
        f'overbet tell should mention polarised: {msg}'
    print(f'overbet tell: {msg[:60]}')


def test_analyze_sizing_tell_small():
    """Small bet sizing tell should mention wide range."""
    msg = analyze_sizing_tell(20, 5)  # 25% pot
    assert isinstance(msg, str) and 'small' in msg.lower(), \
        f'small bet tell should mention small: {msg}'
    print(f'small bet tell: {msg[:60]}')


def test_analyze_sizing_tell_standard():
    """Standard bet sizing should use MDF framing."""
    msg = analyze_sizing_tell(20, 10)  # 50% pot = standard
    assert isinstance(msg, str), f'Should return string: {msg}'
    print(f'standard tell: {msg[:60]}')


def test_edge_positive_when_calling():
    """edge should be positive when action is call."""
    r = _call(['Ah', 'Kd'], equity=0.80)
    if r.action == 'call':
        assert r.edge > 0, f'edge should be positive when calling: {r.edge}'
    print(f'action={r.action}  edge={r.edge:.2f}')


def test_edge_negative_when_folding():
    """edge should be negative or zero when action is fold."""
    r = _call(['2h', '3c'], equity=0.08, villain_bet_bb=15.0, pot_bb=20.0)
    if r.action == 'fold':
        assert r.edge <= 0, f'edge should be <= 0 when folding: {r.edge}'
    print(f'action={r.action}  edge={r.edge:.2f}')


if __name__ == '__main__':
    tests = [
        test_returns_river_call_result,
        test_required_fields,
        test_pot_odds_formula,
        test_mdf_formula,
        test_pot_odds_plus_mdf_equals_one,
        test_ev_fold_is_zero,
        test_high_equity_call,
        test_low_equity_fold,
        test_ev_call_formula,
        test_large_bet_high_pot_odds,
        test_small_bet_low_pot_odds,
        test_blocker_score_ace_on_board,
        test_flush_board_suit_blocker,
        test_high_villain_bet_freq_lowers_threshold,
        test_total_pot_is_pot_plus_bet,
        test_reasoning_is_nonempty_string,
        test_key_factors_is_list,
        test_river_one_liner,
        test_analyze_sizing_tell_overbet,
        test_analyze_sizing_tell_small,
        test_analyze_sizing_tell_standard,
        test_edge_positive_when_calling,
        test_edge_negative_when_folding,
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
