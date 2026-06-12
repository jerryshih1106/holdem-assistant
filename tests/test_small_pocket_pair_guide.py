"""Tests for small_pocket_pair_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.small_pocket_pair_guide import (
    analyze_small_pocket_pair, SmallPocketPairResult, spp_one_liner,
    _set_mining_profitable, _playability_score, _preflop_action,
    SET_FREQUENCY, MIN_STACK_CALL_RATIO,
    PAIR_RANK_PLAYABILITY, VILLAIN_CALL_MODIFIER, POSITION_MODIFIER,
)


def _spp(**kw):
    defaults = dict(pair_rank=4, position='btn', villain_type='reg',
                    stack_bb=100.0, call_bb=3.0)
    defaults.update(kw)
    return analyze_small_pocket_pair(**defaults)


def test_returns_result():
    assert isinstance(_spp(), SmallPocketPairResult)


def test_set_frequency_range():
    assert 0.10 <= SET_FREQUENCY <= 0.14


def test_min_stack_call_ratio():
    assert MIN_STACK_CALL_RATIO == 10.0


def test_set_mining_profitable_true():
    assert _set_mining_profitable(100.0, 5.0) is True


def test_set_mining_profitable_false():
    assert _set_mining_profitable(30.0, 5.0) is False


def test_playability_ranks():
    assert PAIR_RANK_PLAYABILITY[5] > PAIR_RANK_PLAYABILITY[2]


def test_btn_higher_playability_than_utg():
    btn = _playability_score(4, 'btn', 'reg')
    utg = _playability_score(4, 'utg', 'reg')
    assert btn > utg


def test_fish_higher_playability_than_nit():
    fish = _playability_score(4, 'btn', 'fish')
    nit = _playability_score(4, 'btn', 'nit')
    assert fish > nit


def test_deep_stack_calls():
    r = _spp(stack_bb=200.0, call_bb=3.0)
    assert r.set_mining_ok is True
    assert 'CALL' in r.preflop_action


def test_short_stack_folds():
    r = _spp(stack_bb=20.0, call_bb=3.0)
    assert r.set_mining_ok is False
    assert r.preflop_action == 'FOLD'


def test_pair_rank_in_result():
    r = _spp(pair_rank=2)
    assert r.pair_rank == 2


def test_tips_populated():
    r = _spp()
    assert len(r.tips) >= 2


def test_fish_tip():
    r = _spp(villain_type='fish', stack_bb=100.0, call_bb=3.0)
    assert any('FISH' in t or 'fish' in t for t in r.tips)


def test_nit_tip():
    r = _spp(villain_type='nit', stack_bb=200.0, call_bb=3.0)
    assert any('NIT' in t or 'nit' in t for t in r.tips)


def test_one_liner_format():
    r = _spp()
    line = spp_one_liner(r)
    assert '[SPP' in line and 'action=' in line


def test_verdict_fields():
    r = _spp()
    assert 'set_ok=' in r.verdict
    assert 'play=' in r.verdict


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t(); print(f'[OK] {t.__name__}')
        except Exception as e:
            print(f'[FAIL] {t.__name__}: {e}'); failed += 1
    print(f'\n{len(tests)-failed}/{len(tests)} passed')
    sys.exit(failed)
