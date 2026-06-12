"""Tests for poker/overbet.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.overbet import analyze_overbet, overbet_summary


def test_nuts_river_vs_fish():
    """Strong hand + fish villain on river → should overbet."""
    r = analyze_overbet(
        equity=0.88, pot_bb=20.0, stack_bb=120.0,
        street='river',
        villain_vpip=0.48, villain_fold=0.28,
        range_advantage=0.72,
    )
    assert r.should_overbet, f'Expected overbet, got standard (score not shown)'
    assert r.recommended_pct >= 1.0, f'Expected >=1x, got {r.recommended_pct}'
    print(f'Nuts vs fish: {r.sizing_label} = {r.recommended_bb:.0f}BB  EV_ob={r.ev_overbet:.1f} vs EV_std={r.ev_standard:.1f}')


def test_weak_hand_no_overbet():
    """Weak equity → no overbet."""
    r = analyze_overbet(
        equity=0.45, pot_bb=15.0, stack_bb=80.0,
        street='river',
        villain_vpip=0.30, villain_fold=0.55,
    )
    assert not r.should_overbet, f'Should not overbet with weak equity'
    assert r.recommended_pct < 1.0
    print(f'Weak hand: {r.sizing_label}  should_overbet={r.should_overbet}')


def test_multiway_no_overbet():
    """Multiway pot always blocks overbet."""
    r = analyze_overbet(
        equity=0.85, pot_bb=20.0, stack_bb=120.0,
        street='river',
        villain_vpip=0.45, villain_fold=0.25,
        num_opponents=2,
    )
    assert not r.should_overbet, 'Should not overbet in multiway pot'
    print(f'Multiway: should_overbet={r.should_overbet}  blockers={r.blockers[:1]}')


def test_low_spr_no_overbet():
    """Low SPR (already near all-in) → don't overbet."""
    r = analyze_overbet(
        equity=0.80, pot_bb=40.0, stack_bb=25.0,
        street='river',
        villain_vpip=0.35,
    )
    # SPR = 25/40 = 0.625 → should block overbet
    assert not r.should_overbet, f'Low SPR should block overbet'
    print(f'Low SPR={r.spr}: should_overbet={r.should_overbet}')


def test_turn_combo_draw_overbet():
    """Turn with strong combo draw → should recommend overbet to build pot."""
    r = analyze_overbet(
        equity=0.75, pot_bb=12.0, stack_bb=100.0,
        street='turn',
        villain_vpip=0.40, villain_fold=0.30,
        range_advantage=0.65,
        has_strong_draw=True,
    )
    assert r.should_overbet, 'Turn + combo draw + good equity → overbet to build pot'
    print(f'Turn combo draw: {r.sizing_label} = {r.recommended_bb:.0f}BB')


def test_tight_villain_folds_too_much():
    """Villain who folds a lot → standard bet more EV than overbet."""
    r = analyze_overbet(
        equity=0.78, pot_bb=15.0, stack_bb=80.0,
        street='river',
        villain_vpip=0.22, villain_fold=0.72,
        range_advantage=0.60,
    )
    # High fold rate should block overbet
    assert not r.should_overbet or r.recommended_pct <= 1.0, \
        f'Tight villain with high fold should not trigger big overbet'
    print(f'Tight villain: {r.sizing_label}  fold={r.blockers}')


def test_ev_comparison():
    """EV comparison should always be present."""
    r = analyze_overbet(
        equity=0.80, pot_bb=20.0, stack_bb=150.0,
        street='river',
        villain_vpip=0.45, villain_fold=0.30,
    )
    assert isinstance(r.ev_overbet, float)
    assert isinstance(r.ev_standard, float)
    assert isinstance(r.ev_small, float)
    print(f'EV comparison: small={r.ev_small:.1f}  standard={r.ev_standard:.1f}  overbet={r.ev_overbet:.1f}')


def test_summary_format():
    """Summary line should be under 80 chars and contain [注碼]."""
    r = analyze_overbet(
        equity=0.82, pot_bb=18.0, stack_bb=120.0,
        street='river',
        villain_vpip=0.42, villain_fold=0.28,
    )
    s = overbet_summary(r)
    assert '[注碼]' in s, f'Missing [注碼] in: {s}'
    assert len(s) <= 80, f'Too long: {len(s)} chars'
    print(f'Summary ({len(s)} chars): {s}')


def test_oop_penalty():
    """OOP position penalizes overbet score."""
    r_ip = analyze_overbet(
        equity=0.78, pot_bb=15.0, stack_bb=100.0,
        street='river', villain_vpip=0.38, villain_fold=0.35,
        is_oop=False,
    )
    r_oop = analyze_overbet(
        equity=0.78, pot_bb=15.0, stack_bb=100.0,
        street='river', villain_vpip=0.38, villain_fold=0.35,
        is_oop=True,
    )
    # OOP should either not overbet or recommend smaller size
    oop_is_more_conservative = (
        not r_oop.should_overbet or
        r_oop.recommended_pct <= r_ip.recommended_pct
    )
    assert oop_is_more_conservative, \
        f'OOP should be more conservative: IP={r_ip.recommended_pct} OOP={r_oop.recommended_pct}'
    print(f'IP: {r_ip.sizing_label}  OOP: {r_oop.sizing_label}')


if __name__ == '__main__':
    tests = [
        test_nuts_river_vs_fish,
        test_weak_hand_no_overbet,
        test_multiway_no_overbet,
        test_low_spr_no_overbet,
        test_turn_combo_draw_overbet,
        test_tight_villain_folds_too_much,
        test_ev_comparison,
        test_summary_format,
        test_oop_penalty,
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
