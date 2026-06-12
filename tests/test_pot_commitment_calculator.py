"""Tests for pot_commitment_calculator.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.pot_commitment_calculator import (
    analyze_commitment, CommitmentAnalysis, pcc_one_liner,
    _min_equity_to_jam, _spr, _is_committed, _ev_jam,
    COMMIT_SPR_THRESHOLD,
)


def _pcc(**kw):
    defaults = dict(
        hand_category='top_pair',
        stack_bb=40.0,
        pot_bb=20.0,
        equity=0.60,
        villain_bet_bb=15.0,
        street='flop',
        starting_stack_bb=100.0,
    )
    defaults.update(kw)
    return analyze_commitment(**defaults)


def test_returns_commitment_analysis():
    r = _pcc()
    assert isinstance(r, CommitmentAnalysis)


def test_spr_calculation():
    spr = _spr(40.0, 20.0)
    assert abs(spr - 2.0) < 0.01


def test_spr_zero_pot():
    spr = _spr(40.0, 0.0)
    assert spr >= 99.0


def test_min_equity_to_jam():
    eq = _min_equity_to_jam(20.0, 40.0)
    # call = 40, total = 20 + 80 = 100; eq = 40/100 = 0.40
    assert abs(eq - 0.40) < 0.01


def test_min_equity_increases_with_stack():
    eq_small = _min_equity_to_jam(20.0, 20.0)
    eq_large = _min_equity_to_jam(20.0, 80.0)
    assert eq_large > eq_small


def test_set_committed_at_low_spr():
    assert _is_committed('set', 15.0, 20.0) is True   # SPR=0.75 < 5.5


def test_top_pair_not_committed_at_high_spr():
    assert _is_committed('top_pair', 200.0, 10.0) is False   # SPR=20 > 2.0


def test_nuts_committed_at_medium_spr():
    assert _is_committed('nuts', 50.0, 20.0) is True   # SPR=2.5 < 8.0


def test_air_never_committed():
    threshold = COMMIT_SPR_THRESHOLD.get('air', 0)
    assert threshold == 0.0


def test_ev_jam_positive_with_good_equity():
    ev = _ev_jam(0.70, 20.0, 40.0)
    # EV = 0.70 * 100 - 40 = 70 - 40 = +30
    assert ev > 0


def test_ev_jam_negative_with_poor_equity():
    ev = _ev_jam(0.20, 20.0, 80.0)
    # EV = 0.20 * 180 - 80 = 36 - 80 = -44
    assert ev < 0


def test_committed_action_is_jam_or_call():
    r = _pcc(hand_category='set', stack_bb=15.0, pot_bb=20.0)
    assert r.recommended_action in ('jam', 'call', 'call_not_yet_committed')


def test_air_always_folds():
    r = _pcc(hand_category='air', equity=0.05)
    assert r.recommended_action == 'fold'


def test_spr_stored():
    r = _pcc()
    assert r.spr == _spr(r.stack_bb, r.pot_bb)


def test_commit_threshold_stored():
    r = _pcc(hand_category='set')
    assert r.commit_spr_threshold == COMMIT_SPR_THRESHOLD['set']


def test_is_committed_stored():
    r = _pcc()
    assert isinstance(r.is_committed, bool)


def test_commitment_state_valid():
    r = _pcc()
    valid = {'deeply_committed', 'committed', 'approaching_commitment', 'not_committed'}
    assert r.commitment_state in valid


def test_ev_jam_stored():
    r = _pcc()
    expected = _ev_jam(r.equity, r.pot_bb, r.stack_bb)
    assert abs(r.ev_jam - expected) < 0.01


def test_min_equity_stored():
    r = _pcc()
    assert 0.0 < r.min_equity_to_jam < 1.0


def test_tips_populated():
    r = _pcc()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _pcc()
    line = pcc_one_liner(r)
    assert '[PCC' in line
    assert 'spr=' in line
    assert 'ev_jam=' in line


def test_nuts_jam_on_river():
    r = _pcc(hand_category='nuts', stack_bb=30.0, pot_bb=20.0,
              equity=0.95, street='river')
    assert r.is_committed is True


def test_monster_vs_small_stack_committed():
    r = _pcc(hand_category='flush', stack_bb=10.0, pot_bb=30.0)
    assert r.is_committed is True


def test_set_threshold_higher_than_middle_pair():
    assert COMMIT_SPR_THRESHOLD['set'] > COMMIT_SPR_THRESHOLD['middle_pair']


def test_combo_draw_threshold_higher_than_gutshot():
    assert COMMIT_SPR_THRESHOLD['combo_draw'] > COMMIT_SPR_THRESHOLD['gutshot']


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
