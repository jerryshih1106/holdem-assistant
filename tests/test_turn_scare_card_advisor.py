"""Tests for turn_scare_card_advisor.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.turn_scare_card_advisor import (
    advise_scare_card, ScareCardAdvice, sca_one_liner,
    _hero_range_benefit, hero_has_blocker_to_scare,
    _bluff_opportunity, _primary_action,
    VILLAIN_RANGE_BENEFIT, SIZE_ADJ_ON_SCARE,
)


def _sca(**kw):
    defaults = dict(
        scare_card_type='ace_on_low_board',
        hero_role='pfr',
        hero_position='ip',
        hero_hand_category='top_pair',
        hero_has_scare_card_blocker=False,
        villain_vpip=0.30,
        villain_af=2.0,
        flop_action='hero_cbet_called',
        pot_bb=20.0,
        hero_stack_bb=80.0,
    )
    defaults.update(kw)
    return advise_scare_card(**defaults)


def test_returns_scare_card_advice():
    r = _sca()
    assert isinstance(r, ScareCardAdvice)


def test_villain_benefit_ace_high():
    assert VILLAIN_RANGE_BENEFIT['ace_on_low_board'] > 0.55


def test_villain_benefit_board_pairs_lower():
    assert VILLAIN_RANGE_BENEFIT['board_pairs'] < VILLAIN_RANGE_BENEFIT['ace_on_low_board']


def test_size_adj_ace_smaller():
    assert SIZE_ADJ_ON_SCARE['ace_on_low_board'] < 0.80


def test_hero_range_benefit_with_blocker():
    b_no  = _hero_range_benefit('ace_on_low_board', 'pfr', 'middle_pair')
    b_yes = _hero_range_benefit('ace_on_low_board', 'pfr', 'top_pair')
    assert b_yes >= b_no


def test_hero_has_blocker_flush():
    assert hero_has_blocker_to_scare('flush_completes', 'flush') is True


def test_hero_no_blocker_air():
    assert hero_has_blocker_to_scare('ace_on_low_board', 'air') is False


def test_bluff_opportunity_caller_check_check():
    has, freq, desc = _bluff_opportunity('ace_on_low_board', 'caller', 'ip', 'check_check', 0.30)
    assert has is True
    assert freq > 0.0


def test_no_bluff_pfr_board_pairs():
    has, freq, _ = _bluff_opportunity('board_pairs', 'pfr', 'ip', 'hero_cbet_called', 0.30)
    assert not has or freq < 0.40


def test_pfr_no_blocker_ace_checks():
    action, size, _ = _primary_action(
        'ace_on_low_board', 'pfr', 'ip', 'top_pair', False, 'hero_cbet_called', 2.0
    )
    assert action == 'check_back'


def test_pfr_with_blocker_bets():
    action, size, _ = _primary_action(
        'ace_on_low_board', 'pfr', 'ip', 'top_pair', True, 'hero_cbet_called', 2.0
    )
    assert action in ('bet_small', 'bet_value', 'bet_scare')


def test_strong_hand_always_bets():
    action, _, _ = _primary_action(
        'flush_completes', 'caller', 'ip', 'flush', True, 'villain_cbet_hero_called', 2.0
    )
    assert action == 'bet_value'


def test_range_advantage_stored():
    r = _sca()
    assert r.range_advantage in ('hero', 'villain', 'neutral')


def test_villain_range_benefit_stored():
    r = _sca(scare_card_type='ace_on_low_board')
    assert r.villain_range_benefit == VILLAIN_RANGE_BENEFIT['ace_on_low_board']


def test_sizing_adjustment_in_range():
    r = _sca()
    assert 0.0 <= r.sizing_adjustment <= 1.5


def test_has_bluff_opportunity_field():
    r = _sca(hero_role='caller', flop_action='check_check')
    assert isinstance(r.has_bluff_opportunity, bool)


def test_bluff_freq_when_opportunity():
    r = _sca(hero_role='caller', flop_action='check_check',
             scare_card_type='ace_on_low_board')
    if r.has_bluff_opportunity:
        assert r.bluff_frequency > 0.0


def test_ace_high_villain_range_advantage():
    r = _sca(scare_card_type='ace_on_low_board', hero_has_scare_card_blocker=False)
    assert r.range_advantage == 'villain'


def test_flush_complete_caller_ip_blocker():
    r = _sca(scare_card_type='flush_completes', hero_role='caller',
             hero_position='ip', hero_hand_category='flush')
    assert r.primary_action == 'bet_value'


def test_tips_populated():
    r = _sca()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _sca()
    line = sca_one_liner(r)
    assert '[SCA' in line
    assert 'range_adv=' in line
    assert 'size_adj=' in line


def test_board_pairs_with_top_pair_warns():
    r = _sca(scare_card_type='board_pairs', hero_hand_category='top_pair')
    tips_lower = ' '.join(r.tips).lower()
    assert 'pair' in tips_lower or 'trip' in tips_lower or 'vulnerable' in tips_lower


def test_aggressive_villain_tips():
    r = _sca(villain_af=4.0)
    tips_lower = ' '.join(r.tips).lower()
    assert 'af' in tips_lower or 'aggress' in tips_lower or 'check-raise' in tips_lower.replace('-', '')


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
