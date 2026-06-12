"""Tests for poker/monotone_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.monotone_advisor import (
    analyze_monotone, monotone_one_liner, MonotoneAdvice
)


def _mono(hole, board, equity=0.50, ip=True, fold_to_bet=0.45, street='flop'):
    return analyze_monotone(
        hole_cards=hole,
        community=board,
        pot_bb=12.0,
        hero_equity=equity,
        in_position=ip,
        villain_fold_to_bet=fold_to_bet,
        street=street,
    )


# Three-heart monotone board
_BOARD_HH = ['Jh', '7h', '2h']
# Three-spade monotone board
_BOARD_SS = ['As', 'Ks', '5s']


def test_returns_monotone_advice():
    """analyze_monotone should return a MonotoneAdvice."""
    r = _mono(['Ah', 'Kd'], _BOARD_HH)
    assert isinstance(r, MonotoneAdvice), f'Expected MonotoneAdvice: {type(r)}'
    print(f'type: {type(r).__name__}')


def test_required_fields():
    """MonotoneAdvice should have all documented fields."""
    r = _mono(['Ah', 'Kd'], _BOARD_HH)
    fields = [
        'is_monotone', 'board_suit', 'num_suited_board_cards',
        'hero_has_nut_flush', 'hero_has_made_flush', 'hero_has_blocker',
        'hero_flush_rank', 'bet_size_bb', 'bet_size_pct',
        'cbet_freq_adj', 'check_call_threshold',
        'ev_bet', 'ev_check', 'action', 'hand_category',
        'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'MonotoneAdvice missing field: {f}'
    print(f'All {len(fields)} fields present')


def test_board_detected_monotone():
    """Three-heart board should be detected as monotone."""
    r = _mono(['Ah', 'Kd'], _BOARD_HH)
    assert r.is_monotone is True, f'Three-heart board should be monotone: {r.is_monotone}'
    assert r.board_suit == 'h', f'Board suit should be h: {r.board_suit}'
    print(f'Monotone detected: suit={r.board_suit} n={r.num_suited_board_cards}')


def test_non_monotone_board():
    """Rainbow board should not be detected as monotone."""
    r = _mono(['Ah', 'Kd'], ['Jh', '7c', '2d'])
    assert r.is_monotone is False, f'Rainbow board should not be monotone: {r.is_monotone}'
    print(f'Rainbow board: is_monotone={r.is_monotone}')


def test_nut_flush_detected():
    """Ah on heart board should have nut flush with another heart."""
    r = _mono(['Ah', '2h'], _BOARD_HH)
    assert r.hero_has_nut_flush is True, \
        f'Ah2h should have nut flush on heart board: {r.hero_has_nut_flush}'
    assert r.hand_category == 'nut_flush', \
        f'Should be nut_flush: {r.hand_category}'
    print(f'Nut flush detected: {r.hero_has_nut_flush} category={r.hand_category}')


def test_nut_flush_bets():
    """Nut flush should bet."""
    r = _mono(['Ah', '2h'], _BOARD_HH)
    assert r.action == 'bet', f'Nut flush should bet: {r.action}'
    print(f'Nut flush action: {r.action}')


def test_no_flush_holding_checks():
    """No card of board suit should produce check-fold or check-call for air."""
    r = _mono(['Ks', 'Qd'], _BOARD_HH, equity=0.20)  # no hearts
    assert r.action in ('check-fold', 'check-call'), \
        f'No flush low equity should check: {r.action}'
    assert r.hand_category == 'air', \
        f'No flush low equity should be air: {r.hand_category}'
    print(f'No flush low equity: action={r.action} category={r.hand_category}')


def test_blocker_detected():
    """One heart in hand = blocker."""
    r = _mono(['Ah', 'Kd'], _BOARD_HH)  # only Ah, not two hearts
    assert r.hero_has_blocker is True, \
        f'Ah with no second heart should be blocker: {r.hero_has_blocker}'
    assert r.hand_category == 'blocker', \
        f'Should be blocker: {r.hand_category}'
    print(f'Blocker detected: {r.hero_has_blocker} category={r.hand_category}')


def test_blocker_uses_small_sizing():
    """Blocker bet should use smaller sizing (~33% pot)."""
    r = _mono(['Ah', 'Kd'], _BOARD_HH)
    assert r.bet_size_pct <= 0.40, \
        f'Blocker bet should be small (<=40% pot): {r.bet_size_pct}'
    print(f'Blocker sizing: {r.bet_size_pct:.0%} pot')


def test_made_flush_detected():
    """Two hearts in hand = made flush."""
    r = _mono(['Kh', 'Qh'], _BOARD_HH)
    assert r.hero_has_made_flush is True, \
        f'KhQh should have made flush on heart board: {r.hero_has_made_flush}'
    print(f'Made flush: {r.hero_has_made_flush} rank={r.hero_flush_rank}')


def test_made_flush_bets():
    """Made flush should bet."""
    r = _mono(['Kh', 'Qh'], _BOARD_HH, equity=0.70)
    assert r.action == 'bet', f'Made flush should bet: {r.action}'
    print(f'Made flush action: {r.action}')


def test_cbet_freq_lower_than_standard():
    """Cbet frequency on monotone board should be < 60% (standard)."""
    r = _mono(['Ah', 'Kd'], _BOARD_HH)
    assert r.cbet_freq_adj < 0.60, \
        f'Monotone cbet freq should be < 0.60: {r.cbet_freq_adj}'
    print(f'Monotone cbet_freq: {r.cbet_freq_adj:.0%} (standard ~60%)')


def test_bet_size_positive():
    """Bet size should be positive."""
    r = _mono(['Kh', 'Qh'], _BOARD_HH)
    assert r.bet_size_bb > 0, f'Bet size should be > 0: {r.bet_size_bb}'
    print(f'bet_size_bb: {r.bet_size_bb:.1f}')


def test_ev_check_positive_for_high_equity():
    """EV of checking should be positive with high equity."""
    r = _mono(['Ah', '2h'], _BOARD_HH, equity=0.80)
    assert r.ev_check > 0, f'ev_check should be > 0: {r.ev_check}'
    print(f'ev_check: {r.ev_check:.2f}')


def test_oop_air_check_folds():
    """OOP air on monotone board should check-fold."""
    r = _mono(['Ks', 'Qd'], _BOARD_HH, equity=0.18, ip=False)
    assert r.action == 'check-fold', \
        f'OOP air should check-fold: {r.action}'
    print(f'OOP air action: {r.action}')


def test_nut_flush_bigger_size_on_river():
    """Nut flush should use larger sizing on river than flop."""
    r_flop  = _mono(['Ah', '2h'], _BOARD_HH, street='flop')
    r_river = _mono(['Ah', '2h'], _BOARD_HH, street='river')
    assert r_river.bet_size_pct >= r_flop.bet_size_pct, \
        f'River size >= flop size: {r_river.bet_size_pct} vs {r_flop.bet_size_pct}'
    print(f'Nut flush size: flop={r_flop.bet_size_pct:.0%} river={r_river.bet_size_pct:.0%}')


def test_hand_category_is_valid():
    """hand_category should be one of the valid categories."""
    valid = {'nut_flush', 'made_flush', 'blocker', 'air', 'strong_non_flush'}
    for hole in (['Ah', '2h'], ['Kh', 'Qh'], ['Ah', 'Kd'], ['Ks', 'Qd']):
        r = _mono(hole, _BOARD_HH)
        assert r.hand_category in valid, \
            f'{hole} category should be valid: {r.hand_category}'
    print('All hand categories valid')


def test_action_is_valid():
    """action should be one of the valid actions."""
    valid = {'bet', 'check-call', 'check-fold', 'raise'}
    for equity in (0.85, 0.50, 0.15):
        r = _mono(['Ks', 'Qd'], _BOARD_HH, equity=equity)
        assert r.action in valid, \
            f'action for equity={equity} should be valid: {r.action}'
    print('All actions valid')


def test_reasoning_is_string():
    """reasoning should be a non-empty string."""
    r = _mono(['Kh', 'Qh'], _BOARD_HH)
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'reasoning: {r.reasoning[:60]}')


def test_tips_is_list():
    """tips should be a non-empty list."""
    r = _mono(['Kh', 'Qh'], _BOARD_HH)
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'tips count: {len(r.tips)}')


def test_monotone_one_liner():
    """monotone_one_liner should return a non-empty string."""
    r = _mono(['Kh', 'Qh'], _BOARD_HH)
    line = monotone_one_liner(r)
    assert isinstance(line, str) and len(line) > 5
    print(f'one_liner: {line}')


def test_spade_board_detected():
    """Spade board should be detected correctly."""
    r = _mono(['As', 'Ks'], _BOARD_SS)
    assert r.is_monotone is True and r.board_suit == 's', \
        f'Spade board: is_mono={r.is_monotone} suit={r.board_suit}'
    print(f'Spade board detected: suit={r.board_suit}')


if __name__ == '__main__':
    tests = [
        test_returns_monotone_advice,
        test_required_fields,
        test_board_detected_monotone,
        test_non_monotone_board,
        test_nut_flush_detected,
        test_nut_flush_bets,
        test_no_flush_holding_checks,
        test_blocker_detected,
        test_blocker_uses_small_sizing,
        test_made_flush_detected,
        test_made_flush_bets,
        test_cbet_freq_lower_than_standard,
        test_bet_size_positive,
        test_ev_check_positive_for_high_equity,
        test_oop_air_check_folds,
        test_nut_flush_bigger_size_on_river,
        test_hand_category_is_valid,
        test_action_is_valid,
        test_reasoning_is_string,
        test_tips_is_list,
        test_monotone_one_liner,
        test_spade_board_detected,
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
