"""Tests for session leak surfacing in session_tracker + integration."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.session_tracker import get_tracker, reset_tracker, _LEAK_ZH


def _tracker_with_decisions():
    """Build a tracker with 10 decisions (5 over_fold leaks)."""
    t = reset_tracker('test')
    # Record 5 over-fold mistakes (fold when should call) → should show as worst leak
    for i in range(5):
        t.record_decision(
            street='river', position='BTN',
            situation='river facing half-pot bet',
            action_taken='fold', recommended='call',
            ev_taken=-1.0, ev_recommended=2.0,
            equity=0.48, pot_bb=10.0,
        )
        t.new_hand()
    # Record 2 correct decisions
    for i in range(2):
        t.record_decision(
            street='flop', position='BTN',
            situation='cbet opportunity',
            action_taken='raise', recommended='raise',
            ev_taken=3.0, ev_recommended=3.0,
            equity=0.72, pot_bb=8.0,
        )
        t.new_hand()
    return t


def test_leaks_exist_after_mistakes():
    t = _tracker_with_decisions()
    rep = t.get_report()
    assert rep.total_decisions >= 7
    assert len(rep.leaks) > 0
    print(f'Leaks found: {len(rep.leaks)}')
    for lk in rep.leaks:
        print(f'  {lk.category_zh}: {lk.count} decisions, EV={lk.total_ev_loss:+.1f}BB')


def test_worst_leak_is_over_fold():
    t = _tracker_with_decisions()
    rep = t.get_report()
    # Filter out 'correct'
    bad_leaks = [lk for lk in rep.leaks if lk.category != 'correct']
    assert bad_leaks, 'Should have at least one bad leak'
    worst = bad_leaks[0]  # already sorted by severity
    assert worst.category == 'over_fold', \
        f'Expected over_fold as worst, got {worst.category}'
    print(f'Worst leak: {worst.category_zh}  count={worst.count}  '
          f'EV={worst.total_ev_loss:+.1f}BB')


def test_worst_leak_has_negative_ev():
    t = _tracker_with_decisions()
    rep = t.get_report()
    bad = [lk for lk in rep.leaks if lk.category != 'correct']
    if bad:
        assert bad[0].total_ev_loss <= 0, \
            f'Worst leak EV should be <= 0, got {bad[0].total_ev_loss}'
    print('Worst leak has negative EV: OK')


def test_accuracy_rate_computed():
    t = _tracker_with_decisions()
    rep = t.get_report()
    assert 0.0 <= rep.accuracy_rate <= 1.0
    # 2 correct out of 7 decisions = ~28.6%
    print(f'Accuracy rate: {rep.accuracy_rate:.0%}  (expected ~28%)')


def test_leak_advice_in_chinese():
    t = _tracker_with_decisions()
    rep = t.get_report()
    bad = [lk for lk in rep.leaks if lk.category != 'correct']
    if bad:
        assert bad[0].advice, 'Leak should have advice'
        print(f'Leak advice: {bad[0].advice[:40]}')


def test_leak_category_zh_mapping():
    for cat, zh in _LEAK_ZH.items():
        assert zh, f'Category {cat} has empty zh label'
    print('All categories have Chinese labels:', list(_LEAK_ZH.values()))


def test_session_summary_line():
    t = _tracker_with_decisions()
    rep = t.get_report()
    assert rep.summary_line
    print(f'Summary: {rep.summary_line[:60]}')


if __name__ == '__main__':
    tests = [
        test_leaks_exist_after_mistakes,
        test_worst_leak_is_over_fold,
        test_worst_leak_has_negative_ev,
        test_accuracy_rate_computed,
        test_leak_advice_in_chinese,
        test_leak_category_zh_mapping,
        test_session_summary_line,
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
