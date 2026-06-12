"""Tests for turn_probe_bet_advisor.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.turn_probe_bet_advisor import (
    advise_turn_probe, TurnProbeAdvice, tpa_one_liner,
    _villain_range_after_check, _probe_frequency, _probe_size_pct,
    _should_probe, _action_decision,
)


def _tpa(**kw):
    defaults = dict(
        hero_hand_category='top_pair',
        board_texture='dry',
        villain_flop_check_back_pct=0.45,
        villain_af=1.8,
        villain_wtsd=0.32,
        pot_bb=12.0,
        hero_stack_bb=80.0,
        hero_position='oop',
        turn_card_changed_board=False,
    )
    defaults.update(kw)
    return advise_turn_probe(**defaults)


def test_returns_turn_probe_advice():
    r = _tpa()
    assert isinstance(r, TurnProbeAdvice)


def test_villain_range_very_capped():
    assert _villain_range_after_check(0.55, 2.0) == 'very_capped'


def test_villain_range_capped():
    assert _villain_range_after_check(0.40, 2.0) == 'capped'


def test_villain_range_semi_capped():
    assert _villain_range_after_check(0.25, 2.0) == 'semi_capped'


def test_villain_range_uncapped():
    assert _villain_range_after_check(0.15, 2.0) == 'uncapped'


def test_probe_frequency_very_capped_top_pair():
    freq = _probe_frequency('very_capped', 'dry', 'top_pair', False)
    assert freq >= 0.60


def test_probe_frequency_uncapped_air():
    freq = _probe_frequency('uncapped', 'dry', 'air', False)
    assert freq <= 0.20


def test_probe_frequency_draw_wet_board():
    freq = _probe_frequency('capped', 'wet', 'draw', False)
    assert freq >= 0.40


def test_probe_frequency_draw_dry_board():
    freq_wet = _probe_frequency('capped', 'wet', 'draw', False)
    freq_dry = _probe_frequency('capped', 'dry', 'draw', False)
    assert freq_wet >= freq_dry


def test_probe_size_dry_board_value():
    size = _probe_size_pct('dry', 'top_pair', 'capped')
    assert 0.30 <= size <= 0.50


def test_probe_size_wet_board_value():
    size = _probe_size_pct('wet', 'top_pair', 'capped')
    assert size >= 0.50


def test_probe_size_wet_bigger_than_dry():
    dry = _probe_size_pct('dry', 'top_pair', 'capped')
    wet = _probe_size_pct('wet', 'top_pair', 'capped')
    assert wet > dry


def test_action_probe_value_top_pair():
    r = _tpa(hero_hand_category='top_pair', villain_flop_check_back_pct=0.50)
    assert r.action == 'probe_value'


def test_action_check_uncapped_villain():
    r = _tpa(villain_flop_check_back_pct=0.10, hero_hand_category='air')
    assert r.action == 'check'


def test_action_probe_semi_bluff_draw():
    r = _tpa(hero_hand_category='flush_draw', board_texture='wet',
             villain_flop_check_back_pct=0.50)
    assert r.action in ('probe_semi_bluff', 'probe_value', 'check')


def test_probe_bb_computed_from_pot():
    r = _tpa(pot_bb=20.0)
    expected_max = 20.0 * 0.80
    assert r.probe_size_bb <= expected_max


def test_fold_equity_higher_for_capped():
    r_capped = _tpa(villain_flop_check_back_pct=0.55)
    r_uncapped = _tpa(villain_flop_check_back_pct=0.10)
    assert r_capped.fold_equity_estimate > r_uncapped.fold_equity_estimate


def test_probe_ev_positive_for_value():
    r = _tpa(hero_hand_category='top_pair', villain_flop_check_back_pct=0.55)
    if r.action != 'check':
        assert r.probe_ev_estimate > 0.0


def test_probe_ev_zero_on_check():
    r = _tpa(villain_flop_check_back_pct=0.10, hero_hand_category='air')
    assert r.probe_ev_estimate == 0.0


def test_villain_range_type_in_result():
    r = _tpa(villain_flop_check_back_pct=0.50)
    assert r.villain_range_type == 'very_capped'


def test_probe_frequency_in_result():
    r = _tpa()
    assert 0.0 <= r.probe_frequency <= 1.0


def test_tips_populated():
    r = _tpa()
    assert len(r.tips) >= 1


def test_one_liner_format():
    r = _tpa()
    line = tpa_one_liner(r)
    assert '[TPA' in line
    assert 'freq=' in line
    assert 'fold_eq=' in line


def test_turn_changed_board_reduces_frequency():
    r_normal = _tpa(hero_hand_category='air', turn_card_changed_board=False)
    r_changed = _tpa(hero_hand_category='air', turn_card_changed_board=True)
    assert r_changed.probe_frequency <= r_normal.probe_frequency


def test_two_pair_probes_more_than_middle_pair():
    r_strong = _tpa(hero_hand_category='two_pair', villain_flop_check_back_pct=0.45)
    r_weak   = _tpa(hero_hand_category='middle_pair', villain_flop_check_back_pct=0.45)
    assert r_strong.probe_frequency >= r_weak.probe_frequency


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
