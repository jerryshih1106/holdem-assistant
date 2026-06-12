"""Tests for preflop_allin_guide.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.preflop_allin_guide import (
    analyze_preflop_allin, PreFlopAllIn, pfag_one_liner,
    _min_equity_to_call_shove, _equity_vs_villain_range, _allin_response,
    _three_bet_shove_threshold, _four_bet_response,
    EQUITY_VS_RANGE, DEFAULT_EQUITY,
)


def _pfag(**kw):
    defaults = dict(
        hero_hand='QQ',
        hero_position='btn',
        villain_action='four_bet',
        villain_position='utg',
        villain_range_width='tight',
        effective_stack_bb=100.0,
        three_bet_size_bb=22.0,
        current_pot_bb=25.0,
    )
    defaults.update(kw)
    return analyze_preflop_allin(**defaults)


def test_returns_preflop_allin():
    r = _pfag()
    assert isinstance(r, PreFlopAllIn)


def test_min_equity_reasonable():
    eq = _min_equity_to_call_shove(100.0, 25.0)
    assert 0.0 < eq < 1.0


def test_min_equity_increases_with_pot():
    eq_small = _min_equity_to_call_shove(100.0, 10.0)
    eq_large = _min_equity_to_call_shove(100.0, 50.0)
    assert eq_small > eq_large


def test_aa_equity_tight_high():
    eq = _equity_vs_villain_range('AA', 'tight')
    assert eq > 0.70


def test_kk_equity_tight_low():
    eq = _equity_vs_villain_range('KK', 'tight')
    assert eq < 0.45


def test_qq_equity_wide_higher():
    tight = _equity_vs_villain_range('QQ', 'tight')
    wide = _equity_vs_villain_range('QQ', 'wide')
    assert wide > tight


def test_default_equity_fallback():
    eq = _equity_vs_villain_range('72o', 'tight')
    assert eq == DEFAULT_EQUITY['tight']


def test_aa_always_call():
    resp = _allin_response('AA', 'four_bet', 'tight', 100.0, 25.0)
    assert resp == 'call_shove'


def test_kk_always_call():
    resp = _allin_response('KK', 'five_bet', 'tight', 100.0, 25.0)
    assert resp == 'call_shove'


def test_aqo_tight_fold():
    resp = _allin_response('AQo', 'four_bet', 'tight', 100.0, 25.0)
    assert resp == 'fold'


def test_shove_threshold_20bb():
    thresh = _three_bet_shove_threshold(20.0)
    assert 'JJ' in thresh or 'AK' in thresh


def test_shove_threshold_35bb():
    thresh = _three_bet_shove_threshold(35.0)
    assert 'QQ' in thresh or 'AK' in thresh


def test_shove_threshold_deep():
    thresh = _three_bet_shove_threshold(100.0)
    assert 'KK' in thresh or 'AA' in thresh


def test_aa_vs_3bet_4bet():
    resp = _four_bet_response('AA', 'three_bet', 'medium', 100.0, 10.0, 'co')
    assert resp == '4bet_value'


def test_qq_vs_3bet_call_or_4bet():
    resp = _four_bet_response('QQ', 'three_bet', 'medium', 100.0, 10.0, 'co')
    assert '4bet' in resp or 'call' in resp


def test_72o_vs_3bet_fold():
    resp = _four_bet_response('72o', 'three_bet', 'wide', 100.0, 10.0, 'co')
    assert resp == 'fold'


def test_hero_equity_stored():
    r = _pfag()
    assert 0.0 < r.hero_equity < 1.0


def test_min_equity_stored():
    r = _pfag()
    assert 0.0 < r.min_equity_to_call < 1.0


def test_response_valid():
    r = _pfag()
    valid = {'call_shove', 'call_marginal', 'fold', '4bet_value',
             '4bet_or_call', 'call_or_fold', '4bet'}
    assert r.response in valid or any(v in r.response for v in valid)


def test_shove_threshold_stored():
    r = _pfag()
    assert isinstance(r.three_bet_shove_threshold, str)
    assert len(r.three_bet_shove_threshold) > 0


def test_tips_populated():
    r = _pfag()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _pfag()
    line = pfag_one_liner(r)
    assert '[PFAG' in line
    assert 'eq=' in line
    assert 'min=' in line


def test_one_liner_contains_hand():
    r = _pfag(hero_hand='AA')
    line = pfag_one_liner(r)
    assert 'AA' in line


def test_qq_vs_utg_tight_result():
    r = _pfag(hero_hand='QQ', villain_position='utg', villain_range_width='tight')
    assert r.hero_equity == 0.45


def test_ak_vs_utg_tight_fold_or_marginal():
    r = _pfag(hero_hand='AKo', villain_position='utg', villain_range_width='tight')
    assert r.response in ('fold', 'call_marginal')


def test_aa_vs_5bet_call():
    r = _pfag(hero_hand='AA', villain_action='five_bet', villain_range_width='tight')
    assert r.response == 'call_shove'


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
