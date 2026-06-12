"""Tests for poker/bankroll_manager.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from poker.bankroll_manager import advise_bankroll, BankrollAdvice, bankroll_one_liner


def _br(**kw):
    defaults = dict(
        bankroll_bb=2000.0, current_stake_bb=100.0, winrate_bb100=5.0,
        hands_played=15000, std_dev_bb100=80.0, game_type='cash_6max',
        rakeback_pct=0.0, session_buyin_count=1, tilt_score=0.0,
    )
    defaults.update(kw)
    return advise_bankroll(**defaults)


def test_returns_correct_type():
    r = _br()
    assert isinstance(r, BankrollAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _br()
    fields = [
        'bankroll_bb', 'current_stake_bb', 'winrate_bb100', 'hands_played',
        'std_dev_bb100', 'game_type', 'rakeback_pct', 'session_buyin_count',
        'tilt_score', 'buyins_at_stake', 'min_buyins_required', 'standard_buyins_required',
        'conservative_buyins_required', 'risk_of_ruin_pct', 'risk_of_ruin_label',
        'hands_to_confirm_edge', 'is_winrate_confirmed', 'stake_recommendation',
        'next_stake_up_bb', 'next_stake_down_bb', 'bankroll_for_moveup_bb',
        'gross_winrate_bb100', 'rake_cost_bb100', 'net_winrate_bb100',
        'action', 'verdict', 'monthly_ev_estimate_bb', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_buyins_calculation():
    """buyins = bankroll / stake."""
    r = _br(bankroll_bb=3000.0, current_stake_bb=100.0)
    assert abs(r.buyins_at_stake - 30.0) < 0.5, f'Buyins wrong: {r.buyins_at_stake}'
    print(f'Buyins: {r.buyins_at_stake}')


def test_risk_of_ruin_is_probability():
    """ROR must be in [0, 1]."""
    r = _br()
    assert 0.0 <= r.risk_of_ruin_pct <= 1.0, f'ROR out of range: {r.risk_of_ruin_pct}'
    print(f'ROR: {r.risk_of_ruin_pct:.1%}')


def test_large_bankroll_lower_ror():
    """Larger bankroll = lower risk of ruin."""
    r_small = _br(bankroll_bb=500.0)
    r_large = _br(bankroll_bb=5000.0)
    assert r_large.risk_of_ruin_pct <= r_small.risk_of_ruin_pct, \
        f'Larger BR should have lower ROR: {r_large.risk_of_ruin_pct:.1%} vs {r_small.risk_of_ruin_pct:.1%}'
    print(f'ROR: small_br={r_small.risk_of_ruin_pct:.1%} large_br={r_large.risk_of_ruin_pct:.1%}')


def test_higher_winrate_lower_ror():
    """Higher winrate = lower risk of ruin."""
    r_low = _br(winrate_bb100=1.0)
    r_high = _br(winrate_bb100=10.0)
    assert r_high.risk_of_ruin_pct <= r_low.risk_of_ruin_pct, \
        f'Higher WR should have lower ROR: {r_high.risk_of_ruin_pct:.1%} vs {r_low.risk_of_ruin_pct:.1%}'
    print(f'ROR: 1BB/100={r_low.risk_of_ruin_pct:.1%} 10BB/100={r_high.risk_of_ruin_pct:.1%}')


def test_emergency_tilt_stop():
    """Lost 4+ buy-ins → emergency stop action."""
    r = _br(session_buyin_count=5)
    assert r.action in ('emergency_move_down', 'stop_session'), \
        f'4+ BI loss should trigger emergency: {r.action}'
    print(f'Session 5 BI loss: {r.action}')


def test_insufficient_bankroll_move_down():
    """Only 10 BI at current stake → move down."""
    r = _br(bankroll_bb=1000.0, current_stake_bb=100.0)  # 10 BI
    assert r.action in ('move_down',) or r.stake_recommendation in ('move_down', 'caution'), \
        f'10 BI should move down or caution: {r.action} / {r.stake_recommendation}'
    print(f'10 BI: action={r.action} rec={r.stake_recommendation}')


def test_rakeback_improves_net_winrate():
    """Rakeback improves effective winrate."""
    r_no_rb = _br(rakeback_pct=0.0)
    r_rb = _br(rakeback_pct=0.30)
    assert r_rb.net_winrate_bb100 > r_no_rb.net_winrate_bb100, \
        f'Rakeback should improve net WR: {r_rb.net_winrate_bb100} vs {r_no_rb.net_winrate_bb100}'
    print(f'Net WR: no_rb={r_no_rb.net_winrate_bb100:+.1f} 30%_rb={r_rb.net_winrate_bb100:+.1f}')


def test_more_hands_confirms_edge():
    """More hands → edge more likely confirmed."""
    r_few = _br(hands_played=1000)
    r_many = _br(hands_played=100000)
    assert r_many.is_winrate_confirmed or not r_few.is_winrate_confirmed
    print(f'Confirmed: 1k hands={r_few.is_winrate_confirmed} 100k hands={r_many.is_winrate_confirmed}')


def test_action_is_valid():
    valid = {'move_up', 'take_shot', 'stay', 'move_down', 'emergency_move_down', 'stop_session'}
    r = _br()
    assert r.action in valid, f'Invalid action: {r.action}'
    print(f'Action: {r.action}')


def test_next_stake_up_higher():
    """next_stake_up must be greater than current."""
    r = _br(current_stake_bb=100.0)
    assert r.next_stake_up_bb > 100.0, f'Next stake up should be > 100: {r.next_stake_up_bb}'
    print(f'Next up: {r.next_stake_up_bb}BB')


def test_next_stake_down_lower():
    """next_stake_down must be less than current."""
    r = _br(current_stake_bb=100.0)
    assert r.next_stake_down_bb < 100.0, f'Next stake down should be < 100: {r.next_stake_down_bb}'
    print(f'Next down: {r.next_stake_down_bb}BB')


def test_ror_label_valid():
    valid = {'acceptable', 'moderate', 'high', 'extreme'}
    r = _br()
    assert r.risk_of_ruin_label in valid, f'Invalid ROR label: {r.risk_of_ruin_label}'
    print(f'ROR label: {r.risk_of_ruin_label}')


def test_mtt_requires_more_buyins():
    """MTT requires more buy-ins than cash game."""
    r_cash = _br(game_type='cash_6max')
    r_mtt = _br(game_type='mtt')
    assert r_mtt.conservative_buyins_required >= r_cash.conservative_buyins_required, \
        f'MTT BI >= cash: {r_mtt.conservative_buyins_required} vs {r_cash.conservative_buyins_required}'
    print(f'Conservative BI: cash={r_cash.conservative_buyins_required} mtt={r_mtt.conservative_buyins_required}')


def test_all_game_types_work():
    for gt in ['cash_6max', 'cash_full_ring', 'cash_hu', 'mtt', 'sng', 'plo_6max']:
        r = _br(game_type=gt)
        assert r.action in {'move_up', 'take_shot', 'stay', 'move_down', 'emergency_move_down', 'stop_session'}
    print('All game types produce valid actions')


def test_tips_not_empty():
    r = _br()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips: {len(r.tips)}')


def test_verdict_not_empty():
    r = _br()
    assert isinstance(r.verdict, str) and len(r.verdict) > 10
    print(f'Verdict: {r.verdict[:60]}...')


def test_monthly_ev_positive_for_winning_player():
    """Positive winrate → positive monthly EV estimate."""
    r = _br(winrate_bb100=5.0)
    assert r.monthly_ev_estimate_bb > 0, f'Winning player should have positive monthly EV: {r.monthly_ev_estimate_bb}'
    print(f'Monthly EV: {r.monthly_ev_estimate_bb:.0f}BB')


def test_one_liner():
    r = _br()
    line = bankroll_one_liner(r)
    assert 'BR' in line and 'bi=' in line and 'ror=' in line and 'wr=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_buyins_calculation, test_risk_of_ruin_is_probability,
        test_large_bankroll_lower_ror, test_higher_winrate_lower_ror,
        test_emergency_tilt_stop, test_insufficient_bankroll_move_down,
        test_rakeback_improves_net_winrate, test_more_hands_confirms_edge,
        test_action_is_valid, test_next_stake_up_higher,
        test_next_stake_down_lower, test_ror_label_valid,
        test_mtt_requires_more_buyins, test_all_game_types_work,
        test_tips_not_empty, test_verdict_not_empty,
        test_monthly_ev_positive_for_winning_player, test_one_liner,
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
