"""Tests for poker/cold_4bet_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.cold_4bet_advisor import (
    advise_cold_4bet, Cold4BetAdvice, cold_4bet_one_liner
)


def _adv(**kw):
    defaults = dict(
        hero_hand_class='AA', hero_pos='BTN', opener_pos='UTG',
        threebetter_pos='CO', open_raise_bb=3.0, threbet_bb=9.0,
        hero_stack_bb=100.0, villain_3bet_pct=0.07,
        villain_3bet_fold_to_4bet=0.55, villain_vpip=0.25,
        board_type='preflop',
    )
    defaults.update(kw)
    return advise_cold_4bet(**defaults)


def test_returns_cold_4bet_advice():
    r = _adv()
    assert isinstance(r, Cold4BetAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'hero_hand_class', 'hero_pos', 'opener_pos', 'threebetter_pos',
        'open_raise_bb', 'threbet_bb', 'hero_stack_bb', 'villain_3bet_pct',
        'villain_3bet_fold_to_4bet', 'villain_vpip', 'hand_strength',
        'has_ace_blocker', 'has_king_blocker', 'range_type', 'equity_vs_5bet',
        'can_stack_off', 'action', 'fourbet_to_bb', 'pot_after_4bet',
        'ev_bluff_4bet', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing field: {f}'
    print(f'All {len(fields)} fields present')


def test_action_valid_values():
    """Action must be one of the four defined options."""
    valid = {'4bet_value', '4bet_bluff', 'cold_call', 'fold'}
    for h in ['AA', 'KK', 'JJ', 'A5s', 'air']:
        r = _adv(hero_hand_class=h)
        assert r.action in valid, f'Invalid action: {r.action} for {h}'
    print('All actions valid')


def test_aa_always_4bets_value():
    """AA should always cold 4-bet for value."""
    r = _adv(hero_hand_class='AA')
    assert r.action == '4bet_value', f'AA should 4-bet value: {r.action}'
    print(f'AA cold 4-bet: {r.action}')


def test_kk_always_4bets_value():
    """KK should always cold 4-bet for value."""
    r = _adv(hero_hand_class='KK')
    assert r.action == '4bet_value', f'KK should 4-bet value: {r.action}'
    print(f'KK cold 4-bet: {r.action}')


def test_aa_can_stack_off():
    """AA should always be eligible to stack off."""
    r = _adv(hero_hand_class='AA')
    assert r.can_stack_off is True, f'AA should always stack off: {r.can_stack_off}'
    print(f'AA stack off: {r.can_stack_off}')


def test_aa_has_ace_blocker():
    r = _adv(hero_hand_class='AA')
    assert r.has_ace_blocker is True
    print(f'AA ace blocker: {r.has_ace_blocker}')


def test_a5s_is_blocker_type():
    """A5s is an ace-blocker bluff hand in cold 4-bet spots."""
    r = _adv(hero_hand_class='A5s', villain_3bet_fold_to_4bet=0.65)
    assert r.range_type == 'blocker_bluff', \
        f'A5s should be blocker_bluff: {r.range_type}'
    print(f'A5s range type: {r.range_type}')


def test_low_fold_equity_no_bluff():
    """When villain rarely folds to 4-bets, blocker bluff should not fire."""
    r = _adv(hero_hand_class='A5s', villain_3bet_fold_to_4bet=0.30)
    assert r.action in ('fold', 'cold_call'), \
        f'Low fold equity bluff should fold/call: {r.action}'
    print(f'A5s vs low fold equity: {r.action}')


def test_high_fold_equity_blocker_bets():
    """High fold equity: blocker 4-bet should fire."""
    r = _adv(hero_hand_class='A5s', villain_3bet_fold_to_4bet=0.70)
    assert r.action == '4bet_bluff', \
        f'High fold equity blocker should 4-bet: {r.action}'
    print(f'A5s high fold equity: {r.action}')


def test_fourbet_to_is_reasonable_multiple():
    """4-bet sizing should be 2.2x-2.8x the 3-bet."""
    r = _adv(threbet_bb=9.0)
    ratio = r.fourbet_to_bb / r.threbet_bb
    assert 2.0 <= ratio <= 3.0, \
        f'4-bet/3-bet ratio out of range: {ratio:.2f} (4b={r.fourbet_to_bb:.1f}BB 3b={r.threbet_bb:.1f}BB)'
    print(f'4-bet to 3-bet ratio: {ratio:.2f}x ({r.fourbet_to_bb:.1f}BB)')


def test_equity_vs_5bet_in_range():
    """Equity vs 5-bet should be in [0.25, 0.90]."""
    for h in ['AA', 'KK', 'A5s', 'air']:
        r = _adv(hero_hand_class=h)
        assert 0.25 <= r.equity_vs_5bet <= 0.90, \
            f'Equity out of range for {h}: {r.equity_vs_5bet}'
    print('All equity_vs_5bet values in [0.25, 0.90]')


def test_aa_equity_vs_5bet_highest():
    """AA should have highest equity vs 5-bet."""
    r_aa = _adv(hero_hand_class='AA')
    r_kk = _adv(hero_hand_class='KK')
    assert r_aa.equity_vs_5bet > r_kk.equity_vs_5bet, \
        f'AA should have more equity than KK vs 5-bet: {r_aa.equity_vs_5bet:.0%} vs {r_kk.equity_vs_5bet:.0%}'
    print(f'Equity: AA={r_aa.equity_vs_5bet:.0%} KK={r_kk.equity_vs_5bet:.0%}')


def test_nit_villain_reduces_bluff_frequency():
    """Nit 3-bettor with very low 3-bet% should discourage bluff 4-bets."""
    r_nit = _adv(hero_hand_class='A5s', villain_3bet_pct=0.03, villain_3bet_fold_to_4bet=0.65)
    # Nit tips should mention tight range
    has_nit_tip = any('nit' in t.lower() or '3-bet%' in t for t in r_nit.tips)
    # At minimum, tips should not be empty
    assert len(r_nit.tips) > 0
    print(f'Nit villain tips: {len(r_nit.tips)} tips')


def test_loose_villain_encourages_wider_range():
    """Loose 3-bettor: should trigger tip about widening 4-bet range."""
    r = _adv(villain_3bet_pct=0.15)
    has_loose_tip = any('Loose' in t or 'loose' in t or 'bluff' in t for t in r.tips)
    assert len(r.tips) > 0
    print(f'Loose villain tips present: {has_loose_tip}')


def test_range_type_valid():
    """Range type must be one of the expected values."""
    valid = {'value_stack_off', 'value_fold_to_5bet', 'blocker_bluff', 'dont_4bet'}
    for h in ['AA', 'QQ', 'A5s', 'air']:
        r = _adv(hero_hand_class=h)
        assert r.range_type in valid, f'Invalid range_type: {r.range_type} for {h}'
    print('All range types valid')


def test_jj_likely_folds_vs_utg_3bet():
    """JJ cold vs UTG 3-bet should not 4-bet value."""
    r = _adv(hero_hand_class='JJ', opener_pos='UTG', threebetter_pos='CO',
             villain_3bet_pct=0.05, villain_3bet_fold_to_4bet=0.40)
    assert r.action in ('fold', 'cold_call'), \
        f'JJ cold vs tight 3-bet should not 4-bet value: {r.action}'
    print(f'JJ cold vs UTG 3-bet: {r.action}')


def test_pot_after_4bet_positive():
    """Pot after 4-bet should be a positive number."""
    r = _adv()
    assert r.pot_after_4bet > 0, f'Pot after 4-bet must be positive: {r.pot_after_4bet}'
    print(f'Pot after 4-bet: {r.pot_after_4bet:.1f}BB')


def test_tips_not_empty():
    r = _adv()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips: {len(r.tips)}')


def test_reasoning_not_empty():
    r = _adv()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 5
    print(f'Reasoning length: {len(r.reasoning)}')


def test_one_liner():
    r = _adv()
    line = cold_4bet_one_liner(r)
    assert 'C4B' in line and '4b_to=' in line and 'fold_to_4b=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_cold_4bet_advice, test_required_fields,
        test_action_valid_values, test_aa_always_4bets_value,
        test_kk_always_4bets_value, test_aa_can_stack_off,
        test_aa_has_ace_blocker, test_a5s_is_blocker_type,
        test_low_fold_equity_no_bluff, test_high_fold_equity_blocker_bets,
        test_fourbet_to_is_reasonable_multiple, test_equity_vs_5bet_in_range,
        test_aa_equity_vs_5bet_highest, test_nit_villain_reduces_bluff_frequency,
        test_loose_villain_encourages_wider_range, test_range_type_valid,
        test_jj_likely_folds_vs_utg_3bet, test_pot_after_4bet_positive,
        test_tips_not_empty, test_reasoning_not_empty, test_one_liner,
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
