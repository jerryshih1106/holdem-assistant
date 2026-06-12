"""Tests for poker/oop_turn_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.oop_turn_advisor import (
    advise_oop_turn, OopTurnAdvice, oop_turn_one_liner
)


def _adv(**kw):
    defaults = dict(
        flop_sequence='hero_bet_called',
        hero_hand_class='top_pair',
        turn_card_type='blank',
        hero_equity=0.60,
        spr=3.5,
        villain_af=2.0,
        villain_cbet_pct=0.55,
        board_type='medium',
        hero_has_draw=False,
        pot_bb=20.0,
    )
    defaults.update(kw)
    return advise_oop_turn(**defaults)


def test_returns_oop_turn_advice():
    r = _adv()
    assert isinstance(r, OopTurnAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'flop_sequence', 'hero_hand_class', 'turn_card_type',
        'hero_equity', 'spr', 'villain_af', 'board_type', 'hero_has_draw',
        'pot_bb', 'action', 'action_frequency', 'bet_size_pct', 'bet_size_bb',
        'turn_card_modifier', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_strong_hand_bets_or_check_raises():
    """Set-level hand should bet or check-raise."""
    r = _adv(hero_hand_class='set', hero_equity=0.80, flop_sequence='hero_bet_called')
    assert r.action in ('bet', 'check_raise'), \
        f'Set should bet or CR: {r.action}'
    print(f'Set action: {r.action}')


def test_weak_hand_check_folds():
    """Air after betting flop should usually check-fold on blank turn."""
    r = _adv(hero_hand_class='air', hero_equity=0.15, turn_card_type='blank')
    assert r.action == 'check_fold', f'Air should check-fold: {r.action}'
    print(f'Air action: {r.action}')


def test_scare_card_reduces_betting():
    """Scare card on turn reduces bet frequency for medium hands."""
    r_blank = _adv(hero_hand_class='top_pair', turn_card_type='blank')
    r_scare = _adv(hero_hand_class='top_pair', turn_card_type='scare')
    # Scare card modifier should be less than blank
    assert r_scare.turn_card_modifier < r_blank.turn_card_modifier, \
        f'Scare should reduce modifier: {r_scare.turn_card_modifier} vs {r_blank.turn_card_modifier}'
    print(f'Modifier: blank={r_blank.turn_card_modifier} scare={r_scare.turn_card_modifier}')


def test_hero_hits_draw_increases_betting():
    """Hitting draw increases turn_card_modifier."""
    r_blank = _adv(turn_card_type='blank')
    r_hits = _adv(turn_card_type='hero_hits', hero_has_draw=True)
    assert r_hits.turn_card_modifier > r_blank.turn_card_modifier
    print(f'Modifier: blank={r_blank.turn_card_modifier} hits={r_hits.turn_card_modifier}')


def test_both_checked_lead_turn():
    """After both checked flop, OOP should lead turn with value hands."""
    r = _adv(
        flop_sequence='both_checked',
        hero_hand_class='top_pair',
        hero_equity=0.60,
    )
    assert r.action == 'bet', f'Both checked: should lead turn with TP: {r.action}'
    print(f'Both checked + TP: {r.action}')


def test_villain_raised_hero_checks():
    """After hero bet, villain raised, hero called: always check turn."""
    r = _adv(
        flop_sequence='hero_bet_villain_raised_hero_called',
        hero_hand_class='top_pair',
        hero_equity=0.55,
    )
    assert r.action in ('check_call', 'check_fold', 'check_raise'), \
        f'Villain raised flop: should check turn: {r.action}'
    print(f'Villain raised flop: {r.action}')


def test_villain_raised_set_check_raises():
    """Set after villain's flop raise: check-raise turn."""
    r = _adv(
        flop_sequence='hero_bet_villain_raised_hero_called',
        hero_hand_class='set',
        hero_equity=0.85,
    )
    assert r.action == 'check_raise', f'Set vs villain raise: {r.action}'
    print(f'Set vs villain raise: {r.action}')


def test_bet_size_zero_when_not_betting():
    """bet_size_bb should be 0 when action is not bet."""
    r = _adv(hero_hand_class='air', hero_equity=0.10)
    if r.action != 'bet':
        assert r.bet_size_bb == 0.0, f'Non-bet action should have bet_size_bb=0: {r.bet_size_bb}'
    print(f'Non-bet action {r.action}: bet_size_bb={r.bet_size_bb}')


def test_bet_size_positive_when_betting():
    """bet_size_pct and bet_size_bb should be positive when action=bet."""
    r = _adv(
        flop_sequence='both_checked',
        hero_hand_class='top_pair',
        hero_equity=0.65,
    )
    if r.action == 'bet':
        assert r.bet_size_pct > 0, f'Betting: bet_size_pct should be > 0: {r.bet_size_pct}'
        assert r.bet_size_bb > 0, f'Betting: bet_size_bb should be > 0: {r.bet_size_bb}'
    print(f'{r.action}: pct={r.bet_size_pct} bb={r.bet_size_bb}')


def test_aggressive_villain_triggers_check_raise():
    """High AF villain (3.0+) should prompt check-raise with strong hands."""
    r = _adv(
        hero_hand_class='strong', hero_equity=0.80,
        villain_af=3.5, flop_sequence='hero_bet_called',
    )
    assert r.action in ('check_raise', 'bet'), \
        f'Strong hand vs aggressive villain: {r.action}'
    print(f'Strong hand vs AF=3.5: {r.action}')


def test_villain_bet_hero_called_passive_villain_probe():
    """Passive villain (AF < 1.5) after check-call: probe turn."""
    r = _adv(
        flop_sequence='villain_bet_hero_called',
        hero_hand_class='top_pair',
        hero_equity=0.58,
        villain_af=1.2,
    )
    # With passive villain, probe bet should be suggested
    assert r.action in ('bet', 'check_call'), f'Passive villain: should probe or call: {r.action}'
    print(f'Passive villain probe: {r.action}')


def test_action_valid_values():
    """Action must be one of the valid options."""
    valid = {'bet', 'check_call', 'check_fold', 'check_raise'}
    for seq in ['hero_bet_called', 'villain_bet_hero_called', 'both_checked',
                'hero_bet_villain_raised_hero_called']:
        r = _adv(flop_sequence=seq)
        assert r.action in valid, f'Invalid action {r.action!r} for seq={seq}'
    print('All actions valid across sequences')


def test_action_frequency_range():
    """action_frequency should be in [0, 1]."""
    for h in ['air', 'draw', 'top_pair', 'set']:
        r = _adv(hero_hand_class=h)
        assert 0.0 <= r.action_frequency <= 1.0, \
            f'Frequency out of range: {r.action_frequency} for {h}'
    print('Frequencies all in [0, 1]')


def test_tips_not_empty():
    r = _adv()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips: {len(r.tips)}')


def test_wet_board_larger_bet():
    """Wet board should produce larger bet size than dry."""
    r_dry = _adv(board_type='dry', hero_hand_class='top_pair',
                 flop_sequence='both_checked', hero_equity=0.60)
    r_wet = _adv(board_type='wet', hero_hand_class='top_pair',
                 flop_sequence='both_checked', hero_equity=0.60)
    if r_dry.action == 'bet' and r_wet.action == 'bet':
        assert r_wet.bet_size_pct >= r_dry.bet_size_pct, \
            f'Wet should have >= bet: wet={r_wet.bet_size_pct} dry={r_dry.bet_size_pct}'
    print(f'Bet size: dry={r_dry.bet_size_pct} wet={r_wet.bet_size_pct}')


def test_draw_both_checked_leads():
    """Draw on checked-through board: OOP should lead turn."""
    r = _adv(
        flop_sequence='both_checked',
        hero_hand_class='draw',
        hero_has_draw=True,
        hero_equity=0.38,
    )
    assert r.action in ('bet', 'check_call'), \
        f'Draw on checked board should bet or call: {r.action}'
    print(f'Draw + both_checked: {r.action}')


def test_unknown_sequence_defaults():
    """Unknown flop sequence should not crash."""
    r = _adv(flop_sequence='unknown_sequence')
    assert r.action in {'bet', 'check_call', 'check_fold', 'check_raise'}
    print(f'Unknown sequence: {r.action}')


def test_one_liner():
    r = _adv()
    line = oop_turn_one_liner(r)
    assert 'OOP-T' in line and 'eq=' in line and 'SPR=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_oop_turn_advice, test_required_fields,
        test_strong_hand_bets_or_check_raises, test_weak_hand_check_folds,
        test_scare_card_reduces_betting, test_hero_hits_draw_increases_betting,
        test_both_checked_lead_turn, test_villain_raised_hero_checks,
        test_villain_raised_set_check_raises, test_bet_size_zero_when_not_betting,
        test_bet_size_positive_when_betting, test_aggressive_villain_triggers_check_raise,
        test_villain_bet_hero_called_passive_villain_probe, test_action_valid_values,
        test_action_frequency_range, test_tips_not_empty,
        test_wet_board_larger_bet, test_draw_both_checked_leads,
        test_unknown_sequence_defaults, test_one_liner,
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
