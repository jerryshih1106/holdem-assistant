"""Tests for tilt_management_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.tilt_management_guide import (
    analyze_tilt_management, TiltManagementResult, tilt_one_liner,
    _tilt_score, _tilt_level, _hard_stop_triggered,
    TILT_TRIGGER_SEVERITY, TILT_LEVEL_THRESHOLDS, TILT_BEHAVIOR_CHANGES,
    TILT_STOP_ACTION, HARD_STOP_LOSS_BUY_INS,
)


def _tilt(**kw):
    defaults = dict(
        triggers=[], hands_since_trigger=0,
        bb_loss=0.0, buy_in_bb=100.0, session_hours=2.0,
    )
    defaults.update(kw)
    return analyze_tilt_management(**defaults)


def test_returns_result():
    assert isinstance(_tilt(), TiltManagementResult)


def test_no_triggers_no_tilt():
    r = _tilt()
    assert r.tilt_level == 'none'


def test_bad_beat_high_severity():
    assert TILT_TRIGGER_SEVERITY['bad_beat'] >= 0.80


def test_bad_beat_causes_tilt():
    score = _tilt_score(['bad_beat'], 0, 0.0, 100.0, 2.0)
    assert score >= 0.50


def test_tilt_level_none():
    assert _tilt_level(0.10) == 'none'


def test_tilt_level_mild():
    assert _tilt_level(0.30) == 'mild'


def test_tilt_level_moderate():
    assert _tilt_level(0.55) == 'moderate'


def test_tilt_level_severe():
    assert _tilt_level(0.80) == 'severe'


def test_hard_stop_triggers_at_2_buyins():
    assert _hard_stop_triggered(210.0, 100.0) is True


def test_no_hard_stop_below_threshold():
    assert _hard_stop_triggered(50.0, 100.0) is False


def test_recency_decays_with_hands():
    early = _tilt_score(['bad_beat'], 3, 0.0, 100.0, 2.0)
    late  = _tilt_score(['bad_beat'], 35, 0.0, 100.0, 2.0)
    assert early > late


def test_bb_loss_increases_score():
    no_loss  = _tilt_score([], 0, 0.0, 100.0, 2.0)
    big_loss = _tilt_score([], 0, 80.0, 100.0, 2.0)
    assert big_loss > no_loss


def test_long_session_adds_score():
    short = _tilt_score([], 0, 0.0, 100.0, 1.0)
    long  = _tilt_score([], 0, 0.0, 100.0, 6.0)
    assert long > short


def test_behavior_changes_at_severe():
    b = TILT_BEHAVIOR_CHANGES['severe']
    assert b['vpip_adj'] >= 0.20


def test_stop_action_severe():
    assert 'QUIT' in TILT_STOP_ACTION['severe']


def test_tilt_score_in_range():
    r = _tilt(triggers=['bad_beat', 'losing_streak'])
    assert 0.0 <= r.tilt_score <= 1.0


def test_tips_populated():
    r = _tilt()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _tilt()
    line = tilt_one_liner(r)
    assert '[TILT' in line and 'action=' in line


def test_hard_stop_flag():
    r = _tilt(bb_loss=250.0, buy_in_bb=100.0)
    assert r.hard_stop is True


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t()
            print(f'[OK] {t.__name__}')
        except Exception as e:
            print(f'[FAIL] {t.__name__}: {e}')
            failed += 1
    print(f'\n{len(tests)-failed}/{len(tests)} passed')
    sys.exit(failed)
