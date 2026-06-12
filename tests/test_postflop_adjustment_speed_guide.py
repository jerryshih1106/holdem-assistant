"""Tests for postflop_adjustment_speed_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.postflop_adjustment_speed_guide import (
    analyze_postflop_adjustment_speed, PostflopAdjustmentSpeedResult, pas_one_liner,
    _sample_category, _adjustment_magnitude, _exploit_recommendation,
    SAMPLE_SIZE_ADJUSTMENT_MAGNITUDE, VILLAIN_ADAPTATION_SPEED_MODIFIER,
    MAX_ADJUSTMENT_BY_VILLAIN, READ_TYPE_CONFIDENCE_MULTIPLIER,
)


def _pas(**kw):
    defaults = dict(n_observations=20, villain_type='reg', read_type='fold_to_cbet', read_confidence=0.70, current_deviation=0.10)
    defaults.update(kw)
    return analyze_postflop_adjustment_speed(**defaults)


def test_returns_result():
    assert isinstance(_pas(), PostflopAdjustmentSpeedResult)


def test_tiny_sample_category():
    assert _sample_category(5) == 'tiny'


def test_large_sample_category():
    assert _sample_category(65) == 'large'


def test_confident_sample():
    assert _sample_category(200) == 'confident'


def test_more_observations_more_adjustment():
    small = _adjustment_magnitude(10, 'reg', 'fold_to_cbet', 0.70)
    large = _adjustment_magnitude(80, 'reg', 'fold_to_cbet', 0.70)
    assert large > small


def test_fish_adjusts_faster():
    fish = _adjustment_magnitude(30, 'fish', 'fold_to_cbet', 0.70)
    lag  = _adjustment_magnitude(30, 'lag',  'fold_to_cbet', 0.70)
    assert fish > lag


def test_showdown_higher_mult():
    sd  = READ_TYPE_CONFIDENCE_MULTIPLIER['showdown_tendency']
    tim = READ_TYPE_CONFIDENCE_MULTIPLIER['timing_tell']
    assert sd > tim


def test_lag_max_lower_than_fish():
    lag  = MAX_ADJUSTMENT_BY_VILLAIN['lag']
    fish = MAX_ADJUSTMENT_BY_VILLAIN['fish']
    assert lag < fish


def test_stay_gto_tiny_sample():
    rec = _exploit_recommendation(0.03, 0.70)
    assert rec == 'STAY_GTO_INSUFFICIENT_DATA'


def test_strong_exploit_large_magnitude():
    rec = _exploit_recommendation(0.25, 0.80)
    assert rec == 'STRONG_EXPLOIT_HIGH_CONFIDENCE'


def test_adjustment_capped_at_max():
    adj = _adjustment_magnitude(200, 'lag', 'fold_to_cbet', 1.0)
    assert adj <= MAX_ADJUSTMENT_BY_VILLAIN['lag']


def test_adjustment_floored_at_zero():
    adj = _adjustment_magnitude(5, 'reg', 'timing_tell', 0.10)
    assert adj >= 0.0


def test_exploit_rec_stored():
    r = _pas()
    assert r.exploit_recommendation in (
        'STAY_GTO_INSUFFICIENT_DATA',
        'SMALL_EXPLOIT_TENTATIVE',
        'MODERATE_EXPLOIT',
        'STRONG_EXPLOIT_HIGH_CONFIDENCE',
    )


def test_max_allowed_stored():
    r = _pas(villain_type='lag')
    assert r.max_allowed_magnitude == MAX_ADJUSTMENT_BY_VILLAIN['lag']


def test_tips_populated():
    r = _pas()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _pas()
    line = pas_one_liner(r)
    assert '[PAS' in line and 'adj=' in line


def test_small_sample_tip():
    r = _pas(n_observations=5)
    assert any('SMALL' in t or 'data' in t.lower() or 'GTO' in t for t in r.tips)


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
