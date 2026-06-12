"""Tests for hero_call_frequency_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.hero_call_frequency_guide import (
    analyze_hero_call_frequency, HeroCallFrequencyResult, hcf_one_liner,
    _mdf_call, _adjusted_villain_bluff_freq, _hero_call_decision,
    VILLAIN_BLUFF_FREQ_RIVER, BOARD_BLUFF_ADJ_HERO_CALL, BLOCKER_CALL_BOOST,
)


def _hcf(**kw):
    defaults = dict(bet_frac=0.75, villain_type='reg', board_texture='semi_wet', street='river', has_blocker=False)
    defaults.update(kw)
    return analyze_hero_call_frequency(**defaults)


def test_returns_result():
    assert isinstance(_hcf(), HeroCallFrequencyResult)


def test_mdf_75pct_bet():
    assert abs(_mdf_call(0.75) - 0.75/1.75) < 0.01


def test_nit_bluffs_rarely():
    nit = VILLAIN_BLUFF_FREQ_RIVER['nit']
    lag = VILLAIN_BLUFF_FREQ_RIVER['lag']
    assert nit < lag


def test_lag_bluffs_most():
    lag = VILLAIN_BLUFF_FREQ_RIVER['lag']
    reg = VILLAIN_BLUFF_FREQ_RIVER['reg']
    assert lag > reg


def test_missed_draw_increases_bluff_freq():
    miss = _adjusted_villain_bluff_freq('reg', 'flush_draw_missed', 'river', False)
    semi = _adjusted_villain_bluff_freq('reg', 'semi_wet', 'river', False)
    assert miss > semi


def test_blocker_increases_bluff_freq():
    no_b = _adjusted_villain_bluff_freq('reg', 'semi_wet', 'river', False)
    with_b = _adjusted_villain_bluff_freq('reg', 'semi_wet', 'river', True)
    assert with_b > no_b


def test_flop_higher_freq_than_river():
    flop = _adjusted_villain_bluff_freq('reg', 'semi_wet', 'flop', False)
    river = _adjusted_villain_bluff_freq('reg', 'semi_wet', 'river', False)
    assert flop > river


def test_call_vs_lag():
    decision = _hero_call_decision(0.50, 0.43)
    assert 'CALL' in decision or 'STRONG' in decision


def test_fold_vs_nit():
    decision = _hero_call_decision(0.10, 0.43)
    assert 'FOLD' in decision


def test_strong_hero_call():
    decision = _hero_call_decision(0.60, 0.43)
    assert decision == 'STRONG_HERO_CALL'


def test_pot_odds_stored():
    r = _hcf(bet_frac=0.75)
    assert abs(r.pot_odds_needed - 0.75/1.75) < 0.01


def test_bluff_freq_stored():
    r = _hcf()
    assert 0.02 <= r.villain_bluff_freq <= 0.80


def test_tips_populated():
    r = _hcf()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _hcf()
    line = hcf_one_liner(r)
    assert '[HCF' in line and 'bluff=' in line


def test_flush_draw_missed_tip():
    r = _hcf(board_texture='flush_draw_missed')
    assert any('flush' in t.lower() or 'FLUSH' in t for t in r.tips)


def test_nit_fold_recommendation():
    r = _hcf(villain_type='nit')
    assert any('FOLD' in t or 'fold' in t.lower() for t in r.tips)


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
