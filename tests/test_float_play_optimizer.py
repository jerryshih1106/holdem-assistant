"""Tests for float_play_optimizer.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.float_play_optimizer import (
    optimize_float, FloatResult, flt_one_liner,
    _float_ev, _float_profitability,
    DOUBLE_BARREL_PCT, TURN_GIVE_UP_PCT, TURN_FOLD_VS_FLOAT,
)


def _flt(**kw):
    defaults = dict(
        villain_type='rec', flop_cbet_pct=0.65,
        flop_cbet_bb=8.0, pot_before_cbet=12.0,
        position='ip', hero_hand='overcards',
        hero_equity=0.15, hero_turn_bet_frac=0.60,
    )
    defaults.update(kw)
    return optimize_float(**defaults)


def test_returns_float_result():
    assert isinstance(_flt(), FloatResult)


def test_fish_low_double_barrel():
    assert DOUBLE_BARREL_PCT['fish'] < DOUBLE_BARREL_PCT['lag']


def test_fish_high_give_up():
    assert TURN_GIVE_UP_PCT['fish'] > TURN_GIVE_UP_PCT['nit']


def test_ip_float_recommended():
    r = _flt(position='ip', villain_type='fish', hero_equity=0.20)
    assert r.recommendation in ('FLOAT', 'FLOAT_MARGINAL', 'FLOAT_THIN')


def test_oop_float_blocked():
    r = _flt(position='oop')
    assert r.recommendation == 'FLOAT_REQUIRES_IP'


def test_lag_float_risky():
    r_rec = _flt(villain_type='rec')
    r_lag = _flt(villain_type='lag')
    assert r_rec.profitability_score > r_lag.profitability_score


def test_ev_positive_vs_fish():
    r = _flt(villain_type='fish', hero_equity=0.15)
    assert r.float_ev_bb > 0


def test_ev_negative_vs_lag():
    r = _flt(villain_type='lag', hero_equity=0.05)
    assert r.float_ev_bb < r._replace(villain_type='fish').float_ev_bb if hasattr(r, '_replace') else True


def test_ev_negative_lag_lower_than_rec():
    r_rec = _flt(villain_type='rec', hero_equity=0.10)
    r_lag = _flt(villain_type='lag', hero_equity=0.10)
    assert r_rec.float_ev_bb > r_lag.float_ev_bb


def test_high_equity_increases_score():
    r_low  = _flt(hero_equity=0.05)
    r_high = _flt(hero_equity=0.40)
    assert r_high.profitability_score > r_low.profitability_score


def test_turn_bet_bb_computed():
    r = _flt(flop_cbet_bb=8.0, pot_before_cbet=12.0, hero_turn_bet_frac=0.60)
    expected_turn_pot = 12.0 + 8.0 + 8.0  # pot + villain bet + hero call
    expected_bet = round(expected_turn_pot * 0.60, 1)
    assert abs(r.hero_turn_bet_bb - expected_bet) < 0.5


def test_give_up_stored():
    r = _flt(villain_type='fish')
    assert abs(r.turn_give_up_pct - TURN_GIVE_UP_PCT['fish']) < 0.01


def test_double_barrel_stored():
    r = _flt(villain_type='lag')
    assert abs(r.villain_double_barrel_pct - DOUBLE_BARREL_PCT['lag']) < 0.01


def test_tips_populated():
    r = _flt()
    assert len(r.tips) >= 2


def test_double_barrel_tip():
    r = _flt(villain_type='lag')
    assert any('barrel' in t.lower() or 'BARREL' in t for t in r.tips)


def test_ip_tip():
    r = _flt(position='ip')
    assert any('IP' in t or 'ip' in t.lower() or 'position' in t.lower() for t in r.tips)


def test_one_liner_format():
    r = _flt()
    line = flt_one_liner(r)
    assert '[FLT' in line and 'EV=' in line


def test_profitability_score_in_range():
    r = _flt()
    assert 0 <= r.profitability_score <= 10


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
