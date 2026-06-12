"""Tests for facing_check_raise_response.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.facing_check_raise_response import (
    respond_to_check_raise, CheckRaiseResponse, fcrr_one_liner,
    _villain_type, _pot_odds, _check_raise_response,
    _reraise_size, _equity_vs_check_raise_range,
    CALL_FLOOR_BY_VILLAIN, RERAISE_HANDS,
)


def _fcrr(**kw):
    defaults = dict(
        hero_hand_category='top_pair',
        villain_check_raise_size_bb=18.0,
        pot_before_hero_bet=15.0,
        hero_bet_bb=9.0,
        villain_af=1.8,
        street='flop',
        board_texture='wet',
        hero_equity=0.55,
        hero_position='ip',
    )
    defaults.update(kw)
    return respond_to_check_raise(**defaults)


def test_returns_check_raise_response():
    r = _fcrr()
    assert isinstance(r, CheckRaiseResponse)


def test_passive_villain_type():
    assert _villain_type(1.2) == 'passive'


def test_balanced_villain_type():
    assert _villain_type(2.0) == 'balanced'


def test_aggressive_villain_type():
    assert _villain_type(3.5) == 'aggressive'


def test_pot_odds_basic():
    odds = _pot_odds(40.0, 10.0)
    assert abs(odds - 0.2) < 0.01


def test_pot_odds_larger():
    odds = _pot_odds(100.0, 50.0)
    assert abs(odds - 1/3) < 0.01


def test_reraise_size_2x():
    size = _reraise_size(18.0)
    assert size == round(18.0 * 2.8, 1)


def test_reraise_size_small():
    size = _reraise_size(10.0)
    assert size == round(28.0, 1)


def test_nuts_reraise():
    response = _check_raise_response('nuts', 2.0, 0.90, 0.30)
    assert response == 'reraise'


def test_set_reraise_high_equity():
    response = _check_raise_response('set', 2.0, 0.75, 0.30)
    assert response == 'reraise'


def test_top_pair_fold_vs_passive():
    response = _check_raise_response('top_pair', 1.0, 0.32, 0.30)
    assert response == 'fold'


def test_flush_draw_call_vs_aggressive():
    response = _check_raise_response('flush_draw', 3.5, 0.43, 0.30)
    assert response == 'call'


def test_air_always_fold():
    response = _check_raise_response('air', 2.0, 0.13, 0.30)
    assert response == 'fold'


def test_equity_nuts_high():
    eq = _equity_vs_check_raise_range('nuts', 2.0)
    assert eq >= 0.90


def test_equity_air_low():
    eq = _equity_vs_check_raise_range('air', 2.0)
    assert eq <= 0.15


def test_equity_aggressive_boost():
    eq_agg = _equity_vs_check_raise_range('top_pair', 3.5)
    eq_pas = _equity_vs_check_raise_range('top_pair', 1.0)
    assert eq_agg > eq_pas


def test_villain_type_stored():
    r = _fcrr()
    assert r.villain_type in ('passive', 'balanced', 'aggressive')


def test_response_field():
    r = _fcrr()
    assert r.response in ('fold', 'call', 'reraise')


def test_pot_odds_stored():
    r = _fcrr()
    assert 0.0 < r.pot_odds_required < 1.0


def test_call_amount_stored():
    r = _fcrr()
    assert r.call_amount_bb == 18.0 - 9.0


def test_reraise_size_stored():
    r = _fcrr()
    assert r.reraise_size_bb > 0


def test_equity_vs_cr_stored():
    r = _fcrr()
    assert 0.0 < r.equity_vs_cr_range < 1.0


def test_tips_populated():
    r = _fcrr()
    assert len(r.tips) >= 3


def test_nuts_returns_reraise():
    r = _fcrr(hero_hand_category='nuts', hero_equity=0.95)
    assert r.response == 'reraise'


def test_air_returns_fold():
    r = _fcrr(hero_hand_category='air', hero_equity=0.05)
    assert r.response == 'fold'


def test_one_liner_format():
    r = _fcrr()
    line = fcrr_one_liner(r)
    assert '[FCRR' in line
    assert 'eq=' in line
    assert 'min=' in line
    assert 'call_amt=' in line


def test_one_liner_contains_response():
    r = _fcrr()
    line = fcrr_one_liner(r)
    assert r.response.upper() in line


def test_call_floor_passive_high():
    assert CALL_FLOOR_BY_VILLAIN['passive'] > CALL_FLOOR_BY_VILLAIN['aggressive']


def test_reraise_hands_contains_nuts():
    assert 'nuts' in RERAISE_HANDS
    assert 'set' in RERAISE_HANDS


def test_flush_draw_borderline_call():
    r = _fcrr(hero_hand_category='flush_draw', villain_af=3.5)
    assert r.response in ('call', 'fold')


def test_verdict_has_response():
    r = _fcrr()
    assert r.response.upper() in r.verdict or r.response in r.verdict.lower()


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
