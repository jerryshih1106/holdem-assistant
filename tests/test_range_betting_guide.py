"""Tests for range_betting_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.range_betting_guide import (
    analyze_range_betting, RangeBettingResult, rbg_one_liner,
    _range_advantage, _range_bet_decision, _recommended_sizing,
    RANGE_ADVANTAGE_BASELINE, RANGE_BET_THRESHOLD, RANGE_BET_SIZING, MIXED_SIZING,
    VILLAIN_RANGE_MODIFIER,
)


def _rbg(**kw):
    defaults = dict(
        scenario='btn_vs_bb', board_texture='dry',
        villain_type='reg', position='ip',
    )
    defaults.update(kw)
    return analyze_range_betting(**defaults)


def test_returns_result():
    assert isinstance(_rbg(), RangeBettingResult)


def test_btn_dry_has_high_range_adv():
    adv = _range_advantage('btn_vs_bb', 'dry', 'reg', 'ip')
    assert adv >= RANGE_BET_THRESHOLD


def test_utg_wet_low_range_adv():
    adv = _range_advantage('utg_vs_bb', 'wet', 'reg', 'ip')
    assert adv < RANGE_BET_THRESHOLD


def test_dry_board_range_bet_decision():
    d = _range_bet_decision(0.67, 'dry', 'ip')
    assert 'RANGE_BET' in d


def test_low_adv_mixed_decision():
    d = _range_bet_decision(0.52, 'semi_wet', 'ip')
    assert 'MIXED' in d or 'CHECK' in d


def test_check_decision_below_threshold():
    d = _range_bet_decision(0.44, 'wet', 'ip')
    assert 'CHECK' in d or 'MIXED' in d


def test_oop_wet_forces_check():
    d = _range_bet_decision(0.62, 'wet', 'oop')
    assert 'CHECK' in d or 'OOP' in d


def test_range_bet_sizing_dry_small():
    size = _recommended_sizing('RANGE_BET_STRONG', 'dry')
    assert size <= 0.35


def test_range_bet_sizing_wet_larger():
    dry = _recommended_sizing('RANGE_BET_STRONG', 'dry')
    wet = _recommended_sizing('RANGE_BET_STRONG', 'wet')
    assert wet > dry


def test_nit_reduces_range_adv():
    nit = _range_advantage('btn_vs_bb', 'dry', 'nit', 'ip')
    reg = _range_advantage('btn_vs_bb', 'dry', 'reg', 'ip')
    assert nit < reg


def test_fish_increases_range_adv():
    fish = _range_advantage('btn_vs_bb', 'dry', 'fish', 'ip')
    reg  = _range_advantage('btn_vs_bb', 'dry', 'reg', 'ip')
    assert fish > reg


def test_range_adv_in_range():
    r = _rbg()
    assert 0.30 <= r.range_advantage <= 0.85


def test_should_range_bet_dry():
    r = _rbg(board_texture='dry')
    assert r.should_range_bet is True


def test_tips_populated():
    r = _rbg()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _rbg()
    line = rbg_one_liner(r)
    assert '[RBG' in line and 'adv=' in line


def test_wet_tip_warns_oop():
    r = _rbg(board_texture='wet', position='oop')
    assert any('OOP' in t or 'WARNING' in t for t in r.tips)


def test_nit_tip_present():
    r = _rbg(villain_type='nit', board_texture='wet')
    texts = ' '.join(r.tips)
    assert 'NIT' in texts or 'nit' in texts.lower()


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
