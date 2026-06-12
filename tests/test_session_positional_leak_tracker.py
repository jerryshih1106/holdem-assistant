"""Tests for session_positional_leak_tracker.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.session_positional_leak_tracker import (
    track_positional_leaks, PositionalLeakReport, plt_one_liner,
    GTO_VPIP, GTO_PFR, EXPECTED_WIN_RATE, _leak_score, _position_assessment,
)


def _good_stats(bb_won=8.0, vpip=0.43, pfr=0.31):
    return dict(hands=100, bb_won=bb_won, vpip=vpip, pfr=pfr, wtsd=0.27, wsd=0.52)


def _leak_stats(bb_won=-5.0, vpip=0.55, pfr=0.12):
    return dict(hands=100, bb_won=bb_won, vpip=vpip, pfr=pfr, wtsd=0.40, wsd=0.43)


def _plt(**kw):
    defaults = dict(
        ep_stats=dict(hands=80, bb_won=-2.1, vpip=0.18, pfr=0.12, wtsd=0.28, wsd=0.49),
        mp_stats=dict(hands=70, bb_won=1.5, vpip=0.22, pfr=0.16, wtsd=0.30, wsd=0.51),
        co_stats=dict(hands=65, bb_won=3.2, vpip=0.35, pfr=0.20, wtsd=0.29, wsd=0.50),
        btn_stats=dict(hands=90, bb_won=8.5, vpip=0.50, pfr=0.38, wtsd=0.27, wsd=0.52),
        sb_stats=dict(hands=55, bb_won=-8.0, vpip=0.62, pfr=0.22, wtsd=0.38, wsd=0.44),
        bb_stats=dict(hands=85, bb_won=-1.5, vpip=0.70, pfr=0.14, wtsd=0.32, wsd=0.50),
    )
    defaults.update(kw)
    return track_positional_leaks(**defaults)


def test_returns_positional_leak_report():
    r = _plt()
    assert isinstance(r, PositionalLeakReport)


def test_gto_vpip_has_all_positions():
    assert set(GTO_VPIP.keys()) == {'EP', 'MP', 'CO', 'BTN', 'SB', 'BB'}


def test_expected_win_rate_btn_positive():
    assert EXPECTED_WIN_RATE['BTN'] > 0


def test_expected_win_rate_sb_negative():
    assert EXPECTED_WIN_RATE['SB'] < 0


def test_leak_score_good_stats_lower():
    score_good = _leak_score('BTN', 8.0, 0.43, 0.31, 0.27, 0.52)
    score_bad = _leak_score('BTN', -5.0, 0.65, 0.12, 0.42, 0.40)
    assert score_good < score_bad


def test_leak_score_zero_or_positive():
    score = _leak_score('BTN', 8.0, 0.43, 0.31, 0.27, 0.52)
    assert score >= 0.0


def test_position_assessment_reliable():
    result = _position_assessment('BTN', 100, 8.0, 0.43, 0.31, 0.27, 0.52)
    assert result['reliable'] is True


def test_position_assessment_unreliable_small_sample():
    result = _position_assessment('BTN', 30, 8.0, 0.43, 0.31, 0.27, 0.52)
    assert result['reliable'] is False


def test_position_assessment_over_vpip_leak():
    result = _position_assessment('EP', 100, -1.0, 0.40, 0.12, 0.28, 0.50)
    leaks = ' '.join(result['leaks'])
    assert 'VPIP' in leaks or 'wide' in leaks


def test_position_assessment_calling_gap_leak():
    result = _position_assessment('BTN', 100, 8.0, 0.55, 0.12, 0.28, 0.50)
    leaks = ' '.join(result['leaks'])
    assert 'gap' in leaks.lower() or '3-bet' in leaks.lower() or 'calling' in leaks.lower()


def test_total_hands_summed():
    r = _plt()
    assert r.total_hands == sum([80, 70, 65, 90, 55, 85])


def test_top_leak_is_most_leaky():
    r = _plt(sb_stats=dict(hands=100, bb_won=-20.0, vpip=0.80, pfr=0.05, wtsd=0.50, wsd=0.38))
    # SB with terrible stats should be top leak
    assert r.top_leak_position == 'SB'


def test_strongest_position_is_best_wr():
    r = _plt()
    assert r.strongest_position == 'BTN'


def test_weakest_position_is_worst_wr():
    r = _plt()
    assert r.weakest_position == 'SB'


def test_over_vpip_positions_detected():
    r = _plt(ep_stats=dict(hands=100, bb_won=-5.0, vpip=0.40, pfr=0.12, wtsd=0.28, wsd=0.50))
    assert 'EP' in r.over_vpip_positions


def test_under_pfr_positions_detected():
    r = _plt(btn_stats=dict(hands=100, bb_won=8.0, vpip=0.43, pfr=0.10, wtsd=0.27, wsd=0.52))
    assert 'BTN' in r.under_pfr_positions


def test_six_positions_in_data():
    r = _plt()
    assert set(r.position_data.keys()) == {'EP', 'MP', 'CO', 'BTN', 'SB', 'BB'}


def test_leak_ranking_populated():
    r = _plt()
    assert len(r.leak_ranking) > 0


def test_tips_populated():
    r = _plt()
    assert len(r.tips) > 0


def test_one_liner_format():
    r = _plt()
    line = plt_one_liner(r)
    assert '[PLT' in line
    assert 'wr=' in line
    assert 'best=' in line


def test_avg_win_rate_computed():
    r = _plt()
    assert isinstance(r.avg_win_rate_bb100, float)


def test_empty_stats_handled():
    r = track_positional_leaks()  # all defaults
    assert isinstance(r, PositionalLeakReport)


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
