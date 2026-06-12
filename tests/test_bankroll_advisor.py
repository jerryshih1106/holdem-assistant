"""Tests for poker/bankroll_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.bankroll_advisor import (
    analyze_bankroll, bankroll_one_liner, ror_table, BankrollAnalysis
)


def _brm(usd=500.0, stake=25, wr=5.0, sd=90.0):
    return analyze_bankroll(bankroll_usd=usd, stake_nl=stake,
                            win_rate_bb100=wr, std_dev_bb100=sd)


def test_returns_bankroll_analysis():
    r = _brm()
    assert isinstance(r, BankrollAnalysis)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _brm()
    fields = [
        'bankroll_usd', 'stake_nl', 'win_rate_bb100', 'std_dev_bb100',
        'bankroll_bb', 'current_buyins', 'risk_of_ruin',
        'min_buyins_standard', 'min_buyins_conservative',
        'move_up_usd', 'move_down_usd', 'stake_at_5pct_ror',
        'recommended_stake', 'grade', 'action',
        'expected_bb_per_100', 'hours_to_double', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing field: {f}'
    print(f'All {len(fields)} fields present')


def test_bankroll_bb_correct():
    """bankroll_bb = bankroll_usd / bb_value_usd."""
    r = _brm(usd=500.0, stake=25)
    # NL25: BB = $0.25, bankroll_bb = 500 / 0.25 = 2000
    assert abs(r.bankroll_bb - 2000.0) < 1, f'bankroll_bb should be 2000: {r.bankroll_bb}'
    print(f'bankroll_bb: {r.bankroll_bb}')


def test_current_buyins_correct():
    """current_buyins = bankroll / (100 * bb_value)."""
    r = _brm(usd=500.0, stake=25)
    # NL25: buyin = 100 * 0.25 = $25, buyins = 500/25 = 20
    assert abs(r.current_buyins - 20.0) < 0.1, \
        f'current_buyins should be 20: {r.current_buyins}'
    print(f'current_buyins: {r.current_buyins}')


def test_ror_positive():
    """Risk of ruin should be in [0, 1]."""
    r = _brm()
    assert 0 <= r.risk_of_ruin <= 1, f'RoR should be 0-1: {r.risk_of_ruin}'
    print(f'risk_of_ruin: {r.risk_of_ruin:.4f}')


def test_larger_bankroll_lower_ror():
    """Larger bankroll means lower risk of ruin."""
    r_small = _brm(usd=250.0, stake=25)
    r_large = _brm(usd=2000.0, stake=25)
    assert r_large.risk_of_ruin < r_small.risk_of_ruin, \
        f'Larger bankroll lower RoR: {r_large.risk_of_ruin} < {r_small.risk_of_ruin}'
    print(f'RoR: small=${250}={r_small.risk_of_ruin:.4f} large=${2000}={r_large.risk_of_ruin:.4f}')


def test_losing_player_ror_is_one():
    """Losing player (wr<=0) should have RoR = 1.0."""
    r = _brm(wr=-2.0)
    assert r.risk_of_ruin == 1.0, f'Losing player RoR should be 1.0: {r.risk_of_ruin}'
    print(f'Losing player RoR: {r.risk_of_ruin}')


def test_too_few_buyins_moves_down():
    """Less than 15 BI should trigger move_down_immediately."""
    r = _brm(usd=200.0, stake=25)  # $200 / $25 = 8 BI → danger
    assert r.action in ('move_down', 'move_down_immediately'), \
        f'8 BI should move down: {r.action}'
    print(f'8 BI action: {r.action} grade={r.grade}')


def test_adequate_buyins_stays():
    """25+ BI at current stake should stay or be ready to move up."""
    r = _brm(usd=1000.0, stake=25)  # 1000/25 = 40 BI
    assert r.action in ('stay', 'move_up'), \
        f'40 BI should stay or move up: {r.action}'
    print(f'40 BI action: {r.action} grade={r.grade}')


def test_recommended_stake_within_roll():
    """Recommended stake should have >= 25 BI."""
    r = _brm(usd=500.0, stake=100)  # 500/100 = 5 BI — too high
    assert r.recommended_stake < 100, \
        f'Recommended stake should be lower than NL100 for $500: {r.recommended_stake}'
    print(f'Recommended stake for $500: NL{r.recommended_stake}')


def test_move_up_usd_higher_than_current():
    """Move-up threshold should require more than current bankroll."""
    r = _brm(usd=500.0, stake=25)
    # $500 at NL25 is only 20 BI; move-up requires 30 BI at NL50 = $1500
    assert r.move_up_usd > 500.0, \
        f'Move-up threshold should be > $500: {r.move_up_usd}'
    print(f'Move-up at: ${r.move_up_usd:.0f}')


def test_move_down_usd_lower_than_bankroll():
    """Move-down threshold should be below current bankroll for adequate roll."""
    r = _brm(usd=1000.0, stake=25)  # 40 BI — adequate
    assert r.move_down_usd < 1000.0, \
        f'Move-down threshold should be < $1000: {r.move_down_usd}'
    print(f'Move-down at: ${r.move_down_usd:.0f}')


def test_grade_is_valid():
    valid = {'optimal', 'conservative', 'too_high', 'danger'}
    r = _brm()
    assert r.grade in valid, f'Grade should be valid: {r.grade}'
    print(f'grade: {r.grade}')


def test_action_is_valid():
    valid = {'stay', 'move_up', 'move_down', 'move_down_immediately'}
    r = _brm()
    assert r.action in valid, f'Action should be valid: {r.action}'
    print(f'action: {r.action}')


def test_hours_to_double_positive_for_winner():
    """Winning player should have a finite hours_to_double."""
    r = _brm(wr=5.0)
    assert r.hours_to_double is not None and r.hours_to_double > 0, \
        f'Winner should have finite hours_to_double: {r.hours_to_double}'
    print(f'hours_to_double: {r.hours_to_double:.0f}h')


def test_hours_to_double_none_for_loser():
    """Losing player should have None hours_to_double."""
    r = _brm(wr=-3.0)
    assert r.hours_to_double is None, \
        f'Loser should have None hours_to_double: {r.hours_to_double}'
    print(f'Loser hours_to_double: {r.hours_to_double}')


def test_reasoning_is_string():
    r = _brm()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'reasoning: {r.reasoning[:60]}')


def test_tips_is_list():
    r = _brm()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'tips count: {len(r.tips)}')


def test_bankroll_one_liner():
    r = _brm()
    line = bankroll_one_liner(r)
    assert isinstance(line, str) and len(line) > 5
    print(f'one_liner: {line}')


def test_ror_table_returns_list():
    """ror_table should return a list of dicts."""
    table = ror_table(5.0, 90.0)
    assert isinstance(table, list) and len(table) > 0
    assert all('stake' in row and 'ror' in row for row in table)
    print(f'ror_table: {len(table)} rows')


def test_high_ror_at_low_buyins():
    """15 BI should have higher RoR than 30 BI at same stake."""
    table = ror_table(5.0, 90.0)
    nl10_rows = [r for r in table if r['stake'] == 10]
    row_15 = next(r for r in nl10_rows if r['buyins'] == 15)
    row_30 = next(r for r in nl10_rows if r['buyins'] == 30)
    assert row_15['ror'] > row_30['ror'], \
        f'15 BI RoR > 30 BI RoR: {row_15["ror"]} vs {row_30["ror"]}'
    print(f'NL10 RoR: 15BI={row_15["ror"]:.4f} 30BI={row_30["ror"]:.4f}')


if __name__ == '__main__':
    tests = [
        test_returns_bankroll_analysis, test_required_fields,
        test_bankroll_bb_correct, test_current_buyins_correct,
        test_ror_positive, test_larger_bankroll_lower_ror,
        test_losing_player_ror_is_one, test_too_few_buyins_moves_down,
        test_adequate_buyins_stays, test_recommended_stake_within_roll,
        test_move_up_usd_higher_than_current, test_move_down_usd_lower_than_bankroll,
        test_grade_is_valid, test_action_is_valid,
        test_hours_to_double_positive_for_winner, test_hours_to_double_none_for_loser,
        test_reasoning_is_string, test_tips_is_list,
        test_bankroll_one_liner, test_ror_table_returns_list, test_high_ror_at_low_buyins,
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
