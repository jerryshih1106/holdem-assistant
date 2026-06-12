"""Tests for poker/threebet_sizing.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.threebet_sizing import analyze_threebet_sizing, threebet_sizing_summary


def test_oop_larger_than_ip():
    """OOP 3-bet should be larger than IP 3-bet."""
    r_ip  = analyze_threebet_sizing(open_size_bb=3.0, is_ip=True,  stack_bb=100.0)
    r_oop = analyze_threebet_sizing(open_size_bb=3.0, is_ip=False, stack_bb=100.0)
    assert r_oop.recommended_size_bb >= r_ip.recommended_size_bb, \
        f'OOP {r_oop.recommended_size_bb} should >= IP {r_ip.recommended_size_bb}'
    print(f'IP={r_ip.recommended_size_bb:.1f}BB  OOP={r_oop.recommended_size_bb:.1f}BB')


def test_callers_increase_size():
    """Each caller between open and hero should increase 3-bet size."""
    r0 = analyze_threebet_sizing(open_size_bb=3.0, n_callers=0, stack_bb=100.0)
    r2 = analyze_threebet_sizing(open_size_bb=3.0, n_callers=2, stack_bb=100.0)
    assert r2.recommended_size_bb > r0.recommended_size_bb, \
        f'2 callers size {r2.recommended_size_bb} should > 0 callers {r0.recommended_size_bb}'
    print(f'0 callers={r0.recommended_size_bb:.1f}BB  2 callers={r2.recommended_size_bb:.1f}BB')


def test_larger_open_leads_to_larger_threebet():
    """Larger open raise should produce larger 3-bet."""
    r_small = analyze_threebet_sizing(open_size_bb=2.5, stack_bb=100.0)
    r_large = analyze_threebet_sizing(open_size_bb=4.0, stack_bb=100.0)
    assert r_large.recommended_size_bb > r_small.recommended_size_bb, \
        f'Large open {r_large.recommended_size_bb} should > small open {r_small.recommended_size_bb}'
    print(f'Open 2.5x→3bet={r_small.recommended_size_bb:.1f}  Open 4.0→3bet={r_large.recommended_size_bb:.1f}')


def test_linear_vs_fish():
    """vs fish (VPIP>40%) IP should use linear strategy."""
    r = analyze_threebet_sizing(open_size_bb=3.0, is_ip=True,
                                 hero_hand_pct=0.70, villain_vpip=0.45, stack_bb=100.0)
    assert r.strategy_type == 'linear', \
        f'vs fish IP should be linear: {r.strategy_type}'
    print(f'vs fish: strategy={r.strategy_type}')


def test_polarized_oop():
    """OOP should use polarized strategy."""
    r = analyze_threebet_sizing(open_size_bb=3.0, is_ip=False,
                                 hero_hand_pct=0.80, villain_vpip=0.28, stack_bb=100.0)
    assert r.strategy_type == 'polarized', \
        f'OOP should be polarized: {r.strategy_type}'
    print(f'OOP: strategy={r.strategy_type}')


def test_spr_after_call_is_positive():
    """SPR if called should be positive."""
    r = analyze_threebet_sizing(open_size_bb=3.0, stack_bb=100.0, is_ip=True)
    assert r.spr_if_called > 0, f'SPR if called should be positive: {r.spr_if_called}'
    print(f'SPR if called: {r.spr_if_called:.1f}')


def test_short_stack_smaller_multiplier():
    """Short stack should have smaller multiplier than deep stack."""
    r_short = analyze_threebet_sizing(open_size_bb=3.0, stack_bb=30.0,  is_ip=True)
    r_deep  = analyze_threebet_sizing(open_size_bb=3.0, stack_bb=200.0, is_ip=True)
    assert r_short.multiplier <= r_deep.multiplier, \
        f'Short mult {r_short.multiplier:.1f} should <= deep {r_deep.multiplier:.1f}'
    print(f'Short mult={r_short.multiplier:.1f}  Deep mult={r_deep.multiplier:.1f}')


def test_recommended_size_within_bounds():
    """Recommended size should be within min/max bounds."""
    r = analyze_threebet_sizing(open_size_bb=3.0, stack_bb=100.0, is_ip=True, n_callers=1)
    assert r.min_size_bb <= r.recommended_size_bb <= r.max_size_bb, \
        f'Size {r.recommended_size_bb} out of bounds [{r.min_size_bb}, {r.max_size_bb}]'
    print(f'Bounds: [{r.min_size_bb:.1f}, {r.recommended_size_bb:.1f}, {r.max_size_bb:.1f}]')


def test_size_is_multiple_of_half_bb():
    """Recommended size should be a multiple of 0.5 BB."""
    r = analyze_threebet_sizing(open_size_bb=2.5, stack_bb=100.0, is_ip=True)
    assert r.recommended_size_bb % 0.5 == 0.0, \
        f'Size should be multiple of 0.5: {r.recommended_size_bb}'
    print(f'Size={r.recommended_size_bb:.1f}BB (multiple of 0.5: OK)')


def test_summary_format():
    """Summary should be <=85 chars and contain [3-bet."""
    r = analyze_threebet_sizing(open_size_bb=3.0, stack_bb=100.0, is_ip=True)
    s = threebet_sizing_summary(r)
    assert len(s) <= 85, f'Too long ({len(s)}): {s}'
    assert '[3-bet' in s, f'Missing [3-bet: {s}'
    print(f'Summary ({len(s)} chars): {s}')


def test_deep_stack_oop_larger_size():
    """Deep stack OOP should produce larger multiplier."""
    r = analyze_threebet_sizing(open_size_bb=3.0, stack_bb=300.0, is_ip=False)
    assert r.multiplier >= 3.5, f'Deep OOP multiplier should be >=3.5: {r.multiplier}'
    print(f'Deep OOP mult={r.multiplier:.1f}')


if __name__ == '__main__':
    tests = [
        test_oop_larger_than_ip,
        test_callers_increase_size,
        test_larger_open_leads_to_larger_threebet,
        test_linear_vs_fish,
        test_polarized_oop,
        test_spr_after_call_is_positive,
        test_short_stack_smaller_multiplier,
        test_recommended_size_within_bounds,
        test_size_is_multiple_of_half_bb,
        test_summary_format,
        test_deep_stack_oop_larger_size,
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
