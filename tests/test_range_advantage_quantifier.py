"""Tests for range_advantage_quantifier.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.range_advantage_quantifier import (
    quantify_range_advantage, RangeAdvantage, raq_one_liner,
    _high_card_score, _range_advantage_score, _normalize_score,
    _range_advantage_label, _who_has_advantage, _betting_frequency_recommendation,
    HIGH_CARD_ADVANTAGE_SCORE,
)


def _raq(**kw):
    defaults = dict(
        aggressor_position='btn',
        defender_position='bb',
        board_high_card=14,
        board_mid_card=10,
        board_low_card=7,
        board_texture='dry',
        is_paired_board=False,
        is_monotone=False,
    )
    defaults.update(kw)
    return quantify_range_advantage(**defaults)


def test_returns_range_advantage():
    r = _raq()
    assert isinstance(r, RangeAdvantage)


def test_ace_high_card_positive_score():
    assert HIGH_CARD_ADVANTAGE_SCORE[14] > 0


def test_low_high_card_negative_score():
    assert HIGH_CARD_ADVANTAGE_SCORE[2] < 0


def test_high_card_score_ace_wins():
    score_ace = _high_card_score(14, 10)
    score_two = _high_card_score(2, 3)
    assert score_ace > score_two


def test_normalize_positive_raw_above_5():
    score = _normalize_score(3)
    assert score > 5


def test_normalize_negative_raw_below_5():
    score = _normalize_score(-3)
    assert score < 5


def test_normalize_zero_is_5():
    score = _normalize_score(0)
    assert score == 5


def test_normalize_capped_1_to_10():
    assert _normalize_score(100) == 10
    assert _normalize_score(-100) == 1


def test_label_massive_aggressor():
    assert _range_advantage_label(9) == 'massive_aggressor_advantage'


def test_label_neutral():
    assert _range_advantage_label(5) == 'neutral'


def test_label_massive_defender():
    assert _range_advantage_label(2) == 'massive_defender_advantage'


def test_who_has_advantage_aggressor():
    who = _who_has_advantage(8, 'btn', 'bb')
    assert who == 'btn'


def test_who_has_advantage_defender():
    who = _who_has_advantage(3, 'btn', 'bb')
    assert who == 'bb'


def test_who_has_advantage_neutral():
    who = _who_has_advantage(5, 'btn', 'bb')
    assert who == 'neutral'


def test_bet_freq_aggressor_increases_with_score():
    low = _betting_frequency_recommendation(3, True)
    high = _betting_frequency_recommendation(9, True)
    assert high >= low


def test_bet_freq_defender_increases_low_score():
    high_score = _betting_frequency_recommendation(9, False)
    low_score = _betting_frequency_recommendation(3, False)
    assert low_score >= high_score


def test_ace_high_board_aggressor_advantage():
    r = _raq(board_high_card=14, board_mid_card=10, board_low_card=5)
    assert r.score_1_to_10 >= 6


def test_low_board_defender_advantage():
    r = _raq(board_high_card=7, board_mid_card=4, board_low_card=2,
              board_texture='wet')
    assert r.score_1_to_10 <= 4


def test_score_stored():
    r = _raq()
    assert 1 <= r.score_1_to_10 <= 10


def test_label_stored():
    r = _raq()
    assert r.advantage_label in ('massive_aggressor_advantage', 'moderate_aggressor_advantage',
                                  'neutral', 'moderate_defender_advantage', 'massive_defender_advantage')


def test_bet_freq_stored():
    r = _raq()
    assert 0.15 <= r.aggressor_bet_freq <= 0.85


def test_tips_populated():
    r = _raq()
    assert len(r.tips) >= 3


def test_one_liner_format():
    r = _raq()
    line = raq_one_liner(r)
    assert '[RAQ' in line
    assert 'score=' in line
    assert 'agg_bet=' in line


def test_one_liner_contains_positions():
    r = _raq(aggressor_position='btn', defender_position='bb')
    line = raq_one_liner(r)
    assert 'btn' in line and 'bb' in line


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
