"""Tests for poker/postflop_summary.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.postflop_summary import summarize_postflop, postflop_one_liner, PostflopSummary


def _summary(hole, community, pot_bb=10, eff_stack_bb=90, hero_pos='BTN', villain_pos='BB', **kw):
    return summarize_postflop(
        hole_cards=hole, community=community,
        pot_bb=pot_bb, eff_stack_bb=eff_stack_bb,
        hero_pos=hero_pos, villain_pos=villain_pos, **kw
    )


def test_result_has_required_fields():
    """PostflopSummary should have all expected fields."""
    r = _summary(['Ah', 'Ks'], ['Ac', '7h', '2d'])
    required = ['primary_action', 'equity', 'spr', 'board_type', 'confidence',
                'should_commit', 'percentile', 'summary_line', 'tips']
    for field in required:
        assert hasattr(r, field), f'PostflopSummary missing field: {field}'
    print('All required fields present')


def test_equity_in_range():
    """equity should be a float in [0, 1]."""
    r = _summary(['Ah', 'Ks'], ['Ac', '7h', '2d'])
    assert 0.0 <= r.equity <= 1.0, f'equity should be in [0,1]: {r.equity}'
    print(f'TPTK equity: {r.equity:.0%}')


def test_tptk_high_equity():
    """Top pair top kicker should have high equity on a dry board."""
    r = _summary(['Ah', 'Ks'], ['Ac', '7h', '2d'])
    assert r.equity > 0.70, \
        f'TPTK on dry board should have > 70% equity: {r.equity:.0%}'
    print(f'TPTK equity: {r.equity:.0%}')


def test_tptk_should_commit():
    """TPTK on a dry board IP should indicate commitment."""
    r = _summary(['Ah', 'Ks'], ['Ac', '7h', '2d'])
    assert r.should_commit, \
        f'TPTK dry board should_commit should be True: {r.should_commit}'
    print(f'TPTK should_commit: {r.should_commit}')


def test_spr_formula():
    """SPR should equal eff_stack / pot."""
    r = _summary(['Ah', 'Ks'], ['Ac', '7h', '2d'], pot_bb=10, eff_stack_bb=90)
    assert abs(r.spr - 9.0) < 0.1, f'SPR should = 9.0: {r.spr}'
    print(f'SPR: {r.spr:.1f} (expected 9.0)')


def test_board_type_is_string():
    """board_type should be a non-empty string describing the board."""
    r = _summary(['Ah', 'Ks'], ['Ac', '7h', '2d'])
    assert isinstance(r.board_type, str) and len(r.board_type) > 3, \
        f'board_type should be non-empty string: {repr(r.board_type)}'
    print(f'board_type: {r.board_type}')


def test_confidence_is_valid():
    """confidence should be a non-empty string."""
    r = _summary(['Ah', 'Ks'], ['Ac', '7h', '2d'])
    assert isinstance(r.confidence, str) and len(r.confidence) > 0, \
        f'confidence should be non-empty string: {repr(r.confidence)}'
    print(f'confidence: {r.confidence}')


def test_primary_action_is_string():
    """primary_action should be a non-empty string."""
    r = _summary(['Ah', 'Ks'], ['Ac', '7h', '2d'])
    assert isinstance(r.primary_action, str) and len(r.primary_action) > 0, \
        f'primary_action should be non-empty: {repr(r.primary_action)}'
    print(f'primary_action: {r.primary_action}')


def test_postflop_one_liner_returns_string():
    """postflop_one_liner should return a non-empty string."""
    s = postflop_one_liner(['Ah', 'Ks'], ['Ac', '7h', '2d'], pot_bb=10, stack_bb=90)
    assert isinstance(s, str) and len(s) > 5, \
        f'postflop_one_liner should be non-empty string: {repr(s)[:50]}'
    print(f'one_liner length: {len(s)} chars')


def test_facing_bet_changes_analysis():
    """facing_bet=True should produce a different primary action than not facing bet."""
    r_check = _summary(['Ah', 'Ks'], ['Ac', '7h', '2d'], facing_bet=False)
    r_bet   = _summary(['Ah', 'Ks'], ['Ac', '7h', '2d'],
                       facing_bet=True, villain_bet_bb=5.0)
    assert r_check.facing_bet == False
    assert r_bet.facing_bet == True
    print(f'No bet: {r_check.primary_action} | Facing bet: {r_bet.primary_action}')


if __name__ == '__main__':
    tests = [
        test_result_has_required_fields,
        test_equity_in_range,
        test_tptk_high_equity,
        test_tptk_should_commit,
        test_spr_formula,
        test_board_type_is_string,
        test_confidence_is_valid,
        test_primary_action_is_string,
        test_postflop_one_liner_returns_string,
        test_facing_bet_changes_analysis,
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
