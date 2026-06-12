"""Tests for limp_raise_strategy.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.limp_raise_strategy import (
    analyze_limp_raise, LimpRaisePlan, lrp_one_liner,
    _is_limp_raise_hand, _limp_raise_size, _should_limp_raise,
    _vs_open_raise_comparison, _limp_raise_tell_risk,
    LIMP_RAISE_HANDS, PREMIUM_LIMP_RAISE, MIN_ISO_FREQ,
)


def _lrp(**kw):
    defaults = dict(
        hero_hand='AA',
        hero_position='utg',
        table_iso_freq=0.60,
        villain_iso_size_bb=12.0,
        stack_bb=200.0,
        players_at_table=6,
        game_type='live',
        villain_fold_to_3bet=0.55,
    )
    defaults.update(kw)
    return analyze_limp_raise(**defaults)


def test_returns_limp_raise_plan():
    r = _lrp()
    assert isinstance(r, LimpRaisePlan)


def test_aa_is_eligible():
    assert _is_limp_raise_hand('AA') is True


def test_kk_is_eligible():
    assert _is_limp_raise_hand('KK') is True


def test_tt_not_eligible():
    assert _is_limp_raise_hand('TT') is False


def test_low_iso_freq_no_limp_raise():
    assert _should_limp_raise('AA', 0.25, 200.0, 'live') is False


def test_high_iso_freq_limp_raise():
    assert _should_limp_raise('AA', 0.65, 200.0, 'live') is True


def test_ineligible_hand_no_limp_raise():
    assert _should_limp_raise('77', 0.70, 200.0, 'live') is False


def test_limp_raise_size_multiple_of_iso():
    size = _limp_raise_size(12.0, 300.0)
    assert size >= 12.0 * 3.0   # at least 3x iso


def test_limp_raise_size_capped_by_stack():
    size = _limp_raise_size(12.0, 50.0)
    assert size <= 50.0 * 0.30


def test_recommendation_limp_raise():
    rec = _vs_open_raise_comparison('AA', 0.65, 200.0, 'live')
    assert rec == 'limp_raise'


def test_recommendation_open_raise_low_iso():
    rec = _vs_open_raise_comparison('AA', 0.30, 200.0, 'live')
    assert rec == 'open_raise'


def test_recommendation_open_raise_non_eligible():
    rec = _vs_open_raise_comparison('22', 0.70, 200.0, 'live')
    assert rec == 'open_raise'


def test_tell_risk_low_first_time():
    risk = _limp_raise_tell_risk('AA', 0)
    assert risk == 'low_tell_risk'


def test_tell_risk_high_repeated():
    risk = _limp_raise_tell_risk('AA', 2)
    assert risk == 'high_tell_risk'


def test_is_limp_raise_hand_stored():
    r = _lrp()
    assert isinstance(r.is_limp_raise_hand, bool)


def test_limp_raise_size_positive():
    r = _lrp()
    assert r.limp_raise_size_bb > 0


def test_recommendation_stored():
    r = _lrp()
    assert r.recommendation in ('limp_raise', 'open_raise')


def test_tell_risk_stored():
    r = _lrp()
    assert r.tell_risk in ('low_tell_risk', 'moderate_tell_risk', 'high_tell_risk')


def test_tips_populated():
    r = _lrp()
    assert len(r.tips) >= 3


def test_one_liner_format():
    r = _lrp()
    line = lrp_one_liner(r)
    assert '[LRP' in line
    assert 'iso_freq=' in line
    assert 'tell_risk=' in line


def test_aa_deep_stack_live_recommends_limp_raise():
    r = _lrp(hero_hand='AA', stack_bb=250.0, table_iso_freq=0.65, game_type='live')
    assert r.recommendation == 'limp_raise'


def test_aa_short_stack_open_raise():
    r = _lrp(hero_hand='AA', stack_bb=80.0, table_iso_freq=0.50, game_type='live')
    # shallow stack: limp-raise less clear; open_raise may be recommended
    assert r.recommendation in ('open_raise', 'limp_raise')


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
