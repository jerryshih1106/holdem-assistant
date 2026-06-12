"""Tests for session_opening_strategy.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.session_opening_strategy import (
    analyze_session_opening, SessionOpeningResult, sos_one_liner,
    _current_phase, _session_health, PHASE_THRESHOLDS,
    PHASE_BLUFF_ADJUST, PHASE_OPEN_RANGE_ADJUST,
)


def _sos(**kw):
    defaults = dict(
        hands_played=10, profit_bb=0.0, buy_in_bb=100.0,
        fish_position=3, aggressor_position=5,
        hero_position=4, n_seats=6,
    )
    defaults.update(kw)
    return analyze_session_opening(**defaults)


def test_returns_result():
    assert isinstance(_sos(), SessionOpeningResult)


def test_phase_1_early_hands():
    assert _current_phase(5) == 'observation'


def test_phase_2_mid_hands():
    assert _current_phase(40) == 'calibration'


def test_phase_3_late_hands():
    assert _current_phase(100) == 'exploitation'


def test_observation_has_most_restrictions():
    obs = PHASE_BLUFF_ADJUST['observation']
    exp = PHASE_BLUFF_ADJUST['exploitation']
    assert obs < exp


def test_open_range_tightest_in_observation():
    obs = PHASE_OPEN_RANGE_ADJUST['observation']
    exp = PHASE_OPEN_RANGE_ADJUST['exploitation']
    assert obs < exp


def test_losing_session_health():
    h = _session_health(-30.0, 100.0)
    assert h in ('losing_session', 'bad_session')


def test_winning_session_health():
    h = _session_health(60.0, 100.0)
    assert h == 'strong_session'


def test_neutral_session():
    h = _session_health(5.0, 100.0)
    assert h in ('neutral_session', 'positive_session')


def test_observation_more_obs_goals():
    r_obs = _sos(hands_played=5)
    r_exp = _sos(hands_played=100)
    assert len(r_obs.observation_goals) >= len(r_exp.observation_goals)


def test_bluff_adj_negative_in_phase1():
    r = _sos(hands_played=10)
    assert r.bluff_freq_adj < 0


def test_bluff_adj_zero_in_phase3():
    r = _sos(hands_played=100)
    assert r.bluff_freq_adj == 0.0


def test_seat_quality_stored():
    r = _sos()
    assert r.seat_quality != ''


def test_session_health_stored():
    r = _sos()
    assert r.session_health in ('strong_session', 'positive_session',
                                 'neutral_session', 'losing_session', 'bad_session')


def test_tips_populated():
    r = _sos()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _sos()
    line = sos_one_liner(r)
    assert '[SOS' in line and 'bluff=' in line


def test_bad_session_tip():
    r = _sos(profit_bb=-60.0)
    assert any('SESSION HEALTH' in t or 'STRONG' in t or 'TILT' in t.upper() or 'HEALTH' in t for t in r.tips)


def test_observation_goals_not_empty():
    r = _sos(hands_played=5)
    assert len(r.observation_goals) > 0


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
