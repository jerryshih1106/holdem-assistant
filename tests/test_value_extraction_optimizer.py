"""Tests for value_extraction_optimizer.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.value_extraction_optimizer import (
    analyze_value_extraction, ValueExtractionResult, veo_one_liner,
    _slowplay_score, _value_decision, _recommended_sizing, _spr_zone,
    HAND_STRENGTH_FOR_SLOWPLAY, BOARD_SLOWPLAY_PENALTY,
    VILLAIN_SLOWPLAY_MODIFIER, SLOWPLAY_SCORE_THRESHOLD,
)


def _veo(**kw):
    defaults = dict(
        hand_category='set', board_texture='dry', villain_type='reg',
        spr=8.0, hand_sdv=0.90,
    )
    defaults.update(kw)
    return analyze_value_extraction(**defaults)


def test_returns_result():
    assert isinstance(_veo(), ValueExtractionResult)


def test_nuts_eligible_for_slowplay():
    assert HAND_STRENGTH_FOR_SLOWPLAY['nuts'] is True


def test_top_pair_not_slowplay():
    assert HAND_STRENGTH_FOR_SLOWPLAY['top_pair_gk'] is False


def test_wet_board_penalizes_slowplay():
    wet = BOARD_SLOWPLAY_PENALTY['wet']
    dry = BOARD_SLOWPLAY_PENALTY['dry']
    assert wet < dry


def test_lag_increases_slowplay_score():
    lag = _slowplay_score('set', 'dry', 'lag', 8.0)
    reg = _slowplay_score('set', 'dry', 'reg', 8.0)
    assert lag > reg


def test_fish_reduces_slowplay():
    fish = _slowplay_score('set', 'dry', 'fish', 8.0)
    reg  = _slowplay_score('set', 'dry', 'reg',  8.0)
    assert fish < reg


def test_high_spr_increases_slowplay():
    low  = _slowplay_score('set', 'dry', 'reg', 1.0)
    high = _slowplay_score('set', 'dry', 'reg', 15.0)
    assert high > low


def test_wet_board_fast_play():
    score = _slowplay_score('set', 'wet', 'reg', 5.0)
    decision = _value_decision(score, 0.90, 'reg')
    assert 'FAST_PLAY' in decision or 'THIN' in decision or 'CHECK_CALL' in decision


def test_dry_board_lag_slowplay():
    score = _slowplay_score('set', 'dry', 'lag', 10.0)
    decision = _value_decision(score, 0.90, 'lag')
    assert 'SLOW_PLAY' in decision or 'FAST_PLAY' in decision


def test_sizing_zero_when_slowplay():
    r = _veo(hand_category='nuts', board_texture='dry', villain_type='lag', spr=12.0)
    if r.decision == 'SLOW_PLAY_CHECK':
        assert r.recommended_sizing == 0.0


def test_spr_zone_low():
    assert _spr_zone(1.5) == 'low'


def test_spr_zone_high():
    assert _spr_zone(10.0) == 'high'


def test_slowplay_score_in_range():
    r = _veo()
    assert 0.0 <= r.slowplay_score <= 1.0


def test_tips_populated():
    r = _veo()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _veo()
    line = veo_one_liner(r)
    assert '[VEO' in line and 'sp=' in line


def test_fish_tip():
    r = _veo(villain_type='fish')
    assert any('FISH' in t for t in r.tips)


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
