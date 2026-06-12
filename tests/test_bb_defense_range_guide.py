"""Tests for bb_defense_range_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.bb_defense_range_guide import (
    analyze_bb_defense_range, BBDefenseRangeResult, bbd_one_liner,
    _defense_frequency, _threebet_frequency, _pot_odds_equity,
    DEFENSE_FREQ_VS_POSITION, VILLAIN_OPEN_RANGE_PCT,
    VILLAIN_TYPE_DEFENSE_MODIFIER,
)


def _bbd(**kw):
    defaults = dict(open_position='btn', open_size_bb=3.0, villain_type='reg')
    defaults.update(kw)
    return analyze_bb_defense_range(**defaults)


def test_returns_result():
    assert isinstance(_bbd(), BBDefenseRangeResult)


def test_btn_defend_more_than_utg():
    btn = DEFENSE_FREQ_VS_POSITION['btn']
    utg = DEFENSE_FREQ_VS_POSITION['utg']
    assert btn > utg


def test_sb_defend_most():
    sb  = DEFENSE_FREQ_VS_POSITION['sb']
    utg = DEFENSE_FREQ_VS_POSITION['utg']
    assert sb > utg


def test_smaller_open_defend_more():
    small = _defense_frequency('btn', 2.0, 'reg')
    large = _defense_frequency('btn', 4.0, 'reg')
    assert small > large


def test_fish_defend_more():
    fish = _defense_frequency('btn', 3.0, 'fish')
    nit  = _defense_frequency('btn', 3.0, 'nit')
    assert fish > nit


def test_3bet_freq_vs_btn_higher_than_utg():
    btn = _threebet_frequency('btn', 'reg')
    utg = _threebet_frequency('utg', 'reg')
    assert btn > utg


def test_pot_odds_correct():
    eq = _pot_odds_equity(3.0)
    assert 0.25 <= eq <= 0.40


def test_pot_odds_decreases_with_size():
    small = _pot_odds_equity(2.5)
    large = _pot_odds_equity(4.0)
    assert small < large


def test_defense_exceeds_fold():
    r = _bbd()
    assert r.defense_frequency + r.fold_frequency > 0.99


def test_threebet_within_defense():
    r = _bbd()
    assert r.threebet_frequency <= r.defense_frequency


def test_call_freq_positive():
    r = _bbd()
    assert r.call_frequency >= 0


def test_villain_range_stored():
    r = _bbd(open_position='utg')
    assert r.villain_open_range_pct <= 0.20


def test_tips_populated():
    r = _bbd()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _bbd()
    line = bbd_one_liner(r)
    assert '[BBD' in line and 'defend=' in line


def test_lag_tip():
    r = _bbd(villain_type='lag')
    assert any('LAG' in t for t in r.tips)


def test_nit_tip():
    r = _bbd(villain_type='nit')
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
