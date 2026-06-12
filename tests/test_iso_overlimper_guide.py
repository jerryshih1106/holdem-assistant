"""Tests for iso_overlimper_guide.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.iso_overlimper_guide import (
    analyze_iso_overlimper, IsoOverlimperResult, iso_one_liner,
    _iso_sizing, _hand_score, _iso_threshold, _squeeze_risk, _iso_ev,
    ISO_BASE_SIZING_BB, HAND_STRENGTH_ESTIMATE,
)


def _iso(**kw):
    defaults = dict(
        hand='AJs',
        n_limpers=1,
        limper_type='rec',
        position='ip',
        pot_bb=3.5,
        players_behind=2,
        aggressive_behind=False,
    )
    defaults.update(kw)
    return analyze_iso_overlimper(**defaults)


def test_returns_result():
    assert isinstance(_iso(), IsoOverlimperResult)


def test_single_limper_base_size():
    size = _iso_sizing(1, 'rec')
    assert size >= 4.0


def test_fish_limper_larger_size():
    fish_size = _iso_sizing(1, 'fish')
    reg_size  = _iso_sizing(1, 'reg')
    assert fish_size > reg_size


def test_more_limpers_bigger_size():
    s1 = _iso_sizing(1, 'rec')
    s3 = _iso_sizing(3, 'rec')
    assert s3 > s1


def test_oop_threshold_higher():
    ip_t  = _iso_threshold(1, 'ip')
    oop_t = _iso_threshold(1, 'oop')
    assert oop_t > ip_t


def test_threshold_increases_with_limpers():
    t1 = _iso_threshold(1, 'ip')
    t3 = _iso_threshold(3, 'ip')
    assert t3 > t1


def test_aa_high_hand_score():
    assert _hand_score('AA') >= 0.90


def test_22_low_hand_score():
    assert _hand_score('22') < 0.55


def test_squeeze_risk_increases_with_players():
    low  = _squeeze_risk(1, False)
    high = _squeeze_risk(4, False)
    assert high > low


def test_aggressive_behind_increases_risk():
    base = _squeeze_risk(2, False)
    agg  = _squeeze_risk(2, True)
    assert agg > base


def test_strong_hand_iso_action():
    r = _iso(hand='AA', n_limpers=1, position='ip')
    assert r.recommended_action in ('ISO_RAISE', 'ISO_RAISE_BORDERLINE', 'ISO_RAISE_LARGE')


def test_weak_hand_fold_or_overlimp():
    r = _iso(hand='22', n_limpers=3, position='oop')
    assert r.recommended_action in ('FOLD', 'OVER_LIMP', 'FOLD_SQUEEZE_RISK')


def test_high_squeeze_risk_folds_marginal():
    r = _iso(hand='ATs', n_limpers=1, players_behind=5, aggressive_behind=True)
    assert r.recommended_action in ('FOLD', 'FOLD_SQUEEZE_RISK', 'ISO_RAISE_BORDERLINE', 'ISO_RAISE')


def test_tips_populated():
    r = _iso()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _iso()
    line = iso_one_liner(r)
    assert '[ISO' in line and 'EV=' in line


def test_fish_tip_present():
    r = _iso(limper_type='fish')
    assert any('FISH' in t for t in r.tips)


def test_nit_tip_present():
    r = _iso(limper_type='nit')
    assert any('NIT' in t for t in r.tips)


def test_iso_ev_stored():
    r = _iso(hand='KQs')
    assert isinstance(r.iso_ev, float)


def test_all_hand_scores_valid():
    for hand, score in HAND_STRENGTH_ESTIMATE.items():
        assert 0 < score <= 1


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
