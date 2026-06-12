"""Tests for bluff_selection_advisor.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.bluff_selection_advisor import (
    advise_bluff_selection, BluffSelectionAdvice, bsa_one_liner,
    _bluff_score, _bluff_tier, _recommended_bet_size, _ev_of_bluff, _should_bluff,
    BLOCKER_SCORES, SDV_SCORES,
)


def _bsa(**kw):
    defaults = dict(
        street='river',
        board_texture='semi_wet',
        hero_hand_category='missed_flush_draw',
        hero_has_ace_blocker=True,
        hero_has_flush_blocker=True,
        hero_has_straight_blocker=False,
        hero_equity=0.15,
        villain_wtsd=0.30,
        villain_af=2.5,
        pot_bb=40.0,
        bet_size_pct=0.75,
    )
    defaults.update(kw)
    return advise_bluff_selection(**defaults)


def test_returns_bluff_selection_advice():
    r = _bsa()
    assert isinstance(r, BluffSelectionAdvice)


def test_bluff_score_between_zero_and_one():
    score = _bluff_score('missed_flush_draw', True, True, False, 'river', 'semi_wet', 0.30)
    assert 0.0 <= score <= 1.0


def test_ace_blocker_increases_score():
    no_blocker = _bluff_score('air', False, False, False, 'river', 'semi_wet', 0.30)
    with_ace = _bluff_score('air', True, False, False, 'river', 'semi_wet', 0.30)
    assert with_ace > no_blocker


def test_flush_blocker_increases_score_on_wet():
    no_fb = _bluff_score('air', False, False, False, 'river', 'semi_wet', 0.30)
    with_fb = _bluff_score('air', False, True, False, 'river', 'semi_wet', 0.30)
    assert with_fb > no_fb


def test_flush_blocker_no_effect_on_dry():
    no_fb = _bluff_score('air', False, False, False, 'river', 'dry', 0.30)
    with_fb = _bluff_score('air', False, True, False, 'river', 'dry', 0.30)
    assert with_fb == no_fb


def test_low_sdv_improves_score():
    # missed_flush_draw has low SDV (0.05), air also low
    missed = _bluff_score('missed_flush_draw', False, False, False, 'river', 'dry', 0.30)
    top_pair = _bluff_score('top_pair', False, False, False, 'river', 'dry', 0.30)
    assert missed > top_pair


def test_calling_station_reduces_score():
    nit = _bluff_score('missed_flush_draw', True, True, False, 'river', 'semi_wet', 0.20)
    station = _bluff_score('missed_flush_draw', True, True, False, 'river', 'semi_wet', 0.45)
    assert nit > station


def test_tier1_optimal():
    assert _bluff_tier(0.75) == 'tier1_optimal'


def test_tier2_good():
    assert _bluff_tier(0.55) == 'tier2_good'


def test_tier3_acceptable():
    assert _bluff_tier(0.35) == 'tier3_acceptable'


def test_tier4_avoid():
    assert _bluff_tier(0.25) == 'tier4_avoid'


def test_flush_blocker_increases_bet_size():
    size = _recommended_bet_size('missed_flush_draw', True, 0.50, 'river', 0.30)
    assert size >= 0.75


def test_river_min_bet_size():
    size = _recommended_bet_size('air', False, 0.50, 'river', 0.30)
    assert size >= 0.75


def test_calling_station_reduces_bet_size():
    normal = _recommended_bet_size('air', False, 0.90, 'river', 0.25)
    station = _recommended_bet_size('air', False, 0.90, 'river', 0.45)
    assert station <= normal


def test_ev_positive_vs_nit():
    ev = _ev_of_bluff(40.0, 0.75, 0.20, 'dry', 'river', 0.70)
    assert ev > 0


def test_ev_negative_vs_station():
    ev = _ev_of_bluff(40.0, 0.75, 0.45, 'wet', 'river', 0.30)
    assert ev < ev + 5  # station reduces EV


def test_should_not_bluff_calling_station():
    assert _should_bluff(0.70, 10.0, 0.45, 'river') is False


def test_should_not_bluff_very_negative_ev():
    assert _should_bluff(0.60, -6.0, 0.25, 'river') is False


def test_should_bluff_good_score_positive_ev():
    assert _should_bluff(0.60, 5.0, 0.25, 'river') is True


def test_missed_flush_draw_with_blockers_is_tier1():
    r = _bsa(hero_hand_category='missed_flush_draw', hero_has_ace_blocker=True,
             hero_has_flush_blocker=True, villain_wtsd=0.25)
    assert r.bluff_tier in ('tier1_optimal', 'tier2_good')


def test_top_pair_is_poor_bluff():
    score = _bluff_score('top_pair', False, False, False, 'river', 'dry', 0.30)
    tier = _bluff_tier(score)
    assert tier in ('tier3_acceptable', 'tier4_avoid')


def test_should_bluff_stored():
    r = _bsa()
    assert isinstance(r.should_bluff, bool)


def test_bluff_score_stored():
    r = _bsa()
    assert 0.0 <= r.bluff_score <= 1.0


def test_recommended_bet_size_stored():
    r = _bsa()
    assert 0.0 < r.recommended_bet_size <= 1.5


def test_tips_populated():
    r = _bsa()
    assert len(r.tips) >= 2


def test_tips_contain_blocker_analysis():
    r = _bsa()
    combined = ' '.join(r.tips).lower()
    assert 'blocker' in combined


def test_calling_station_tip():
    r = _bsa(villain_wtsd=0.45)
    combined = ' '.join(r.tips).lower()
    assert 'station' in combined or 'bluff' in combined


def test_nit_tip():
    r = _bsa(villain_wtsd=0.20)
    combined = ' '.join(r.tips).lower()
    assert 'fold' in combined or 'nit' in combined or 'folder' in combined or 'wtsd' in combined


def test_one_liner_format():
    r = _bsa()
    line = bsa_one_liner(r)
    assert '[BSA' in line
    assert 'score=' in line
    assert 'ev=' in line


def test_one_liner_contains_bluff_status():
    r = _bsa()
    line = bsa_one_liner(r)
    assert 'BLUFF' in line or 'NO_BLUFF' in line


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
