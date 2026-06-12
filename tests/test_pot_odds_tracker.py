"""Tests for poker/pot_odds_tracker.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.pot_odds_tracker import (
    build_pot_odds_table, lookup_odds, pot_odds_one_liner,
    PotOddsTable, PotOddsEntry
)


def test_returns_pot_odds_table():
    r = build_pot_odds_table(pot_bb=40.0, hero_equity=0.50)
    assert isinstance(r, PotOddsTable)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = build_pot_odds_table(pot_bb=40.0)
    fields = ['pot_bb', 'hero_equity', 'entries', 'profitable_calls',
              'marginal_calls', 'clear_folds', 'summary_text']
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_entries_populated():
    r = build_pot_odds_table(pot_bb=40.0)
    assert len(r.entries) >= 8, f'Expected >= 8 entries: {len(r.entries)}'
    print(f'Entries: {len(r.entries)}')


def test_psb_required_equity_is_33pct():
    """Pot-sized bet (1.0x): hero must have 33% equity to call."""
    r = build_pot_odds_table(pot_bb=30.0)
    psb = next(e for e in r.entries if abs(e.bet_pct - 1.00) < 0.01)
    assert abs(psb.required_equity - 1/3) < 0.01, (
        f'PSB req equity: expected ~33%, got {psb.required_equity:.1%}'
    )
    print(f'PSB required equity: {psb.required_equity:.1%}')


def test_half_pot_required_equity_is_25pct():
    """Half-pot bet: hero needs 25% equity."""
    r = build_pot_odds_table(pot_bb=20.0)
    half = next(e for e in r.entries if abs(e.bet_pct - 0.50) < 0.01)
    assert abs(half.required_equity - 0.25) < 0.01, (
        f'Half-pot req equity: {half.required_equity:.1%}'
    )
    print(f'Half-pot required equity: {half.required_equity:.1%}')


def test_larger_bet_requires_more_equity():
    """Bigger bets require more equity to call profitably."""
    r = build_pot_odds_table(pot_bb=30.0)
    eq_33 = next(e for e in r.entries if abs(e.bet_pct - 0.33) < 0.02)
    eq_100 = next(e for e in r.entries if abs(e.bet_pct - 1.00) < 0.02)
    eq_200 = next(e for e in r.entries if abs(e.bet_pct - 2.00) < 0.05)
    assert eq_33.required_equity < eq_100.required_equity < eq_200.required_equity, (
        f'Required eq should grow: {eq_33.required_equity:.0%} < '
        f'{eq_100.required_equity:.0%} < {eq_200.required_equity:.0%}'
    )
    print(f'Required eq: 33%pot={eq_33.required_equity:.0%} PSB={eq_100.required_equity:.0%} 2x={eq_200.required_equity:.0%}')


def test_mdf_plus_alpha_equals_one():
    """MDF + alpha (required_equity scaled) should equal 1."""
    r = build_pot_odds_table(pot_bb=20.0)
    for e in r.entries:
        alpha = e.bet_bb / (e.total_pot_after_bb)
        assert abs(e.mdf + alpha - 1.0) < 0.01, (
            f'MDF + alpha != 1: {e.mdf:.3f} + {alpha:.3f} = {e.mdf+alpha:.3f}'
        )
    print('MDF + alpha = 1 for all entries')


def test_is_profitable_matches_equity():
    """is_profitable should be True when hero_equity >= required_equity."""
    r = build_pot_odds_table(pot_bb=30.0, hero_equity=0.50)
    for e in r.entries:
        expected = 0.50 >= e.required_equity
        assert e.is_profitable == expected, (
            f'{e.label}: is_profitable={e.is_profitable} but '
            f'hero=50% vs req={e.required_equity:.0%}'
        )
    print('is_profitable matches equity for all entries')


def test_profitable_calls_not_empty_high_equity():
    """With 65% equity, many bets should be profitable to call."""
    r = build_pot_odds_table(pot_bb=20.0, hero_equity=0.65)
    assert len(r.profitable_calls) > 0
    print(f'Profitable calls at 65%: {r.profitable_calls}')


def test_clear_folds_not_empty_low_equity():
    """With 15% equity, most bets should be clear folds."""
    r = build_pot_odds_table(pot_bb=20.0, hero_equity=0.15)
    assert len(r.clear_folds) > 0
    print(f'Clear folds at 15%: {len(r.clear_folds)} bets')


def test_lookup_odds_returns_entry():
    e = lookup_odds(pot_bb=30.0, villain_bet_bb=15.0, hero_equity=0.40)
    assert isinstance(e, PotOddsEntry)
    print(f'lookup_odds: {e.label} req={e.required_equity:.0%}')


def test_lookup_psb_correct():
    e = lookup_odds(pot_bb=20.0, villain_bet_bb=20.0, hero_equity=0.35)
    assert abs(e.required_equity - 1/3) < 0.01
    assert e.is_profitable  # 35% >= 33%
    print(f'Lookup PSB: req={e.required_equity:.0%} is_profitable={e.is_profitable}')


def test_summary_text_not_empty():
    r = build_pot_odds_table(pot_bb=40.0, hero_equity=0.50)
    assert isinstance(r.summary_text, str) and len(r.summary_text) > 50
    assert 'Pot' in r.summary_text
    print(f'Summary text length: {len(r.summary_text)}')


def test_custom_bet_pcts():
    r = build_pot_odds_table(pot_bb=20.0, custom_bet_pcts=[0.50, 1.00, 2.00])
    assert len(r.entries) == 3
    print(f'Custom entries: {[e.label for e in r.entries]}')


def test_pot_odds_one_liner():
    line = pot_odds_one_liner(pot_bb=30.0, villain_bet_bb=20.0, hero_equity=0.50)
    assert 'PO' in line and 'BB' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_pot_odds_table, test_required_fields, test_entries_populated,
        test_psb_required_equity_is_33pct, test_half_pot_required_equity_is_25pct,
        test_larger_bet_requires_more_equity, test_mdf_plus_alpha_equals_one,
        test_is_profitable_matches_equity, test_profitable_calls_not_empty_high_equity,
        test_clear_folds_not_empty_low_equity,
        test_lookup_odds_returns_entry, test_lookup_psb_correct,
        test_summary_text_not_empty, test_custom_bet_pcts, test_pot_odds_one_liner,
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
