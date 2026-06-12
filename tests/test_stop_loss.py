"""Tests for poker/stop_loss.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.stop_loss import analyze_stop_loss, stop_loss_one_liner, StopLossResult


def _sl(lost=1.0, bankroll=25.0, hands=300, tilt=0.0, hours=2.0, table='average'):
    return analyze_stop_loss(
        session_buy_ins_lost=lost,
        total_bankroll_bis=bankroll,
        hands_played=hands,
        tilt_score=tilt,
        hours_played=hours,
        table_quality=table,
    )


def test_returns_stop_loss_result():
    r = _sl()
    assert isinstance(r, StopLossResult)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _sl()
    fields = [
        'session_state', 'urgency', 'buy_ins_lost', 'total_bankroll_bis',
        'bankroll_pct_lost', 'hands_played', 'hours_played', 'tilt_score',
        'stop_loss_threshold_bis', 'break_threshold_bis',
        'hands_per_hour', 'cognitive_limit_hours', 'hands_remaining_estimate',
        'session_ev_per_100', 'recommendation', 'action_items',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing field: {f}'
    print(f'All {len(fields)} fields present')


def test_continue_when_small_loss():
    """Small loss, fresh, good table = continue."""
    r = _sl(lost=0.3, bankroll=30.0, tilt=0.0, hours=0.5, table='good')
    assert r.session_state == 'continue', \
        f'Small loss should be continue: {r.session_state}'
    print(f'Small loss state: {r.session_state}')


def test_stop_session_at_threshold():
    """Hit the 2 BI stop-loss → stop session."""
    r = _sl(lost=2.5, bankroll=25.0, tilt=0.0, hours=2.0)
    assert r.session_state in ('stop_session', 'emergency_stop'), \
        f'2.5 BI loss on 25 BI roll should stop: {r.session_state}'
    print(f'2.5 BI loss state: {r.session_state}')


def test_emergency_stop_on_high_tilt():
    """High tilt + loss = emergency stop."""
    r = _sl(lost=1.5, bankroll=25.0, tilt=0.85, hours=3.0)
    assert r.session_state == 'emergency_stop', \
        f'High tilt + loss should emergency stop: {r.session_state}'
    print(f'High tilt state: {r.session_state}')


def test_take_break_on_moderate_loss():
    """Moderate loss triggers break."""
    r = _sl(lost=1.3, bankroll=25.0, tilt=0.0, hours=1.5, table='average')
    assert r.session_state in ('take_break', 'stop_session', 'emergency_stop'), \
        f'Moderate loss should at least trigger break: {r.session_state}'
    print(f'Moderate loss state: {r.session_state}')


def test_stop_loss_higher_for_bigger_bankroll():
    """Larger bankroll = higher stop-loss threshold."""
    r_small = _sl(bankroll=15.0)
    r_large = _sl(bankroll=60.0)
    assert r_large.stop_loss_threshold_bis > r_small.stop_loss_threshold_bis, \
        f'Larger roll should have higher threshold: {r_large.stop_loss_threshold_bis} > {r_small.stop_loss_threshold_bis}'
    print(f'Stop-loss: 15BI={r_small.stop_loss_threshold_bis} 60BI={r_large.stop_loss_threshold_bis}')


def test_bankroll_pct_lost_correct():
    """bankroll_pct_lost = lost / total."""
    r = _sl(lost=2.0, bankroll=20.0)
    expected = 2.0 / 20.0
    assert abs(r.bankroll_pct_lost - expected) < 0.01, \
        f'bankroll_pct_lost should be {expected:.2f}: {r.bankroll_pct_lost}'
    print(f'bankroll_pct_lost: {r.bankroll_pct_lost:.2f}')


def test_session_state_valid():
    valid = {'continue', 'take_break', 'move_down', 'stop_session', 'emergency_stop'}
    for lost in (0.3, 1.0, 2.0, 3.5):
        r = _sl(lost=lost)
        assert r.session_state in valid, f'State should be valid: {r.session_state}'
    print('All states valid')


def test_urgency_valid():
    valid = {'none', 'low', 'medium', 'high', 'critical'}
    r = _sl()
    assert r.urgency in valid, f'urgency should be valid: {r.urgency}'
    print(f'urgency: {r.urgency}')


def test_bad_table_triggers_move_down():
    """Bad table quality with some loss should trigger move_down."""
    r = _sl(lost=0.7, bankroll=30.0, tilt=0.0, hours=1.0, table='bad')
    assert r.session_state in ('move_down', 'take_break', 'stop_session'), \
        f'Bad table should prompt adjustment: {r.session_state}'
    print(f'Bad table state: {r.session_state}')


def test_long_session_triggers_break():
    """Playing 4h should trigger break or stop."""
    r = _sl(lost=0.1, bankroll=50.0, tilt=0.0, hours=4.0, table='good')
    assert r.session_state in ('take_break', 'stop_session', 'emergency_stop', 'move_down'), \
        f'4h session should trigger at least break: {r.session_state}'
    print(f'4h session state: {r.session_state}')


def test_recommendation_is_string():
    r = _sl()
    assert isinstance(r.recommendation, str) and len(r.recommendation) > 5
    print(f'recommendation: {r.recommendation[:60]}')


def test_action_items_not_empty():
    r = _sl()
    assert isinstance(r.action_items, list) and len(r.action_items) > 0
    print(f'action_items: {len(r.action_items)} items')


def test_session_ev_lower_with_tilt():
    """Higher tilt = lower session EV."""
    r_no_tilt  = _sl(tilt=0.0)
    r_tilted   = _sl(tilt=0.6)
    assert r_tilted.session_ev_per_100 < r_no_tilt.session_ev_per_100, \
        f'Tilt should reduce EV: {r_tilted.session_ev_per_100} < {r_no_tilt.session_ev_per_100}'
    print(f'EV: no_tilt={r_no_tilt.session_ev_per_100:.1f} tilted={r_tilted.session_ev_per_100:.1f}')


def test_session_ev_better_on_good_table():
    """Good table = higher session EV."""
    r_good = _sl(table='good')
    r_bad  = _sl(table='bad')
    assert r_good.session_ev_per_100 > r_bad.session_ev_per_100, \
        f'Good table should have higher EV: {r_good.session_ev_per_100} > {r_bad.session_ev_per_100}'
    print(f'EV: good={r_good.session_ev_per_100:.1f} bad={r_bad.session_ev_per_100:.1f}')


def test_stop_loss_one_liner():
    r = _sl()
    line = stop_loss_one_liner(r)
    assert isinstance(line, str) and len(line) > 5
    print(f'one_liner: {line}')


def test_small_bankroll_triggers_emergency():
    """Very low bankroll (10 BI) should trigger emergency even with small loss."""
    r = _sl(lost=1.0, bankroll=9.0)
    assert r.session_state == 'emergency_stop', \
        f'10 BI bankroll should emergency stop: {r.session_state}'
    print(f'Small bankroll state: {r.session_state}')


def test_break_threshold_less_than_stop():
    """Break threshold should always be less than stop threshold."""
    for bankroll in (15.0, 25.0, 50.0):
        r = _sl(bankroll=bankroll)
        assert r.break_threshold_bis < r.stop_loss_threshold_bis, \
            f'Break thresh < stop thresh: {r.break_threshold_bis} < {r.stop_loss_threshold_bis}'
    print('Break threshold always < stop threshold')


def test_hands_remaining_non_negative():
    """Remaining hands estimate should be >= 0."""
    r = _sl(hours=4.0)
    assert r.hands_remaining_estimate >= 0
    print(f'hands_remaining: {r.hands_remaining_estimate}')


if __name__ == '__main__':
    tests = [
        test_returns_stop_loss_result, test_required_fields,
        test_continue_when_small_loss, test_stop_session_at_threshold,
        test_emergency_stop_on_high_tilt, test_take_break_on_moderate_loss,
        test_stop_loss_higher_for_bigger_bankroll, test_bankroll_pct_lost_correct,
        test_session_state_valid, test_urgency_valid,
        test_bad_table_triggers_move_down, test_long_session_triggers_break,
        test_recommendation_is_string, test_action_items_not_empty,
        test_session_ev_lower_with_tilt, test_session_ev_better_on_good_table,
        test_stop_loss_one_liner, test_small_bankroll_triggers_emergency,
        test_break_threshold_less_than_stop, test_hands_remaining_non_negative,
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
