"""Tests for squeeze_play_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.squeeze_play_advisor import (
    advise_squeeze, SqueezeResult, sqz_one_liner,
    _squeeze_size, _dead_money, _fold_probability,
    FOLD_VS_SQUEEZE, OPENER_FOLD_VS_SQUEEZE,
)


def _sqz(**kw):
    defaults = dict(
        open_bb=3.0, n_callers=1, opener_type='reg',
        caller_types=['rec'], opener_position='co',
        hero_position='btn', hero_hand='AKs',
        hero_equity_if_called=0.55, hero_stack_bb=100.0,
        pot_before_bb=1.5,
    )
    defaults.update(kw)
    return advise_squeeze(**defaults)


def test_returns_squeeze_result():
    assert isinstance(_sqz(), SqueezeResult)


def test_squeeze_size_grows_with_callers():
    size_1 = _squeeze_size(3.0, 1)
    size_2 = _squeeze_size(3.0, 2)
    assert size_2 > size_1


def test_dead_money_includes_callers():
    dead = _dead_money(3.0, 2)
    assert dead == 3.0 * 3  # open + 2 callers * open


def test_fold_pct_decreases_with_lag():
    pct_nit = _fold_probability('nit', ['nit'])
    pct_lag = _fold_probability('lag', ['lag'])
    assert pct_nit > pct_lag


def test_more_callers_reduces_combined_fold():
    fold_1 = _fold_probability('reg', ['rec'])
    fold_2 = _fold_probability('reg', ['rec', 'rec'])
    assert fold_2 < fold_1


def test_ev_stored():
    r = _sqz()
    assert isinstance(r.squeeze_ev_bb, float)


def test_dead_money_stored():
    r = _sqz(open_bb=3.0, n_callers=2)
    assert r.dead_money_bb > 0


def test_rec_callers_fold_more_than_lag():
    r_rec = _sqz(caller_types=['rec', 'rec'], n_callers=2)
    r_lag = _sqz(caller_types=['lag', 'lag'], n_callers=2)
    assert r_rec.combined_fold_pct > r_lag.combined_fold_pct


def test_fish_caller_high_fold_vs_squeeze():
    fish_fold = FOLD_VS_SQUEEZE.get('fish', 0)
    lag_fold  = FOLD_VS_SQUEEZE.get('lag', 0)
    assert fish_fold > lag_fold


def test_tips_include_size():
    r = _sqz()
    assert any('SQUEEZE SIZE' in t or 'BB' in t for t in r.tips)


def test_ip_position_tip():
    r = _sqz(hero_position='btn')
    assert any('IP' in t or 'position' in t.lower() for t in r.tips)


def test_oop_position_tip():
    r = _sqz(hero_position='sb')
    assert any('OOP' in t or 'oop' in t.lower() for t in r.tips)


def test_multiway_tip_with_2_callers():
    r = _sqz(n_callers=2, caller_types=['rec', 'rec'])
    assert any('multi' in t.lower() or 'caller' in t.lower() for t in r.tips)


def test_range_advice_tight_for_utg_open():
    r = _sqz(opener_position='utg')
    assert 'premium' in r.range_advice.lower() or 'value' in r.range_advice.lower()


def test_range_advice_wider_for_btn_open():
    r = _sqz(opener_position='btn')
    assert 'wide' in r.range_advice.lower() or 'TT+' in r.range_advice or 'AQ' in r.range_advice


def test_one_liner_format():
    r = _sqz()
    line = sqz_one_liner(r)
    assert '[SQZ' in line and 'fold=' in line


def test_verdict_contains_size():
    r = _sqz()
    assert str(int(r.squeeze_size_bb)) + 'BB' in r.verdict or 'BB' in r.verdict


def test_squeeze_size_positive():
    r = _sqz(open_bb=2.5, n_callers=1)
    assert r.squeeze_size_bb > 0


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
