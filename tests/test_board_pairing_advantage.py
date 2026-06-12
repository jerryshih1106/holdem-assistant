"""Tests for board_pairing_advantage.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.board_pairing_advantage import (
    analyze_board_pairing, BoardPairingResult, bpa_one_liner,
    _pairing_advantage_score, _draw_devaluation, _strategic_adjustment,
)


def _bpa(**kw):
    defaults = dict(
        paired_card='7', hero_is_pfr=True,
        position='ip', board_texture='dry',
        hero_hand='top_pair', pot_bb=20.0, street='turn',
    )
    defaults.update(kw)
    return analyze_board_pairing(**defaults)


def test_returns_result():
    assert isinstance(_bpa(), BoardPairingResult)


def test_ace_pairing_benefits_pfr():
    score = _pairing_advantage_score(14, True, 'ip')
    assert score >= 7.0


def test_low_card_pairing_benefits_defender():
    score = _pairing_advantage_score(3, False, 'oop')
    assert score >= 6.0


def test_pfr_ace_board_benefits_hero():
    r = _bpa(paired_card='A', hero_is_pfr=True)
    assert r.hero_benefits is True


def test_defender_low_board_benefits_hero():
    r = _bpa(paired_card='3', hero_is_pfr=False)
    assert r.hero_benefits is True


def test_pfr_low_board_hurts_hero():
    r = _bpa(paired_card='3', hero_is_pfr=True)
    assert r.hero_benefits is False


def test_ip_vs_oop_advantage():
    score_ip  = _pairing_advantage_score(10, True, 'ip')
    score_oop = _pairing_advantage_score(10, True, 'oop')
    assert score_ip > score_oop


def test_draw_devaluation_high_on_two_tone():
    deval = _draw_devaluation('two_tone', 7)
    assert deval >= 0.25


def test_draw_devaluation_low_on_dry():
    deval = _draw_devaluation('dry', 7)
    assert deval <= 0.15


def test_advantage_score_in_range():
    r = _bpa()
    assert 0 <= r.advantage_score <= 10


def test_hero_benefits_flag_consistent():
    r = _bpa(paired_card='A', hero_is_pfr=True)
    assert r.hero_benefits == (r.advantage_score >= 5.0)


def test_tips_populated():
    r = _bpa()
    assert len(r.tips) >= 2


def test_strong_hand_tip():
    r = _bpa(hero_hand='trips')
    assert any('trips' in t.lower() or 'STRONG' in t or 'full_house' in t.lower() for t in r.tips)


def test_high_card_tip():
    r = _bpa(paired_card='A', hero_is_pfr=True)
    assert any('A' in t or 'high' in t.lower() or 'HIGH' in t for t in r.tips)


def test_low_card_tip():
    r = _bpa(paired_card='3', hero_is_pfr=True)
    assert any('low' in t.lower() or 'LOW' in t for t in r.tips)


def test_one_liner_format():
    r = _bpa()
    line = bpa_one_liner(r)
    assert '[BPA' in line


def test_paired_card_stored():
    r = _bpa(paired_card='K')
    assert r.paired_card == 'K'


def test_strategic_adjustment_stored():
    r = _bpa()
    assert r.strategic_adjustment is not None and len(r.strategic_adjustment) > 0


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
