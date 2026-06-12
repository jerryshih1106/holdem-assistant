"""Tests for river_check_fold_range_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.river_check_fold_range_guide import (
    analyze_river_check_fold, RiverCheckFoldResult, rcf_one_liner,
    _mdf_for_bet, _check_fold_threshold, _hand_sdv, _check_fold_frequency,
    CHECK_FOLD_SDV_THRESHOLD, HAND_SDV_ESTIMATE,
)


def _rcf(**kw):
    defaults = dict(
        villain_type='reg', hand_strength='missed_flush_draw',
        pot_bb=20.0, villain_bet_frac=0.60,
        blocker_score=3, hero_range_sdv_distribution=0.50,
    )
    defaults.update(kw)
    return analyze_river_check_fold(**defaults)


def test_returns_result():
    assert isinstance(_rcf(), RiverCheckFoldResult)


def test_mdf_halfpot():
    mdf = _mdf_for_bet(0.50)
    assert abs(mdf - (1.0/1.5)) < 0.01


def test_mdf_fullpot():
    mdf = _mdf_for_bet(1.00)
    assert abs(mdf - 0.50) < 0.01


def test_nit_higher_threshold():
    nit_t = _check_fold_threshold('nit')
    lag_t = _check_fold_threshold('lag')
    assert nit_t > lag_t


def test_missed_draw_low_sdv():
    sdv = _hand_sdv('missed_flush_draw')
    assert sdv <= 0.10


def test_set_high_sdv():
    sdv = _hand_sdv('set')
    assert sdv >= 0.85


def test_check_fold_freq_in_range():
    freq = _check_fold_frequency('reg')
    assert 0 < freq < 1


def test_missed_draw_should_check_fold():
    r = _rcf(hand_strength='missed_flush_draw')
    assert r.should_check_fold is True


def test_top_pair_gk_not_check_fold():
    r = _rcf(hand_strength='top_pair_gk')
    assert r.should_check_fold is False


def test_action_check_fold_for_air():
    r = _rcf(hand_strength='air')
    assert r.recommended_action in ('CHECK_FOLD', 'CONSIDER_LEAD_BLUFF')


def test_action_check_call_for_top_pair():
    r = _rcf(hand_strength='top_pair_gk')
    assert r.recommended_action in ('CHECK_CALL', 'CHECK_CALL_BORDERLINE')


def test_strong_blockers_suggests_bluff():
    r = _rcf(hand_strength='air', blocker_score=8)
    assert r.recommended_action in ('CONSIDER_LEAD_BLUFF', 'CHECK_FOLD')


def test_mdf_stored():
    r = _rcf()
    assert 0 < r.mdf < 1


def test_tips_populated():
    r = _rcf()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _rcf()
    line = rcf_one_liner(r)
    assert '[RCF' in line and 'SDV=' in line


def test_sdv_stored_correctly():
    r = _rcf(hand_strength='bottom_pair')
    expected = HAND_SDV_ESTIMATE['bottom_pair']
    assert abs(r.hand_sdv - expected) < 0.01


def test_all_hands_have_sdv():
    for h, s in HAND_SDV_ESTIMATE.items():
        assert 0 <= s <= 1


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
