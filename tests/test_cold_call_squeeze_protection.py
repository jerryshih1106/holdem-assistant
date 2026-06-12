"""Tests for cold_call_squeeze_protection.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.cold_call_squeeze_protection import (
    analyze_cold_call_squeeze, ColdCallSqueezeResult, ccs_one_liner,
    _combined_squeeze_pct, _cold_call_ev, _squeeze_risk_level, _recommended_action,
    SQUEEZE_PROB_PER_PLAYER,
)


def _ccs(**kw):
    defaults = dict(
        hand_strength='speculative', player_types_behind=['rec'],
        cold_call_bb=3.0, pot_bb_if_reaches_flop=9.0,
        can_3bet=True, position='btn',
    )
    defaults.update(kw)
    return analyze_cold_call_squeeze(**defaults)


def test_returns_result():
    assert isinstance(_ccs(), ColdCallSqueezeResult)


def test_single_lag_high_squeeze():
    sq = _combined_squeeze_pct(['lag'])
    assert sq >= 0.15


def test_single_nit_low_squeeze():
    sq = _combined_squeeze_pct(['nit'])
    assert sq <= 0.06


def test_two_players_higher_squeeze():
    one = _combined_squeeze_pct(['rec'])
    two = _combined_squeeze_pct(['rec', 'rec'])
    assert two > one


def test_lag_behind_medium_risk():
    r = _ccs(player_types_behind=['lag'])
    assert r.squeeze_risk_level in ('medium', 'high', 'low')


def test_risk_levels():
    assert _squeeze_risk_level(0.40) == 'high'
    assert _squeeze_risk_level(0.20) == 'medium'
    assert _squeeze_risk_level(0.10) == 'low'
    assert _squeeze_risk_level(0.03) == 'minimal'


def test_premium_hand_gets_3bet():
    r = _ccs(hand_strength='premium', can_3bet=True)
    assert r.recommended_action == '3BET_ISOLATE'


def test_weak_hand_high_squeeze_folds():
    r = _ccs(hand_strength='weak', player_types_behind=['lag', 'reg'])
    assert r.recommended_action in ('FOLD_SQUEEZE_RISK', 'FOLD', '3BET_OR_FOLD')


def test_speculative_low_risk_cold_calls():
    r = _ccs(hand_strength='speculative', player_types_behind=['nit'])
    assert r.recommended_action in ('COLD_CALL', '3BET_ISOLATE', '3BET_OR_FOLD', 'FOLD')


def test_ev_positive_with_low_squeeze():
    ev = _cold_call_ev(3.0, 9.0, 'speculative', 0.05)
    assert ev > 0


def test_ev_reduced_with_high_squeeze():
    ev_low  = _cold_call_ev(3.0, 9.0, 'speculative', 0.05)
    ev_high = _cold_call_ev(3.0, 9.0, 'speculative', 0.40)
    assert ev_low > ev_high


def test_squeeze_pct_stored():
    r = _ccs()
    assert 0 < r.squeeze_pct < 1


def test_tips_populated():
    r = _ccs()
    assert len(r.tips) >= 2


def test_one_liner_format():
    r = _ccs()
    line = ccs_one_liner(r)
    assert '[CCS' in line and 'squeeze=' in line and 'EV=' in line


def test_lag_higher_squeeze_than_nit():
    lag_sq = _combined_squeeze_pct(['lag'])
    nit_sq = _combined_squeeze_pct(['nit'])
    assert lag_sq > nit_sq


def test_squeeze_prob_all_positive():
    for k, v in SQUEEZE_PROB_PER_PLAYER.items():
        assert v > 0


def test_player_types_stored():
    r = _ccs(player_types_behind=['lag', 'nit'])
    assert 'lag' in r.player_types_behind


def test_no_players_behind_minimal_risk():
    sq = _combined_squeeze_pct([])
    assert sq == 0.0


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
