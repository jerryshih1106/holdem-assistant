"""Tests for river_probe_bet_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.river_probe_bet_advisor import (
    analyze_river_probe, RiverProbeResult, rpb_one_liner,
    _optimal_probe_size, _probe_fold_pct, _probe_ev,
    VILLAIN_CHECKBACK_RANGE,
)


def _rpb(**kw):
    defaults = dict(
        villain_type='rec', hand_strength='thin_value',
        river_card='blank', pot_bb=20.0,
        hero_equity_if_called=0.35, hero_sdv=0.55,
        checked_street='turn',
    )
    defaults.update(kw)
    return analyze_river_probe(**defaults)


def test_returns_result():
    assert isinstance(_rpb(), RiverProbeResult)


def test_probe_size_reasonable():
    r = _rpb()
    assert 0.30 <= r.probe_size_frac <= 0.80


def test_probe_size_bb_computed():
    r = _rpb(pot_bb=20.0)
    expected = round(20.0 * r.probe_size_frac, 1)
    assert abs(r.probe_size_bb - expected) < 0.2


def test_flush_card_increases_size():
    normal = _optimal_probe_size('rec', 'thin_value', 'blank')
    flush  = _optimal_probe_size('rec', 'thin_value', 'flush_completes')
    assert flush >= normal


def test_nuts_gets_larger_size():
    thin = _optimal_probe_size('rec', 'thin_value', 'blank')
    nuts = _optimal_probe_size('rec', 'nuts', 'blank')
    assert nuts >= thin


def test_fold_pct_reasonable():
    fold = _probe_fold_pct('rec', 0.55, 'blank')
    assert 0.20 <= fold <= 0.80


def test_scare_card_increases_fold():
    normal_fold = _probe_fold_pct('rec', 0.55, 'blank')
    scare_fold  = _probe_fold_pct('rec', 0.55, 'flush_completes')
    assert scare_fold >= normal_fold


def test_board_pairs_reduces_fold():
    normal_fold = _probe_fold_pct('rec', 0.55, 'blank')
    paired_fold = _probe_fold_pct('rec', 0.55, 'board_pairs')
    assert paired_fold <= normal_fold


def test_probe_ev_formula():
    ev = _probe_ev(20.0, 10.0, 0.50, 0.40)
    # fold_ev = 0.50 * 20 = 10.0
    # call_ev = 0.50 * (0.40 * 40 - 10) = 0.50 * 6 = 3.0
    assert abs(ev - 13.0) < 0.5


def test_strong_hand_gets_value_action():
    r = _rpb(hand_strength='nuts')
    assert r.recommended_action == 'PROBE_VALUE'


def test_high_sdv_checks_down():
    r = _rpb(hand_strength='medium_value', hero_sdv=0.80, hero_equity_if_called=0.20)
    assert r.recommended_action == 'CHECK_SHOWDOWN'


def test_bluff_fish_high_fold():
    r = _rpb(hand_strength='air', villain_type='fish', river_card='blank')
    assert r.recommended_action in ('PROBE_BLUFF', 'CHECK_SHOWDOWN')


def test_score_in_range():
    r = _rpb()
    assert 1 <= r.probe_score <= 10


def test_one_liner_format():
    r = _rpb()
    line = rpb_one_liner(r)
    assert '[RPB' in line and 'EV=' in line


def test_tips_populated():
    r = _rpb()
    assert len(r.tips) >= 2


def test_villain_type_stored():
    r = _rpb(villain_type='nit')
    assert r.villain_type == 'nit'


def test_nit_lower_fold_than_fish():
    nit_fold  = _probe_fold_pct('nit', 0.55, 'blank')
    fish_fold = _probe_fold_pct('fish', 0.55, 'blank')
    assert fish_fold >= nit_fold


def test_river_card_stored():
    r = _rpb(river_card='flush_completes')
    assert r.river_card == 'flush_completes'


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
