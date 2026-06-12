"""Tests for cbet_continuation_rate.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.cbet_continuation_rate import (
    advise_cbet_rate, CbetRateAdvice, ccr_one_liner,
    _gto_cbet_freq, _should_cbet, _cbet_size, _multi_street_plan,
    GTO_CBET_BASE, TEXTURE_ADJ,
)


def _ccr(**kw):
    defaults = dict(
        hero_hand_category='top_pair',
        street='flop',
        hero_position='ip',
        board_texture='dry',
        villain_fold_to_cbet=0.50,
        villain_af=2.0,
        prior_cbets=0,
        hero_equity=0.62,
        pot_bb=20.0,
        spr=6.0,
    )
    defaults.update(kw)
    return advise_cbet_rate(**defaults)


def test_returns_cbet_rate_advice():
    r = _ccr()
    assert isinstance(r, CbetRateAdvice)


def test_gto_freq_higher_ip_than_oop():
    ip = _gto_cbet_freq('flop', 'ip', 'dry', 'top_pair', 0.50, 2.0, 0)
    oop = _gto_cbet_freq('flop', 'oop', 'dry', 'top_pair', 0.50, 2.0, 0)
    assert ip > oop


def test_dry_board_higher_freq():
    dry = _gto_cbet_freq('flop', 'ip', 'dry', 'top_pair', 0.50, 2.0, 0)
    wet = _gto_cbet_freq('flop', 'ip', 'wet', 'top_pair', 0.50, 2.0, 0)
    assert dry > wet


def test_strong_hand_higher_freq():
    set_freq = _gto_cbet_freq('flop', 'ip', 'dry', 'set', 0.50, 2.0, 0)
    air_freq = _gto_cbet_freq('flop', 'ip', 'dry', 'air', 0.50, 2.0, 0)
    assert set_freq > air_freq


def test_folder_increases_freq():
    low = _gto_cbet_freq('flop', 'ip', 'dry', 'top_pair', 0.40, 2.0, 0)
    high = _gto_cbet_freq('flop', 'ip', 'dry', 'top_pair', 0.65, 2.0, 0)
    assert high > low


def test_aggressive_villain_reduces_freq():
    calm = _gto_cbet_freq('flop', 'ip', 'dry', 'top_pair', 0.50, 1.5, 0)
    aggr = _gto_cbet_freq('flop', 'ip', 'dry', 'top_pair', 0.50, 3.5, 0)
    assert aggr < calm


def test_triple_barrel_lower_freq():
    first = _gto_cbet_freq('river', 'ip', 'dry', 'top_pair', 0.50, 2.0, 0)
    third = _gto_cbet_freq('river', 'ip', 'dry', 'top_pair', 0.50, 2.0, 2)
    assert third <= first


def test_freq_in_valid_range():
    freq = _gto_cbet_freq('flop', 'ip', 'dry', 'top_pair', 0.50, 2.0, 0)
    assert 0.05 <= freq <= 0.95


def test_value_hands_always_cbet():
    assert _should_cbet(0.30, 'set', 'flop', 0) is True
    assert _should_cbet(0.30, 'overpair', 'flop', 0) is True


def test_low_freq_doesnt_cbet():
    assert _should_cbet(0.25, 'air', 'flop', 0) is False


def test_cbet_size_smaller_on_wet():
    dry = _cbet_size('flop', 'dry', 'top_pair')
    wet = _cbet_size('flop', 'wet', 'top_pair')
    assert dry > wet


def test_cbet_size_larger_on_river():
    flop = _cbet_size('flop', 'dry', 'top_pair')
    river = _cbet_size('river', 'dry', 'top_pair')
    assert river > flop


def test_strong_hand_size_up():
    tp = _cbet_size('flop', 'dry', 'top_pair')
    st = _cbet_size('flop', 'dry', 'set')
    assert st >= tp


def test_triple_barrel_plan():
    plan = _multi_street_plan('set', 'dry', 0.70, 5.0)
    assert 'triple' in plan or 'value' in plan


def test_draw_plan():
    plan = _multi_street_plan('flush_draw', 'wet', 0.42, 5.0)
    assert 'semi' in plan or 'bluff' in plan


def test_gto_freq_stored():
    r = _ccr()
    assert 0.05 <= r.gto_cbet_freq <= 0.95


def test_cbet_size_stored():
    r = _ccr()
    assert 0.0 < r.cbet_size <= 1.0


def test_should_cbet_stored():
    r = _ccr()
    assert isinstance(r.should_cbet, bool)


def test_multi_street_plan_stored():
    r = _ccr()
    assert isinstance(r.multi_street_plan, str)


def test_tips_populated():
    r = _ccr()
    assert len(r.tips) >= 2


def test_folder_tip():
    r = _ccr(villain_fold_to_cbet=0.65)
    combined = ' '.join(r.tips).lower()
    assert 'fold' in combined


def test_caller_tip():
    r = _ccr(villain_fold_to_cbet=0.30)
    combined = ' '.join(r.tips).lower()
    assert 'call' in combined or 'check' in combined


def test_third_barrel_tip():
    r = _ccr(prior_cbets=2)
    combined = ' '.join(r.tips).lower()
    assert 'barrel' in combined or 'third' in combined or 'triple' in combined


def test_one_liner_format():
    r = _ccr()
    line = ccr_one_liner(r)
    assert '[CCR' in line
    assert 'freq=' in line
    assert 'plan=' in line


def test_one_liner_cbet_or_check():
    r = _ccr()
    line = ccr_one_liner(r)
    assert 'CBET' in line or 'CHECK' in line


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
