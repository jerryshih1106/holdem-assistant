"""Tests for m_ratio_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.m_ratio_guide import (
    analyze_m_ratio, MRatioResult, mr_one_liner,
    _m_ratio, _effective_m, _m_zone,
    M_ZONES, CALL_EQUITY_REQUIRED, PUSH_RANGE_BY_M,
    PLAYERS_EFFECTIVE_M_FACTOR,
)


def _mr(**kw):
    defaults = dict(
        stack_bb=20.0, bb=1.0, sb=0.5, antes_total=0.0, players_at_table=9,
    )
    defaults.update(kw)
    return analyze_m_ratio(**defaults)


def test_returns_result():
    assert isinstance(_mr(), MRatioResult)


def test_m_ratio_no_antes():
    m = _m_ratio(20.0, 1.0, 0.5, 0.0)
    assert abs(m - 13.33) < 0.1


def test_m_ratio_with_antes():
    m = _m_ratio(20.0, 1.0, 0.5, 1.8)
    assert m < 13.33


def test_effective_m_shorter_at_6handed():
    m9 = _effective_m(15.0, 9)
    m6 = _effective_m(15.0, 6)
    assert m6 < m9


def test_zone_green():
    assert _m_zone(25.0) == 'green'


def test_zone_yellow():
    assert _m_zone(15.0) == 'yellow'


def test_zone_orange():
    assert _m_zone(8.0) == 'orange'


def test_zone_red():
    assert _m_zone(3.0) == 'red'


def test_zone_dead():
    assert _m_zone(0.5) == 'dead'


def test_call_equity_lower_at_red():
    green = CALL_EQUITY_REQUIRED['green']
    red   = CALL_EQUITY_REQUIRED['red']
    assert red < green


def test_push_range_wider_at_red():
    assert PUSH_RANGE_BY_M['red']['min_pair'] <= PUSH_RANGE_BY_M['green']['min_pair']


def test_large_stack_is_green():
    r = _mr(stack_bb=200.0)
    assert r.zone == 'green'


def test_small_stack_is_red():
    r = _mr(stack_bb=4.0)
    assert r.zone in ('red', 'orange')


def test_effective_m_stored():
    r = _mr()
    assert r.effective_m <= r.m_ratio


def test_tips_populated():
    r = _mr()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _mr()
    line = mr_one_liner(r)
    assert '[M zone=' in line and 'stack=' in line


def test_shorthand_tip():
    r = _mr(players_at_table=6, stack_bb=20.0)
    assert any('SHORT' in t or '6' in t for t in r.tips)


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
