"""Tests for poker/villain_tilt_detector.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.villain_tilt_detector import detect_villain_tilt, VillainTiltResult, tilt_one_liner


def _det(**kw):
    defaults = dict(
        current_vpip=0.48, baseline_vpip=0.28,
        current_avg_bet_size=0.85, baseline_avg_bet_size=0.55,
        current_3bet=0.14, baseline_3bet=0.06,
        current_wtsd=0.38, baseline_wtsd=0.22,
        consecutive_losses=3, big_pot_loss_bb=80.0,
        total_session_hands=45,
    )
    defaults.update(kw)
    return detect_villain_tilt(**defaults)


def test_returns_correct_type():
    r = _det()
    assert isinstance(r, VillainTiltResult)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _det()
    fields = [
        'current_vpip', 'baseline_vpip', 'current_avg_bet_size', 'baseline_avg_bet_size',
        'current_3bet', 'baseline_3bet', 'current_wtsd', 'baseline_wtsd',
        'consecutive_losses', 'big_pot_loss_bb', 'total_session_hands',
        'vpip_delta', 'bet_size_ratio', 'tilt_score', 'tilt_level', 'tilt_type',
        'exploitation_strategy', 'reliability_note', 'indicator_scores', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_tilt_score_range():
    r = _det()
    assert 0.0 <= r.tilt_score <= 1.0, f'Score out of range: {r.tilt_score}'
    print(f'Score: {r.tilt_score:.2f}')


def test_no_changes_no_tilt():
    """When current == baseline, no tilt detected."""
    r = _det(
        current_vpip=0.28, baseline_vpip=0.28,
        current_avg_bet_size=0.55, baseline_avg_bet_size=0.55,
        current_3bet=0.06, baseline_3bet=0.06,
        current_wtsd=0.22, baseline_wtsd=0.22,
        consecutive_losses=0, big_pot_loss_bb=0.0,
    )
    assert r.tilt_level == 'none', f'No change should = no tilt: {r.tilt_level} (score={r.tilt_score:.2f})'
    print(f'No change: tilt_level={r.tilt_level} score={r.tilt_score:.2f}')


def test_severe_tilt_all_indicators():
    """All indicators maxed → severe tilt."""
    r = _det(
        current_vpip=0.60, baseline_vpip=0.20,  # +40% VPIP
        current_avg_bet_size=1.50, baseline_avg_bet_size=0.50,  # 3x bet
        current_3bet=0.20, baseline_3bet=0.04,  # +16% 3bet
        current_wtsd=0.55, baseline_wtsd=0.20,  # +35% WTSD
        consecutive_losses=8, big_pot_loss_bb=200.0,
    )
    assert r.tilt_level == 'severe', f'All indicators maxed should be severe: {r.tilt_level} (score={r.tilt_score:.2f})'
    print(f'Severe: level={r.tilt_level} score={r.tilt_score:.2f}')


def test_vpip_delta_correct():
    """vpip_delta = current - baseline."""
    r = _det(current_vpip=0.40, baseline_vpip=0.25)
    expected = round(0.40 - 0.25, 3)
    assert abs(r.vpip_delta - expected) < 0.001, f'VPIP delta: {r.vpip_delta} vs {expected}'
    print(f'VPIP delta: {r.vpip_delta:+.0%}')


def test_bet_size_ratio_correct():
    """bet_size_ratio = current / baseline."""
    r = _det(current_avg_bet_size=0.90, baseline_avg_bet_size=0.60)
    expected = round(0.90 / 0.60, 2)
    assert abs(r.bet_size_ratio - expected) < 0.01, f'Bet ratio: {r.bet_size_ratio} vs {expected}'
    print(f'Bet ratio: {r.bet_size_ratio:.1f}x')


def test_tilt_level_thresholds():
    """Level brackets: none<0.30, moderate<0.60, significant<0.80, severe."""
    r_none = _det(
        current_vpip=0.28, baseline_vpip=0.28,
        current_avg_bet_size=0.55, baseline_avg_bet_size=0.55,
        current_3bet=0.06, baseline_3bet=0.06,
        current_wtsd=0.22, baseline_wtsd=0.22,
        consecutive_losses=0, big_pot_loss_bb=0.0,
    )
    assert r_none.tilt_level == 'none'
    print(f'None: score={r_none.tilt_score:.2f}')


def test_station_tilt_classification():
    """High WTSD + high VPIP, low 3bet → station_tilt."""
    r = _det(
        current_wtsd=0.42, baseline_wtsd=0.22,   # +20% WTSD
        current_vpip=0.45, baseline_vpip=0.25,   # +20% VPIP
        current_3bet=0.06, baseline_3bet=0.05,   # no 3bet change
        current_avg_bet_size=0.55, baseline_avg_bet_size=0.55,
        big_pot_loss_bb=80.0, consecutive_losses=3,
    )
    assert r.tilt_type == 'station_tilt', f'Expected station_tilt: {r.tilt_type}'
    print(f'Station tilt: {r.tilt_type}')


def test_aggression_tilt_classification():
    """High 3bet + high bet size → aggression_tilt."""
    r = _det(
        current_3bet=0.18, baseline_3bet=0.06,   # +12% 3bet
        current_avg_bet_size=1.00, baseline_avg_bet_size=0.55,  # 1.8x bet
        current_vpip=0.35, baseline_vpip=0.28,   # small VPIP change
        current_wtsd=0.25, baseline_wtsd=0.22,
        big_pot_loss_bb=80.0, consecutive_losses=2,
    )
    assert r.tilt_type == 'aggression_tilt', f'Expected aggression_tilt: {r.tilt_type}'
    print(f'Aggression tilt: {r.tilt_type}')


def test_indicator_scores_dict_correct():
    r = _det()
    expected_keys = {'vpip_spike', 'bet_size_spike', 'threbet_spike', 'wtsd_spike',
                     'consecutive_losses', 'big_pot_loss'}
    assert set(r.indicator_scores.keys()) == expected_keys
    for k, v in r.indicator_scores.items():
        assert 0.0 <= v <= 1.0, f'Score out of range: {k}={v}'
    print(f'Indicator scores: {r.indicator_scores}')


def test_exploitation_strategy_not_empty():
    r = _det()
    assert isinstance(r.exploitation_strategy, str) and len(r.exploitation_strategy) > 20
    print(f'Strategy: {r.exploitation_strategy[:60]}...')


def test_reliability_note_by_hands():
    r_small = _det(total_session_hands=15)
    r_big = _det(total_session_hands=100)
    assert 'LOW' in r_small.reliability_note.upper() or 'SMALL' in r_small.reliability_note.upper()
    assert 'SUFFICIENT' in r_big.reliability_note.upper()
    print(f'Small: {r_small.reliability_note[:40]}')
    print(f'Big: {r_big.reliability_note[:40]}')


def test_tips_not_empty():
    r = _det()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips: {len(r.tips)}')


def test_reasoning_not_empty():
    r = _det()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'Reasoning: {r.reasoning[:70]}...')


def test_more_losses_higher_score():
    """More consecutive losses → higher tilt score."""
    r_few = _det(consecutive_losses=1)
    r_many = _det(consecutive_losses=7)
    assert r_many.tilt_score >= r_few.tilt_score, \
        f'More losses should have higher score: {r_many.tilt_score:.2f} vs {r_few.tilt_score:.2f}'
    print(f'Score: 1loss={r_few.tilt_score:.2f} 7loss={r_many.tilt_score:.2f}')


def test_bigger_pot_loss_higher_score():
    """Bigger pot loss → higher tilt score."""
    r_small = _det(big_pot_loss_bb=10.0, consecutive_losses=0)
    r_large = _det(big_pot_loss_bb=150.0, consecutive_losses=0)
    assert r_large.tilt_score >= r_small.tilt_score, \
        f'Larger pot loss should have higher score: {r_large.tilt_score:.2f} vs {r_small.tilt_score:.2f}'
    print(f'Score: 10BB loss={r_small.tilt_score:.2f} 150BB loss={r_large.tilt_score:.2f}')


def test_small_sample_tip_for_few_hands():
    """Few hands → warning tip in output."""
    r = _det(total_session_hands=12)
    tip_text = ' '.join(r.tips).lower()
    assert 'sample' in tip_text or 'hand' in tip_text, 'Should warn about small sample'
    print(f'Small sample warning present')


def test_passive_tilt_classification():
    """VPIP down + WTSD down → passive_tilt."""
    r = _det(
        current_vpip=0.10, baseline_vpip=0.25,  # VPIP DOWN
        current_wtsd=0.10, baseline_wtsd=0.22,  # WTSD DOWN
        current_avg_bet_size=0.55, baseline_avg_bet_size=0.55,
        current_3bet=0.06, baseline_3bet=0.06,
        consecutive_losses=4, big_pot_loss_bb=100.0,
    )
    assert r.tilt_type == 'passive_tilt', f'Expected passive_tilt: {r.tilt_type}'
    print(f'Passive tilt: {r.tilt_type}')


def test_tilt_type_valid():
    valid = {'no_tilt', 'station_tilt', 'aggression_tilt', 'maniac_tilt', 'steam_tilt', 'passive_tilt'}
    r = _det()
    assert r.tilt_type in valid, f'Invalid tilt type: {r.tilt_type}'
    print(f'Tilt type: {r.tilt_type}')


def test_one_liner():
    r = _det()
    line = tilt_one_liner(r)
    assert 'TILT' in line and 'score=' in line and 'level=' in line and 'type=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_tilt_score_range, test_no_changes_no_tilt,
        test_severe_tilt_all_indicators, test_vpip_delta_correct,
        test_bet_size_ratio_correct, test_tilt_level_thresholds,
        test_station_tilt_classification, test_aggression_tilt_classification,
        test_indicator_scores_dict_correct, test_exploitation_strategy_not_empty,
        test_reliability_note_by_hands, test_tips_not_empty,
        test_reasoning_not_empty, test_more_losses_higher_score,
        test_bigger_pot_loss_higher_score, test_small_sample_tip_for_few_hands,
        test_passive_tilt_classification, test_tilt_type_valid,
        test_one_liner,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f'  PASS  {t.__name__}')
        except Exception as e:
            print(f'  FAIL  {t.__name__}: {e}')
            import traceback; traceback.print_exc()
            failed += 1
    print(f'\n{len(tests)-failed}/{len(tests)} passed')
    sys.exit(failed)
