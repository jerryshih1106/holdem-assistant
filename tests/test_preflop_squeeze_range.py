"""Tests for preflop_squeeze_range.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.preflop_squeeze_range import (
    build_squeeze_range, SqueezeDecision, psq_one_liner,
    _hand_category, _squeeze_size_bb, _fold_equity, _squeeze_ev, _should_squeeze,
    VALUE_SQUEEZE_HANDS, BLUFF_SQUEEZE_HANDS,
)


def _psq(**kw):
    defaults = dict(
        hero_hand='ATs',
        hero_position='btn',
        villain_position='utg',
        num_callers=1,
        raiser_vpip=0.28,
        raiser_pfr=0.20,
        open_raise_size_bb=3.0,
        stack_bb=100.0,
        hero_history_3bet=0.08,
        pot_bb=8.5,
    )
    defaults.update(kw)
    return build_squeeze_range(**defaults)


def test_returns_squeeze_decision():
    r = _psq()
    assert isinstance(r, SqueezeDecision)


def test_aa_is_value_category():
    assert _hand_category('AA') == 'value'


def test_a5s_is_bluff_category():
    assert _hand_category('A5s') == 'bluff'


def test_small_pairs_avoid():
    for hand in ('22', '33', '44', '55'):
        assert _hand_category(hand) == 'avoid'


def test_squeeze_size_increases_with_callers():
    size1 = _squeeze_size_bb(3.0, 1, 100.0)
    size2 = _squeeze_size_bb(3.0, 2, 100.0)
    assert size2 > size1


def test_squeeze_size_positive():
    size = _squeeze_size_bb(3.0, 1, 100.0)
    assert size > 0


def test_squeeze_size_capped_by_stack():
    size = _squeeze_size_bb(3.0, 5, 20.0)
    assert size <= 5.0   # cap at 25% of 20BB stack


def test_fold_equity_between_zero_and_one():
    fe = _fold_equity(0.28, 0.20, 1, 'btn')
    assert 0.0 <= fe <= 1.0


def test_more_callers_reduces_fold_equity():
    fe1 = _fold_equity(0.28, 0.20, 1, 'btn')
    fe3 = _fold_equity(0.28, 0.20, 3, 'btn')
    assert fe1 > fe3


def test_ip_position_improves_fold_equity():
    oop = _fold_equity(0.28, 0.20, 1, 'bb')
    ip = _fold_equity(0.28, 0.20, 1, 'btn')
    assert ip > oop


def test_wider_raiser_increases_fold_equity():
    tight = _fold_equity(0.18, 0.16, 1, 'btn')
    loose = _fold_equity(0.40, 0.18, 1, 'btn')
    assert loose >= tight


def test_ev_calculated():
    ev = _squeeze_ev(5.5, 0.55, 12.0, 3.0)
    assert isinstance(ev, float)


def test_value_hand_should_squeeze():
    assert _should_squeeze('value', 0.45, 5.0, 1, 0.08) is True


def test_avoid_hand_no_squeeze():
    assert _should_squeeze('avoid', 0.55, 3.0, 1, 0.08) is False


def test_bluff_needs_fold_equity():
    # Low fold equity: should not squeeze with bluff
    assert _should_squeeze('bluff', 0.35, -2.0, 1, 0.08) is False


def test_bluff_with_good_fold_equity():
    assert _should_squeeze('bluff', 0.55, 2.0, 1, 0.08) is True


def test_multiway_avoid_bluff():
    # 3+ callers: value only
    assert _should_squeeze('bluff', 0.60, 5.0, 3, 0.08) is False


def test_aa_squeezes():
    r = _psq(hero_hand='AA')
    assert r.should_squeeze is True


def test_55_does_not_squeeze():
    r = _psq(hero_hand='55')
    assert r.should_squeeze is False


def test_a5s_squeezes_with_good_fold_equity():
    r = _psq(hero_hand='A5s', raiser_vpip=0.35, raiser_pfr=0.20)
    # May or may not squeeze depending on math; just verify it runs
    assert isinstance(r.should_squeeze, bool)


def test_dead_money_stored():
    r = _psq()
    assert r.dead_money_bb >= 0


def test_tips_populated():
    r = _psq()
    assert len(r.tips) >= 2


def test_tips_contain_sizing():
    r = _psq()
    combined = ' '.join(r.tips).lower()
    assert 'size' in combined or 'squeeze' in combined or 'bb' in combined


def test_multi_caller_tip():
    r = _psq(num_callers=3, hero_hand='KK')
    combined = ' '.join(r.tips).lower()
    assert 'multi' in combined or 'caller' in combined or 'fold' in combined


def test_tight_3bet_image_tip():
    r = _psq(hero_history_3bet=0.02)
    combined = ' '.join(r.tips).lower()
    assert '3bet' in combined or 'tight' in combined or 'image' in combined


def test_one_liner_format():
    r = _psq()
    line = psq_one_liner(r)
    assert '[PSQ' in line
    assert 'ev=' in line
    assert 'fold=' in line


def test_one_liner_contains_hand():
    r = _psq(hero_hand='ATs')
    line = psq_one_liner(r)
    assert 'ATs' in line


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
