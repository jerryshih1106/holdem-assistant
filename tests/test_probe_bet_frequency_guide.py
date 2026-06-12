"""Tests for probe_bet_frequency_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.probe_bet_frequency_guide import (
    analyze_probe_bet_frequency, ProbeBetFrequencyResult, pbfg_one_liner,
    _optimal_probe_freq, _probe_decision, _probe_status,
    BASELINE_PROBE_FREQ_BY_STREET, BOARD_TEXTURE_PROBE_ADJ,
    VILLAIN_IP_PROBE_MODIFIER, TURN_CARD_PROBE_ADJ,
)


def _pbf(**kw):
    defaults = dict(
        street='turn', board_texture='semi_wet', turn_card='medium',
        villain_type='reg', hand_sdv=0.45, has_draw=False, actual_probe_freq=0.50,
    )
    defaults.update(kw)
    return analyze_probe_bet_frequency(**defaults)


def test_returns_result():
    assert isinstance(_pbf(), ProbeBetFrequencyResult)


def test_turn_baseline_higher_than_river():
    assert BASELINE_PROBE_FREQ_BY_STREET['turn'] > BASELINE_PROBE_FREQ_BY_STREET['river']


def test_dry_board_probes_more():
    dry = _optimal_probe_freq('turn', 'dry', 'brick', 'reg')
    wet = _optimal_probe_freq('turn', 'wet', 'medium', 'reg')
    assert dry > wet


def test_brick_turn_probes_more():
    brick = _optimal_probe_freq('turn', 'semi_wet', 'brick', 'reg')
    scare = _optimal_probe_freq('turn', 'semi_wet', 'scare_card', 'reg')
    assert brick > scare


def test_nit_probes_more():
    nit  = _optimal_probe_freq('turn', 'semi_wet', 'medium', 'nit')
    fish = _optimal_probe_freq('turn', 'semi_wet', 'medium', 'fish')
    assert nit > fish


def test_flush_complete_reduces_probe():
    brick   = TURN_CARD_PROBE_ADJ['brick']
    flush_c = TURN_CARD_PROBE_ADJ['flush_complete']
    assert brick > flush_c


def test_probe_value_bet_high_sdv():
    decision = _probe_decision(0.60, 0.80, False)
    assert decision == 'PROBE_VALUE_BET'


def test_probe_semi_bluff_with_draw():
    decision = _probe_decision(0.60, 0.30, True)
    assert decision == 'PROBE_SEMI_BLUFF'


def test_check_back_low_freq_medium_sdv():
    decision = _probe_decision(0.40, 0.50, False)
    assert decision == 'CHECK_BACK_POT_CONTROL'


def test_over_probing_detected():
    status = _probe_status(0.80, 0.50)
    assert 'OVER' in status


def test_under_probing_detected():
    status = _probe_status(0.20, 0.60)
    assert 'UNDER' in status


def test_ok_status():
    status = _probe_status(0.55, 0.55)
    assert status == 'PROBE_FREQUENCY_OK'


def test_optimal_capped():
    r = _pbf(board_texture='dry', turn_card='brick', villain_type='nit')
    assert r.optimal_probe_freq <= 0.82


def test_optimal_floored():
    r = _pbf(board_texture='wet', turn_card='flush_complete', villain_type='fish')
    assert r.optimal_probe_freq >= 0.15


def test_draw_tip_present():
    r = _pbf(has_draw=True)
    assert any('draw' in t.lower() or 'SEMI_BLUFF' in t for t in r.tips)


def test_tips_populated():
    r = _pbf()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _pbf()
    line = pbfg_one_liner(r)
    assert '[PROBE' in line and 'optimal=' in line


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
