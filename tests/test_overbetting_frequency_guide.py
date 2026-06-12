"""Tests for overbetting_frequency_guide.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.overbetting_frequency_guide import (
    guide_overbet, OverbetGuide, obg_one_liner,
    _alpha, _overbet_frequency, _recommended_overbet_size,
    _should_overbet, _overbet_rationale,
    BASE_OVERBET_FREQ, OVERBET_SIZE_BY_NUT,
)


def _obg(**kw):
    defaults = dict(
        street='river',
        hero_hand_category='nuts',
        hero_position='ip',
        hero_role='pfr',
        board_texture='dry',
        nut_advantage='dominant',
        villain_wtsd=0.28,
        spr=4.0,
        pot_bb=40.0,
        villain_af=2.2,
    )
    defaults.update(kw)
    return guide_overbet(**defaults)


def test_returns_overbet_guide():
    r = _obg()
    assert isinstance(r, OverbetGuide)


def test_alpha_calculation():
    assert abs(_alpha(1.0) - 0.50) < 0.001   # 100% pot: alpha=0.5
    assert abs(_alpha(1.5) - 0.60) < 0.001   # 150% pot: alpha=0.6


def test_alpha_increases_with_bet():
    assert _alpha(0.75) < _alpha(1.50) < _alpha(2.0)


def test_dominant_river_high_freq():
    freq = _overbet_frequency('river', 'dominant', 'nuts', 0.25, 4.0, 'ip')
    assert freq >= 0.30


def test_none_nut_advantage_low_freq():
    freq = _overbet_frequency('river', 'none', 'top_pair', 0.28, 4.0, 'ip')
    assert freq <= 0.10


def test_calling_station_reduces_freq():
    normal = _overbet_frequency('river', 'dominant', 'nuts', 0.28, 4.0, 'ip')
    station = _overbet_frequency('river', 'dominant', 'nuts', 0.45, 4.0, 'ip')
    assert station < normal


def test_low_spr_zero_freq():
    freq = _overbet_frequency('river', 'dominant', 'nuts', 0.28, 1.0, 'ip')
    assert freq == 0.0


def test_dominant_size_gt_pot():
    size = _recommended_overbet_size('dominant', 'river', 'nuts', 0.25)
    assert size >= 1.25


def test_none_size_is_zero():
    size = _recommended_overbet_size('none', 'river', 'top_pair', 0.28)
    assert size == 0.0


def test_should_overbet_dominant():
    assert _should_overbet(0.40, 'dominant', 0.28, 4.0) is True


def test_should_not_overbet_station():
    assert _should_overbet(0.40, 'dominant', 0.50, 4.0) is False


def test_should_not_overbet_low_spr():
    assert _should_overbet(0.40, 'dominant', 0.28, 1.0) is False


def test_should_not_overbet_no_advantage():
    assert _should_overbet(0.05, 'none', 0.28, 4.0) is False


def test_nuts_on_river_dominant_should_overbet():
    r = _obg(hero_hand_category='nuts', nut_advantage='dominant', street='river')
    assert r.should_overbet is True


def test_no_nut_advantage_no_overbet():
    r = _obg(nut_advantage='none', hero_hand_category='top_pair')
    assert r.should_overbet is False


def test_calling_station_no_overbet():
    r = _obg(villain_wtsd=0.50)
    assert r.should_overbet is False


def test_overbet_freq_stored():
    r = _obg()
    assert 0.0 <= r.overbet_frequency <= 0.80


def test_recommended_size_stored():
    r = _obg()
    assert r.recommended_size >= 0.0


def test_alpha_stored():
    r = _obg()
    assert 0.0 <= r.required_villain_equity <= 1.0


def test_tips_populated():
    r = _obg()
    assert len(r.tips) >= 2


def test_calling_station_warning_tip():
    r = _obg(villain_wtsd=0.42)
    combined = ' '.join(r.tips).lower()
    assert 'station' in combined or 'wtsd' in combined or 'call' in combined


def test_low_spr_tip():
    r = _obg(spr=1.5)
    combined = ' '.join(r.tips).lower()
    assert 'spr' in combined or 'low' in combined or 'shov' in combined


def test_no_nut_advantage_tip():
    r = _obg(nut_advantage='none', hero_hand_category='top_pair')
    combined = ' '.join(r.tips).lower()
    assert 'nut' in combined or 'advantage' in combined or 'standard' in combined


def test_one_liner_format():
    r = _obg()
    line = obg_one_liner(r)
    assert '[OBG' in line
    assert 'freq=' in line
    assert 'alpha=' in line


def test_one_liner_overbet_or_no():
    r = _obg()
    line = obg_one_liner(r)
    assert 'OVERBET' in line or 'NO_OVERBET' in line


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
