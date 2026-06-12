"""Tests for poker/jam_caller.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.jam_caller import analyze_jam_call, jam_call_summary


def test_clear_call_strong_hand_fish():
    """Strong hand (AA-ish) vs fish short stack shove → clear call."""
    r = analyze_jam_call(
        villain_pos='BTN', villain_stack_bb=15.0,
        hero_hand_pct=0.95,  # AA
        pot_before_bb=2.5, villain_vpip=0.50,
    )
    assert r.should_call, f'AA vs fish 15BB shove should call: {r.verdict}'
    assert r.verdict in ('clear_call', 'marginal_call'), f'Should be clear/marginal call, got {r.verdict}'
    print(f'AA vs fish 15BB: equity={r.hero_equity:.0%}  required={r.required_equity:.0%}  EV={r.ev_call:+.1f}BB')


def test_clear_fold_weak_hand_nit():
    """Weak hand vs nit UTG short shove → fold."""
    r = analyze_jam_call(
        villain_pos='UTG', villain_stack_bb=20.0,
        hero_hand_pct=0.25,  # weak Kx
        pot_before_bb=2.5, villain_vpip=0.12, villain_hands=30,
    )
    assert not r.should_call, f'Weak hand vs nit UTG should fold: {r.verdict}'
    assert r.verdict in ('clear_fold', 'marginal_fold'), f'Should be fold, got {r.verdict}'
    print(f'Weak vs nit UTG 20BB: equity={r.hero_equity:.0%}  required={r.required_equity:.0%}  EV={r.ev_call:+.1f}BB')


def test_btn_shoves_wider_than_utg():
    """BTN shoves wider range than UTG at same stack."""
    r_btn = analyze_jam_call(villain_pos='BTN', villain_stack_bb=25.0,
                             hero_hand_pct=0.60, pot_before_bb=2.5, villain_vpip=0.28)
    r_utg = analyze_jam_call(villain_pos='UTG', villain_stack_bb=25.0,
                             hero_hand_pct=0.60, pot_before_bb=2.5, villain_vpip=0.28)
    assert r_btn.villain_range_pct > r_utg.villain_range_pct, \
        f'BTN should shove wider: {r_btn.villain_range_pct:.0%} vs {r_utg.villain_range_pct:.0%}'
    print(f'BTN range: {r_btn.villain_range_pct:.0%}  UTG range: {r_utg.villain_range_pct:.0%}')


def test_short_stack_wider_range():
    """Shorter stack → wider shove range."""
    r_short = analyze_jam_call(villain_pos='BTN', villain_stack_bb=10.0,
                               hero_hand_pct=0.60, pot_before_bb=2.5, villain_vpip=0.28)
    r_deep  = analyze_jam_call(villain_pos='BTN', villain_stack_bb=40.0,
                               hero_hand_pct=0.60, pot_before_bb=2.5, villain_vpip=0.28)
    assert r_short.villain_range_pct > r_deep.villain_range_pct, \
        f'Short stack should shove wider: {r_short.villain_range_pct:.0%} vs {r_deep.villain_range_pct:.0%}'
    print(f'10BB range: {r_short.villain_range_pct:.0%}  40BB range: {r_deep.villain_range_pct:.0%}')


def test_fish_widens_range():
    """Fish villain shoves wider than TAG at same position/stack."""
    r_fish = analyze_jam_call(villain_pos='CO', villain_stack_bb=25.0,
                              hero_hand_pct=0.60, pot_before_bb=2.5,
                              villain_vpip=0.50, villain_hands=50)
    r_tag  = analyze_jam_call(villain_pos='CO', villain_stack_bb=25.0,
                              hero_hand_pct=0.60, pot_before_bb=2.5,
                              villain_vpip=0.22, villain_hands=50)
    assert r_fish.villain_range_pct > r_tag.villain_range_pct, \
        f'Fish should shove wider: {r_fish.villain_range_pct:.0%} vs {r_tag.villain_range_pct:.0%}'
    print(f'Fish range: {r_fish.villain_range_pct:.0%}  TAG range: {r_tag.villain_range_pct:.0%}')


def test_required_equity_formula():
    """Required equity = call / (pot + call) by definition."""
    r = analyze_jam_call(
        villain_pos='BTN', villain_stack_bb=20.0,
        hero_hand_pct=0.60, pot_before_bb=5.0,
        hero_invested_bb=0.0, villain_vpip=0.28,
    )
    # call = 20BB, pot_after_call = 5 + 20 + 20 = 45
    expected_req = 20.0 / (5.0 + 20.0 + 20.0)
    assert abs(r.required_equity - expected_req) < 0.005, \
        f'Required equity formula: {r.required_equity:.3f} vs expected {expected_req:.3f}'
    print(f'Required equity: {r.required_equity:.3f} (expected {expected_req:.3f})')


def test_hero_invested_reduces_call():
    """Hero already invested reduces the call amount."""
    r_cold = analyze_jam_call(villain_pos='BTN', villain_stack_bb=20.0,
                              hero_hand_pct=0.65, pot_before_bb=3.0,
                              hero_invested_bb=0.0, villain_vpip=0.30)
    r_part = analyze_jam_call(villain_pos='BTN', villain_stack_bb=20.0,
                              hero_hand_pct=0.65, pot_before_bb=3.0,
                              hero_invested_bb=10.0, villain_vpip=0.30)
    assert r_part.call_amount_bb < r_cold.call_amount_bb, \
        f'Partial investment should reduce call: {r_part.call_amount_bb} vs {r_cold.call_amount_bb}'
    # Required equity is lower when already in the pot
    assert r_part.required_equity < r_cold.required_equity, \
        f'Already invested should lower required equity: {r_part.required_equity:.3f} vs {r_cold.required_equity:.3f}'
    print(f'Cold call req: {r_cold.required_equity:.0%}  Partial req: {r_part.required_equity:.0%}')


def test_ev_call_improves_with_better_hand():
    """Better hand → higher EV for calling."""
    r_weak   = analyze_jam_call(villain_pos='BTN', villain_stack_bb=20.0,
                                hero_hand_pct=0.20, pot_before_bb=3.0, villain_vpip=0.35)
    r_medium = analyze_jam_call(villain_pos='BTN', villain_stack_bb=20.0,
                                hero_hand_pct=0.60, pot_before_bb=3.0, villain_vpip=0.35)
    r_strong = analyze_jam_call(villain_pos='BTN', villain_stack_bb=20.0,
                                hero_hand_pct=0.95, pot_before_bb=3.0, villain_vpip=0.35)
    assert r_medium.ev_call > r_weak.ev_call, f'Medium hand should have better EV than weak'
    assert r_strong.ev_call > r_medium.ev_call, f'Strong hand should have better EV than medium'
    print(f'EV: weak={r_weak.ev_call:+.1f}  medium={r_medium.ev_call:+.1f}  strong={r_strong.ev_call:+.1f}')


def test_equity_margin_determines_verdict():
    """Equity margin aligns with verdict category."""
    for hand_pct, expected_verdict_contains in [
        (0.90, 'call'), (0.40, 'fold'),
    ]:
        r = analyze_jam_call(villain_pos='UTG', villain_stack_bb=25.0,
                             hero_hand_pct=hand_pct, pot_before_bb=2.5,
                             villain_vpip=0.22, villain_hands=50)
        if expected_verdict_contains == 'call':
            assert r.should_call, f'Strong hand should call: {r.verdict}'
        else:
            assert not r.should_call, f'Weak hand vs nit UTG should fold: {r.verdict}'
        print(f'hand={hand_pct:.0%}: verdict={r.verdict}  margin={r.equity_margin:+.1%}')


def test_summary_format():
    """Summary should be <=85 chars and contain [跟注分析]."""
    r = analyze_jam_call(
        villain_pos='BTN', villain_stack_bb=20.0,
        hero_hand_pct=0.65, pot_before_bb=3.0,
    )
    s = jam_call_summary(r)
    assert len(s) <= 85, f'Too long ({len(s)}): {s}'
    assert '[跟注分析]' in s, f'Missing [跟注分析]: {s}'
    print(f'Summary ({len(s)} chars): {s}')


def test_zero_hands_fallback():
    """Zero hands on villain → uses base range only (no crash)."""
    r = analyze_jam_call(villain_pos='BTN', villain_stack_bb=20.0,
                         hero_hand_pct=0.60, pot_before_bb=2.5,
                         villain_vpip=0.28, villain_hands=0)
    assert 0 < r.villain_range_pct < 1.0, f'Range out of bounds: {r.villain_range_pct}'
    print(f'Zero hands: range={r.villain_range_pct:.0%}  (no crash)')


if __name__ == '__main__':
    tests = [
        test_clear_call_strong_hand_fish,
        test_clear_fold_weak_hand_nit,
        test_btn_shoves_wider_than_utg,
        test_short_stack_wider_range,
        test_fish_widens_range,
        test_required_equity_formula,
        test_hero_invested_reduces_call,
        test_ev_call_improves_with_better_hand,
        test_equity_margin_determines_verdict,
        test_summary_format,
        test_zero_hands_fallback,
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
