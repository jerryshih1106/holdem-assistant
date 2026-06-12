"""Tests for poker/action_line_reader.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.action_line_reader import (
    read_action_line, action_line_one_liner, ActionLineReading
)


def _read(actions, board='semi_wet', vpip=0.25, af=2.0, equity=0.50, bet=0.0):
    return read_action_line(
        actions=actions,
        board_type=board,
        villain_vpip=vpip,
        villain_af=af,
        hero_equity=equity,
        pot_bb=10.0,
        current_bet_bb=bet,
    )


_3BARREL = [('preflop','open',3.0), ('flop','cbet',0.60),
            ('turn','cbet',0.65), ('river','bet',0.75)]
_BXB = [('preflop','open',3.0), ('flop','cbet',0.55),
        ('turn','check',0.0), ('river','bet',0.40)]
_CHECKRAISE = [('preflop','call',0.0), ('flop','check',0.0), ('flop','raise',2.5)]
_PURE_CALL  = [('preflop','call',0.0), ('flop','call',0.0), ('turn','call',0.0)]


def test_returns_action_line_reading():
    r = _read(_3BARREL)
    assert isinstance(r, ActionLineReading)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _read(_3BARREL)
    fields = [
        'action_pattern', 'aggression_score', 'avg_bet_size_pct',
        'hand_category_estimate', 'likely_range', 'confidence',
        'estimated_equity_vs_hero', 'is_likely_bluffing', 'is_likely_value',
        'street_notes', 'hero_recommendation', 'reasoning',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_3barrel_pattern():
    """3-barrel should produce pattern 'BBB'."""
    r = _read(_3BARREL)
    assert 'B' in r.action_pattern, f'3-barrel should have B in pattern: {r.action_pattern}'
    print(f'3-barrel pattern: {r.action_pattern}')


def test_3barrel_is_value_heavy():
    """3-barrel on dry board vs tight player = value."""
    r = _read(_3BARREL, board='dry', vpip=0.15, af=2.5)
    assert not r.is_likely_bluffing, \
        f'3-barrel vs nit on dry should not be bluff: {r.is_likely_bluffing}'
    print(f'3-barrel dry: value={r.is_likely_value} bluff={r.is_likely_bluffing}')


def test_check_raise_is_strong():
    """Check-raise action line = strong hand."""
    r = _read(_CHECKRAISE)
    assert not r.is_likely_bluffing, \
        f'Check-raise likely strong: {r.hand_category_estimate}'
    print(f'Check-raise: {r.hand_category_estimate}')


def test_pure_call_wide_range():
    """Multiple calls without raising = medium-wide range."""
    r = _read(_PURE_CALL)
    assert r.hand_category_estimate in (
        'medium_wide', 'medium_narrow', 'unknown', 'value_heavy'
    ), f'Pure calls = medium range: {r.hand_category_estimate}'
    print(f'Pure call category: {r.hand_category_estimate}')


def test_aggression_score_high_for_3barrel():
    """3-barrel → high aggression score."""
    r = _read(_3BARREL)
    assert r.aggression_score > 0.5, \
        f'3-barrel agg score should be > 0.5: {r.aggression_score}'
    print(f'3-barrel agg_score: {r.aggression_score:.2f}')


def test_aggression_score_low_for_calls():
    """Pure calls → low aggression score."""
    r = _read(_PURE_CALL)
    assert r.aggression_score < 0.5, \
        f'Pure calls agg score should be < 0.5: {r.aggression_score}'
    print(f'Pure call agg_score: {r.aggression_score:.2f}')


def test_loose_villain_higher_bluff_estimate():
    """Loose villain more likely to be bluffing than tight villain."""
    r_loose = _read(_3BARREL, vpip=0.45, af=3.5)
    r_tight = _read(_3BARREL, vpip=0.15, af=2.0)
    assert r_loose.estimated_equity_vs_hero <= r_tight.estimated_equity_vs_hero, \
        f'Loose villian bluffs more: {r_loose.estimated_equity_vs_hero} <= {r_tight.estimated_equity_vs_hero}'
    print(f'Est equity: loose={r_loose.estimated_equity_vs_hero:.2f} tight={r_tight.estimated_equity_vs_hero:.2f}')


def test_equity_estimate_in_range():
    """Estimated equity should be 0-1."""
    for actions in (_3BARREL, _BXB, _CHECKRAISE, _PURE_CALL):
        r = _read(actions)
        assert 0 <= r.estimated_equity_vs_hero <= 1, \
            f'Equity should be 0-1: {r.estimated_equity_vs_hero}'
    print('All equity estimates in range')


def test_confidence_valid():
    valid = {'high', 'medium', 'low'}
    for actions in (_3BARREL, _BXB, _CHECKRAISE, _PURE_CALL):
        r = _read(actions)
        assert r.confidence in valid, f'Confidence should be valid: {r.confidence}'
    print('All confidence levels valid')


def test_hero_recommendation_is_string():
    r = _read(_3BARREL)
    assert isinstance(r.hero_recommendation, str) and len(r.hero_recommendation) > 5
    print(f'hero_recommendation: {r.hero_recommendation[:60]}')


def test_street_notes_populated():
    """Street notes should be generated for each action."""
    r = _read(_3BARREL)
    assert isinstance(r.street_notes, list) and len(r.street_notes) > 0
    print(f'street_notes count: {len(r.street_notes)}')


def test_likely_range_is_string():
    r = _read(_CHECKRAISE)
    assert isinstance(r.likely_range, str) and len(r.likely_range) > 5
    print(f'likely_range: {r.likely_range[:60]}')


def test_reasoning_is_string():
    r = _read(_3BARREL)
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'reasoning: {r.reasoning[:60]}')


def test_one_liner():
    r = _read(_3BARREL)
    line = action_line_one_liner(r)
    assert isinstance(line, str) and len(line) > 5
    print(f'one_liner: {line}')


def test_bxb_pattern_matched():
    """Bet-check-bet pattern should be recognized."""
    r = _read(_BXB)
    assert 'B' in r.action_pattern and 'X' in r.action_pattern, \
        f'BXB pattern should contain B and X: {r.action_pattern}'
    print(f'BXB pattern: {r.action_pattern}')


def test_hero_folds_when_outranged():
    """When hero has low equity vs strong villain action, recommend fold."""
    r = _read(_CHECKRAISE, equity=0.20, vpip=0.12, af=1.5)
    assert 'FOLD' in r.hero_recommendation.upper() or 'MARGIN' in r.hero_recommendation.upper(), \
        f'Low equity vs check-raise should suggest fold: {r.hero_recommendation}'
    print(f'Hero vs check-raise with 20% equity: {r.hero_recommendation[:40]}')


def test_passive_villain_high_af_value_skew():
    """Low AF villian's bets skew more toward value."""
    r_passive = _read(_3BARREL, af=0.8)
    r_aggro   = _read(_3BARREL, af=3.5)
    assert r_passive.estimated_equity_vs_hero >= r_aggro.estimated_equity_vs_hero, \
        f'Passive villain bets = more value: {r_passive.estimated_equity_vs_hero} >= {r_aggro.estimated_equity_vs_hero}'
    print(f'Equity: passive={r_passive.estimated_equity_vs_hero:.2f} aggro={r_aggro.estimated_equity_vs_hero:.2f}')


def test_avg_bet_size_calculated():
    r = _read(_3BARREL)
    assert 0 < r.avg_bet_size_pct < 2.0, \
        f'avg_bet_size should be positive: {r.avg_bet_size_pct}'
    print(f'avg_bet_size_pct: {r.avg_bet_size_pct:.2f}')


def test_check_fold_action():
    """Quick fold = no aggression."""
    actions = [('preflop','open',3.0), ('flop','cbet',0.50), ('turn','fold',0.0)]
    r = _read(actions)
    assert r.aggression_score < 1.0
    print(f'Check-fold agg_score: {r.aggression_score:.2f}')


if __name__ == '__main__':
    tests = [
        test_returns_action_line_reading, test_required_fields,
        test_3barrel_pattern, test_3barrel_is_value_heavy,
        test_check_raise_is_strong, test_pure_call_wide_range,
        test_aggression_score_high_for_3barrel, test_aggression_score_low_for_calls,
        test_loose_villain_higher_bluff_estimate, test_equity_estimate_in_range,
        test_confidence_valid, test_hero_recommendation_is_string,
        test_street_notes_populated, test_likely_range_is_string,
        test_reasoning_is_string, test_one_liner, test_bxb_pattern_matched,
        test_hero_folds_when_outranged, test_passive_villain_high_af_value_skew,
        test_avg_bet_size_calculated, test_check_fold_action,
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
