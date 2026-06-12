# -*- coding: cp950 -*-
import sys, os; sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.triple_barrel_frequency_guide import (
    analyze_triple_barrel, TripleBarrelResult, triple_barrel_one_liner,
    TRIPLE_BARREL_FREQ, RIVER_CARD_TB_MOD, STORY_CREDIBILITY_THRESHOLD,
)


def _tb(**kw):
    defaults = dict(villain_type='reg', river_card_type='brick', board_texture='dry', pot_bb=12.0)
    defaults.update(kw)
    return analyze_triple_barrel(**defaults)


def test_returns_result():
    assert isinstance(_tb(), TripleBarrelResult)


def test_nit_higher_than_fish():
    r_nit = _tb(villain_type='nit')
    r_fish = _tb(villain_type='fish')
    assert r_nit.tb_freq > r_fish.tb_freq


def test_calling_station_lowest():
    r_cs = _tb(villain_type='calling_station')
    for vt in TRIPLE_BARREL_FREQ:
        if vt != 'calling_station':
            r = _tb(villain_type=vt)
            assert r_cs.tb_freq <= r.tb_freq, f"cs should be lowest but {vt} was lower"


def test_scare_boosts_freq():
    r_brick = _tb(river_card_type='brick')
    r_scare = _tb(river_card_type='scare')
    assert r_scare.tb_freq > r_brick.tb_freq


def test_pairing_lowers_freq():
    r_brick = _tb(river_card_type='brick')
    r_pair = _tb(river_card_type='pairing')
    assert r_pair.tb_freq < r_brick.tb_freq


def test_freq_bounds():
    for vt in TRIPLE_BARREL_FREQ:
        for rc in RIVER_CARD_TB_MOD:
            r = _tb(villain_type=vt, river_card_type=rc)
            assert 0.0 <= r.tb_freq <= 1.0


def test_size_pct_is_70():
    r = _tb()
    assert abs(r.size_pct - 0.70) < 0.001


def test_story_credibility_dry_higher_than_wet():
    r_dry = _tb(board_texture='dry')
    r_wet = _tb(board_texture='wet')
    assert r_dry.story_credibility > r_wet.story_credibility


def test_story_credibility_bounds():
    for bt in ('dry', 'wet', 'paired', 'monotone'):
        r = _tb(board_texture=bt)
        assert 0.0 <= r.story_credibility <= 1.0


def test_action_give_up_when_low_story():
    r = _tb(villain_type='calling_station', board_texture='wet', river_card_type='pairing')
    assert r.action == 'give_up'


def test_action_triple_barrel_nit_dry():
    r = _tb(villain_type='nit', board_texture='dry', river_card_type='scare')
    assert r.action in ('triple_barrel', 'triple_barrel_value_only')


def test_tips_at_least_2():
    r = _tb()
    assert len(r.tips) >= 2


def test_reasoning_contains_freq():
    r = _tb()
    assert 'freq=' in r.reasoning


def test_verdict_equals_action():
    r = _tb()
    assert r.verdict == r.action


def test_one_liner_format():
    r = _tb()
    s = triple_barrel_one_liner(r)
    assert s.startswith('[TB')
    assert 'freq=' in s
    assert 'story=' in s
    assert 'action=' in s


def test_pot_bb_stored():
    r = _tb(pot_bb=25.0)
    assert r.pot_bb == 25.0


def test_story_threshold_applied():
    # When story credibility is above threshold, should not be give_up for higher freq villains
    r = _tb(villain_type='nit', board_texture='dry', river_card_type='brick')
    assert r.story_credibility >= STORY_CREDIBILITY_THRESHOLD
    assert r.action != 'give_up'


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t(); print(f'[OK] {t.__name__}')
        except Exception as e:
            print(f'[FAIL] {t.__name__}: {e}'); failed += 1
    print(f'\n{len(tests)-failed}/{len(tests)} passed'); sys.exit(failed)
