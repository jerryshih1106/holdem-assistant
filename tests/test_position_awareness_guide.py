"""Tests for position_awareness_guide.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.position_awareness_guide import (
    guide_position_play, PositionGuide, pag_one_liner,
    _positional_advantage_score, _position_category, _ip_or_oop,
    _recommended_open_pct, POSITIONAL_ADVANTAGE, POSITION_OPEN_PCT,
)


def _pag(**kw):
    defaults = dict(
        hero_position='btn',
        villain_position='bb',
        street='flop',
        hero_hand_category='top_pair',
        hero_equity=0.62,
        pot_bb=20.0,
        spr=5.0,
        villain_af=2.2,
        board_texture='semi_wet',
    )
    defaults.update(kw)
    return guide_position_play(**defaults)


def test_returns_position_guide():
    r = _pag()
    assert isinstance(r, PositionGuide)


def test_btn_vs_bb_high_score():
    score = _positional_advantage_score('btn', 'bb')
    assert score >= 8


def test_utg_vs_btn_low_score():
    score = _positional_advantage_score('utg', 'btn')
    assert score <= 2


def test_position_category_dominant():
    cat = _position_category(9)
    assert cat == 'dominant_ip'


def test_position_category_strong_oop():
    cat = _position_category(1)
    assert cat == 'strong_oop'


def test_position_category_neutral():
    cat = _position_category(3)
    assert cat == 'neutral'


def test_btn_vs_bb_is_ip():
    pos = _ip_or_oop('btn', 'bb')
    assert pos == 'ip'


def test_bb_vs_btn_is_oop():
    pos = _ip_or_oop('bb', 'btn')
    assert pos == 'oop'


def test_sb_vs_bb_is_oop():
    pos = _ip_or_oop('sb', 'bb')
    assert pos == 'oop'


def test_bb_vs_sb_is_ip():
    pos = _ip_or_oop('bb', 'sb')
    assert pos == 'ip'


def test_btn_open_pct_highest():
    btn = _recommended_open_pct('btn')
    utg = _recommended_open_pct('utg')
    assert btn > utg


def test_bb_open_pct_zero():
    assert _recommended_open_pct('bb') == 0.0


def test_utg_tighter_than_co():
    utg = _recommended_open_pct('utg')
    co = _recommended_open_pct('co')
    assert utg < co


def test_positional_score_stored():
    r = _pag()
    assert 1 <= r.positional_advantage_score <= 10


def test_position_category_stored():
    r = _pag()
    assert r.position_category in ('dominant_ip', 'strong_ip', 'slight_ip',
                                    'neutral', 'slight_oop', 'strong_oop')


def test_is_ip_stored():
    r = _pag()
    assert r.is_ip in ('ip', 'oop')


def test_open_pct_stored():
    r = _pag()
    assert 0.0 <= r.recommended_open_pct <= 0.60


def test_action_advice_stored():
    r = _pag()
    assert isinstance(r.action_advice, str)
    assert len(r.action_advice) > 20


def test_tips_populated():
    r = _pag()
    assert len(r.tips) >= 2


def test_dominant_ip_tip():
    r = _pag(hero_position='btn', villain_position='bb')
    combined = ' '.join(r.tips).lower()
    assert 'ip' in combined or 'position' in combined or 'score' in combined


def test_oop_tip():
    r = _pag(hero_position='bb', villain_position='btn')
    combined = ' '.join(r.tips).lower()
    assert 'oop' in combined or 'check' in combined or 'tighten' in combined


def test_bb_defense_tip():
    r = _pag(hero_position='bb', villain_position='btn')
    combined = ' '.join(r.tips).lower()
    assert 'bb' in combined or 'defend' in combined or 'check' in combined


def test_utg_has_low_score():
    r = _pag(hero_position='utg', villain_position='btn')
    assert r.positional_advantage_score <= 2


def test_btn_vs_bb_dominant():
    r = _pag(hero_position='btn', villain_position='bb')
    assert r.position_category in ('dominant_ip', 'strong_ip')
    assert r.is_ip == 'ip'


def test_one_liner_format():
    r = _pag()
    line = pag_one_liner(r)
    assert '[PAG' in line
    assert 'score=' in line
    assert 'open=' in line


def test_one_liner_contains_ip_oop():
    r = _pag()
    line = pag_one_liner(r)
    assert 'IP' in line or 'OOP' in line


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
