"""Tests for river_block_bet_guide.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.river_block_bet_guide import (
    guide_river_block_bet, RiverBlockBetGuide, rbbg_one_liner,
    _should_block_bet, _block_size, _block_ev, _raise_response, _alternative_line,
    BLOCK_ELIGIBLE_HANDS, BET_LARGE_HANDS, BLOCK_BET_SIZE,
)


def _rbbg(**kw):
    defaults = dict(
        hero_hand_category='top_pair_weak',
        hero_position='oop',
        villain_af=1.5,
        villain_fold_to_river_bet=0.45,
        pot_bb=40.0,
        effective_stack=25.0,
        board_texture='dry',
        has_showdown_value=True,
    )
    defaults.update(kw)
    return guide_river_block_bet(**defaults)


def test_returns_river_block_bet_guide():
    r = _rbbg()
    assert isinstance(r, RiverBlockBetGuide)


def test_top_pair_weak_block_eligible():
    assert _should_block_bet('top_pair_weak', 1.5, True, 'dry') is True


def test_nuts_should_not_block():
    assert _should_block_bet('nuts', 1.5, True, 'dry') is False


def test_set_should_not_block():
    assert _should_block_bet('set', 1.5, True, 'dry') is False


def test_aggressive_villain_no_block():
    assert _should_block_bet('top_pair_weak', 3.5, True, 'dry') is False


def test_monotone_board_no_block():
    assert _should_block_bet('middle_pair', 1.5, True, 'monotone') is False


def test_air_no_sdv_no_block():
    assert _should_block_bet('air', 1.5, False, 'dry') is False


def test_block_size_is_fraction_of_pot():
    size = _block_size(40.0, 100.0)
    assert size <= 40.0 * (BLOCK_BET_SIZE + 0.05)


def test_block_size_capped_by_stack():
    size = _block_size(40.0, 5.0)
    assert size <= 5.0


def test_block_ev_computed():
    ev = _block_ev(40.0, 11.2, 0.45, 0.55)
    assert isinstance(ev, float)


def test_raise_response_strong_hand():
    resp = _raise_response('set')
    assert 'call' in resp or 'reraise' in resp


def test_raise_response_medium_hand():
    resp = _raise_response('middle_pair')
    assert resp == 'fold'


def test_alternative_aggressive_check_call():
    alt = _alternative_line('top_pair_weak', 3.5)
    assert 'check_call' in alt or 'call' in alt


def test_alternative_passive_check_fold():
    alt = _alternative_line('air', 1.5)
    assert 'check_fold' in alt or 'fold' in alt


def test_should_block_stored():
    r = _rbbg()
    assert isinstance(r.should_block_bet, bool)


def test_block_size_stored():
    r = _rbbg()
    assert r.block_bet_size_bb > 0


def test_block_pct_reasonable():
    r = _rbbg()
    assert 0.15 <= r.block_bet_pct <= 0.45


def test_raise_response_stored():
    r = _rbbg()
    assert r.raise_response in ('fold', 'call_or_reraise')


def test_tips_populated():
    r = _rbbg()
    assert len(r.tips) >= 3


def test_one_liner_format():
    r = _rbbg()
    line = rbbg_one_liner(r)
    assert '[RBBG' in line
    assert 'ev=' in line
    assert 'if_raised=' in line


def test_strong_hand_does_not_block():
    r = _rbbg(hero_hand_category='nuts')
    assert r.should_block_bet is False


def test_passive_villain_allows_block():
    r = _rbbg(villain_af=1.2, hero_hand_category='middle_pair')
    assert r.should_block_bet is True


def test_aggressive_villain_prevents_block():
    r = _rbbg(villain_af=4.0)
    assert r.should_block_bet is False


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
