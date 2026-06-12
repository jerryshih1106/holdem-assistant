"""Tests for hand_vs_hand_equity_table.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.hand_vs_hand_equity_table import (
    get_equity, equity_advantage, analyze_equity_matchup,
    EquityMatchup, hvhe_one_liner, DRAW_CATEGORIES,
)


def _hvhe(**kw):
    defaults = dict(
        hero_category='top_pair',
        villain_category='flush_draw',
        street='flop',
        pot_bb=20.0,
        bet_size_pct=0.60,
    )
    defaults.update(kw)
    return analyze_equity_matchup(**defaults)


def test_returns_equity_matchup():
    r = _hvhe()
    assert isinstance(r, EquityMatchup)


def test_nuts_vs_air_high_equity():
    eq = get_equity('nuts', 'air', 'flop')
    assert eq >= 0.95


def test_air_vs_nuts_low_equity():
    eq = get_equity('air', 'nuts', 'flop')
    assert eq <= 0.05


def test_set_vs_flush_draw_hero_ahead():
    eq = get_equity('set', 'flush_draw', 'flop')
    assert eq >= 0.60


def test_flush_draw_vs_set_complement():
    eq1 = get_equity('set', 'flush_draw', 'flop')
    eq2 = get_equity('flush_draw', 'set', 'flop')
    assert abs(eq1 + eq2 - 1.0) < 0.01


def test_symmetry_via_reversed_lookup():
    eq_fwd = get_equity('top_pair', 'overpair', 'flop')
    eq_rev = get_equity('overpair', 'top_pair', 'flop')
    assert abs(eq_fwd + eq_rev - 1.0) < 0.02


def test_same_category_is_50pct():
    eq = get_equity('top_pair', 'top_pair', 'flop')
    assert abs(eq - 0.50) < 0.01


def test_overpair_beats_top_pair():
    eq = get_equity('overpair', 'top_pair', 'flop')
    assert eq > 0.60


def test_combo_draw_higher_than_flush_draw():
    eq_combo = get_equity('combo_draw', 'set', 'flop')
    eq_fd = get_equity('flush_draw', 'set', 'flop')
    assert eq_combo > eq_fd


def test_draw_equity_drops_on_turn():
    eq_flop = get_equity('flush_draw', 'top_pair', 'flop')
    eq_turn = get_equity('flush_draw', 'top_pair', 'turn')
    assert eq_turn < eq_flop


def test_draw_equity_drops_further_on_river():
    eq_flop = get_equity('flush_draw', 'overpair', 'flop')
    eq_river = get_equity('flush_draw', 'overpair', 'river')
    assert eq_river < eq_flop


def test_equity_bounded():
    for hero in ['nuts', 'set', 'air', 'flush_draw']:
        for villain in ['nuts', 'top_pair', 'air']:
            eq = get_equity(hero, villain, 'flop')
            assert 0.0 <= eq <= 1.0, f'{hero} vs {villain}: {eq}'


def test_equity_advantage_nuts_vs_air():
    adv = equity_advantage('nuts', 'air', 'flop')
    assert adv == 'massive_hero_advantage'


def test_equity_advantage_air_vs_nuts():
    adv = equity_advantage('air', 'nuts', 'flop')
    assert adv == 'hero_behind'


def test_equity_advantage_symmetric():
    adv1 = equity_advantage('flush_draw', 'set', 'flop')
    adv2 = equity_advantage('set', 'flush_draw', 'flop')
    # Set should be ahead, flush draw should be behind
    assert 'behind' in adv1 or 'villain' in adv1
    assert 'ahead' in adv2 or 'advantage' in adv2


def test_hero_equity_stored():
    r = _hvhe()
    assert 0.0 < r.hero_equity < 1.0


def test_villain_equity_is_complement():
    r = _hvhe()
    assert abs(r.hero_equity + r.villain_equity - 1.0) < 0.01


def test_advantage_stored():
    r = _hvhe()
    valid = {'massive_hero_advantage', 'hero_ahead', 'slight_hero_advantage',
             'neutral', 'slight_villain_advantage', 'hero_behind'}
    assert r.advantage in valid


def test_tips_populated():
    r = _hvhe()
    assert len(r.tips) >= 2


def test_action_implications_populated():
    r = _hvhe()
    assert len(r.action_implications) >= 1


def test_one_liner_format():
    r = _hvhe()
    line = hvhe_one_liner(r)
    assert '[HVHE' in line
    assert 'hero_eq=' in line


def test_nuts_vs_top_pair_hero_ahead():
    r = _hvhe(hero_category='nuts', villain_category='top_pair')
    assert r.hero_equity >= 0.90


def test_two_pair_vs_set_hero_behind():
    r = _hvhe(hero_category='two_pair', villain_category='set')
    assert r.hero_equity < 0.40


def test_draw_categories_populated():
    assert 'flush_draw' in DRAW_CATEGORIES
    assert 'oesd' in DRAW_CATEGORIES
    assert 'set' not in DRAW_CATEGORIES


def test_street_top_pair_vs_fd():
    eq_flop = get_equity('top_pair', 'flush_draw', 'flop')
    assert eq_flop >= 0.50  # top pair is favorite vs FD on flop


def test_unknown_matchup_returns_50():
    eq = get_equity('unknown_hand', 'another_unknown', 'flop')
    assert eq == 0.50


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
