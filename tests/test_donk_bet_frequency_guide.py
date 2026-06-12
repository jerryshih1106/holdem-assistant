"""Tests for donk_bet_frequency_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.donk_bet_frequency_guide import (
    analyze_donk_bet_frequency, DonkBetFrequencyResult, dbf_one_liner,
    _base_donk_freq, _optimal_donk_freq, _donk_size_pct, _donk_size_bb,
    _donk_decision, FLOP_DONK_FREQ_BY_TEXTURE, VILLAIN_DONK_MODIFIER,
)


def _dbf(**kw):
    defaults = dict(street='turn', board_texture='brick', villain_type='reg', pot_bb=8.0)
    defaults.update(kw)
    return analyze_donk_bet_frequency(**defaults)


def test_returns_result():
    assert isinstance(_dbf(), DonkBetFrequencyResult)


def test_wet_flop_higher_than_dry():
    wet = _base_donk_freq('flop', 'wet')
    dry = _base_donk_freq('flop', 'dry')
    assert wet > dry


def test_turn_higher_than_flop():
    turn = _base_donk_freq('turn', 'brick')
    flop = _base_donk_freq('flop', 'dry')
    assert turn > flop


def test_river_higher_than_flop():
    river = _base_donk_freq('river', 'blank')
    flop = _base_donk_freq('flop', 'dry')
    assert river > flop


def test_nit_increases_freq():
    nit = _optimal_donk_freq('turn', 'brick', 'nit')
    reg = _optimal_donk_freq('turn', 'brick', 'reg')
    assert nit > reg


def test_lag_decreases_freq():
    lag = _optimal_donk_freq('turn', 'brick', 'lag')
    reg = _optimal_donk_freq('turn', 'brick', 'reg')
    assert lag < reg


def test_fish_decreases_freq():
    assert VILLAIN_DONK_MODIFIER['fish'] < 0


def test_scare_card_high_freq():
    scare = _base_donk_freq('turn', 'ace_king')
    brick = _base_donk_freq('turn', 'brick')
    assert scare > brick


def test_donk_size_turn_larger_than_flop():
    turn = _donk_size_pct('turn', 'semi_wet')
    flop = _donk_size_pct('flop', 'semi_wet')
    assert turn > flop


def test_wet_board_larger_size():
    wet = _donk_size_pct('flop', 'wet')
    dry = _donk_size_pct('flop', 'dry')
    assert wet > dry


def test_donk_size_bb_computed():
    size = _donk_size_bb(10.0, 'turn', 'brick')
    assert size > 0


def test_high_freq_decision():
    assert _donk_decision(0.45) == 'HIGH_FREQ_DONK'


def test_avoid_donk_decision():
    assert _donk_decision(0.02) == 'AVOID_DONK'


def test_tips_populated():
    r = _dbf()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _dbf()
    line = dbf_one_liner(r)
    assert '[DONK' in line and 'freq=' in line


def test_draw_complete_river_high():
    r = _dbf(street='river', board_texture='draw_complete')
    assert r.optimal_donk_freq >= 0.35


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
