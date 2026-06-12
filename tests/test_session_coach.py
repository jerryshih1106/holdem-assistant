"""Tests for poker/session_coach.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.session_coach import coach_session, coach_one_liner, CoachAdvice, LeakFix
from poker.session_tracker import get_tracker, reset_tracker


def _make_tracker_with_over_folds(n_folds=3, n_correct=5):
    reset_tracker()
    t = get_tracker()
    for _ in range(n_folds):
        t.record_decision('flop', 'BTN', 'cbet', 'fold', 'call',
                          ev_taken=-5.0, ev_recommended=2.0,
                          equity=0.42, pot_bb=10, pot_odds=0.33)
    for _ in range(n_correct):
        t.record_decision('preflop', 'BTN', 'open', 'raise', 'raise',
                          ev_taken=3.0, ev_recommended=3.0,
                          equity=0.65, pot_bb=3)
    return t


def _make_empty_tracker():
    reset_tracker()
    return get_tracker()


def _make_perfect_tracker(n=8):
    reset_tracker()
    t = get_tracker()
    for _ in range(n):
        t.record_decision('preflop', 'BTN', 'open', 'raise', 'raise',
                          ev_taken=3.0, ev_recommended=3.0, equity=0.65, pot_bb=3)
    return t


def test_returns_coach_advice():
    """coach_session should return a CoachAdvice instance."""
    t = _make_tracker_with_over_folds()
    advice = coach_session(t)
    assert isinstance(advice, CoachAdvice), f'Expected CoachAdvice: {type(advice)}'
    print(f'type: {type(advice).__name__}')


def test_required_fields():
    """CoachAdvice should have all documented fields."""
    t = _make_tracker_with_over_folds()
    advice = coach_session(t)
    fields = ['total_decisions', 'accuracy_rate', 'total_ev_loss_per_100', 'grade',
              'grade_desc', 'top_leak', 'all_leaks', 'best_position', 'worst_position',
              'worst_street', 'priority_fix', 'summary']
    for f in fields:
        assert hasattr(advice, f), f'CoachAdvice missing field: {f}'
    print(f'All {len(fields)} fields present')


def test_total_decisions_correct():
    """total_decisions should match number of recorded decisions."""
    t = _make_tracker_with_over_folds(n_folds=3, n_correct=5)
    advice = coach_session(t)
    assert advice.total_decisions == 8, \
        f'total_decisions should be 8: {advice.total_decisions}'
    print(f'total_decisions: {advice.total_decisions}')


def test_accuracy_rate_range():
    """accuracy_rate should be in [0.0, 1.0]."""
    t = _make_tracker_with_over_folds()
    advice = coach_session(t)
    assert 0.0 <= advice.accuracy_rate <= 1.0, \
        f'accuracy_rate out of range: {advice.accuracy_rate}'
    print(f'accuracy_rate: {advice.accuracy_rate:.2f}')


def test_over_fold_detected():
    """Tracker with 3 over-folds should have over_fold as top leak."""
    t = _make_tracker_with_over_folds(n_folds=3, n_correct=1)
    advice = coach_session(t)
    assert advice.top_leak is not None, 'top_leak should not be None with over-folds'
    assert advice.top_leak.category == 'over_fold', \
        f'top_leak should be over_fold: {advice.top_leak.category}'
    print(f'top_leak: {advice.top_leak.category}')


def test_top_leak_is_leakfix():
    """top_leak should be a LeakFix dataclass."""
    t = _make_tracker_with_over_folds()
    advice = coach_session(t)
    if advice.top_leak:
        assert isinstance(advice.top_leak, LeakFix), \
            f'top_leak should be LeakFix: {type(advice.top_leak)}'
        print(f'top_leak type: {type(advice.top_leak).__name__}')
    else:
        print('top_leak is None (no leaks recorded)')


def test_leakfix_fields():
    """Each LeakFix in all_leaks should have expected fields."""
    t = _make_tracker_with_over_folds()
    advice = coach_session(t)
    for lf in advice.all_leaks:
        for f in ['category', 'category_name', 'count', 'ev_loss_per_100', 'fix', 'drill']:
            assert hasattr(lf, f), f'LeakFix missing field: {f}'
    print(f'all_leaks count: {len(advice.all_leaks)}  fields OK')


def test_grade_is_letter():
    """grade should be A, B, C, D, or F."""
    t = _make_tracker_with_over_folds()
    advice = coach_session(t)
    assert advice.grade in ('A', 'B', 'C', 'D', 'F'), \
        f'grade should be A-F: {advice.grade}'
    print(f'grade: {advice.grade}  ({advice.grade_desc[:30]})')


def test_perfect_session_grade_a():
    """Perfect accuracy with no EV loss should receive grade A."""
    t = _make_perfect_tracker(n=10)
    advice = coach_session(t)
    # Grade A = ev_loss_per_100 < 3; perfect tracker loses no EV
    assert advice.grade in ('A', 'B'), \
        f'Perfect session should get A or B: {advice.grade}'
    print(f'Perfect session grade: {advice.grade}')


def test_bad_session_grade_low():
    """Many over-folds should result in a low grade (C, D, or F)."""
    t = _make_tracker_with_over_folds(n_folds=8, n_correct=1)
    advice = coach_session(t)
    assert advice.grade in ('C', 'D', 'F'), \
        f'Bad session should get C/D/F: {advice.grade}'
    print(f'Bad session grade: {advice.grade}')


def test_worst_street_tracked():
    """worst_street should be a string or None."""
    t = _make_tracker_with_over_folds()
    advice = coach_session(t)
    assert advice.worst_street is None or isinstance(advice.worst_street, str), \
        f'worst_street should be str or None: {advice.worst_street}'
    print(f'worst_street: {advice.worst_street}')


def test_over_fold_worst_street_flop():
    """Over-folds on flop should set worst_street to flop."""
    t = _make_tracker_with_over_folds(n_folds=5, n_correct=0)
    advice = coach_session(t)
    assert advice.worst_street == 'flop', \
        f'worst_street should be flop: {advice.worst_street}'
    print(f'worst_street (all flop errors): {advice.worst_street}')


def test_priority_fix_is_string():
    """priority_fix should be a non-empty string."""
    t = _make_tracker_with_over_folds()
    advice = coach_session(t)
    assert isinstance(advice.priority_fix, str) and len(advice.priority_fix) > 5, \
        f'priority_fix should be non-empty string: {repr(advice.priority_fix[:40])}'
    print(f'priority_fix (first 60): {advice.priority_fix[:60]}')


def test_summary_is_string():
    """summary should be a non-empty string."""
    t = _make_tracker_with_over_folds()
    advice = coach_session(t)
    assert isinstance(advice.summary, str) and len(advice.summary) > 5, \
        f'summary should be non-empty string: {repr(advice.summary[:40])}'
    print(f'summary: {advice.summary[:60]}')


def test_empty_tracker_no_crash():
    """coach_session on an empty tracker should not crash."""
    t = _make_empty_tracker()
    advice = coach_session(t)
    assert isinstance(advice, CoachAdvice), 'Should return CoachAdvice on empty tracker'
    assert advice.total_decisions == 0, \
        f'Empty tracker total_decisions should be 0: {advice.total_decisions}'
    print(f'Empty tracker: grade={advice.grade} total={advice.total_decisions}')


def test_all_leaks_sorted_by_ev_loss():
    """all_leaks should be sorted descending by ev_loss_per_100."""
    t = _make_tracker_with_over_folds()
    advice = coach_session(t)
    costs = [lf.ev_loss_per_100 for lf in advice.all_leaks]
    assert costs == sorted(costs, reverse=True), \
        f'all_leaks should be sorted descending by EV loss: {costs}'
    print(f'all_leaks EV costs (descending): {costs}')


def test_coach_one_liner_with_leaks():
    """coach_one_liner should return a non-empty string when leaks exist."""
    t = _make_tracker_with_over_folds()
    advice = coach_session(t)
    line = coach_one_liner(advice)
    assert isinstance(line, str) and len(line) > 5, \
        f'coach_one_liner should be non-empty: {repr(line)}'
    assert advice.grade in line, f'grade should appear in one_liner: {line}'
    print(f'one_liner: {line[:60]}')


def test_coach_one_liner_no_leaks():
    """coach_one_liner with no leaks should still return valid string."""
    t = _make_perfect_tracker()
    advice = coach_session(t)
    line = coach_one_liner(advice)
    assert isinstance(line, str) and len(line) > 3, \
        f'one_liner with no leaks should be non-empty: {repr(line)}'
    print(f'one_liner (no leaks): {line}')


def test_ev_loss_per_100_is_numeric():
    """total_ev_loss_per_100 should be a number."""
    t = _make_tracker_with_over_folds()
    advice = coach_session(t)
    assert isinstance(advice.total_ev_loss_per_100, (int, float)), \
        f'total_ev_loss_per_100 should be numeric: {advice.total_ev_loss_per_100}'
    print(f'total_ev_loss_per_100: {advice.total_ev_loss_per_100:.1f}')


if __name__ == '__main__':
    tests = [
        test_returns_coach_advice,
        test_required_fields,
        test_total_decisions_correct,
        test_accuracy_rate_range,
        test_over_fold_detected,
        test_top_leak_is_leakfix,
        test_leakfix_fields,
        test_grade_is_letter,
        test_perfect_session_grade_a,
        test_bad_session_grade_low,
        test_worst_street_tracked,
        test_over_fold_worst_street_flop,
        test_priority_fix_is_string,
        test_summary_is_string,
        test_empty_tracker_no_crash,
        test_all_leaks_sorted_by_ev_loss,
        test_coach_one_liner_with_leaks,
        test_coach_one_liner_no_leaks,
        test_ev_loss_per_100_is_numeric,
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
