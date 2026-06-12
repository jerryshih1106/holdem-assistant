"""Tests for overcall_frequency_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.overcall_frequency_guide import (
    analyze_overcall_frequency, OvercallFrequencyResult, ocf_one_liner,
    _optimal_overcall_freq, _overcall_decision, _is_ip,
    BASELINE_OVERCALL_FREQ, HAND_TYPE_OVERCALL_MODIFIER, VILLAIN_OVERCALL_MODIFIER,
)


def _ocf(**kw):
    defaults = dict(position='btn', n_players_in=1, hand_type='suited_connector', hand_sdv=0.40, squeezers_behind=0, villain_type='reg')
    defaults.update(kw)
    return analyze_overcall_frequency(**defaults)


def test_returns_result():
    assert isinstance(_ocf(), OvercallFrequencyResult)


def test_btn_higher_than_utg():
    btn = BASELINE_OVERCALL_FREQ['btn']
    utg = BASELINE_OVERCALL_FREQ['utg']
    assert btn > utg


def test_more_players_reduces_freq():
    one = _optimal_overcall_freq('btn', 1, 'suited_connector', 0, 'reg')
    two = _optimal_overcall_freq('btn', 2, 'suited_connector', 0, 'reg')
    assert two < one


def test_squeeze_reduces_freq():
    no_sq = _optimal_overcall_freq('btn', 1, 'suited_connector', 0, 'reg')
    sq2   = _optimal_overcall_freq('btn', 1, 'suited_connector', 2, 'reg')
    assert no_sq > sq2


def test_fish_increases_freq():
    fish = _optimal_overcall_freq('btn', 1, 'suited_connector', 0, 'fish')
    nit  = _optimal_overcall_freq('btn', 1, 'suited_connector', 0, 'nit')
    assert fish > nit


def test_sc_better_than_offsuit_broadway():
    sc  = HAND_TYPE_OVERCALL_MODIFIER['suited_connector']
    off = HAND_TYPE_OVERCALL_MODIFIER['offsuit_broadway']
    assert sc > off


def test_is_ip_btn():
    assert _is_ip('btn') is True


def test_is_oop_sb():
    assert _is_ip('sb') is False


def test_strong_hand_3bet_preferred():
    decision = _overcall_decision(0.80, 0.15, 'btn')
    assert decision == '3BET_PREFERRED'


def test_weak_hand_fold():
    decision = _overcall_decision(0.15, 0.10, 'btn')
    assert 'FOLD' in decision


def test_implied_odds_decision():
    decision = _overcall_decision(0.45, 0.15, 'btn')
    assert 'OVERCALL' in decision or 'FOLD' in decision


def test_multiway_implied_multiplier():
    r = _ocf(n_players_in=2)
    assert r.multiway_implied_multiplier > 1.0


def test_tips_populated():
    r = _ocf()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _ocf()
    line = ocf_one_liner(r)
    assert '[OC' in line and 'freq=' in line


def test_squeeze_tip_present():
    r = _ocf(squeezers_behind=2)
    assert any('squeeze' in t.lower() or 'SQUEEZE' in t for t in r.tips)


def test_multiway_tip_present():
    r = _ocf(n_players_in=2)
    assert any('player' in t.lower() or 'multiway' in t.lower() or 'way' in t.lower() for t in r.tips)


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
