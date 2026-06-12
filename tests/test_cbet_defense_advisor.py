"""Tests for cbet_defense_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.cbet_defense_advisor import (
    advise_cbet_defense, CbetDefenseResult, cbd_one_liner,
    _mdf, _determine_action, _raise_size,
    CALL_EQUITY_THRESHOLD, RAISE_HANDS,
)


def _cbd(**kw):
    defaults = dict(
        hand_category='top_pair', board_texture='dry', hero_position='ip',
        hero_equity=0.55, villain_cbet_size_frac=0.67, villain_fcbet=0.50,
        villain_af=2.0, pot_bb=15.0,
    )
    defaults.update(kw)
    return advise_cbet_defense(**defaults)


def test_returns_cbet_defense_result():
    assert isinstance(_cbd(), CbetDefenseResult)


def test_mdf_formula():
    mdf = _mdf(0.67)
    assert abs(mdf - (1 - 0.67/1.67)) < 0.01


def test_mdf_half_pot():
    mdf = _mdf(0.50)
    assert abs(mdf - (2/3)) < 0.01


def test_set_raises_on_dry():
    action, _ = _determine_action('set', 0.88, 'oop', 'dry', 0.67, 0.50, 2.0)
    assert action == 'raise'


def test_air_folds():
    action, _ = _determine_action('air', 0.05, 'oop', 'dry', 0.67, 0.50, 2.0)
    assert action == 'fold'


def test_top_pair_calls_ip():
    action, _ = _determine_action('top_pair', 0.60, 'ip', 'dry', 0.67, 0.50, 2.0)
    assert action in ('call', 'raise')


def test_oop_higher_call_threshold():
    ip_thresh = CALL_EQUITY_THRESHOLD.get(('ip', 'dry'), 0.30)
    oop_thresh = CALL_EQUITY_THRESHOLD.get(('oop', 'dry'), 0.36)
    assert oop_thresh > ip_thresh


def test_wet_higher_call_threshold():
    dry_thresh = CALL_EQUITY_THRESHOLD.get(('ip', 'dry'), 0.30)
    wet_thresh = CALL_EQUITY_THRESHOLD.get(('ip', 'wet'), 0.35)
    assert wet_thresh >= dry_thresh


def test_raise_size_reasonable():
    size = _raise_size(10.0, 15.0)
    assert size >= 10.0 * 2.0


def test_mdf_stored():
    r = _cbd()
    assert 0 < r.mdf < 1.0


def test_action_stored():
    r = _cbd()
    assert r.recommended_action in ('fold', 'call', 'raise')


def test_confidence_stored():
    r = _cbd()
    assert 0 < r.confidence <= 1.0


def test_high_fcbet_reduces_raise_threshold():
    r_high = _cbd(villain_fcbet=0.80, hand_category='oesd')
    r_low = _cbd(villain_fcbet=0.30, hand_category='oesd')
    # High FCBet should favor raising more
    assert r_high.call_threshold <= r_low.call_threshold


def test_raise_hands_contains_set():
    assert 'set' in RAISE_HANDS.get('dry', set())


def test_tips_populated():
    r = _cbd()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _cbd()
    line = cbd_one_liner(r)
    assert '[CBD' in line
    assert 'MDF=' in line


def test_high_af_tip():
    r = _cbd(villain_af=3.5)
    assert any('AF' in t or 'barrel' in t.lower() for t in r.tips)


def test_raise_tip_present_when_raising():
    r = _cbd(hand_category='set', hero_position='oop')
    if r.recommended_action == 'raise':
        assert r.raise_size_bb > 0


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
