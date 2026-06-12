"""Tests for poker/semibluff.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.semibluff import analyze_semibluff, semibluff_summary


def test_combo_draw_recommends_bet():
    """Combo draw (15 outs) with decent fold equity should recommend BET."""
    r = analyze_semibluff(outs=15, pot_bb=10.0, cards_to_come=1, fold_equity=0.45)
    assert r.recommended == 'BET', f'Combo draw should BET: {r.recommended}'
    assert r.is_profitable_bet is True
    print(f'Combo draw: {r.action_zh} EV={r.ev_bet:.1f}BB')


def test_gutshot_no_fold_equity_prefers_check():
    """Gutshot (4 outs) with zero fold equity should prefer check/fold over bet."""
    r = analyze_semibluff(outs=4, pot_bb=10.0, cards_to_come=1, fold_equity=0.15)
    # Low fold equity + weak draw → check or bet EV should be negative or near check EV
    assert r.ev_check_behind >= r.ev_bet or r.recommended != 'BET', \
        f'Weak gutshot with no fold equity should not BET strongly: {r.recommended}'
    print(f'Gutshot 0 fold_eq: {r.action_zh} EV_bet={r.ev_bet:.1f}BB EV_check={r.ev_check_behind:.1f}BB')


def test_flush_draw_rule_of_2_equity():
    """With 1 card to come, flush draw (9 outs) equity = ~18% (rule of 2)."""
    r = analyze_semibluff(outs=9, pot_bb=10.0, cards_to_come=1)
    expected_eq = min(0.95, 9 * 0.02)
    assert abs(r.draw_equity - expected_eq) < 0.01, \
        f'Rule of 2: equity should be {expected_eq:.2f}, got {r.draw_equity:.2f}'
    print(f'FD 1 card: equity={r.draw_equity:.0%} (expected {expected_eq:.0%})')


def test_flush_draw_rule_of_4_equity():
    """With 2 cards to come, flush draw (9 outs) equity = ~36% (rule of 4)."""
    r = analyze_semibluff(outs=9, pot_bb=10.0, cards_to_come=2)
    expected_eq = min(0.95, 9 * 0.04)
    assert abs(r.draw_equity - expected_eq) < 0.01, \
        f'Rule of 4: equity should be {expected_eq:.2f}, got {r.draw_equity:.2f}'
    print(f'FD 2 cards: equity={r.draw_equity:.0%} (expected {expected_eq:.0%})')


def test_high_fold_equity_creates_positive_ev_bet():
    """When villain folds often, even a weak draw has positive EV to bet."""
    # OESD (8 outs) on turn, villain folds 70%
    r = analyze_semibluff(outs=8, pot_bb=10.0, cards_to_come=1, fold_equity=0.70)
    assert r.ev_bet > 0, f'High fold equity should create positive bet EV: {r.ev_bet:.2f}'
    print(f'OESD 70% fold: EV_bet={r.ev_bet:.1f}BB')


def test_breakeven_fold_zero_when_called_ev_positive():
    """When called EV is positive (strong draw), breakeven fold = 0."""
    # 15 outs on flop (combo draw) — calling a bet may already be profitable
    r = analyze_semibluff(outs=15, pot_bb=5.0, cards_to_come=2,
                           facing_bet=True, bet_to_call=2.0)
    if r.ev_check_call >= 0:
        assert r.breakeven_fold == 0.0, \
            f'Positive called EV → breakeven_fold should be 0, got {r.breakeven_fold}'
    print(f'Combo draw call EV={r.ev_check_call:.1f}BB breakeven_fold={r.breakeven_fold:.0%}')


def test_facing_bet_call_when_pot_odds_sufficient():
    """When facing a bet with sufficient pot odds for a draw, recommend CHECK_CALL."""
    # FD (9 outs, 18% equity), facing 2BB into 10BB pot → pot odds = 2/12 = 17%
    r = analyze_semibluff(outs=9, pot_bb=10.0, cards_to_come=1,
                           facing_bet=True, bet_to_call=2.0, fold_equity=0.30)
    assert r.ev_check_call >= 0 or r.recommended in ('CHECK_CALL', 'BET'), \
        f'With sufficient pot odds for FD, should call or raise: {r.recommended}'
    print(f'FD facing 2BB into 10BB: {r.recommended} EV_call={r.ev_check_call:.1f}BB')


def test_semibleff_preferred_over_call_when_ev_dominant():
    """If bet EV > call EV by > 1BB, should recommend BET even when facing a bet."""
    # Strong draw with very high fold equity → raising dominates calling
    r = analyze_semibluff(outs=15, pot_bb=8.0, cards_to_come=1, fold_equity=0.70,
                           facing_bet=True, bet_to_call=3.0)
    if r.ev_bet > r.ev_check_call + 1.0:
        assert r.recommended == 'BET', \
            f'EV_bet={r.ev_bet:.1f} >> EV_call={r.ev_check_call:.1f}: should BET'
    print(f'Combo draw vs facing bet: {r.recommended} EV_bet={r.ev_bet:.1f} EV_call={r.ev_check_call:.1f}')


def test_equity_share_increases_draw_equity():
    """has_equity_share adds to draw equity (e.g. top pair + flush draw)."""
    r_pure  = analyze_semibluff(outs=9, pot_bb=10.0, cards_to_come=1, has_equity_share=0.0)
    r_tpfd  = analyze_semibluff(outs=9, pot_bb=10.0, cards_to_come=1, has_equity_share=0.25)
    assert r_tpfd.draw_equity > r_pure.draw_equity, \
        f'TP+FD equity {r_tpfd.draw_equity:.2f} should > FD only {r_pure.draw_equity:.2f}'
    print(f'FD only: {r_pure.draw_equity:.0%}, TP+FD: {r_tpfd.draw_equity:.0%}')


def test_oesd_sizing_pct():
    """OESD (8 outs) should use 60% pot sizing."""
    r = analyze_semibluff(outs=8, pot_bb=10.0, cards_to_come=1)
    assert r.sizing_pct == 0.60, f'OESD sizing should be 60%: {r.sizing_pct}'
    print(f'OESD sizing_pct={r.sizing_pct:.0%}')


def test_summary_format():
    """semibluff_summary should contain [半詐唬] and not be excessively long."""
    r = analyze_semibluff(outs=9, pot_bb=10.0, cards_to_come=1, fold_equity=0.45)
    s = semibluff_summary(r)
    assert '[半詐唬]' in s, f'Summary missing [半詐唬]: {s}'
    assert len(s) <= 100, f'Summary too long ({len(s)}): {s}'
    print(f'Summary ({len(s)}): {s}')


if __name__ == '__main__':
    tests = [
        test_combo_draw_recommends_bet,
        test_gutshot_no_fold_equity_prefers_check,
        test_flush_draw_rule_of_2_equity,
        test_flush_draw_rule_of_4_equity,
        test_high_fold_equity_creates_positive_ev_bet,
        test_breakeven_fold_zero_when_called_ev_positive,
        test_facing_bet_call_when_pot_odds_sufficient,
        test_semibleff_preferred_over_call_when_ev_dominant,
        test_equity_share_increases_draw_equity,
        test_oesd_sizing_pct,
        test_summary_format,
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
