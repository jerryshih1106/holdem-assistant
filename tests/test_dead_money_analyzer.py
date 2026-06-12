"""Tests for dead_money_analyzer.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.dead_money_analyzer import (
    analyze_dead_money, DeadMoneyAnalysis, dma_one_liner,
    _total_dead_money, _steal_ev, _break_even_fold_prob,
    _open_range_widening, _squeeze_opportunity, _straddle_impact,
)


def _dma(**kw):
    defaults = dict(
        hero_position='btn',
        small_blind=0.5,
        big_blind=1.0,
        ante_per_player=1.0,
        players_at_table=6,
        limpers=0,
        straddle=0.0,
        hero_open_size_bb=2.5,
        villain_fold_to_steal=0.60,
    )
    defaults.update(kw)
    return analyze_dead_money(**defaults)


def test_returns_dead_money_analysis():
    r = _dma()
    assert isinstance(r, DeadMoneyAnalysis)


def test_dead_money_no_antes():
    dead = _total_dead_money(0.5, 1.0, 0.0, 6, 0, 0.0)
    assert abs(dead - 1.5) < 0.01


def test_dead_money_with_antes():
    dead = _total_dead_money(0.5, 1.0, 1.0, 6, 0, 0.0)
    assert abs(dead - 7.5) < 0.01   # 1.5 blinds + 6 antes


def test_dead_money_with_limper():
    dead = _total_dead_money(0.5, 1.0, 0.0, 6, 1, 0.0)
    assert abs(dead - 2.5) < 0.01   # 1.5 + 1 limper


def test_dead_money_with_straddle():
    dead = _total_dead_money(0.5, 1.0, 0.0, 6, 0, 2.0)
    assert abs(dead - 3.5) < 0.01   # 1.5 + 2 straddle


def test_steal_ev_positive_high_fold():
    ev = _steal_ev(7.5, 2.5, 0.80)
    assert ev > 0


def test_steal_ev_negative_low_fold():
    ev = _steal_ev(1.5, 2.5, 0.30)
    assert ev < 0


def test_break_even_fold_reasonable():
    be = _break_even_fold_prob(7.5, 2.5)
    assert 0.0 < be < 1.0


def test_break_even_increases_with_open_size():
    be_small = _break_even_fold_prob(7.5, 2.0)
    be_large = _break_even_fold_prob(7.5, 4.0)
    assert be_large > be_small


def test_break_even_decreases_with_more_dead():
    be_little = _break_even_fold_prob(1.5, 2.5)
    be_lots = _break_even_fold_prob(8.0, 2.5)
    assert be_lots < be_little


def test_range_widens_with_antes():
    no_ante = _open_range_widening(1.5, 0.25)
    with_ante = _open_range_widening(7.5, 0.25)
    assert with_ante > no_ante


def test_range_capped_at_85():
    wide = _open_range_widening(100.0, 0.25)
    assert wide <= 0.85


def test_squeeze_opportunity_strong():
    opp = _squeeze_opportunity(5.0, 1)
    assert opp == 'strong_squeeze_opportunity'


def test_squeeze_opportunity_none():
    opp = _squeeze_opportunity(1.5, 0)
    assert opp == 'standard_raise'


def test_straddle_impact_none():
    impact = _straddle_impact(0.0, 1.0)
    assert impact == 'no_straddle'


def test_straddle_impact_2x():
    impact = _straddle_impact(2.0, 1.0)
    assert '2x' in impact or 'straddle' in impact


def test_total_dead_stored():
    r = _dma()
    assert r.total_dead_money > 0


def test_steal_ev_stored():
    r = _dma()
    assert isinstance(r.steal_ev, float)


def test_break_even_stored():
    r = _dma()
    assert 0.0 < r.break_even_fold_prob < 1.0


def test_widened_range_stored():
    r = _dma()
    assert 0.0 < r.widened_open_range <= 0.85


def test_tips_populated():
    r = _dma()
    assert len(r.tips) >= 3


def test_one_liner_format():
    r = _dma()
    line = dma_one_liner(r)
    assert '[DMA' in line
    assert 'ev=' in line
    assert 'be=' in line
    assert 'open=' in line


def test_limper_increases_dead_money():
    r_no_limp = _dma(limpers=0)
    r_with_limp = _dma(limpers=2)
    assert r_with_limp.total_dead_money > r_no_limp.total_dead_money


def test_straddle_squeeze_tip():
    r = _dma(straddle=2.0, limpers=1)
    combined = ' '.join(r.tips).lower()
    assert 'straddle' in combined or 'squeeze' in combined


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
