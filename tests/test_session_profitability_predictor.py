"""Tests for poker/session_profitability_predictor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.session_profitability_predictor import predict_session, SessionPrediction, spp_one_liner


def _spp(**kw):
    defaults = dict(
        hero_win_rate_bb100=4.0, fish_count=1, reg_count=3,
        hero_tilt_risk=0.1, planned_hours=4.0,
        game_format='6max', hero_std_dev_bb100=80.0, n_players=6,
    )
    defaults.update(kw)
    return predict_session(**defaults)


def test_returns_correct_type():
    r = _spp()
    assert isinstance(r, SessionPrediction)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _spp()
    fields = [
        'hero_win_rate_bb100', 'fish_count', 'reg_count', 'hero_tilt_risk',
        'planned_hours', 'game_format', 'hero_std_dev_bb100', 'n_players',
        'game_quality', 'quality_multiplier', 'tilt_penalty_bb100',
        'adjusted_wr_bb100', 'est_hands', 'session_ev_bb', 'session_std_dev_bb',
        'prob_positive_session', 'session_recommendation', 'recommended_hours',
        'stop_loss_bb', 'take_profit_bb', 'hourly_ev_bb', 'verdict', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_game_quality_excellent_with_3_fish():
    r = _spp(fish_count=3, reg_count=2, n_players=6)
    assert r.game_quality == 'excellent', f'3 fish should be excellent: {r.game_quality}'
    print(f'3 fish -> quality: {r.game_quality}')


def test_game_quality_tough_with_no_fish():
    r = _spp(fish_count=0, reg_count=5, n_players=6)
    assert r.game_quality in ('tough', 'terrible'), f'0 fish should be tough+: {r.game_quality}'
    print(f'0 fish -> quality: {r.game_quality}')


def test_adjusted_wr_lower_with_tilt():
    r_fresh = _spp(hero_tilt_risk=0.0)
    r_tilted = _spp(hero_tilt_risk=0.5)
    assert r_tilted.adjusted_wr_bb100 < r_fresh.adjusted_wr_bb100, \
        f'Tilt should reduce WR: fresh={r_fresh.adjusted_wr_bb100} tilted={r_tilted.adjusted_wr_bb100}'
    print(f'Adj WR: fresh={r_fresh.adjusted_wr_bb100:+.2f} tilted={r_tilted.adjusted_wr_bb100:+.2f}')


def test_skip_recommendation_on_high_tilt():
    r = _spp(hero_tilt_risk=0.9)
    assert r.session_recommendation == 'skip', \
        f'High tilt should skip: {r.session_recommendation}'
    print(f'Tilt=90% -> rec: {r.session_recommendation}')


def test_play_recommendation_on_good_conditions():
    r = _spp(fish_count=2, hero_tilt_risk=0.1, hero_win_rate_bb100=5.0)
    assert r.session_recommendation in ('play', 'short_session'), \
        f'Good conditions should play: {r.session_recommendation}'
    print(f'Good conditions -> rec: {r.session_recommendation}')


def test_session_ev_positive_when_adj_wr_positive():
    r = _spp(hero_win_rate_bb100=5.0, fish_count=2, hero_tilt_risk=0.0)
    assert r.session_ev_bb > 0, f'Positive WR should have positive EV: {r.session_ev_bb}'
    print(f'Session EV: {r.session_ev_bb:+.0f}BB')


def test_session_ev_negative_when_adj_wr_negative():
    r = _spp(hero_win_rate_bb100=2.0, fish_count=0, reg_count=5, hero_tilt_risk=0.8)
    assert r.session_ev_bb < 0 or r.adjusted_wr_bb100 < 0, \
        f'Bad conditions: adj_wr={r.adjusted_wr_bb100}'
    print(f'Bad conditions: adj_wr={r.adjusted_wr_bb100:+.2f}BB/100')


def test_prob_positive_between_0_and_1():
    r = _spp()
    assert 0.0 <= r.prob_positive_session <= 1.0, \
        f'Probability out of range: {r.prob_positive_session}'
    print(f'Prob positive: {r.prob_positive_session:.1%}')


def test_stop_loss_negative():
    r = _spp()
    assert r.stop_loss_bb < 0, f'Stop loss should be negative: {r.stop_loss_bb}'
    print(f'Stop loss: {r.stop_loss_bb:.0f}BB')


def test_stop_loss_between_minus50_and_minus200():
    r = _spp()
    assert -200 <= r.stop_loss_bb <= -50, \
        f'Stop loss out of range: {r.stop_loss_bb}'
    print(f'Stop loss within range: {r.stop_loss_bb:.0f}BB')


def test_est_hands_proportional_to_hours():
    r1 = _spp(planned_hours=2.0)
    r2 = _spp(planned_hours=4.0)
    assert r2.est_hands == r1.est_hands * 2, \
        f'Hands not proportional: {r1.est_hands} vs {r2.est_hands}'
    print(f'Hands 2h={r1.est_hands} 4h={r2.est_hands}')


def test_quality_multiplier_excellent_above_1():
    r = _spp(fish_count=3, reg_count=1)
    assert r.quality_multiplier > 1.0, \
        f'Excellent quality should have mult > 1: {r.quality_multiplier}'
    print(f'Excellent quality mult: {r.quality_multiplier:.2f}x')


def test_quality_multiplier_tough_below_1():
    r = _spp(fish_count=0, reg_count=5)
    assert r.quality_multiplier < 1.0, \
        f'Tough quality should have mult < 1: {r.quality_multiplier}'
    print(f'Tough quality mult: {r.quality_multiplier:.2f}x')


def test_hourly_ev_positive_when_adj_wr_positive():
    r = _spp(fish_count=2, hero_tilt_risk=0.0, hero_win_rate_bb100=5.0)
    assert r.hourly_ev_bb > 0, f'Positive WR -> positive hourly EV: {r.hourly_ev_bb}'
    print(f'Hourly EV: {r.hourly_ev_bb:+.2f}BB/hr')


def test_tips_not_empty():
    r = _spp()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips count: {len(r.tips)}')


def test_verdict_contains_recommendation():
    r = _spp()
    assert r.session_recommendation.upper() in r.verdict, \
        f'Verdict should contain recommendation: {r.verdict[:80]}'
    print(f'Verdict: {r.verdict[:80]}')


def test_reasoning_not_empty():
    r = _spp()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'Reasoning: {r.reasoning[:80]}')


def test_multitable_increases_est_hands():
    r1 = _spp(n_tables=1)
    r2 = _spp(n_tables=2)
    assert r2.est_hands > r1.est_hands, \
        f'2 tables should increase hands: {r1.est_hands} vs {r2.est_hands}'
    print(f'Est hands: 1tbl={r1.est_hands} 2tbl={r2.est_hands}')


def test_full_ring_fewer_hands_than_6max():
    r_fr = _spp(game_format='full_ring')
    r_6m = _spp(game_format='6max')
    assert r_fr.est_hands < r_6m.est_hands, \
        f'Full ring fewer hands: {r_fr.est_hands} vs {r_6m.est_hands}'
    print(f'Hands: full_ring={r_fr.est_hands} 6max={r_6m.est_hands}')


def test_one_liner():
    r = _spp()
    line = spp_one_liner(r)
    assert 'SPP' in line and 'adj_wr=' in line and 'stop=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_game_quality_excellent_with_3_fish, test_game_quality_tough_with_no_fish,
        test_adjusted_wr_lower_with_tilt, test_skip_recommendation_on_high_tilt,
        test_play_recommendation_on_good_conditions, test_session_ev_positive_when_adj_wr_positive,
        test_session_ev_negative_when_adj_wr_negative, test_prob_positive_between_0_and_1,
        test_stop_loss_negative, test_stop_loss_between_minus50_and_minus200,
        test_est_hands_proportional_to_hours, test_quality_multiplier_excellent_above_1,
        test_quality_multiplier_tough_below_1, test_hourly_ev_positive_when_adj_wr_positive,
        test_tips_not_empty, test_verdict_contains_recommendation,
        test_reasoning_not_empty, test_multitable_increases_est_hands,
        test_full_ring_fewer_hands_than_6max, test_one_liner,
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
