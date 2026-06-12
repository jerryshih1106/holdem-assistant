"""Tests for position_value_quantifier.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.position_value_quantifier import (
    analyze_position_value, PositionValueResult, pvq_one_liner,
    _base_position_value, _spr_modifier, _equity_realization_gap, _per_hand_ev_edge,
    EQUITY_REALIZATION, VILLAIN_AGGRESSION_MULTIPLIER,
)


def _pvq(**kw):
    defaults = dict(
        hero_pos='btn', villain_pos='bb', villain_type='rec',
        hand_type='suited_connector', spr=6.0,
        board_texture='semi_wet', hero_steal_pct=0.35,
        hero_3bet_pct=0.06,
    )
    defaults.update(kw)
    return analyze_position_value(**defaults)


def test_returns_result():
    assert isinstance(_pvq(), PositionValueResult)


def test_btn_vs_bb_positive_value():
    base = _base_position_value('btn', 'bb')
    assert base > 0


def test_ip_player_is_detected():
    r = _pvq(hero_pos='btn', villain_pos='bb')
    assert r.hero_is_ip is True


def test_spr_modifier_increases_deep():
    mod_shallow = _spr_modifier(2.0)
    mod_deep    = _spr_modifier(20.0)
    assert mod_deep > mod_shallow


def test_equity_realization_ip_higher():
    assert EQUITY_REALIZATION['ip'] > EQUITY_REALIZATION['oop']


def test_lag_amplifies_position_value():
    lag_ev  = _per_hand_ev_edge(5.0, 'lag',  'suited_connector', 6.0, 'semi_wet')
    nit_ev  = _per_hand_ev_edge(5.0, 'nit',  'suited_connector', 6.0, 'semi_wet')
    assert lag_ev > nit_ev


def test_suited_connector_higher_than_big_pair():
    sc_ev = _per_hand_ev_edge(5.0, 'rec', 'suited_connector', 6.0, 'semi_wet')
    bp_ev = _per_hand_ev_edge(5.0, 'rec', 'big_pair',         6.0, 'semi_wet')
    assert sc_ev > bp_ev


def test_per_hand_ev_stored():
    r = _pvq()
    assert isinstance(r.per_hand_ev_edge_bb, float)


def test_base_value_stored():
    r = _pvq()
    assert r.base_value_bb100 != 0


def test_exploitation_score_in_range():
    r = _pvq()
    assert 1 <= r.exploitation_score <= 10


def test_good_steal_pct_high_score():
    r = _pvq(hero_pos='btn', hero_steal_pct=0.45, hero_3bet_pct=0.10)
    assert r.exploitation_score >= 7


def test_low_steal_pct_low_score():
    r = _pvq(hero_pos='btn', hero_steal_pct=0.10, hero_3bet_pct=0.02)
    assert r.exploitation_score <= 4


def test_tips_populated():
    r = _pvq()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _pvq()
    line = pvq_one_liner(r)
    assert '[PVQ' in line and 'BB/100' in line


def test_equity_realization_gap_positive():
    gap = _equity_realization_gap(6.0)
    assert gap > 0


def test_villain_type_stored():
    r = _pvq(villain_type='lag')
    assert r.villain_type == 'lag'


def test_lag_aggression_gt_nit():
    assert VILLAIN_AGGRESSION_MULTIPLIER['lag'] > VILLAIN_AGGRESSION_MULTIPLIER['nit']


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
