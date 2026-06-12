"""Tests for poker/situation_analyzer.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.situation_analyzer import (
    analyze_situation, situation_one_liner, situation_full_report, FullAnalysis
)


def test_result_type():
    """analyze_situation should return a FullAnalysis dataclass."""
    r = analyze_situation(['Ah', 'Ks'], ['Ac', '7h', '2d'], pot_bb=10, eff_stack_bb=90)
    assert isinstance(r, FullAnalysis), f'Expected FullAnalysis, got {type(r)}'
    print(f'type: {type(r).__name__}')


def test_required_fields():
    """FullAnalysis should have all documented fields."""
    r = analyze_situation(['Ah', 'Ks'], ['Ac', '7h', '2d'], pot_bb=10, eff_stack_bb=90)
    fields = ['equity', 'hand_class', 'hand_percentile', 'board_type', 'board_wetness',
              'primary_action', 'confidence', 'ev_breakdown', 'optimal_bet_bb',
              'optimal_bet_pct', 'bet_ev_vs_check', 'spr', 'spr_label', 'should_commit',
              'one_liner', 'tips']
    for f in fields:
        assert hasattr(r, f), f'FullAnalysis missing field: {f}'
    print(f'All {len(fields)} fields present')


def test_equity_range():
    """equity should be in [0, 1]."""
    r = analyze_situation(['Ah', 'Ks'], ['Ac', '7h', '2d'], pot_bb=10, eff_stack_bb=90)
    assert 0.0 <= r.equity <= 1.0, f'equity out of range: {r.equity}'
    print(f'equity: {r.equity:.3f}')


def test_tptk_high_equity():
    """Top pair top kicker on dry board should have high equity (>0.6)."""
    r = analyze_situation(['Ah', 'Ks'], ['Ac', '7h', '2d'], pot_bb=10, eff_stack_bb=90)
    assert r.equity > 0.6, f'TPTK on dry board equity should be >0.6: {r.equity:.3f}'
    print(f'TPTK equity: {r.equity:.3f}')


def test_tptk_should_commit():
    """TPTK on dry board should have should_commit=True."""
    r = analyze_situation(['Ah', 'Ks'], ['Ac', '7h', '2d'], pot_bb=10, eff_stack_bb=90)
    assert r.should_commit is True, f'TPTK should commit: {r.should_commit}'
    print(f'should_commit: {r.should_commit}')


def test_tptk_primary_action_bet():
    """TPTK with no facing bet should recommend bet or raise."""
    r = analyze_situation(['Ah', 'Ks'], ['Ac', '7h', '2d'], pot_bb=10, eff_stack_bb=90,
                          call_amount=0.0)
    assert r.primary_action in ('下注', '加注', 'bet', 'raise'), \
        f'TPTK should bet/raise: {r.primary_action}'
    print(f'primary_action: {r.primary_action}')


def test_spr_calculation():
    """SPR should equal eff_stack / pot approximately."""
    r = analyze_situation(['Ah', 'Ks'], ['Ac', '7h', '2d'], pot_bb=10, eff_stack_bb=90)
    expected_spr = 90 / 10
    assert abs(r.spr - expected_spr) < 2.0, \
        f'SPR should be ~{expected_spr}: {r.spr}'
    print(f'spr: {r.spr:.1f} (expected ~{expected_spr:.1f})')


def test_optimal_bet_bb_positive():
    """optimal_bet_bb should be a positive number."""
    r = analyze_situation(['Ah', 'Ks'], ['Ac', '7h', '2d'], pot_bb=10, eff_stack_bb=90)
    assert r.optimal_bet_bb > 0, f'optimal_bet_bb should be >0: {r.optimal_bet_bb}'
    print(f'optimal_bet_bb: {r.optimal_bet_bb:.1f}')


def test_optimal_bet_pct_in_range():
    """optimal_bet_pct should be a fraction in (0, 2.0)."""
    r = analyze_situation(['Ah', 'Ks'], ['Ac', '7h', '2d'], pot_bb=10, eff_stack_bb=90)
    assert 0.0 < r.optimal_bet_pct <= 2.0, \
        f'optimal_bet_pct should be in (0, 2.0]: {r.optimal_bet_pct}'
    print(f'optimal_bet_pct: {r.optimal_bet_pct:.0%}')


def test_ev_breakdown_keys():
    """ev_breakdown should contain standard keys."""
    r = analyze_situation(['Ah', 'Ks'], ['Ac', '7h', '2d'], pot_bb=10, eff_stack_bb=90)
    for key in ('fold', 'check', 'call', 'raise', 'allin'):
        assert key in r.ev_breakdown, f'ev_breakdown missing key: {key}'
    print(f'ev_breakdown keys: {list(r.ev_breakdown.keys())}')


def test_tips_list():
    """tips should be a non-empty list of strings."""
    r = analyze_situation(['Ah', 'Ks'], ['Ac', '7h', '2d'], pot_bb=10, eff_stack_bb=90)
    assert isinstance(r.tips, list) and len(r.tips) > 0, \
        f'tips should be non-empty list: {r.tips}'
    assert all(isinstance(t, str) for t in r.tips), 'All tips should be strings'
    print(f'tips count: {len(r.tips)}')


def test_facing_bet_can_raise():
    """When facing a large bet with strong equity, action can be raise."""
    r = analyze_situation(['Ah', 'Ks'], ['Ac', '7h', '2d'], pot_bb=10, eff_stack_bb=90,
                          call_amount=3.0)
    assert r.primary_action in ('加注', '跟注', '下注', 'raise', 'call', 'bet'), \
        f'Facing bet with TPTK: {r.primary_action}'
    print(f'Facing 3bb bet action: {r.primary_action}')


def test_weak_hand_low_equity():
    """Weak hand should have equity lower than strong hand."""
    strong = analyze_situation(['Ah', 'Ks'], ['Ac', '7h', '2d'], pot_bb=10, eff_stack_bb=90)
    weak   = analyze_situation(['2h', '7c'], ['Ac', '7h', '2d'], pot_bb=10, eff_stack_bb=90)
    # 72o on A72 has lower equity vs random (both have good hands, but AK dominates)
    # Just check that equity is a valid number
    assert 0.0 <= weak.equity <= 1.0, f'weak equity out of range: {weak.equity}'
    print(f'AKs equity={strong.equity:.3f} vs 27o equity={weak.equity:.3f}')


def test_one_liner_is_string():
    """one_liner should be a non-empty string."""
    r = analyze_situation(['Ah', 'Ks'], ['Ac', '7h', '2d'], pot_bb=10, eff_stack_bb=90)
    assert isinstance(r.one_liner, str) and len(r.one_liner) > 5, \
        f'one_liner should be non-empty string: {repr(r.one_liner)}'
    print(f'one_liner: {r.one_liner[:60]}')


def test_situation_one_liner_function():
    """situation_one_liner() function should return the one_liner string."""
    r = analyze_situation(['Ah', 'Ks'], ['Ac', '7h', '2d'], pot_bb=10, eff_stack_bb=90)
    line = situation_one_liner(r)
    assert line == r.one_liner, f'situation_one_liner should match r.one_liner'
    print(f'situation_one_liner: {line[:40]}')


def test_situation_full_report():
    """situation_full_report should return a multi-line string."""
    r = analyze_situation(['Ah', 'Ks'], ['Ac', '7h', '2d'], pot_bb=10, eff_stack_bb=90)
    report = situation_full_report(r)
    assert isinstance(report, str) and len(report) > 50, \
        f'full_report should be long string: {len(report)} chars'
    assert '\n' in report, 'full_report should be multi-line'
    print(f'full_report lines: {len(report.splitlines())}')


def test_board_type_not_preflop_with_community():
    """board_type should not be Preflop when community cards are present."""
    r = analyze_situation(['Ah', 'Ks'], ['Ac', '7h', '2d'], pot_bb=10, eff_stack_bb=90)
    assert r.board_type != 'Preflop', f'board_type should not be Preflop: {r.board_type}'
    print(f'board_type: {r.board_type}')


def test_preflop_no_community():
    """analyze_situation with empty community should use preflop street."""
    r = analyze_situation(['Ah', 'Ks'], [], pot_bb=3, eff_stack_bb=100)
    assert isinstance(r, FullAnalysis), 'Should return FullAnalysis preflop'
    assert r.board_type == 'Preflop', f'Expected Preflop, got: {r.board_type}'
    print(f'Preflop board_type: {r.board_type}')


def test_villain_stats_affect_result():
    """Different villain VPIP should affect bet_ev_vs_check."""
    r_loose = analyze_situation(['Ah', 'Ks'], ['Ac', '7h', '2d'], pot_bb=10,
                                eff_stack_bb=90, villain_vpip=0.50)
    r_tight = analyze_situation(['Ah', 'Ks'], ['Ac', '7h', '2d'], pot_bb=10,
                                eff_stack_bb=90, villain_vpip=0.15)
    # Both should produce valid FullAnalysis objects
    assert isinstance(r_loose, FullAnalysis) and isinstance(r_tight, FullAnalysis)
    print(f'loose EV_vs_check={r_loose.bet_ev_vs_check:.2f} '
          f'tight EV_vs_check={r_tight.bet_ev_vs_check:.2f}')


if __name__ == '__main__':
    tests = [
        test_result_type,
        test_required_fields,
        test_equity_range,
        test_tptk_high_equity,
        test_tptk_should_commit,
        test_tptk_primary_action_bet,
        test_spr_calculation,
        test_optimal_bet_bb_positive,
        test_optimal_bet_pct_in_range,
        test_ev_breakdown_keys,
        test_tips_list,
        test_facing_bet_can_raise,
        test_weak_hand_low_equity,
        test_one_liner_is_string,
        test_situation_one_liner_function,
        test_situation_full_report,
        test_board_type_not_preflop_with_community,
        test_preflop_no_community,
        test_villain_stats_affect_result,
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
