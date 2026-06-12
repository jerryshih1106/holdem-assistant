"""Tests for card_removal_effect_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.card_removal_effect_advisor import (
    analyze_card_removal, CardRemovalResult, cre_one_liner,
    _rank_from_card, _suit_from_card, _combo_reduction, _blocker_score,
    _call_ev_adjustment, BASE_COMBOS,
)


def _cre(**kw):
    defaults = dict(
        hero_cards=['Ah', '5s'], villain_range_type='value_heavy',
        pot_bb=20.0, call_size_bb=8.0,
        base_villain_fold=0.45, action_type='call',
    )
    defaults.update(kw)
    return analyze_card_removal(**defaults)


def test_returns_result():
    assert isinstance(_cre(), CardRemovalResult)


def test_rank_extraction():
    assert _rank_from_card('Ah') == 'A'
    assert _rank_from_card('Kd') == 'K'
    assert _rank_from_card('Ts') == 'T'


def test_suit_extraction():
    assert _suit_from_card('Ah') == 'h'
    assert _suit_from_card('Kd') == 'd'


def test_ace_reduces_combos():
    no_ace = _combo_reduction(['2s', '3d'], 'AKs')
    ace    = _combo_reduction(['Ah', '5s'], 'AKs')
    assert ace < no_ace


def test_no_blockers_full_combos():
    reduction = _combo_reduction(['2s', '3d'], 'AKs')
    assert reduction >= 0.90


def test_ace_blocker_score_high():
    score = _blocker_score(['Ah', '5s'], 'value_heavy')
    assert score >= 5


def test_no_blocker_score_low():
    score = _blocker_score(['2s', '3d'], 'value_heavy')
    assert score <= 5


def test_call_ev_adj_positive_with_blockers():
    adj = _call_ev_adjustment(20.0, 8.0, 0.45, 0.75)
    assert isinstance(adj, float)


def test_combo_reduction_in_range():
    r = _cre()
    assert 0.0 < r.combo_reduction <= 1.0


def test_blocker_score_in_range():
    r = _cre()
    assert 1 <= r.blocker_score <= 10


def test_ace_hand_gets_higher_score_than_low_cards():
    ace_score = _blocker_score(['Ah', 'Kd'], 'value_heavy')
    low_score = _blocker_score(['3s', '5d'], 'value_heavy')
    assert ace_score > low_score


def test_bluff_action_gives_bluff_rec():
    r = _cre(hero_cards=['Ah', 'Ks'], action_type='bluff')
    assert 'BLUFF' in r.recommended_adjustment


def test_tips_populated():
    r = _cre()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _cre()
    line = cre_one_liner(r)
    assert '[CRE' in line and 'score=' in line


def test_hero_cards_stored():
    r = _cre(hero_cards=['Kh', 'Qs'])
    assert 'Kh' in r.hero_cards


def test_flush_range_checks_suits():
    r = _cre(hero_cards=['Ah', 'Kh'], villain_range_type='flush_heavy')
    assert r.blocker_score >= 3


def test_base_combos_positive():
    for k, v in BASE_COMBOS.items():
        assert v > 0


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
