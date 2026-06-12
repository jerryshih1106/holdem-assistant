"""Tests for villain_sizing_tell_analyzer.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.villain_sizing_tell_analyzer import (
    analyze_sizing_tell, SizingTellResult, sta_one_liner,
    _size_category, _detect_pattern,
    SIZE_RANGE_IMPLICATION, TELL_CONFIDENCE, MULTI_STREET_PATTERNS,
)


def _sta(**kw):
    defaults = dict(
        current_bet_frac=0.67, betting_history=[], villain_type='rec',
        street='river', pot_bb=20.0,
    )
    defaults.update(kw)
    return analyze_sizing_tell(**defaults)


def test_returns_sizing_tell_result():
    assert isinstance(_sta(), SizingTellResult)


def test_min_bet_category():
    assert _size_category(0.15) == 'min_bet'


def test_small_category():
    assert _size_category(0.35) == 'small'


def test_standard_category():
    assert _size_category(0.67) == 'standard'


def test_overbet_category():
    assert _size_category(1.25) == 'overbet'


def test_overbet_after_small_pattern():
    pattern = _detect_pattern([0.30, 0.25, 1.50])
    assert pattern == 'overbet_after_small'


def test_increasing_pattern():
    pattern = _detect_pattern([0.33, 0.55, 0.90])
    assert pattern == 'increasing'


def test_decreasing_pattern():
    pattern = _detect_pattern([0.90, 0.60, 0.33])
    assert pattern == 'decreasing'


def test_consistent_large_pattern():
    pattern = _detect_pattern([0.75, 0.80, 0.70])
    assert pattern == 'consistent_large'


def test_min_all_pattern():
    pattern = _detect_pattern([0.20, 0.15, 0.18])
    assert pattern == 'min_all'


def test_fish_higher_confidence():
    fish_conf = TELL_CONFIDENCE.get('fish', 0.0)
    lag_conf = TELL_CONFIDENCE.get('lag', 0.0)
    assert fish_conf > lag_conf


def test_size_category_stored():
    r = _sta()
    assert r.size_category in SIZE_RANGE_IMPLICATION


def test_adjusted_confidence_in_range():
    r = _sta()
    assert 0 < r.adjusted_confidence <= 1.0


def test_tips_populated():
    r = _sta()
    assert len(r.tips) >= 1


def test_one_liner_format():
    r = _sta()
    line = sta_one_liner(r)
    assert '[STA' in line
    assert 'conf=' in line


def test_min_bet_generates_raise_tip():
    r = _sta(current_bet_frac=0.15)
    assert any('RAISE' in t or 'min' in t.lower() or 'blocking' in t.lower() for t in r.tips)


def test_overbet_generates_polarized_tip():
    r = _sta(current_bet_frac=1.25)
    assert any('overbet' in t.lower() or 'OVERBET' in t or 'polar' in t.lower() for t in r.tips)


def test_lag_warns_about_unreliable():
    r = _sta(villain_type='lag')
    assert any('unreliable' in t.lower() or 'WARNING' in t for t in r.tips)


def test_history_affects_pattern():
    r_no_hist = _sta(betting_history=[])
    r_with_hist = _sta(betting_history=[0.30, 0.25], current_bet_frac=1.50)
    assert r_with_hist.pattern != r_no_hist.pattern


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
