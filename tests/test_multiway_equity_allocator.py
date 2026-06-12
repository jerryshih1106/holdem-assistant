"""Tests for multiway_equity_allocator.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.multiway_equity_allocator import (
    analyze_multiway_equity, MultiwayEquityResult, mea_one_liner,
    _multiway_equity, _should_continue, _implied_odds_bonus_multiway,
    BASE_EQUITY_HU, EQUITY_RETENTION_PER_OPP, MULTIWAY_CBET_REDUCTION,
)


def _mea(**kw):
    defaults = dict(
        hand_category='top_pair',
        n_opponents=2,
        board_texture='dry',
        hero_position='ip',
        pot_bb=20.0,
        stack_bb=100.0,
        villain_bet_bb=0.0,
        hero_is_pfr=True,
    )
    defaults.update(kw)
    return analyze_multiway_equity(**defaults)


def test_returns_multiway_equity_result():
    r = _mea()
    assert isinstance(r, MultiwayEquityResult)


def test_equity_drops_with_more_opponents():
    eq2 = _multiway_equity('top_pair', 2)
    eq3 = _multiway_equity('top_pair', 3)
    assert eq2 > eq3


def test_nuts_retains_equity():
    eq1 = _multiway_equity('nuts', 1)
    eq4 = _multiway_equity('nuts', 4)
    assert eq4 >= 0.90  # nuts stays nuts


def test_air_low_equity_any_count():
    eq = _multiway_equity('air', 2)
    assert eq < 0.20


def test_hu_equity_equals_base():
    eq = _multiway_equity('top_pair', 1)
    base = BASE_EQUITY_HU.get('top_pair', 0.65)
    assert abs(eq - base) < 0.01


def test_set_drops_slower_than_top_pair():
    set_drop = _multiway_equity('top_pair', 1) - _multiway_equity('top_pair', 3)
    tp_drop = _multiway_equity('set', 1) - _multiway_equity('set', 3)
    assert set_drop > tp_drop  # top_pair loses more equity multiway


def test_should_continue_strong_3way():
    result = _should_continue('set', 2, 0.75)
    assert result is True


def test_should_not_continue_weak_4way():
    result = _should_continue('air', 4, 0.10)
    assert result is False


def test_should_continue_with_pot_odds():
    result = _should_continue('flush_draw', 2, 0.38, pot_odds=0.30)
    assert result is True


def test_implied_odds_bonus_draws():
    bonus = _implied_odds_bonus_multiway('flush_draw', 3, 20.0, 100.0)
    assert bonus > 0


def test_implied_odds_zero_for_value():
    bonus = _implied_odds_bonus_multiway('top_pair', 3, 20.0, 100.0)
    assert bonus == 0.0


def test_more_opponents_more_implied():
    b2 = _implied_odds_bonus_multiway('flush_draw', 2, 20.0, 100.0)
    b4 = _implied_odds_bonus_multiway('flush_draw', 4, 20.0, 100.0)
    assert b4 > b2


def test_cbet_reduction_3way():
    reduction = MULTIWAY_CBET_REDUCTION.get(3, 1.0)
    assert reduction < 1.0


def test_cbet_freq_lower_multiway():
    r2 = _mea(n_opponents=1)
    r4 = _mea(n_opponents=3)
    assert r4.cbet_frequency < r2.cbet_frequency


def test_equity_loss_stored():
    r = _mea()
    assert r.equity_loss >= 0


def test_hu_equity_stored():
    r = _mea(hand_category='top_pair')
    assert abs(r.hu_equity - BASE_EQUITY_HU['top_pair']) < 0.01


def test_multiway_equity_lower_than_hu():
    r = _mea(n_opponents=2)
    assert r.multiway_equity <= r.hu_equity


def test_tips_populated():
    r = _mea()
    assert len(r.tips) >= 2


def test_draw_multiway_extra_tip():
    r_draw = _mea(hand_category='flush_draw')
    assert len(r_draw.tips) >= 3


def test_one_liner_format():
    r = _mea()
    line = mea_one_liner(r)
    assert '[MEA' in line
    assert 'eq=' in line
    assert 'cbet=' in line


def test_total_players_stored():
    r = _mea(n_opponents=2)
    assert r.n_total_players == 3


def test_set_continues_multiway():
    r = _mea(hand_category='set', n_opponents=3)
    assert r.should_continue is True


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
