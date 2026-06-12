"""Tests for pot_control_sizing_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.pot_control_sizing_guide import (
    analyze_pot_control_sizing, PotControlSizingResult, pcs_one_liner,
    _spr_category, _pot_control_needed, _optimal_pc_size, _pot_control_decision,
    POT_CONTROL_TRIGGER_SDV_RANGE, BOARD_POT_CONTROL_MODIFIER, SPR_CATEGORY_THRESHOLDS,
)


def _pcs(**kw):
    defaults = dict(hand_sdv=0.52, street='flop', board_texture='semi_wet', position='ip', spr=8.0, pot_bb=12.0)
    defaults.update(kw)
    return analyze_pot_control_sizing(**defaults)


def test_returns_result():
    assert isinstance(_pcs(), PotControlSizingResult)


def test_deep_spr_category():
    assert _spr_category(10.0) == 'deep'


def test_committed_spr_category():
    assert _spr_category(1.0) == 'committed'


def test_medium_sdv_needs_pc():
    assert _pot_control_needed(0.52, 8.0, 'ip', 'semi_wet') is True


def test_strong_sdv_no_pc_needed():
    assert _pot_control_needed(0.80, 8.0, 'ip', 'semi_wet') is False


def test_low_sdv_no_pc_needed():
    assert _pot_control_needed(0.20, 8.0, 'ip', 'semi_wet') is False


def test_wet_board_increases_pc_size():
    wet = _optimal_pc_size('flop', 'wet', 8.0, 'oop')
    dry = _optimal_pc_size('flop', 'dry', 8.0, 'oop')
    assert wet > dry


def test_ip_returns_zero_size():
    size = _optimal_pc_size('flop', 'semi_wet', 8.0, 'ip')
    assert size == 0.0


def test_check_back_ip():
    dec = _pot_control_decision(0.52, 8.0, 'ip', 'semi_wet')
    assert dec == 'CHECK_BACK_POT_CONTROL'


def test_small_bet_oop():
    dec = _pot_control_decision(0.52, 8.0, 'oop', 'semi_wet')
    assert dec == 'SMALL_BET_POT_CONTROL'


def test_value_bet_strong_hand():
    dec = _pot_control_decision(0.80, 8.0, 'ip', 'semi_wet')
    assert dec == 'VALUE_BET_FULL'


def test_pc_size_zero_ip():
    r = _pcs(position='ip')
    assert r.pc_size_pct == 0.0


def test_pc_size_positive_oop():
    r = _pcs(position='oop')
    assert r.pc_size_pct > 0.0


def test_tips_populated():
    r = _pcs()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _pcs()
    line = pcs_one_liner(r)
    assert '[PCS' in line and 'SDV=' in line


def test_spr_category_stored():
    r = _pcs(spr=8.0)
    assert r.spr_category in ('deep', 'medium', 'very_deep')


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
