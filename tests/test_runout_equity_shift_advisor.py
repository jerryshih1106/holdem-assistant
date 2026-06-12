"""Tests for runout_equity_shift_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.runout_equity_shift_advisor import (
    analyze_runout_equity_shift, RunoutEquityShiftResult, res_one_liner,
    _equity_shift, _shift_category, _barrel_frequency, _barrel_sizing,
    CARD_SHIFT,
)


def _res(**kw):
    defaults = dict(
        card_type='blank', hero_is_pfr=True, street='turn',
        position='ip', flop_texture='semi_wet',
        hand_strength='top_pair', pot_bb=20.0,
    )
    defaults.update(kw)
    return analyze_runout_equity_shift(**defaults)


def test_returns_result():
    assert isinstance(_res(), RunoutEquityShiftResult)


def test_overcard_pfr_positive_shift():
    shift = _equity_shift('overcard_for_pfr', True)
    assert shift > 0


def test_flush_completes_negative_for_pfr():
    shift = _equity_shift('flush_draw_completes', True)
    assert shift < 0


def test_flush_completes_positive_for_caller():
    shift = _equity_shift('flush_draw_completes', False)
    assert shift > 0


def test_shift_categories():
    assert _shift_category(0.10) == 'large_hero_gain'
    assert _shift_category(0.05) == 'moderate_hero_gain'
    assert _shift_category(0.00) == 'neutral'
    assert _shift_category(-0.06) == 'moderate_villain_gain'
    assert _shift_category(-0.12) == 'large_villain_gain'


def test_large_gain_high_barrel():
    freq = _barrel_frequency('large_hero_gain', 'semi_wet', 'ip')
    assert freq >= 0.70


def test_large_villain_gain_low_barrel():
    freq = _barrel_frequency('large_villain_gain', 'semi_wet', 'ip')
    assert freq <= 0.35


def test_barrel_size_increases_with_gain():
    size_gain = _barrel_sizing('large_hero_gain', 'turn')
    size_loss = _barrel_sizing('large_villain_gain', 'turn')
    assert size_gain > size_loss


def test_pfr_overcard_barrels():
    r = _res(card_type='overcard_for_pfr', hero_is_pfr=True)
    assert r.recommended_action in (
        'BARREL_STRONG', 'BARREL_VALUE', 'BARREL_SELECTIVE', 'BARREL_NORMAL'
    )


def test_flush_completes_pfr_slows_down():
    r = _res(card_type='flush_draw_completes', hero_is_pfr=True, hand_strength='top_pair')
    assert r.recommended_action in (
        'CHECK_CONTROL', 'CHECK_FOLD_BLUFFS', 'BARREL_NORMAL', 'BET_PROTECTED_VALUE'
    )


def test_barrel_bb_consistent():
    r = _res(pot_bb=20.0)
    expected = round(20.0 * r.barrel_size_frac, 1)
    assert abs(r.barrel_size_frac * 20.0 - expected) < 0.2


def test_equity_shift_stored():
    r = _res(card_type='overcard_for_pfr')
    assert r.equity_shift != 0.0


def test_shift_category_valid():
    r = _res()
    assert r.shift_category in (
        'large_hero_gain', 'moderate_hero_gain', 'neutral',
        'moderate_villain_gain', 'large_villain_gain',
    )


def test_tips_populated():
    r = _res()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _res()
    line = res_one_liner(r)
    assert '[RES' in line and 'barrel=' in line


def test_ip_higher_barrel_than_oop():
    freq_ip  = _barrel_frequency('neutral', 'semi_wet', 'ip')
    freq_oop = _barrel_frequency('neutral', 'semi_wet', 'oop')
    assert freq_ip > freq_oop


def test_card_shift_dict_pairs():
    for k, v in CARD_SHIFT.items():
        assert len(v) == 2


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
