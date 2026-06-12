"""Tests for hand_reading_guide.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.hand_reading_guide import (
    read_villain_hand, HandReadingGuide, hrg_one_liner,
    _build_line, _normalize_texture, _lookup_hand_buckets,
    _river_specific_bucket, _most_likely, _confidence,
    _check_raise_warning, _donk_warning,
    LINE_TO_HAND_MAP, RIVER_ACTION_BUCKETS,
)


def _hrg(**kw):
    defaults = dict(
        preflop_action='open',
        villain_position='btn',
        flop_action='bet_medium',
        turn_action='bet',
        river_action='bet_large',
        board_texture='dry',
        villain_vpip=0.28,
        villain_af=2.5,
    )
    defaults.update(kw)
    return read_villain_hand(**defaults)


def test_returns_hand_reading_guide():
    r = _hrg()
    assert isinstance(r, HandReadingGuide)


def test_build_line_bet_bet_bet():
    line = _build_line('bet_medium', 'bet', 'bet_large')
    assert line == 'bet_bet_bet'


def test_build_line_check_bet_check():
    line = _build_line('check', 'bet', 'check_call')
    assert line == 'check_bet_check'


def test_build_line_raise_treated_as_bet():
    line = _build_line('check_raise', 'bet', 'bet_large')
    assert line == 'bet_bet_bet'


def test_normalize_wet():
    assert _normalize_texture('wet') == 'wet'


def test_normalize_monotone_is_wet():
    assert _normalize_texture('monotone') == 'wet'


def test_normalize_dry():
    assert _normalize_texture('dry') == 'dry'


def test_normalize_semi_wet_is_dry():
    assert _normalize_texture('semi_wet') == 'dry'


def test_lookup_bet_bet_bet_dry():
    buckets = _lookup_hand_buckets('bet_bet_bet', 'dry')
    assert len(buckets) > 0
    assert 'top_pair' in buckets or 'overpair' in buckets


def test_lookup_check_check_check_dry():
    buckets = _lookup_hand_buckets('check_check_check', 'dry')
    assert len(buckets) > 0


def test_river_bucket_large_bet():
    buckets = _river_specific_bucket('bet_large')
    assert 'nuts' in buckets or 'near_nuts' in buckets


def test_river_bucket_check_call():
    buckets = _river_specific_bucket('check_call')
    assert 'bluff_catcher' in buckets or 'top_pair' in buckets


def test_river_bucket_check_raise():
    buckets = _river_specific_bucket('check_raise')
    assert 'nuts' in buckets


def test_most_likely_returns_first():
    assert _most_likely(['a', 'b', 'c']) == 'a'


def test_confidence_high_af_boost():
    low_conf = _confidence(['a', 'b', 'c', 'd'], 0.28, 1.0, 'open')
    high_conf = _confidence(['a', 'b', 'c', 'd'], 0.28, 3.0, 'open')
    assert high_conf > low_conf


def test_confidence_loose_villain_reduces():
    tight = _confidence(['a', 'b'], 0.25, 2.5, 'open')
    loose = _confidence(['a', 'b'], 0.55, 2.5, 'open')
    assert tight >= loose


def test_check_raise_warning():
    assert _check_raise_warning('check_raise') is True
    assert _check_raise_warning('bet_medium') is False


def test_donk_warning_bb():
    assert _donk_warning('bet', 'bb') is True


def test_donk_warning_btn():
    assert _donk_warning('bet_medium', 'btn') is False


def test_line_signature_stored():
    r = _hrg()
    assert r.line_signature == 'bet_bet_bet'


def test_confidence_range():
    r = _hrg()
    assert 0.0 <= r.confidence <= 0.90


def test_most_likely_stored():
    r = _hrg()
    assert isinstance(r.most_likely_hand, str)
    assert len(r.most_likely_hand) > 0


def test_is_check_raise_detected():
    r = _hrg(flop_action='check_raise')
    assert r.is_check_raise is True


def test_is_not_check_raise():
    r = _hrg(flop_action='bet_medium')
    assert r.is_check_raise is False


def test_is_donk_detected():
    r = _hrg(villain_position='bb', flop_action='bet')
    assert r.is_donk_bet is True


def test_tips_populated():
    r = _hrg()
    assert len(r.tips) >= 3


def test_one_liner_format():
    r = _hrg()
    line = hrg_one_liner(r)
    assert '[HRG' in line
    assert 'conf=' in line


def test_triple_barrel_likely_strong():
    r = _hrg(flop_action='bet_medium', turn_action='bet', river_action='bet_large')
    assert r.most_likely_hand != 'unknown'


def test_check_check_bet_likely_weak():
    r = _hrg(flop_action='check', turn_action='check', river_action='bet_medium')
    assert r.most_likely_hand != 'nuts'


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
