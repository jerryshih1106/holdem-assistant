"""Tests for poker/preflop_ev.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.preflop_ev import calc_open_ev, ev_summary, position_ev_table, PreflopEV


def test_premium_hand_positive_ev():
    """AA from any position should have positive EV estimate."""
    for pos in ['BTN', 'CO', 'UTG']:
        r = calc_open_ev('AA', position=pos)
        assert r.ev_estimate > 0, \
            f'AA {pos} should have positive EV: {r.ev_estimate}'
    print('AA positive EV in all positions')


def test_btn_higher_steal_success_than_utg_for_any_hand():
    """BTN steal success rate should exceed UTG (fewer remaining players)."""
    r_btn = calc_open_ev('A8s', position='BTN')
    r_utg = calc_open_ev('A8s', position='UTG')
    assert r_btn.steal_success_pct > r_utg.steal_success_pct, \
        f'BTN steal {r_btn.steal_success_pct:.0%} should > UTG {r_utg.steal_success_pct:.0%}'
    print(f'A8s steal success: BTN={r_btn.steal_success_pct:.0%} UTG={r_utg.steal_success_pct:.0%}')


def test_result_has_all_fields():
    """PreflopEV should have all expected fields."""
    r = calc_open_ev('TT', position='BTN')
    required = ['hand', 'position', 'action', 'ev_estimate', 'ev_vs_fold',
                'confidence', 'steal_success_pct', 'postflop_edge', 'recommendation', 'notes']
    for field in required:
        assert hasattr(r, field), f'PreflopEV missing field: {field}'
    print(f'TT BTN: all fields present')


def test_steal_success_pct_in_range():
    """steal_success_pct should be between 0 and 1."""
    r = calc_open_ev('AKs', position='BTN')
    assert 0.0 <= r.steal_success_pct <= 1.0, \
        f'steal_success_pct should be in [0,1]: {r.steal_success_pct}'
    print(f'AKs BTN steal_success_pct: {r.steal_success_pct:.0%}')


def test_btn_higher_steal_success_than_utg():
    """BTN should have higher steal success rate than UTG (fewer players left)."""
    r_btn = calc_open_ev('A2s', position='BTN')
    r_utg = calc_open_ev('A2s', position='UTG')
    assert r_btn.steal_success_pct >= r_utg.steal_success_pct, \
        f'BTN steal {r_btn.steal_success_pct:.0%} should >= UTG {r_utg.steal_success_pct:.0%}'
    print(f'A2s steal success: BTN={r_btn.steal_success_pct:.0%} UTG={r_utg.steal_success_pct:.0%}')


def test_trash_hand_low_postflop_edge():
    """72o should have lower postflop edge than AA."""
    r_aa = calc_open_ev('AA', position='BTN')
    r_72 = calc_open_ev('72o', position='BTN')
    assert r_aa.postflop_edge >= r_72.postflop_edge, \
        f'AA postflop edge {r_aa.postflop_edge:.2f} should >= 72o {r_72.postflop_edge:.2f}'
    print(f'Postflop edge: AA={r_aa.postflop_edge:.2f} 72o={r_72.postflop_edge:.2f}')


def test_ev_vs_fold_nonnegative_for_good_hand():
    """ev_vs_fold should be >= 0 for premium hands (opening beats folding)."""
    r = calc_open_ev('QQ', position='BTN')
    assert r.ev_vs_fold >= 0, \
        f'QQ BTN ev_vs_fold should be >= 0: {r.ev_vs_fold}'
    print(f'QQ BTN ev_vs_fold: {r.ev_vs_fold:.2f}')


def test_ev_summary_returns_string():
    """ev_summary should return a non-empty string."""
    r = calc_open_ev('AKs', position='BTN')
    s = ev_summary(r)
    assert isinstance(s, str) and len(s) > 5, \
        f'ev_summary should be non-empty string: {repr(s)[:50]}'
    print(f'ev_summary length: {len(s)} chars')


def test_position_ev_table_returns_string():
    """position_ev_table should return a non-empty string."""
    s = position_ev_table('AKs')
    assert isinstance(s, str) and len(s) > 10, \
        f'position_ev_table should be non-empty string: {repr(s)[:50]}'
    print(f'position_ev_table length: {len(s)} chars')


def test_tight_villain_better_steal_ev():
    """Against a tighter villain (low PFR), steal EV should be higher."""
    r_tight = calc_open_ev('A5s', position='BTN', villain_pfr=0.10)
    r_loose  = calc_open_ev('A5s', position='BTN', villain_pfr=0.35)
    assert r_tight.ev_estimate >= r_loose.ev_estimate, \
        f'Tight villain EV {r_tight.ev_estimate:.2f} should >= loose {r_loose.ev_estimate:.2f}'
    print(f'A5s BTN EV: tight={r_tight.ev_estimate:.2f} loose={r_loose.ev_estimate:.2f}')


if __name__ == '__main__':
    tests = [
        test_premium_hand_positive_ev,
        test_btn_higher_steal_success_than_utg_for_any_hand,
        test_result_has_all_fields,
        test_steal_success_pct_in_range,
        test_btn_higher_steal_success_than_utg,
        test_trash_hand_low_postflop_edge,
        test_ev_vs_fold_nonnegative_for_good_hand,
        test_ev_summary_returns_string,
        test_position_ev_table_returns_string,
        test_tight_villain_better_steal_ev,
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
