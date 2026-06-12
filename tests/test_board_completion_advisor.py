"""Tests for board_completion_advisor.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.board_completion_advisor import (
    analyze_draw_completion, DrawCompletionResult, bca_one_liner,
    _turn_completion_prob, _flop_to_river_prob, _implied_odds_bonus,
    _range_advantage_shift, DRAW_OUTS, VILLAIN_DRAW_WEIGHT, PFR_DRAW_WEIGHT,
)


def _bca(**kw):
    defaults = dict(
        draw_type='flush_draw',
        street='flop',
        draw_completed=False,
        hero_has_draw=True,
        hero_is_pfr=True,
        pot_bb=15.0,
        stack_bb=100.0,
        hero_equity_if_hits=0.90,
        villain_stackoff_freq=0.50,
        hero_position='ip',
    )
    defaults.update(kw)
    return analyze_draw_completion(**defaults)


def test_returns_draw_completion_result():
    r = _bca()
    assert isinstance(r, DrawCompletionResult)


def test_flush_draw_9_outs():
    assert DRAW_OUTS['flush_draw'] == 9


def test_oesd_8_outs():
    assert DRAW_OUTS['oesd'] == 8


def test_combo_draw_15_outs():
    assert DRAW_OUTS['combo_draw'] == 15


def test_gutshot_4_outs():
    assert DRAW_OUTS['gutshot'] == 4


def test_turn_completion_flush_draw():
    prob = _turn_completion_prob(9, 'flop')
    assert abs(prob - 9/47) < 0.001


def test_turn_completion_oesd():
    prob = _turn_completion_prob(8, 'flop')
    assert abs(prob - 8/47) < 0.001


def test_flop_to_river_prob_higher_than_turn():
    ftr = _flop_to_river_prob(9)
    turn = _turn_completion_prob(9, 'flop')
    assert ftr > turn


def test_combo_draw_high_probability():
    prob = _flop_to_river_prob(15)
    assert prob >= 0.50


def test_gutshot_low_probability():
    prob = _flop_to_river_prob(4)
    assert prob < 0.20


def test_villain_draw_weight_higher_than_pfr():
    v_wt = VILLAIN_DRAW_WEIGHT.get('flush_draw', 0.0)
    p_wt = PFR_DRAW_WEIGHT.get('flush_draw', 0.0)
    assert v_wt > p_wt


def test_pfr_range_disadvantage_when_flush_completes():
    shift = _range_advantage_shift('flush_draw', hero_is_pfr=True)
    assert shift < 0  # PFR disadvantaged when flush completes


def test_caller_range_advantage_when_flush_completes():
    shift = _range_advantage_shift('flush_draw', hero_is_pfr=False)
    assert shift > 0  # caller advantaged when flush completes


def test_implied_odds_bonus_positive():
    bonus = _implied_odds_bonus('flush_draw', 15.0, 100.0, 0.50)
    assert bonus > 0


def test_larger_stack_more_implied_odds():
    bonus_deep = _implied_odds_bonus('flush_draw', 15.0, 200.0, 0.50)
    bonus_short = _implied_odds_bonus('flush_draw', 15.0, 30.0, 0.50)
    assert bonus_deep > bonus_short


def test_strategy_hit_draw():
    r = _bca(draw_completed=True, hero_has_draw=True)
    assert 'value_bet' in r.strategy or 'bet' in r.strategy


def test_strategy_missed_villain_hit():
    r = _bca(draw_completed=True, hero_has_draw=False, hero_equity_if_hits=0.40)
    assert 'fold' in r.strategy or 'check' in r.strategy


def test_strategy_pending_good_draw():
    r = _bca(draw_completed=False, hero_has_draw=True, hero_equity_if_hits=0.90)
    assert 'continue' in r.strategy


def test_outs_stored():
    r = _bca(draw_type='flush_draw')
    assert r.outs == 9


def test_turn_prob_stored():
    r = _bca()
    assert 0 < r.turn_prob < 1.0


def test_ftr_prob_stored():
    r = _bca()
    assert 0 < r.flop_to_river_prob < 1.0


def test_tips_populated():
    r = _bca()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _bca()
    line = bca_one_liner(r)
    assert '[BCA' in line
    assert 'p=' in line
    assert 'adv_shift=' in line


def test_verdict_contains_street():
    r = _bca(street='flop')
    assert 'flop' in r.verdict.lower()


def test_range_advantage_shift_stored():
    r = _bca()
    assert r.range_advantage_shift != 0


def test_turn_street_fewer_remaining_cards():
    flop_prob = _turn_completion_prob(9, 'flop')
    turn_prob = _turn_completion_prob(9, 'turn')
    # slightly different denominators: 47 vs 46
    assert abs(flop_prob - turn_prob) < 0.01  # close but not equal


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
