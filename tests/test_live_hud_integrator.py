"""Tests for live_hud_integrator.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.live_hud_integrator import (
    build_hud_profile, HUDProfile, hud_one_liner,
    _classify_archetype, _session_override, _compute_effective_adj,
    ARCHETYPES, ARCHETYPE_ADJUSTMENTS,
)


def _hud(**kw):
    defaults = dict(
        vpip=0.28,
        pfr=0.20,
        af=2.0,
        three_bet_freq=0.08,
        session_pattern='no_pattern',
        weakness_signals=[],
        board_texture='dry',
        hand_category='top_pair',
        hero_position='ip',
    )
    defaults.update(kw)
    return build_hud_profile(**defaults)


def test_returns_hud_profile():
    r = _hud()
    assert isinstance(r, HUDProfile)


def test_calling_station_archetype():
    arch = _classify_archetype(0.50, 0.08, 1.2)
    assert arch == 'calling_station'


def test_nit_archetype():
    arch = _classify_archetype(0.15, 0.10, 1.0)
    assert arch == 'nit'


def test_maniac_archetype():
    arch = _classify_archetype(0.45, 0.30, 3.5)
    assert arch == 'maniac'


def test_lag_archetype():
    arch = _classify_archetype(0.30, 0.18, 2.5)
    assert arch == 'lag'


def test_tag_archetype():
    arch = _classify_archetype(0.18, 0.14, 2.2)
    assert arch == 'tag'


def test_reg_archetype_default():
    arch = _classify_archetype(0.25, 0.18, 2.2)
    assert arch == 'reg'


def test_calling_station_reduces_bluff():
    adjs = ARCHETYPE_ADJUSTMENTS.get('calling_station', {})
    assert adjs.get('bluff_freq', 0) < 0


def test_nit_increases_bluff():
    adjs = ARCHETYPE_ADJUSTMENTS.get('nit', {})
    assert adjs.get('bluff_freq', 0) > 0


def test_fold_streak_increases_bluff():
    base = {'bluff_freq': 0.0, 'value_size': 0.0, 'call_threshold': 0.0}
    adjs = _session_override('fold_streak', base)
    assert adjs['bluff_freq'] > 0


def test_call_streak_reduces_bluff():
    base = {'bluff_freq': 0.0, 'value_size': 0.0, 'call_threshold': 0.0}
    adjs = _session_override('call_streak', base)
    assert adjs['bluff_freq'] < 0


def test_weakness_signals_boost_bluff():
    base = {'bluff_freq': 0.0, 'value_size': 0.0, 'call_threshold': 0.0}
    adjs = _compute_effective_adj(base, ['check_check_multiway'])
    assert adjs['bluff_freq'] > 0


def test_archetype_stored():
    r = _hud()
    assert r.archetype in ARCHETYPES


def test_archetype_description_non_empty():
    r = _hud()
    assert len(r.archetype_description) > 0


def test_effective_adjustments_stored():
    r = _hud()
    assert isinstance(r.effective_bluff_adj, float)
    assert isinstance(r.effective_value_adj, float)
    assert isinstance(r.effective_call_threshold_adj, float)


def test_top_insight_non_empty():
    r = _hud()
    assert len(r.top_insight) > 0


def test_fold_streak_shown_in_insight():
    r = _hud(session_pattern='fold_streak')
    assert 'FOLD STREAK' in r.top_insight or 'fold' in r.top_insight.lower()


def test_tips_populated():
    r = _hud()
    assert len(r.tips) >= 3


def test_high_3bet_adds_tip():
    r = _hud(three_bet_freq=0.20)
    assert len(r.tips) >= 4


def test_low_3bet_adds_tip():
    r = _hud(three_bet_freq=0.03)
    assert len(r.tips) >= 4


def test_one_liner_format():
    r = _hud()
    line = hud_one_liner(r)
    assert '[HUD' in line
    assert 'VPIP=' in line
    assert 'bluff_adj=' in line


def test_calling_station_combo():
    r = _hud(vpip=0.50, pfr=0.08, af=1.2)
    assert r.archetype == 'calling_station'
    assert r.effective_bluff_adj < 0


def test_maniac_call_threshold_adj():
    r = _hud(vpip=0.45, pfr=0.30, af=3.5)
    assert r.effective_call_threshold_adj <= 0  # call lighter vs maniac


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
