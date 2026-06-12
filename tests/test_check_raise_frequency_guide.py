"""Tests for check_raise_frequency_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.check_raise_frequency_guide import (
    analyze_check_raise_frequency, CheckRaiseFrequencyResult, crf_one_liner,
    _cr_frequency, _cr_sizing, _cr_hand_category, _cbet_size_category,
    BASELINE_CR_FREQ, VILLAIN_CR_ADJUSTMENT, STREET_CR_MODIFIER,
    VALUE_CR_THRESHOLD, SEMI_BLUFF_CR_THRESHOLD,
)


def _crf(**kw):
    defaults = dict(
        board_texture='wet', villain_type='reg', street='flop',
        villain_cbet_tendency='medium', cbet_frac=0.50, pot_bb=20.0,
        hand_sdv=0.70, has_draw=False,
    )
    defaults.update(kw)
    return analyze_check_raise_frequency(**defaults)


def test_returns_result():
    assert isinstance(_crf(), CheckRaiseFrequencyResult)


def test_wet_higher_than_dry():
    wet = BASELINE_CR_FREQ['wet']
    dry = BASELINE_CR_FREQ['dry']
    assert wet > dry


def test_lag_increases_cr_freq():
    lag = _cr_frequency('wet', 'lag', 'flop', 'medium')
    reg = _cr_frequency('wet', 'reg', 'flop', 'medium')
    assert lag > reg


def test_fish_decreases_cr_freq():
    fish = _cr_frequency('wet', 'fish', 'flop', 'medium')
    reg  = _cr_frequency('wet', 'reg',  'flop', 'medium')
    assert fish < reg


def test_high_cbet_tendency_increases_cr():
    high = _cr_frequency('wet', 'reg', 'flop', 'very_high')
    low  = _cr_frequency('wet', 'reg', 'flop', 'very_low')
    assert high > low


def test_river_lower_freq_than_flop():
    flop  = _cr_frequency('wet', 'reg', 'flop', 'medium')
    river = _cr_frequency('wet', 'reg', 'river', 'medium')
    assert river < flop


def test_small_cbet_large_sizing():
    size_cat = _cbet_size_category(0.25)
    assert size_cat == 'small_cbet'


def test_cr_sizing_positive():
    size = _cr_sizing(0.50, 20.0)
    assert size > 0


def test_value_cr_high_sdv():
    cat = _cr_hand_category(0.80, False)
    assert cat == 'VALUE_CR'


def test_semi_bluff_cr_draw():
    cat = _cr_hand_category(0.50, True)
    assert cat in ('SEMI_BLUFF_CR', 'VALUE_CR_THIN')


def test_no_cr_weak_hand():
    cat = _cr_hand_category(0.30, False)
    assert cat == 'DO_NOT_CR'


def test_cr_freq_in_range():
    r = _crf()
    assert 0.03 <= r.cr_frequency <= 0.40


def test_tips_populated():
    r = _crf()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _crf()
    line = crf_one_liner(r)
    assert '[CRF' in line and 'cr_freq=' in line


def test_lag_tip():
    r = _crf(villain_type='lag')
    assert any('LAG' in t for t in r.tips)


def test_fish_tip():
    r = _crf(villain_type='fish')
    assert any('FISH' in t or 'fish' in t.lower() for t in r.tips)


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
