"""Tests for poker/tilt_monitor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.tilt_monitor import TiltMonitor, tilt_summary


def test_no_decisions_neutral():
    """Empty monitor → neutral result."""
    m = TiltMonitor()
    r = m.analyze()
    assert r.tilt_level == 'none'
    assert r.consecutive_bad == 0
    print(f'Empty: tilt={r.tilt_level}  consecutive_bad={r.consecutive_bad}')


def test_good_decisions_no_tilt():
    """Sequence of correct decisions → no tilt."""
    m = TiltMonitor()
    for _ in range(8):
        m.record(ev_loss=0.0, is_correct=True, street='flop', action='call')
    r = m.analyze()
    assert r.tilt_level == 'none', f'Good decisions should show no tilt: {r.tilt_level}'
    assert r.consecutive_bad == 0
    print(f'Good decisions: tilt={r.tilt_level}  accuracy={r.recent_accuracy:.0%}')


def test_consecutive_bad_triggers_warning():
    """2 consecutive bad decisions → warning."""
    m = TiltMonitor()
    # Establish baseline
    for _ in range(5):
        m.record(ev_loss=0.0, is_correct=True, street='flop', action='call')
    # Now 2 bad decisions
    m.record(ev_loss=-3.0, is_correct=False, street='river', action='call')
    m.record(ev_loss=-2.5, is_correct=False, street='turn', action='call')
    r = m.analyze()
    assert r.tilt_level in ('warning', 'tilt'), \
        f'Expected warning/tilt after 2 bad decisions, got {r.tilt_level}'
    assert r.consecutive_bad == 2
    print(f'2 bad decisions: tilt={r.tilt_level}  consecutive={r.consecutive_bad}')


def test_three_consecutive_bad_tilt():
    """3 consecutive bad decisions → tilt."""
    m = TiltMonitor()
    for _ in range(5):
        m.record(ev_loss=0.0, is_correct=True)
    for _ in range(3):
        m.record(ev_loss=-3.0, is_correct=False)
    r = m.analyze()
    assert r.tilt_level in ('tilt', 'severe'), \
        f'Expected tilt/severe after 3 bad decisions, got {r.tilt_level}'
    assert r.consecutive_bad == 3
    assert r.should_pause == True
    print(f'3 bad decisions: tilt={r.tilt_level}  should_pause={r.should_pause}')


def test_four_consecutive_bad_severe():
    """4 consecutive bad decisions → severe tilt."""
    m = TiltMonitor()
    for _ in range(5):
        m.record(ev_loss=0.0, is_correct=True)
    for _ in range(4):
        m.record(ev_loss=-4.0, is_correct=False)
    r = m.analyze()
    assert r.tilt_level == 'severe', f'Expected severe after 4 bad decisions, got {r.tilt_level}'
    assert r.should_pause == True
    print(f'4 bad decisions: tilt={r.tilt_level}  score={r.tilt_score:.2f}')


def test_accuracy_drop_triggers_warning():
    """Large accuracy drop between baseline and recent → warning."""
    m = TiltMonitor()
    # Establish good baseline: 10 correct
    for _ in range(10):
        m.record(ev_loss=0.0, is_correct=True)
    # Recent 5: only 1 correct (20% accuracy vs 100% baseline)
    m.record(ev_loss=-2.0, is_correct=False)
    m.record(ev_loss=-1.5, is_correct=False)
    m.record(ev_loss=-2.0, is_correct=False)
    m.record(ev_loss=-1.0, is_correct=True)   # one good
    m.record(ev_loss=-2.5, is_correct=False)
    r = m.analyze()
    assert r.tilt_level in ('warning', 'tilt', 'severe'), \
        f'Expected warning+ with 80% accuracy drop, got {r.tilt_level}'
    assert r.accuracy_drop < 0
    print(f'Accuracy drop: {r.accuracy_drop:.0%}  tilt={r.tilt_level}')


def test_good_decision_resets_consecutive():
    """One correct decision resets the consecutive bad counter."""
    m = TiltMonitor()
    m.record(ev_loss=-3.0, is_correct=False)
    m.record(ev_loss=-2.0, is_correct=False)
    m.record(ev_loss=0.0, is_correct=True)   # reset
    r = m.analyze()
    assert r.consecutive_bad == 0, \
        f'Good decision should reset consecutive_bad: {r.consecutive_bad}'
    print(f'After reset: consecutive_bad={r.consecutive_bad}  tilt={r.tilt_level}')


def test_positive_momentum():
    """Recent decisions better than baseline → positive momentum."""
    m = TiltMonitor()
    # Establish mediocre baseline
    for _ in range(10):
        m.record(ev_loss=-0.5, is_correct=False)
    # Recent 5: all correct
    for _ in range(5):
        m.record(ev_loss=0.0, is_correct=True)
    r = m.analyze()
    assert r.momentum == 'positive', f'Expected positive momentum, got {r.momentum}'
    print(f'Positive momentum: accuracy_drop={r.accuracy_drop:.0%}  momentum={r.momentum_zh}')


def test_summary_format():
    """Summary should contain state info and be under 80 chars."""
    m = TiltMonitor()
    for _ in range(3):
        m.record(ev_loss=-2.0, is_correct=False)
    r = m.analyze()
    s = tilt_summary(r)
    assert len(s) <= 80, f'Too long ({len(s)}): {s}'
    assert s  # non-empty
    print(f'Summary ({len(s)} chars): {s}')


def test_reset_clears_history():
    """After reset, monitor starts fresh."""
    m = TiltMonitor()
    for _ in range(4):
        m.record(ev_loss=-4.0, is_correct=False)
    r_before = m.analyze()
    assert r_before.tilt_level in ('tilt', 'severe')
    m.reset()
    r_after = m.analyze()
    assert r_after.tilt_level == 'none'
    assert m.decision_count == 0
    print(f'Before reset: {r_before.tilt_level}  After reset: {r_after.tilt_level}')


if __name__ == '__main__':
    tests = [
        test_no_decisions_neutral,
        test_good_decisions_no_tilt,
        test_consecutive_bad_triggers_warning,
        test_three_consecutive_bad_tilt,
        test_four_consecutive_bad_severe,
        test_accuracy_drop_triggers_warning,
        test_good_decision_resets_consecutive,
        test_positive_momentum,
        test_summary_format,
        test_reset_clears_history,
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
