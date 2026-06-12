"""Tests for live_poker_adjustments.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.live_poker_adjustments import (
    get_live_adjustments, LiveAdjustmentPlan, lap_one_liner,
    _game_type, _iso_size, _live_cbet_size, _should_value_bet_live,
    _should_bluff_live, _three_bet_live, _implied_odds_adjustment,
    LIVE_VPIP_BY_STAKES, LIVE_THIN_VALUE, LIVE_FOLD_CBET,
)


def _lap(**kw):
    defaults = dict(
        stakes='2_5',
        hero_position='btn',
        action_facing='limp_limp',
        hero_hand_category='top_pair',
        pot_bb=15.0,
        spr=8.0,
        board_texture='semi_wet',
        limpers=2,
        villain_estimated_vpip=0.55,
    )
    defaults.update(kw)
    return get_live_adjustments(**defaults)


def test_returns_live_adjustment_plan():
    r = _lap()
    assert isinstance(r, LiveAdjustmentPlan)


def test_high_vpip_very_soft():
    gtype = _game_type(0.55)
    assert gtype == 'very_soft'


def test_extreme_vpip_extremely_soft():
    gtype = _game_type(0.65)
    assert gtype == 'extremely_soft'


def test_moderate_vpip_soft():
    gtype = _game_type(0.45)
    assert gtype == 'soft'


def test_low_vpip_semi_tough():
    gtype = _game_type(0.35)
    assert gtype == 'semi_tough'


def test_iso_size_increases_with_limpers():
    iso_0 = _iso_size('btn', 0)
    iso_2 = _iso_size('btn', 2)
    assert iso_2 > iso_0


def test_iso_size_positive():
    assert _iso_size('btn', 1) > 0


def test_live_cbet_larger_than_online():
    size = _live_cbet_size('dry', 'flop')
    assert size >= 0.60   # online is ~0.50-0.55


def test_wet_board_reduces_cbet():
    dry = _live_cbet_size('dry', 'flop')
    wet = _live_cbet_size('wet', 'flop')
    assert dry >= wet


def test_middle_pair_value_vs_soft_game():
    assert _should_value_bet_live('middle_pair', '1_2', 'extremely_soft') is True


def test_middle_pair_not_value_vs_tough():
    assert _should_value_bet_live('middle_pair', '10_25', 'semi_tough') is False


def test_top_pair_always_value():
    for stakes in ('1_2', '2_5', '5_10'):
        assert _should_value_bet_live('top_pair', stakes, 'soft') is True


def test_air_never_value():
    for stakes in ('1_2', '2_5', '5_10'):
        assert _should_value_bet_live('air', stakes, 'soft') is False


def test_should_not_bluff_very_soft():
    assert _should_bluff_live('very_soft', 0.55) is False


def test_should_not_bluff_high_vpip():
    assert _should_bluff_live('soft', 0.48) is False


def test_can_bluff_semi_tough():
    assert _should_bluff_live('semi_tough', 0.35) is True


def test_three_bet_strong_hand_value():
    rec = _three_bet_live('set', 'very_soft')
    assert 'value' in rec or 'three_bet' in rec


def test_three_bet_soft_game_fold_or_call():
    rec = _three_bet_live('middle_pair', 'very_soft')
    assert 'fold_or_call' in rec or 'call' in rec


def test_implied_odds_deep_soft():
    quality = _implied_odds_adjustment(12.0, 'very_soft')
    assert quality == 'excellent_implied_odds'


def test_implied_odds_low_spr():
    quality = _implied_odds_adjustment(2.5, 'very_soft')
    assert quality == 'limited_implied_odds'


def test_game_type_stored():
    r = _lap()
    assert r.game_type in ('soft', 'very_soft', 'extremely_soft', 'semi_tough', 'standard')


def test_fold_cbet_stored():
    r = _lap()
    assert 0.0 < r.estimated_fold_cbet < 1.0


def test_iso_size_stored():
    r = _lap()
    assert r.iso_raise_size > 0


def test_tips_populated():
    r = _lap()
    assert len(r.tips) >= 4


def test_one_liner_format():
    r = _lap()
    line = lap_one_liner(r)
    assert '[LAP' in line
    assert 'iso=' in line
    assert 'cbet=' in line


def test_one_liner_no_bluff_soft():
    r = _lap(villain_estimated_vpip=0.60)
    line = lap_one_liner(r)
    assert 'bluff=N' in line


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
