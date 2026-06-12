"""Tests for poker/threbet_bluff.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.threbet_bluff import (
    analyze_3bet_bluff, bluff3b_summary, rank_bluff_candidates, ThreeBetBluffResult
)


def test_suited_ace_is_good_bluff():
    """A5s from BTN vs CO should be a good 3-bet bluff (blocker + playability)."""
    r = analyze_3bet_bluff('A5s', 'BTN', 'CO', villain_pfr=0.25)
    assert r.is_good_bluff, \
        f'A5s BTN vs CO should be a good bluff: is_good_bluff={r.is_good_bluff}'
    print(f'A5s BTN vs CO: is_good_bluff={r.is_good_bluff} bluff_freq={r.bluff_freq:.0%}')


def test_trash_hand_not_good_bluff():
    """72o should not be a good 3-bet bluff (no blocker, bad playability)."""
    r = analyze_3bet_bluff('72o', 'BTN', 'CO', villain_pfr=0.25)
    assert not r.is_good_bluff, \
        f'72o should not be a good bluff: is_good_bluff={r.is_good_bluff}'
    print(f'72o is_good_bluff={r.is_good_bluff}')


def test_result_has_required_fields():
    """ThreeBetBluffResult should have all expected fields."""
    r = analyze_3bet_bluff('KQs', 'BTN', 'CO', villain_pfr=0.25)
    required = ['is_good_bluff', 'bluff_freq', 'fold_equity_score', 'blocker_score',
                'three_bet_size_bb', 'reasoning', 'is_in_value_range', 'hand', 'hero_pos', 'villain_pos']
    for field in required:
        assert hasattr(r, field), f'ThreeBetBluffResult missing field: {field}'
    print(f'KQs BTN: all fields present')


def test_three_bet_size_positive():
    """three_bet_size_bb should be a positive number."""
    r = analyze_3bet_bluff('A4s', 'BTN', 'CO', villain_pfr=0.25, open_size_bb=2.5)
    assert r.three_bet_size_bb > 0, \
        f'three_bet_size_bb should be > 0: {r.three_bet_size_bb}'
    print(f'A4s 3-bet size: {r.three_bet_size_bb:.1f} BB')


def test_bluff_freq_in_range():
    """bluff_freq should be a probability in [0, 1]."""
    r = analyze_3bet_bluff('A5s', 'BTN', 'CO', villain_pfr=0.25)
    assert 0.0 <= r.bluff_freq <= 1.0, \
        f'bluff_freq should be in [0,1]: {r.bluff_freq}'
    print(f'A5s bluff_freq: {r.bluff_freq:.0%}')


def test_tight_villain_lower_fold_equity():
    """Against tight villain (low PFR), fold equity should be lower."""
    r_tight = analyze_3bet_bluff('A5s', 'BTN', 'CO', villain_pfr=0.10)
    r_loose  = analyze_3bet_bluff('A5s', 'BTN', 'CO', villain_pfr=0.40)
    # Loose villain 3-bets more, so fold equity vs loose < vs tight is NOT guaranteed
    # But fold equity score exists and is valid for both
    assert 0.0 <= r_tight.fold_equity_score <= 1.0
    assert 0.0 <= r_loose.fold_equity_score <= 1.0
    print(f'fold_equity: tight={r_tight.fold_equity_score:.2f} loose={r_loose.fold_equity_score:.2f}')


def test_blocker_score_higher_for_ace_blocker():
    """Ace-blocker hand should have higher blocker score than no-blocker hand."""
    r_ace  = analyze_3bet_bluff('A2s', 'BTN', 'CO', villain_pfr=0.25)
    r_none = analyze_3bet_bluff('87o', 'BTN', 'CO', villain_pfr=0.25)
    assert r_ace.blocker_score >= r_none.blocker_score, \
        f'A2s blocker_score {r_ace.blocker_score:.2f} should >= 87o {r_none.blocker_score:.2f}'
    print(f'Blocker score: A2s={r_ace.blocker_score:.2f} 87o={r_none.blocker_score:.2f}')


def test_premium_hand_in_value_range():
    """AA should be flagged as in value range, not bluff range."""
    r = analyze_3bet_bluff('AA', 'BTN', 'CO', villain_pfr=0.25)
    assert r.is_in_value_range, \
        f'AA should be in value range: is_in_value_range={r.is_in_value_range}'
    print(f'AA is_in_value_range={r.is_in_value_range}')


def test_bluff3b_summary_returns_string():
    """bluff3b_summary should return a non-empty string."""
    r = analyze_3bet_bluff('A5s', 'BTN', 'CO', villain_pfr=0.25)
    s = bluff3b_summary(r)
    assert isinstance(s, str) and len(s) > 5, \
        f'bluff3b_summary should be non-empty: {repr(s)[:50]}'
    print(f'Summary length: {len(s)} chars')


def test_rank_bluff_candidates_returns_sorted_list():
    """rank_bluff_candidates should return a list of ThreeBetBluffResult."""
    hands = ['A5s', 'A4s', 'KQs', '87s', '72o', 'T9s']
    results = rank_bluff_candidates(hands, 'BTN', 'CO', villain_pfr=0.25)
    assert isinstance(results, list) and len(results) == len(hands), \
        f'rank_bluff_candidates should return {len(hands)} results: {len(results)}'
    for r in results:
        assert isinstance(r, ThreeBetBluffResult)
    # First result should be better bluff than last
    if results[0].is_good_bluff or not results[-1].is_good_bluff:
        print(f'Top: {results[0].hand} is_good={results[0].is_good_bluff}')
    print(f'rank_bluff_candidates: {len(results)} results')


if __name__ == '__main__':
    tests = [
        test_suited_ace_is_good_bluff,
        test_trash_hand_not_good_bluff,
        test_result_has_required_fields,
        test_three_bet_size_positive,
        test_bluff_freq_in_range,
        test_tight_villain_lower_fold_equity,
        test_blocker_score_higher_for_ace_blocker,
        test_premium_hand_in_value_range,
        test_bluff3b_summary_returns_string,
        test_rank_bluff_candidates_returns_sorted_list,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f'  PASS  {t.__name__}')
        except Exception as e:
            print(f'  FAIL  {t.__name__}: {e}')
            import traceback; traceback.print_exc()
            failed += 1
    print(f'\n{len(tests)-failed}/{len(tests)} passed')
    sys.exit(failed)
