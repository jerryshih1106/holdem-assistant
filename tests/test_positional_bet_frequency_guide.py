"""Tests for positional_bet_frequency_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.positional_bet_frequency_guide import (
    analyze_positional_bet_frequency, PositionalBetFrequencyResult, pbf_one_liner,
    _bet_frequency, _bet_frequency_label,
    BASELINE_BET_FREQ, BOARD_TEXTURE_FREQ_ADJ, VILLAIN_FREQ_ADJ, MULTIWAY_FREQ_ADJ,
    POSITION_IP_OOP,
)


def _pbf(**kw):
    defaults = dict(
        position='btn', street='flop',
        board_texture='semi_wet', villain_type='reg', extra_opponents=0,
    )
    defaults.update(kw)
    return analyze_positional_bet_frequency(**defaults)


def test_returns_result():
    assert isinstance(_pbf(), PositionalBetFrequencyResult)


def test_btn_higher_than_utg_flop():
    btn = BASELINE_BET_FREQ['btn']['flop']
    utg = BASELINE_BET_FREQ['utg']['flop']
    assert btn > utg


def test_dry_board_higher_freq():
    dry = _bet_frequency('btn', 'flop', 'dry', 'reg', 0)
    wet = _bet_frequency('btn', 'flop', 'wet', 'reg', 0)
    assert dry > wet


def test_fish_higher_freq():
    fish = _bet_frequency('btn', 'flop', 'semi_wet', 'fish', 0)
    nit  = _bet_frequency('btn', 'flop', 'semi_wet', 'nit', 0)
    assert fish > nit


def test_multiway_reduces_freq():
    hu  = _bet_frequency('btn', 'flop', 'semi_wet', 'reg', 0)
    mw4 = _bet_frequency('btn', 'flop', 'semi_wet', 'reg', 3)
    assert mw4 < hu


def test_monotone_lowest_texture_freq():
    mono = BOARD_TEXTURE_FREQ_ADJ['monotone']
    dry  = BOARD_TEXTURE_FREQ_ADJ['dry']
    assert mono < dry


def test_fish_positive_adjustment():
    assert VILLAIN_FREQ_ADJ['fish'] > 0


def test_nit_negative_adjustment():
    assert VILLAIN_FREQ_ADJ['nit'] < 0


def test_sb_is_oop():
    assert POSITION_IP_OOP['sb'] == 'oop'


def test_btn_is_ip():
    assert POSITION_IP_OOP['btn'] == 'ip'


def test_freq_label_high():
    assert 'HIGH' in _bet_frequency_label(0.75)


def test_freq_label_low():
    assert 'LOW' in _bet_frequency_label(0.20)


def test_freq_in_range():
    r = _pbf()
    assert 0.10 <= r.adjusted_freq <= 0.85


def test_tips_populated():
    r = _pbf()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _pbf()
    line = pbf_one_liner(r)
    assert '[PBF' in line and 'bet=' in line


def test_multiway_tip():
    r = _pbf(extra_opponents=2)
    assert any('MULTIWAY' in t or 'player' in t.lower() for t in r.tips)


def test_fish_tip():
    r = _pbf(villain_type='fish')
    assert any('FISH' in t for t in r.tips)


def test_nit_tip():
    r = _pbf(villain_type='nit')
    assert any('NIT' in t for t in r.tips)


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
