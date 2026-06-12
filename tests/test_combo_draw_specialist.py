"""Tests for combo_draw_specialist.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.combo_draw_specialist import (
    analyze_combo_draw, ComboDrawResult, cds_one_liner,
    _total_outs, _equity_flop, _equity_turn, _combo_strength,
    _shove_ev, DRAW_OUTS,
)


def _cds(**kw):
    defaults = dict(
        draw_types=['flush_draw', 'oesd'],
        street='flop', position='ip',
        spr=6.0, pot_bb=15.0,
        hero_stack_bb=90.0, villain_stack_bb=90.0,
        villain_fold_pct=0.40,
    )
    defaults.update(kw)
    return analyze_combo_draw(**defaults)


def test_returns_combo_draw_result():
    assert isinstance(_cds(), ComboDrawResult)


def test_fd_oesd_outs_with_overlap():
    outs = _total_outs(['flush_draw', 'oesd'])
    # 9 + 8 - 2 overlap = 15
    assert outs == 15


def test_fd_gutshot_outs():
    outs = _total_outs(['flush_draw', 'gutshot'])
    # 9 + 4 - 1 = 12
    assert outs == 12


def test_fd_overcard_outs():
    outs = _total_outs(['flush_draw', 'overcard'])
    # 9 + 3 - 1 = 11
    assert outs == 11


def test_single_draw_no_overlap():
    outs = _total_outs(['flush_draw'])
    assert outs == DRAW_OUTS['flush_draw']


def test_equity_flop_15_outs():
    eq = _equity_flop(15)
    # 15 * 0.038 = 0.57
    assert eq >= 0.54 and eq <= 0.60


def test_equity_flop_small_outs():
    eq = _equity_flop(4)
    assert abs(eq - 0.16) < 0.01


def test_equity_turn_half_outs():
    # Turn: 15 outs * 0.02 = 0.30
    eq = _equity_turn(15)
    assert abs(eq - 0.30) < 0.01


def test_equity_decreases_turn_vs_flop():
    eq_flop = _equity_flop(12)
    eq_turn = _equity_turn(12)
    assert eq_flop > eq_turn


def test_monster_combo_15_outs():
    assert _combo_strength(15) == 'monster_combo'


def test_strong_combo_12_outs():
    assert _combo_strength(12) == 'strong_combo'


def test_good_combo_9_outs():
    assert _combo_strength(9) == 'good_combo'


def test_weak_combo_6_outs():
    assert _combo_strength(6) == 'weak_combo'


def test_monster_combo_recommends_aggression():
    r = _cds(draw_types=['flush_draw', 'oesd'])  # 15 outs
    assert r.recommended_action in ('raise_semi_bluff', 'semi_bluff_shove', 'jam')


def test_low_spr_recommends_jam():
    r = _cds(spr=1.5)
    assert r.recommended_action == 'jam'


def test_weak_combo_check_fold():
    r = _cds(draw_types=['gutshot'], villain_fold_pct=0.30)
    assert 'fold' in r.recommended_action or 'check' in r.recommended_action or 'call' in r.recommended_action


def test_shove_ev_positive_with_high_equity():
    ev = _shove_ev(0.55, 90.0, 90.0, 15.0)
    assert ev > 0


def test_shove_ev_negative_with_low_equity():
    ev = _shove_ev(0.10, 90.0, 90.0, 15.0)
    assert ev < 0


def test_tips_populated():
    r = _cds()
    assert len(r.tips) >= 2


def test_one_liner_contains_outs_and_equity():
    r = _cds()
    line = cds_one_liner(r)
    assert 'outs' in line and 'eq=' in line


def test_one_liner_contains_action():
    r = _cds()
    line = cds_one_liner(r)
    assert r.recommended_action in line


def test_oop_monster_check_raise():
    r = _cds(draw_types=['flush_draw', 'oesd'], position='oop', spr=6.0, villain_fold_pct=0.40)
    assert 'raise' in r.recommended_action or r.recommended_action in ('jam', 'semi_bluff_shove')


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
