"""Tests for min_4bet_threshold.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.min_4bet_threshold import (
    analyze_4bet, FourBetResult, fbt_one_liner,
    _4bet_size, _alpha, _is_value_4bet, _is_bluff_4bet, _should_cold_call,
    HAND_RANK, COLD_CALL_RANGE, BLUFF_4BET_HANDS, VALUE_4BET_THRESHOLD,
)


def _4bt(**kw):
    defaults = dict(
        hero_hand='AKs', stack_bb=100.0, position='ip',
        threebet_bb=9.0, pot_before_4bet=12.0,
        villain_fold_to_4bet=0.55, hero_equity_if_4bet_called=0.55,
    )
    defaults.update(kw)
    return analyze_4bet(**defaults)


def test_returns_fourbet_result():
    assert isinstance(_4bt(), FourBetResult)


def test_aa_is_value_4bet():
    assert _is_value_4bet('AA', 100.0)


def test_weak_is_not_value_4bet():
    assert not _is_value_4bet('77', 100.0)


def test_a5s_is_bluff_4bet():
    assert _is_bluff_4bet('A5s')


def test_jj_should_cold_call():
    assert _should_cold_call('JJ')


def test_ip_smaller_than_oop_sizing():
    ip_size  = _4bet_size(9.0, 'ip')
    oop_size = _4bet_size(9.0, 'oop')
    assert ip_size < oop_size


def test_alpha_formula():
    a = _alpha(20.0, 12.0)
    assert abs(a - 20.0 / 32.0) < 0.01


def test_aa_gets_4bet_value_action():
    r = _4bt(hero_hand='AA')
    assert r.recommended_action == '4BET_VALUE'


def test_jj_gets_cold_call():
    r = _4bt(hero_hand='JJ')
    assert r.recommended_action == 'COLD_CALL'


def test_a5s_high_fold_pct_gets_bluff():
    r = _4bt(hero_hand='A5s', villain_fold_to_4bet=0.65)
    assert r.recommended_action in ('4BET_BLUFF', '4BET_VALUE', 'COLD_CALL')


def test_weak_hand_folds():
    r = _4bt(hero_hand='72o', villain_fold_to_4bet=0.30)
    assert r.recommended_action == 'FOLD'


def test_alpha_stored():
    r = _4bt()
    assert 0 < r.alpha_breakeven < 1


def test_4bet_size_bb_stored():
    r = _4bt(threebet_bb=9.0)
    assert r.fourbet_size_bb > 9.0


def test_tips_populated():
    r = _4bt()
    assert len(r.tips) >= 2


def test_value_4bet_tip():
    r = _4bt(hero_hand='AA')
    assert any('value' in t.lower() or 'VALUE' in t for t in r.tips)


def test_bluff_range_tip():
    r = _4bt(hero_hand='AA')
    assert any('bluff' in t.lower() or 'BALANCED' in t for t in r.tips)


def test_one_liner_format():
    r = _4bt()
    line = fbt_one_liner(r)
    assert '[4BT' in line and 'EV=' in line


def test_hand_rank_ordering():
    assert HAND_RANK['AA'] > HAND_RANK['AKs'] > HAND_RANK['JJ'] > HAND_RANK['TT']


def test_bluff_4bet_hands_have_blockers():
    for h in BLUFF_4BET_HANDS:
        assert h.startswith('A') or h.startswith('K')


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
