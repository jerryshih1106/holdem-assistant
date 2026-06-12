"""Tests for turn_runout_analysis.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.turn_runout_analysis import (
    analyze_turn_runout, TurnRunoutResult, tra_one_liner,
    _classify_turn_card, _compute_turn_cbet, _range_advantage_label,
    PFR_RANGE_BENEFIT, CBET_ADJ_BY_CARD, FLOP_CBET_BASE,
)


def _tra(**kw):
    defaults = dict(
        flop_cards=['As', 'Kh', '7c'],
        turn_card='2s',
        flop_texture='dry',
        hero_position='ip',
        hand_category='top_pair',
        villain_af=2.0,
        hero_is_pfr=True,
    )
    defaults.update(kw)
    return analyze_turn_runout(**defaults)


def test_returns_turn_runout_result():
    r = _tra()
    assert isinstance(r, TurnRunoutResult)


def test_blank_turn_classification():
    # 9 on AK7: not pairing, not flush, not straight, not broadway, not low card
    card_type = _classify_turn_card(['As', 'Kh', '7c'], '9d')
    assert card_type == 'blank'


def test_pairs_board_detection():
    card_type = _classify_turn_card(['As', 'Kh', '7c'], 'As')
    assert card_type == 'pairs_board'


def test_flush_completes_detection():
    # Three spades on flop + spade on turn
    card_type = _classify_turn_card(['As', 'Ks', '7s'], '9s')
    assert card_type == 'flush_completes'


def test_scare_ace_detected():
    card_type = _classify_turn_card(['7s', '8h', '2c'], 'Ad')
    assert card_type == 'scare_ace'


def test_scare_king_detected():
    card_type = _classify_turn_card(['7s', '8h', '2c'], 'Kd')
    assert card_type == 'scare_king'


def test_low_card_detected():
    card_type = _classify_turn_card(['As', 'Kh', 'Qd'], '3s')
    assert card_type == 'low_card'


def test_broadway_detected():
    card_type = _classify_turn_card(['2s', '5h', '9c'], 'Qd')
    assert card_type == 'broadway'


def test_range_advantage_label_strong_pfr():
    label = _range_advantage_label(0.20)
    assert label == 'strong_pfr_advantage'


def test_range_advantage_label_neutral():
    label = _range_advantage_label(0.00)
    assert label == 'neutral'


def test_range_advantage_label_caller_advantage():
    label = _range_advantage_label(-0.20)
    assert label == 'strong_caller_advantage'


def test_scare_ace_pfr_advantage():
    r = _tra(turn_card='Ac', flop_cards=['7s', '8h', '2c'], hero_is_pfr=True)
    assert r.pfr_benefit > 0


def test_flush_completes_caller_advantage_for_pfr():
    r = _tra(
        flop_cards=['As', 'Ks', '7s'],
        turn_card='9s',
        hero_is_pfr=True,
    )
    assert r.pfr_benefit < 0


def test_caller_view_inverts_pfr_benefit():
    r_pfr = _tra(flop_cards=['7s', '8h', '2c'], turn_card='Ac', hero_is_pfr=True)
    r_caller = _tra(flop_cards=['7s', '8h', '2c'], turn_card='Ac', hero_is_pfr=False)
    assert r_pfr.pfr_benefit == -r_caller.pfr_benefit


def test_cbet_in_range():
    r = _tra()
    assert 0.0 < r.turn_cbet_freq <= 1.0


def test_scare_ace_cbet_higher_than_blank():
    cbet_blank = _compute_turn_cbet('blank', 'dry', 'ip', 'top_pair', 2.0)
    cbet_ace = _compute_turn_cbet('scare_ace', 'dry', 'ip', 'top_pair', 2.0)
    assert cbet_ace >= cbet_blank


def test_flush_completes_cbet_lower():
    cbet_blank = _compute_turn_cbet('blank', 'dry', 'ip', 'top_pair', 2.0)
    cbet_flush = _compute_turn_cbet('flush_completes', 'dry', 'ip', 'top_pair', 2.0)
    assert cbet_flush < cbet_blank


def test_oop_cbet_lower():
    cbet_ip = _compute_turn_cbet('blank', 'dry', 'ip', 'top_pair', 2.0)
    cbet_oop = _compute_turn_cbet('blank', 'dry', 'oop', 'top_pair', 2.0)
    assert cbet_oop < cbet_ip


def test_air_cbet_lower_than_value():
    cbet_air = _compute_turn_cbet('blank', 'dry', 'ip', 'air', 2.0)
    cbet_set = _compute_turn_cbet('blank', 'dry', 'ip', 'set', 2.0)
    assert cbet_air < cbet_set


def test_card_type_stored():
    r = _tra()
    assert r.card_type in CBET_ADJ_BY_CARD


def test_size_adjustment_stored():
    r = _tra()
    assert r.bet_size_adjustment > 0.0


def test_tips_populated():
    r = _tra()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _tra()
    line = tra_one_liner(r)
    assert '[TRA' in line
    assert 'cbet=' in line
    assert 'size_adj=' in line


def test_verdict_contains_card():
    r = _tra(turn_card='Kd', flop_cards=['7s', '8h', '2c'])
    assert 'Kd' in r.verdict


def test_pfr_range_benefit_table_complete():
    assert 'blank' in PFR_RANGE_BENEFIT
    assert 'flush_completes' in PFR_RANGE_BENEFIT
    assert 'scare_ace' in PFR_RANGE_BENEFIT


def test_flop_texture_affects_cbet():
    r_dry = _tra(flop_texture='dry')
    r_wet = _tra(flop_texture='wet')
    assert r_dry.turn_cbet_freq != r_wet.turn_cbet_freq


def test_flop_cards_none_defaults():
    r = analyze_turn_runout(flop_cards=None, turn_card='2s')
    assert r.card_type is not None


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
