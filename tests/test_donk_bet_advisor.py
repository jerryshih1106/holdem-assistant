"""Tests for donk_bet_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.donk_bet_advisor import (
    advise_donk_bet, DonkBetResult, dnk_one_liner,
    _board_donk_score, _oop_range_advantage, _donk_sizing, _donk_verdict,
)


def _dnk(**kw):
    defaults = dict(
        hero_hand='top_pair', board_texture='connected',
        top_card_rank=7, pot_bb=12.0,
        position_vs_pfr='oop', pfr_cbet_pct=0.65,
        street='flop',
    )
    defaults.update(kw)
    return advise_donk_bet(**defaults)


def test_returns_donk_bet_result():
    assert isinstance(_dnk(), DonkBetResult)


def test_low_board_high_score():
    score = _board_donk_score('connected', 6)
    assert score >= 5


def test_high_board_low_score():
    score = _board_donk_score('dry', 14)  # A board
    assert score <= 0


def test_low_board_strong_donk():
    r = _dnk(board_texture='connected', top_card_rank=5)
    assert r.recommendation in ('STRONG_DONK', 'DONK_BET')


def test_ace_board_no_donk():
    r = _dnk(board_texture='dry', top_card_rank=14)
    assert r.recommendation in ('CHECK_RAISE_OR_CALL', 'CHECK_FIRST')


def test_connected_board_higher_advantage_than_dry():
    adv_connected = _oop_range_advantage('top_pair', 'connected', 6)
    adv_dry_high  = _oop_range_advantage('top_pair', 'dry', 14)
    assert adv_connected > adv_dry_high


def test_set_gets_large_sizing():
    size_set = _donk_sizing('set', 0.70, 7)
    size_weak = _donk_sizing('air', 0.50, 3)
    assert size_set > size_weak


def test_draw_gets_medium_sizing():
    size = _donk_sizing('flush_draw', 0.60, 5)
    assert 0.40 <= size <= 0.65


def test_optimal_bet_bb_matches_size():
    r = _dnk(pot_bb=15.0)
    expected = round(15.0 * r.optimal_size_frac, 1)
    assert abs(r.optimal_bet_bb - expected) < 0.2


def test_donk_score_stored():
    r = _dnk()
    assert -5 <= r.donk_score <= 10


def test_range_advantage_in_bounds():
    r = _dnk()
    assert 0.0 < r.range_advantage <= 1.0


def test_tips_populated():
    r = _dnk()
    assert len(r.tips) >= 2


def test_draw_protection_tip():
    r = _dnk(hero_hand='flush_draw')
    assert any('draw' in t.lower() or 'protect' in t.lower() for t in r.tips)


def test_high_board_tip():
    r = _dnk(board_texture='dry', top_card_rank=14)
    assert any('high' in t.lower() or 'HIGH' in t or 'A' in t for t in r.tips)


def test_low_board_tip():
    r = _dnk(board_texture='connected', top_card_rank=5)
    assert any('low' in t.lower() or 'LOW' in t or 'range' in t.lower() for t in r.tips)


def test_one_liner_format():
    r = _dnk()
    line = dnk_one_liner(r)
    assert '[DNK' in line and 'range_adv=' in line


def test_verdict_contains_recommendation():
    r = _dnk()
    assert r.recommendation in r.verdict


def test_high_cbet_pct_tip():
    r = _dnk(pfr_cbet_pct=0.80)
    assert any('c-bet' in t.lower() or 'cbet' in t.lower() or 'C-BETS' in t for t in r.tips)


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
