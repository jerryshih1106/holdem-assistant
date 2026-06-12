"""Tests for villain_weakness_detector.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.villain_weakness_detector import (
    detect_villain_weakness, WeaknessDetectionResult, vwd_one_liner,
    _weakness_score, _bluff_tier, _adjusted_fold_equity, _bluff_ev,
    WEAKNESS_SIGNALS, BOARD_FOLD_EQUITY, BLUFF_SIZE_BY_SCORE,
)


def _vwd(**kw):
    defaults = dict(
        weakness_signals=['check_check_multiway'],
        board_texture='dry',
        hero_position='ip',
        villain_af=2.0,
        pot_bb=20.0,
        hero_equity_if_called=0.30,
        hero_hand_category='air',
    )
    defaults.update(kw)
    return detect_villain_weakness(**defaults)


def test_returns_weakness_detection_result():
    r = _vwd()
    assert isinstance(r, WeaknessDetectionResult)


def test_no_signals_zero_score():
    score = _weakness_score([])
    assert score == 0


def test_single_signal_score():
    score = _weakness_score(['bet_fold_history'])
    assert score == WEAKNESS_SIGNALS['bet_fold_history']


def test_multiple_signals_higher_score():
    score1 = _weakness_score(['double_check'])
    score2 = _weakness_score(['double_check', 'tiny_bet_sizing'])
    assert score2 >= score1


def test_score_capped_at_10():
    score = _weakness_score(['bet_fold_history', 'check_check_multiway', 'tiny_bet_sizing', 'min_bet'])
    assert score <= 10


def test_bluff_tier_high():
    assert _bluff_tier(9) == 'high'


def test_bluff_tier_medium():
    assert _bluff_tier(6) == 'medium'


def test_bluff_tier_probe():
    assert _bluff_tier(3) == 'probe'


def test_bluff_tier_none():
    assert _bluff_tier(1) == 'none'


def test_dry_board_higher_fold_equity():
    fe_dry = _adjusted_fold_equity(7, 'dry', 'ip', 2.0)
    fe_wet = _adjusted_fold_equity(7, 'wet', 'ip', 2.0)
    assert fe_dry > fe_wet


def test_ip_higher_fold_equity():
    fe_ip = _adjusted_fold_equity(7, 'dry', 'ip', 2.0)
    fe_oop = _adjusted_fold_equity(7, 'dry', 'oop', 2.0)
    assert fe_ip > fe_oop


def test_aggressive_villain_lower_fold_equity():
    fe_passive = _adjusted_fold_equity(7, 'dry', 'ip', 1.0)
    fe_aggro = _adjusted_fold_equity(7, 'dry', 'ip', 4.0)
    assert fe_aggro < fe_passive


def test_bluff_ev_positive_with_high_fold_equity():
    ev = _bluff_ev(20.0, 0.75, 0.70, 0.20)
    assert ev > 0


def test_bluff_ev_negative_low_fold_equity():
    ev = _bluff_ev(20.0, 0.75, 0.15, 0.05)
    assert ev < 0


def test_no_signals_no_bluff():
    r = _vwd(weakness_signals=[])
    assert r.bluff_tier == 'none'
    assert r.bluff_bet_bb == 0.0


def test_strong_signal_high_bluff():
    r = _vwd(weakness_signals=['bet_fold_history'])
    assert r.bluff_tier == 'high'


def test_bluff_size_correlates_with_tier():
    r_high = _vwd(weakness_signals=['bet_fold_history'])
    r_probe = _vwd(weakness_signals=['single_check'])
    assert r_high.recommended_bluff_size >= r_probe.recommended_bluff_size


def test_weakness_score_stored():
    r = _vwd()
    assert 0 <= r.weakness_score <= 10


def test_fold_equity_stored():
    r = _vwd()
    assert 0 < r.adjusted_fold_equity < 1.0


def test_tips_populated():
    r = _vwd()
    assert len(r.tips) >= 2


def test_no_signals_still_has_tip():
    r = _vwd(weakness_signals=[])
    assert len(r.tips) >= 1


def test_semi_bluff_adds_extra_tip():
    r_air = _vwd(hero_hand_category='air')
    r_draw = _vwd(hero_hand_category='flush_draw')
    assert len(r_draw.tips) >= len(r_air.tips)


def test_one_liner_format():
    r = _vwd()
    line = vwd_one_liner(r)
    assert '[VWD' in line
    assert 'fold_eq=' in line
    assert 'ev=' in line


def test_verdict_contains_score():
    r = _vwd()
    assert 'score=' in r.verdict


def test_board_fold_equity_table():
    assert BOARD_FOLD_EQUITY['dry'] > BOARD_FOLD_EQUITY['wet']


def test_bluff_size_high_gt_medium():
    assert BLUFF_SIZE_BY_SCORE['high'] > BLUFF_SIZE_BY_SCORE['medium']


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
