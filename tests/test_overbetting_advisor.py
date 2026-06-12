"""Tests for overbetting_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.overbetting_advisor import (
    advise_overbet, OverbetAdvice, oba_one_liner,
    _polarization_score, _optimal_overbet_size, _bluff_to_value_ratio,
    _overbet_ev, OVERBET_VALUE_HANDS, MIN_POLARIZATION_FOR_OVERBET,
)


def _oba(**kw):
    defaults = dict(
        hand_category='nuts', board_texture='dry', street='river',
        hero_is_pfr=True, hero_position='ip', spr=3.0, pot_bb=30.0,
        hero_equity=0.90, villain_call_freq=0.40,
    )
    defaults.update(kw)
    return advise_overbet(**defaults)


def test_returns_overbet_advice():
    assert isinstance(_oba(), OverbetAdvice)


def test_nuts_river_should_overbet():
    r = _oba(hand_category='nuts', street='river')
    assert r.should_overbet is True


def test_top_pair_not_overbet():
    r = _oba(hand_category='top_pair', street='river')
    assert r.should_overbet is False


def test_polarization_score_nuts_high():
    score = _polarization_score('nuts', 'dry', True, 'river')
    assert score >= MIN_POLARIZATION_FOR_OVERBET


def test_polarization_score_top_pair_lower():
    score_nuts = _polarization_score('nuts', 'dry', True, 'river')
    score_tp = _polarization_score('top_pair', 'dry', True, 'river')
    assert score_nuts > score_tp


def test_river_higher_polarization_than_flop():
    score_river = _polarization_score('nuts', 'dry', True, 'river')
    score_flop = _polarization_score('nuts', 'dry', True, 'flop')
    assert score_river > score_flop


def test_pfr_higher_polarization():
    score_pfr = _polarization_score('set', 'dry', True, 'river')
    score_caller = _polarization_score('set', 'dry', False, 'river')
    assert score_pfr >= score_caller


def test_bluff_to_value_ratio():
    bluffs, fold_req = _bluff_to_value_ratio(1.5)
    # alpha = 1.5/2.5 = 0.60, bluffs = 1-0.60 = 0.40
    assert abs(fold_req - 0.60) < 0.01
    assert abs(bluffs - 0.40) < 0.01


def test_overbet_ev_positive_high_equity():
    ev = _overbet_ev(0.90, 30.0, 1.5, 0.40)
    assert ev > 0


def test_optimal_size_river_nuts():
    size = _optimal_overbet_size('river', 'nuts', 3.0)
    assert size >= 1.25


def test_bet_bb_proportional():
    r = _oba(pot_bb=20.0)
    if r.should_overbet:
        assert r.bet_bb == round(20.0 * r.recommended_size, 1)


def test_oop_flop_no_overbet():
    r = _oba(hero_position='oop', street='flop', hand_category='nuts')
    assert r.should_overbet is False


def test_overbet_value_hands_set():
    assert 'nuts' in OVERBET_VALUE_HANDS
    assert 'set' in OVERBET_VALUE_HANDS


def test_polarization_score_in_range():
    score = _polarization_score('flush', 'wet', True, 'turn')
    assert 0.0 <= score <= 1.0


def test_tips_populated():
    r = _oba()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _oba()
    line = oba_one_liner(r)
    assert '[OBA' in line
    assert 'pol=' in line


def test_turn_overbet_builds_pot():
    r = _oba(street='turn', hand_category='flush')
    if r.should_overbet:
        assert 'TURN SETUP' in ' '.join(r.tips) or any('turn' in t.lower() for t in r.tips)


def test_no_overbet_tips_has_reason():
    r = _oba(hand_category='middle_pair')
    assert any('NO OVERBET' in t or 'standard' in t.lower() for t in r.tips)


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
