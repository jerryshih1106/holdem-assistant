"""Tests for preflop_sizing_optimizer.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.preflop_sizing_optimizer import (
    optimize_preflop_sizing, PreflopSizingResult, pso_one_liner,
    _compute_open_size, _classify_3bet_freq, _classify_stack,
    _defense_frequency, _spr_after_call, _size_label,
    BASE_OPEN_SIZE, THREE_BET_FREQ_ADJ,
)


def _pso(**kw):
    defaults = dict(
        position='btn',
        three_bet_freq=0.10,
        stack_bb=100.0,
        ante_type='no_ante',
        n_players_to_act=3,
        dead_money_bb=1.5,
    )
    defaults.update(kw)
    return optimize_preflop_sizing(**defaults)


def test_returns_preflop_sizing_result():
    r = _pso()
    assert isinstance(r, PreflopSizingResult)


def test_three_bet_freq_classification_very_low():
    assert _classify_3bet_freq(0.03) == 'very_low'


def test_three_bet_freq_classification_high():
    assert _classify_3bet_freq(0.15) == 'high'


def test_three_bet_freq_classification_very_high():
    assert _classify_3bet_freq(0.20) == 'very_high'


def test_stack_depth_short():
    assert _classify_stack(20.0) == 'short'


def test_stack_depth_deep():
    assert _classify_stack(120.0) == 'deep'


def test_high_3bet_reduces_open():
    size_low = _compute_open_size('btn', 0.05, 100.0, 'no_ante', 3)
    size_high = _compute_open_size('btn', 0.20, 100.0, 'no_ante', 3)
    assert size_high < size_low


def test_antes_reduce_open_size():
    size_no_ante = _compute_open_size('btn', 0.10, 100.0, 'no_ante', 3)
    size_antes = _compute_open_size('btn', 0.10, 100.0, 'full_ante', 3)
    assert size_antes < size_no_ante


def test_more_players_slightly_bigger():
    size_2 = _compute_open_size('btn', 0.10, 100.0, 'no_ante', 2)
    size_5 = _compute_open_size('btn', 0.10, 100.0, 'no_ante', 5)
    assert size_5 >= size_2


def test_open_size_in_reasonable_range():
    size = _compute_open_size('btn', 0.10, 100.0, 'no_ante', 3)
    assert 2.0 <= size <= 5.0


def test_defense_frequency_formula():
    mdf = _defense_frequency(3.0, 1.5)
    # call_amount = 3.0, total_pot = 1.5 + 3.0 = 4.5
    # mdf = 1 - 3/4.5 = 0.333
    assert abs(mdf - 0.333) < 0.01


def test_defense_frequency_positive():
    mdf = _defense_frequency(2.5, 1.5)
    assert 0 < mdf < 1.0


def test_spr_after_call_formula():
    spr = _spr_after_call(100.0, 3.0, 1.5)
    # pot = 3*2 + 1.5 = 7.5, remaining = 97
    assert abs(spr - (97 / 7.5)) < 0.1


def test_size_label_max():
    label = _size_label(3.5, 2.5)
    assert label == 'max_open'


def test_size_label_standard():
    label = _size_label(2.5, 2.5)
    assert label == 'standard_open'


def test_size_label_small():
    label = _size_label(2.0, 2.5)
    assert label == 'small_open'


def test_recommended_open_stored():
    r = _pso()
    assert 2.0 <= r.recommended_open_bb <= 5.0


def test_defense_frequency_stored():
    r = _pso()
    assert 0 < r.defense_frequency < 1.0


def test_spr_stored():
    r = _pso()
    assert r.spr_after_call > 0


def test_tips_populated():
    r = _pso()
    assert len(r.tips) >= 3


def test_one_liner_format():
    r = _pso()
    line = pso_one_liner(r)
    assert '[PSO' in line
    assert 'OPEN' in line
    assert 'spr=' in line


def test_high_3bet_villain_has_4th_tip():
    r = _pso(three_bet_freq=0.20)
    assert len(r.tips) >= 4


def test_ante_game_has_ante_tip():
    r = _pso(ante_type='bb_ante')
    tip_texts = ' '.join(r.tips)
    assert 'ANTES' in tip_texts or 'ante' in tip_texts.lower()


def test_utg_bigger_than_btn_base():
    utg_base = BASE_OPEN_SIZE.get('utg', 3.0)
    btn_base = BASE_OPEN_SIZE.get('btn', 2.5)
    assert utg_base >= btn_base


def test_three_bet_adj_very_high_less_than_1():
    adj = THREE_BET_FREQ_ADJ.get('very_high', 1.0)
    assert adj < 1.0


def test_three_bet_adj_very_low_gt_1():
    adj = THREE_BET_FREQ_ADJ.get('very_low', 1.0)
    assert adj > 1.0


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
