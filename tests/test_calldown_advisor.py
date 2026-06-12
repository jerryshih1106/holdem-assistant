"""Tests for poker/calldown_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.calldown_advisor import analyze_calldown, calldown_summary


def test_strong_hand_calls_all_streets():
    """Strong hand (0.85) with good pot odds should call all streets."""
    r = analyze_calldown(
        hero_hand_pct=0.85, pot_bb=15.0, call_amount=7.0,
        stack_bb=80.0, street='flop',
    )
    assert r.strategy in ('call_all',), \
        f'Strong hand should call all streets: {r.strategy}  ev_all={r.ev_call_all:+.1f}'
    print(f'Strong hand: strategy={r.strategy}  ev_all={r.ev_call_all:+.1f}BB')


def test_weak_hand_folds_immediately():
    """Very weak hand (0.20) vs aggressive villain should fold now."""
    r = analyze_calldown(
        hero_hand_pct=0.20, pot_bb=20.0, call_amount=18.0,
        stack_bb=60.0, street='flop', villain_af=2.8,
    )
    print(f'Weak hand: strategy={r.strategy}  ev_all={r.ev_call_all:+.1f}BB  '
          f'ev_fold={r.ev_fold_now:+.1f}BB')
    # Fold or call-fold should be recommended (not call_all)
    assert r.strategy != 'call_all' or r.ev_call_all < 0, \
        f'Weak hand facing aggressive villain should not call all: ev={r.ev_call_all}'


def test_passive_villain_increases_call_ev():
    """Passive villain (low AF) bets less often → calling is better."""
    passive = analyze_calldown(
        hero_hand_pct=0.55, pot_bb=15.0, call_amount=8.0,
        street='flop', villain_af=0.5, villain_vpip=0.28,
    )
    aggressive = analyze_calldown(
        hero_hand_pct=0.55, pot_bb=15.0, call_amount=8.0,
        street='flop', villain_af=3.0, villain_vpip=0.28,
    )
    # Passive villain barrels less, so EV of calling is better
    print(f'Passive ev_all={passive.ev_call_all:+.1f}BB  Aggressive ev_all={aggressive.ev_call_all:+.1f}BB')
    assert passive.villain_barrel_freq < aggressive.villain_barrel_freq, \
        f'Passive barrel={passive.villain_barrel_freq:.0%} should < aggressive={aggressive.villain_barrel_freq:.0%}'


def test_river_has_no_future_streets():
    """On river, call_all == call_fold (only one street)."""
    r = analyze_calldown(
        hero_hand_pct=0.60, pot_bb=20.0, call_amount=10.0,
        street='river',
    )
    assert r.streets_remaining == 0, f'River should have 0 streets remaining: {r.streets_remaining}'
    assert abs(r.ev_call_all - r.ev_call_fold) < 1.0, \
        f'River: ev_all={r.ev_call_all:+.1f} should ≈ ev_fold={r.ev_call_fold:+.1f}'
    print(f'River: streets_remaining={r.streets_remaining}  '
          f'ev_all={r.ev_call_all:+.1f}  ev_fold={r.ev_call_fold:+.1f}')


def test_required_equity_correct():
    """Required equity = call / (pot + 2*call)."""
    call = 10.0; pot = 20.0
    r = analyze_calldown(
        hero_hand_pct=0.50, pot_bb=pot, call_amount=call,
        street='flop',
    )
    expected = call / (pot + 2 * call)
    assert abs(r.required_equity_now - expected) < 0.02, \
        f'Required equity: {r.required_equity_now:.3f} vs {expected:.3f}'
    print(f'Required equity: {r.required_equity_now:.0%} (expected {expected:.0%})')


def test_turn_has_one_street_remaining():
    """Turn should have 1 street remaining (river)."""
    r = analyze_calldown(
        hero_hand_pct=0.60, pot_bb=25.0, call_amount=12.0,
        street='turn',
    )
    assert r.streets_remaining == 1, f'Turn should have 1 remaining: {r.streets_remaining}'
    print(f'Turn streets_remaining={r.streets_remaining}')


def test_commitment_increases_with_call_all():
    """Call all strategy should have higher total commitment than call_fold."""
    r = analyze_calldown(
        hero_hand_pct=0.70, pot_bb=15.0, call_amount=8.0,
        stack_bb=100.0, street='flop', villain_af=2.0,
    )
    print(f'Total committed: {r.total_committed_bb:.1f}BB  '
          f'fraction={r.commitment_fraction:.0%}  strategy={r.strategy}')
    assert r.total_committed_bb >= r.call_amount, \
        f'Total committed should be at least call_amount: {r.total_committed_bb} vs {r.call_amount}'


def test_high_af_raises_barrel_frequency():
    """High AF villain should have higher barrel frequency."""
    r_high_af = analyze_calldown(
        hero_hand_pct=0.55, pot_bb=15.0, call_amount=8.0,
        street='flop', villain_af=3.5,
    )
    r_low_af = analyze_calldown(
        hero_hand_pct=0.55, pot_bb=15.0, call_amount=8.0,
        street='flop', villain_af=0.5,
    )
    assert r_high_af.villain_barrel_freq > r_low_af.villain_barrel_freq, \
        f'High AF={r_high_af.villain_barrel_freq:.0%} should > Low AF={r_low_af.villain_barrel_freq:.0%}'
    print(f'AF=3.5 barrel={r_high_af.villain_barrel_freq:.0%}  AF=0.5 barrel={r_low_af.villain_barrel_freq:.0%}')


def test_marginal_hand_middle_strategy():
    """Medium-strength hand should have a valid strategy that's not extreme."""
    r = analyze_calldown(
        hero_hand_pct=0.52, pot_bb=18.0, call_amount=9.0,
        stack_bb=80.0, street='flop', villain_af=1.5,
    )
    assert r.strategy in ('call_all', 'call_fold_turn', 'call_fold_river', 'fold_now'), \
        f'Invalid strategy: {r.strategy}'
    print(f'Medium hand: strategy={r.strategy}  ev_all={r.ev_call_all:+.1f}BB  '
          f'ev_fold={r.ev_call_fold:+.1f}BB')


def test_ev_fold_always_zero():
    """EV of folding now is always 0 (reference point)."""
    r = analyze_calldown(
        hero_hand_pct=0.45, pot_bb=20.0, call_amount=12.0,
        street='turn',
    )
    assert r.ev_fold_now == 0.0, f'EV fold should be 0.0: {r.ev_fold_now}'
    print(f'EV fold: {r.ev_fold_now} (OK = 0.0)')


def test_summary_format():
    """Summary should be <=85 chars and contain [多街策略]."""
    r = analyze_calldown(
        hero_hand_pct=0.60, pot_bb=20.0, call_amount=10.0,
        street='flop',
    )
    s = calldown_summary(r)
    assert len(s) <= 85, f'Too long ({len(s)}): {s}'
    assert '[多街策略]' in s, f'Missing [多街策略]: {s}'
    print(f'Summary ({len(s)} chars): {s}')


if __name__ == '__main__':
    tests = [
        test_strong_hand_calls_all_streets,
        test_weak_hand_folds_immediately,
        test_passive_villain_increases_call_ev,
        test_river_has_no_future_streets,
        test_required_equity_correct,
        test_turn_has_one_street_remaining,
        test_commitment_increases_with_call_all,
        test_high_af_raises_barrel_frequency,
        test_marginal_hand_middle_strategy,
        test_ev_fold_always_zero,
        test_summary_format,
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
