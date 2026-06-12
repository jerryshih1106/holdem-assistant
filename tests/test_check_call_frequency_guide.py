"""Tests for check_call_frequency_guide.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.check_call_frequency_guide import (
    guide_check_call, CheckCallGuide, ccg_one_liner,
    _adjusted_cc_freq, _check_call_line,
    BASE_CHECK_CALL_FREQ,
)


def _ccg(**kw):
    defaults = dict(
        hero_hand_category='middle_pair',
        street='flop',
        hero_position='oop',
        villain_af=2.5,
        villain_cbet_pct=0.65,
        board_texture='semi_wet',
        hero_equity=0.38,
        spr=5.0,
        pot_bb=20.0,
    )
    defaults.update(kw)
    return guide_check_call(**defaults)


def test_returns_check_call_guide():
    r = _ccg()
    assert isinstance(r, CheckCallGuide)


def test_cc_freq_between_zero_and_one():
    freq = _adjusted_cc_freq('middle_pair', 2.5, 'oop', 'semi_wet', 5.0)
    assert 0.0 <= freq <= 1.0


def test_bluff_catcher_high_cc_freq():
    freq = _adjusted_cc_freq('bluff_catcher', 2.5, 'oop', 'semi_wet', 5.0)
    assert freq >= 0.60


def test_air_low_cc_freq():
    freq = _adjusted_cc_freq('air', 2.5, 'oop', 'semi_wet', 5.0)
    assert freq <= 0.20


def test_high_af_increases_cc_freq():
    low = _adjusted_cc_freq('middle_pair', 1.5, 'oop', 'semi_wet', 5.0)
    high = _adjusted_cc_freq('middle_pair', 3.5, 'oop', 'semi_wet', 5.0)
    assert high > low


def test_oop_higher_cc_freq_than_ip():
    oop = _adjusted_cc_freq('top_pair', 2.5, 'oop', 'semi_wet', 5.0)
    ip = _adjusted_cc_freq('top_pair', 2.5, 'ip', 'semi_wet', 5.0)
    assert oop > ip


def test_low_spr_reduces_cc_freq():
    normal = _adjusted_cc_freq('middle_pair', 2.5, 'oop', 'semi_wet', 5.0)
    low_spr = _adjusted_cc_freq('middle_pair', 2.5, 'oop', 'semi_wet', 1.5)
    assert low_spr < normal


def test_set_vs_aggressive_check_raise():
    line, _ = _check_call_line('set', 3.0, 'oop', 'semi_wet', 5.0, 0.40, 0.60)
    assert line == 'check_raise'


def test_air_vs_regular_cbetter_check_fold():
    line, _ = _check_call_line('air', 2.5, 'oop', 'semi_wet', 5.0, 0.05, 0.60)
    assert line == 'check_fold'


def test_middle_pair_vs_aggressive_check_call():
    line, _ = _check_call_line('middle_pair', 2.5, 'oop', 'semi_wet', 5.0, 0.55, 0.60)
    assert line == 'check_call'


def test_flush_draw_oop_vs_aggressive_check_call():
    line, _ = _check_call_line('flush_draw', 3.0, 'oop', 'semi_wet', 5.0, 0.35, 0.60)
    assert line == 'check_call'


def test_cc_freq_stored():
    r = _ccg()
    assert 0.0 <= r.check_call_frequency <= 1.0


def test_recommended_line_stored():
    r = _ccg()
    assert isinstance(r.recommended_line, str)
    assert len(r.recommended_line) > 0


def test_tips_populated():
    r = _ccg()
    assert len(r.tips) >= 2


def test_high_af_tip():
    r = _ccg(villain_af=3.5)
    combined = ' '.join(r.tips).lower()
    assert 'af' in combined or 'aggress' in combined


def test_high_cbet_tip():
    r = _ccg(villain_cbet_pct=0.75)
    combined = ' '.join(r.tips).lower()
    assert 'cbet' in combined or 'c-bet' in combined or 'mdf' in combined or 'bet' in combined


def test_low_spr_tip():
    r = _ccg(spr=1.5)
    combined = ' '.join(r.tips).lower()
    assert 'spr' in combined or 'low' in combined


def test_river_tip():
    r = _ccg(street='river')
    combined = ' '.join(r.tips).lower()
    assert 'river' in combined


def test_ip_on_dry_tip():
    r = _ccg(hero_position='ip', board_texture='dry')
    combined = ' '.join(r.tips).lower()
    assert 'ip' in combined or 'position' in combined or 'pot' in combined


def test_bluff_catcher_gives_check_call():
    r = _ccg(hero_hand_category='bluff_catcher', villain_af=2.5)
    assert r.recommended_line in ('check_call', 'check_call_or_fold')


def test_one_liner_format():
    r = _ccg()
    line = ccg_one_liner(r)
    assert '[CCG' in line
    assert 'eq=' in line
    assert 'spr=' in line


def test_one_liner_contains_hand():
    r = _ccg(hero_hand_category='middle_pair')
    line = ccg_one_liner(r)
    assert 'middle_pair' in line


def test_verdict_stored():
    r = _ccg()
    assert isinstance(r.verdict, str)
    assert len(r.verdict) > 10


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
