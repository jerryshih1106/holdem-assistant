"""Tests for poker/session_tracker.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.session_tracker import get_tracker, reset_tracker, classify_leak


def _fresh():
    reset_tracker()
    return get_tracker()


def test_classify_leak_over_fold():
    """Folding when call is correct and equity > pot_odds = over_fold."""
    category, ev_loss = classify_leak('fold', 'call', -5.0, 2.0, 0.40, 0.35, 'flop')
    assert category == 'over_fold', f'Should be over_fold: {category}'
    assert ev_loss < 0, f'EV loss should be negative: {ev_loss}'
    print(f'over_fold: category={category} ev_loss={ev_loss}')


def test_classify_leak_over_call():
    """Calling when fold is correct (equity < pot_odds) = over_call."""
    category, ev_loss = classify_leak('call', 'fold', 2.0, 0.5, 0.20, 0.25, 'river')
    assert category == 'over_call', f'Should be over_call: {category}'
    print(f'over_call: category={category}')


def test_classify_leak_correct_action_no_leak():
    """Correct action (action == recommended) should return no_leak or near-zero loss."""
    category, ev_loss = classify_leak('raise', 'raise', 5.0, 5.0, 0.70, 0.20, 'turn')
    assert ev_loss == 0.0 or category in ('no_leak', 'correct'), \
        f'Correct action should have 0 EV loss: category={category} ev_loss={ev_loss}'
    print(f'Correct action: category={category} ev_loss={ev_loss}')


def test_report_total_decisions():
    """total_decisions should count all recorded decisions."""
    t = _fresh()
    for i in range(5):
        t.record_decision('flop', 'BTN', 'cbet', 'raise', 'raise',
                          ev_taken=3.0, ev_recommended=3.0, equity=0.7, pot_bb=10)
    report = t.get_report()
    assert report.total_decisions == 5, \
        f'Should have 5 decisions: {report.total_decisions}'
    print(f'total_decisions: {report.total_decisions}')


def test_accuracy_rate_all_correct():
    """100% correct decisions should give accuracy_rate = 1.0."""
    t = _fresh()
    for _ in range(4):
        t.record_decision('preflop', 'BTN', 'open', 'raise', 'raise',
                          ev_taken=3.0, ev_recommended=3.0, equity=0.65, pot_bb=3)
    report = t.get_report()
    assert abs(report.accuracy_rate - 1.0) < 0.01, \
        f'All-correct accuracy should = 1.0: {report.accuracy_rate}'
    print(f'accuracy_rate (all correct): {report.accuracy_rate:.0%}')


def test_accuracy_rate_partial():
    """Mixed correct/wrong decisions should give partial accuracy."""
    t = _fresh()
    # 2 correct
    for _ in range(2):
        t.record_decision('preflop', 'BTN', 'open', 'raise', 'raise',
                          ev_taken=3.0, ev_recommended=3.0, equity=0.65, pot_bb=3)
    # 2 wrong
    for _ in range(2):
        t.record_decision('flop', 'BTN', 'cbet', 'fold', 'call',
                          ev_taken=-5.0, ev_recommended=2.0, equity=0.40, pot_bb=10)
    report = t.get_report()
    assert abs(report.accuracy_rate - 0.5) < 0.01, \
        f'50% accuracy: {report.accuracy_rate}'
    print(f'accuracy_rate (50/50): {report.accuracy_rate:.0%}')


def test_ev_loss_accumulated():
    """total_ev_loss should accumulate EV difference across mistakes."""
    t = _fresh()
    t.record_decision('flop', 'BTN', 'cbet', 'fold', 'call',
                      ev_taken=-5.0, ev_recommended=2.0, equity=0.40, pot_bb=10)
    report = t.get_report()
    assert report.total_ev_loss < 0, \
        f'total_ev_loss should be negative after mistake: {report.total_ev_loss}'
    print(f'total_ev_loss: {report.total_ev_loss}')


def test_leaks_list_populated_on_mistakes():
    """leaks should be populated when mistakes are made."""
    t = _fresh()
    t.record_decision('flop', 'BTN', 'cbet', 'fold', 'call',
                      ev_taken=-5.0, ev_recommended=2.0, equity=0.40, pot_bb=10)
    report = t.get_report()
    assert isinstance(report.leaks, list) and len(report.leaks) > 0, \
        f'leaks should be non-empty after mistake: {report.leaks}'
    print(f'leaks count: {len(report.leaks)} first={report.leaks[0].category}')


def test_summary_line_is_string():
    """summary_line should be a non-empty string."""
    t = _fresh()
    t.record_decision('turn', 'CO', 'bet', 'raise', 'raise',
                      ev_taken=4.0, ev_recommended=4.0, equity=0.72, pot_bb=20)
    report = t.get_report()
    assert isinstance(report.summary_line, str) and len(report.summary_line) > 5, \
        f'summary_line should be non-empty string: {repr(report.summary_line)[:50]}'
    print(f'summary_line length: {len(report.summary_line)}')


def test_worst_street_identified():
    """worst_street should be the street with most EV loss."""
    t = _fresh()
    # flop mistake: -7 EV
    t.record_decision('flop', 'BTN', 'cbet', 'fold', 'call',
                      ev_taken=-5.0, ev_recommended=2.0, equity=0.40, pot_bb=10)
    # correct turn
    t.record_decision('turn', 'BTN', 'bet', 'raise', 'raise',
                      ev_taken=5.0, ev_recommended=5.0, equity=0.75, pot_bb=15)
    report = t.get_report()
    assert report.worst_street == 'flop', \
        f'worst_street should be flop: {report.worst_street}'
    print(f'worst_street: {report.worst_street}')


if __name__ == '__main__':
    tests = [
        test_classify_leak_over_fold,
        test_classify_leak_over_call,
        test_classify_leak_correct_action_no_leak,
        test_report_total_decisions,
        test_accuracy_rate_all_correct,
        test_accuracy_rate_partial,
        test_ev_loss_accumulated,
        test_leaks_list_populated_on_mistakes,
        test_summary_line_is_string,
        test_worst_street_identified,
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
