"""Tests for poker/spr_commitment.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.spr_commitment import analyze_spr_commitment, spr_commitment_summary


def test_ultra_low_spr_second_pair_commits():
    """SPR < 2: second pair should commit."""
    r = analyze_spr_commitment(pot_bb=20.0, stack_bb=30.0, hand_type='second_pair')
    assert r.spr < 2.0
    assert r.should_commit, f'Ultra-low SPR second pair should commit: {r.zone_zh}'
    print(f'Ultra-low SPR={r.spr:.1f}: should_commit={r.should_commit}')


def test_high_spr_tpgk_does_not_commit():
    """SPR > 13: TPGK should not commit (only flush+ qualifies)."""
    r = analyze_spr_commitment(pot_bb=10.0, stack_bb=200.0, hand_type='tpgk')
    assert r.spr > 13
    assert not r.should_commit, f'High SPR TPGK should not commit: spr={r.spr}'
    print(f'High SPR={r.spr:.1f}: TPGK should_commit={r.should_commit}')


def test_low_spr_tpgk_commits():
    """SPR 2-4: TPGK should commit."""
    r = analyze_spr_commitment(pot_bb=20.0, stack_bb=60.0, hand_type='tpgk')
    assert 2.0 <= r.spr <= 4.0, f'SPR should be low: {r.spr}'
    assert r.should_commit, f'Low SPR TPGK should commit: {r.zone_zh}'
    print(f'Low SPR={r.spr:.1f}: TPGK should_commit={r.should_commit}')


def test_medium_spr_requires_two_pair():
    """SPR 4-7: two pair commits, TPGK does not."""
    r_2p   = analyze_spr_commitment(pot_bb=20.0, stack_bb=100.0, hand_type='two_pair')
    r_tpgk = analyze_spr_commitment(pot_bb=20.0, stack_bb=100.0, hand_type='tpgk')
    assert 4.0 <= r_2p.spr <= 7.0, f'SPR should be medium: {r_2p.spr}'
    assert r_2p.should_commit, f'Medium SPR two pair should commit'
    assert not r_tpgk.should_commit, f'Medium SPR TPGK should NOT commit'
    print(f'Medium SPR={r_2p.spr:.1f}: two_pair={r_2p.should_commit} tpgk={r_tpgk.should_commit}')


def test_set_always_commits():
    """Set should commit at any reasonable SPR."""
    for pot, stack in [(20, 30), (20, 80), (20, 180)]:
        r = analyze_spr_commitment(pot_bb=pot, stack_bb=stack, hand_type='set')
        if r.spr <= 13:
            assert r.should_commit, f'Set SPR={r.spr:.1f} should commit'
    print('Set commits at low/medium SPR: OK')


def test_ev_commit_larger_for_strong_hands():
    """Stronger hands should have higher commit EV."""
    r_set  = analyze_spr_commitment(pot_bb=20.0, stack_bb=60.0, hand_type='set')
    r_tpwk = analyze_spr_commitment(pot_bb=20.0, stack_bb=60.0, hand_type='tpwk')
    assert r_set.ev_commit > r_tpwk.ev_commit, \
        f'Set EV {r_set.ev_commit} should > TPWK EV {r_tpwk.ev_commit}'
    print(f'Set EV={r_set.ev_commit:+.1f}BB  TPWK EV={r_tpwk.ev_commit:+.1f}BB')


def test_spr_zone_thresholds():
    """Verify SPR zone classification at boundaries."""
    r1 = analyze_spr_commitment(pot_bb=10, stack_bb=15)   # spr=1.5
    r2 = analyze_spr_commitment(pot_bb=10, stack_bb=30)   # spr=3.0
    r3 = analyze_spr_commitment(pot_bb=10, stack_bb=55)   # spr=5.5
    r4 = analyze_spr_commitment(pot_bb=10, stack_bb=100)  # spr=10
    r5 = analyze_spr_commitment(pot_bb=10, stack_bb=150)  # spr=15
    assert r1.zone_key == 'ultra_low'
    assert r2.zone_key == 'low'
    assert r3.zone_key == 'medium'
    assert r4.zone_key == 'medium_high'
    assert r5.zone_key == 'high'
    print('SPR zone thresholds: OK')


def test_stack_off_action_ultra_low():
    """Ultra-low SPR should recommend stack_off action."""
    r = analyze_spr_commitment(pot_bb=20.0, stack_bb=25.0, hand_type='tpgk')
    assert r.action_key == 'stack_off', f'Ultra-low should stack_off: {r.action_key}'
    print(f'Ultra-low action: {r.action_key}')


def test_high_spr_flush_commits():
    """High SPR flush should commit."""
    r = analyze_spr_commitment(pot_bb=10.0, stack_bb=200.0, hand_type='flush')
    assert r.spr > 13
    assert r.should_commit, f'Flush at high SPR should commit: {r.zone_zh}'
    print(f'High SPR={r.spr:.1f}: flush should_commit={r.should_commit}')


def test_summary_format():
    """Summary should be <=85 chars and contain [SPR."""
    r = analyze_spr_commitment(pot_bb=20.0, stack_bb=80.0, hand_type='tpgk')
    s = spr_commitment_summary(r)
    assert len(s) <= 85, f'Too long ({len(s)}): {s}'
    assert '[SPR' in s, f'Missing [SPR: {s}'
    print(f'Summary ({len(s)} chars): {s}')


def test_air_never_commits():
    """Air/bluff should never commit at any SPR."""
    for pot, stack in [(20, 20), (20, 50), (20, 100)]:
        r = analyze_spr_commitment(pot_bb=pot, stack_bb=stack, hand_type='air')
        assert not r.should_commit, f'Air should never commit: SPR={r.spr:.1f}'
    print('Air never commits: OK')


if __name__ == '__main__':
    tests = [
        test_ultra_low_spr_second_pair_commits,
        test_high_spr_tpgk_does_not_commit,
        test_low_spr_tpgk_commits,
        test_medium_spr_requires_two_pair,
        test_set_always_commits,
        test_ev_commit_larger_for_strong_hands,
        test_spr_zone_thresholds,
        test_stack_off_action_ultra_low,
        test_high_spr_flush_commits,
        test_summary_format,
        test_air_never_commits,
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
