"""Tests for poker/flop_thin_value.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.flop_thin_value import (
    advise_flop_thin_value, FlopThinValueAdvice, flop_thin_value_one_liner
)


def _adv(**kw):
    defaults = dict(
        hero_hand_class='top_pair', board_type='dry', hero_pos='IP',
        hero_equity=0.60, spr=7.0, villain_vpip=0.30, villain_wtsd=0.28,
        villain_af=1.8, pot_bb=15.0, hero_stack_bb=100.0, n_opponents=1,
    )
    defaults.update(kw)
    return advise_flop_thin_value(**defaults)


def test_returns_flop_thin_value_advice():
    r = _adv()
    assert isinstance(r, FlopThinValueAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'hero_hand_class', 'board_type', 'hero_pos', 'hero_equity',
        'spr', 'villain_vpip', 'villain_wtsd', 'villain_af',
        'pot_bb', 'hero_stack_bb', 'n_opponents',
        'action', 'recommended_bet_pct', 'recommended_bet_bb',
        'ev_bet', 'ev_check', 'ev_advantage', 'fold_freq',
        'is_thin_value_spot', 'multiway_equity_penalty', 'draw_bleed_pct',
        'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_action_valid_values():
    """Action must be bet or check."""
    for h in ['top_pair', 'tptk', 'overpair', 'two_pair']:
        r = _adv(hero_hand_class=h)
        assert r.action in ('bet', 'check'), f'Invalid action: {r.action} for {h}'
    print('All actions valid')


def test_high_equity_dry_board_bets():
    """High equity on dry board: thin value bet is profitable."""
    r = _adv(hero_equity=0.65, board_type='dry', villain_wtsd=0.32)
    assert r.action == 'bet', \
        f'High equity dry board should bet: {r.action}, ev_bet={r.ev_bet:.1f} ev_chk={r.ev_check:.1f}'
    print(f'High eq dry: {r.action}')


def test_wet_board_lower_ev_for_bet():
    """Wet board has higher draw bleed, reducing bet EV."""
    r_dry = _adv(board_type='dry', hero_equity=0.60)
    r_wet = _adv(board_type='wet', hero_equity=0.60)
    # Wet board should have higher bleed
    assert r_wet.draw_bleed_pct > r_dry.draw_bleed_pct, \
        f'Wet should have higher bleed: wet={r_wet.draw_bleed_pct:.0%} dry={r_dry.draw_bleed_pct:.0%}'
    print(f'Bleed: dry={r_dry.draw_bleed_pct:.0%} wet={r_wet.draw_bleed_pct:.0%}')


def test_high_wtsd_villain_gets_larger_bet():
    """High WTSD villain: bet larger for value."""
    r_low = _adv(villain_wtsd=0.22)
    r_high = _adv(villain_wtsd=0.42)
    assert r_high.recommended_bet_pct >= r_low.recommended_bet_pct, \
        f'High WTSD should get larger bet: {r_high.recommended_bet_pct:.0%} vs {r_low.recommended_bet_pct:.0%}'
    print(f'Bet: low_wtsd={r_low.recommended_bet_pct:.0%} high_wtsd={r_high.recommended_bet_pct:.0%}')


def test_fold_frequency_in_range():
    """Fold frequency should be in [0.1, 0.85]."""
    for bt in ['dry', 'medium', 'wet']:
        r = _adv(board_type=bt)
        assert 0.10 <= r.fold_freq <= 0.85, \
            f'Fold freq out of range: {r.fold_freq:.0%} for {bt}'
    print('Fold frequencies in range')


def test_ev_bet_formula_positive_equity():
    """EV of bet should be positive with high equity."""
    r = _adv(hero_equity=0.70, board_type='dry')
    assert r.ev_bet > 0, f'EV_bet should be positive: {r.ev_bet:.1f}'
    print(f'EV_bet (70% eq dry): {r.ev_bet:.1f}')


def test_recommended_bet_bb_equals_pct_times_pot():
    """recommended_bet_bb should approximately equal pct * pot."""
    r = _adv(pot_bb=20.0)
    expected = r.pot_bb * r.recommended_bet_pct
    assert abs(r.recommended_bet_bb - expected) < 0.2, \
        f'Bet BB mismatch: {r.recommended_bet_bb:.1f} vs {expected:.1f}'
    print(f'Bet: {r.recommended_bet_pct:.0%} pot = {r.recommended_bet_bb:.1f}BB (pot={r.pot_bb}BB)')


def test_multiway_equity_penalty():
    """More opponents = more equity penalty."""
    r1 = _adv(n_opponents=1)
    r2 = _adv(n_opponents=3)
    assert r2.multiway_equity_penalty > r1.multiway_equity_penalty, \
        f'More opponents should have higher penalty: 1opp={r1.multiway_equity_penalty:.0%} 3opp={r2.multiway_equity_penalty:.0%}'
    print(f'Penalty: 1opp={r1.multiway_equity_penalty:.0%} 3opp={r2.multiway_equity_penalty:.0%}')


def test_draw_bleed_pct_reasonable():
    """Draw bleed should be in [0, 0.4]."""
    for bt in ['dry', 'medium', 'wet']:
        r = _adv(board_type=bt)
        assert 0.0 <= r.draw_bleed_pct <= 0.40, \
            f'Draw bleed out of range: {r.draw_bleed_pct:.0%} for {bt}'
    print('Draw bleeds all in range')


def test_ev_advantage_equals_bet_minus_check():
    """ev_advantage should equal ev_bet - ev_check."""
    r = _adv()
    expected = round(r.ev_bet - r.ev_check, 2)
    assert abs(r.ev_advantage - expected) < 0.05, \
        f'EV advantage mismatch: {r.ev_advantage:.2f} vs {expected:.2f}'
    print(f'EV_adv={r.ev_advantage:.2f} (bet={r.ev_bet:.2f} chk={r.ev_check:.2f})')


def test_is_thin_value_spot():
    """Medium strength hands should be flagged as thin value spots."""
    r = _adv(hero_hand_class='top_pair', hero_equity=0.60)
    assert r.is_thin_value_spot == True, \
        f'Top pair 60% equity should be thin value: {r.is_thin_value_spot}'
    print(f'Is thin value: {r.is_thin_value_spot}')


def test_bet_pct_in_reasonable_range():
    """Bet size should be between 0.25 and 0.75."""
    for h in ['top_pair', 'tptk', 'overpair']:
        r = _adv(hero_hand_class=h)
        assert 0.20 <= r.recommended_bet_pct <= 0.80, \
            f'Bet pct out of range: {r.recommended_bet_pct:.0%} for {h}'
    print('Bet pcts in range')


def test_oop_smaller_bet_than_ip():
    """OOP position should recommend smaller bets due to raise risk."""
    r_ip = _adv(hero_pos='IP', villain_af=2.0)
    r_oop = _adv(hero_pos='OOP', villain_af=2.0)
    assert r_oop.recommended_bet_pct <= r_ip.recommended_bet_pct, \
        f'OOP should have <= bet size: OOP={r_oop.recommended_bet_pct:.0%} IP={r_ip.recommended_bet_pct:.0%}'
    print(f'Bet: IP={r_ip.recommended_bet_pct:.0%} OOP={r_oop.recommended_bet_pct:.0%}')


def test_tight_villain_folds_more():
    """Tight villain (low VPIP) folds more, increasing thin value EV."""
    r_tight = _adv(villain_vpip=0.15)
    r_loose = _adv(villain_vpip=0.55)
    assert r_tight.fold_freq > r_loose.fold_freq, \
        f'Tight villain should fold more: tight={r_tight.fold_freq:.0%} loose={r_loose.fold_freq:.0%}'
    print(f'Fold: tight={r_tight.fold_freq:.0%} loose={r_loose.fold_freq:.0%}')


def test_tips_not_empty():
    r = _adv()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips: {len(r.tips)}')


def test_one_liner():
    r = _adv()
    line = flop_thin_value_one_liner(r)
    assert 'FTV' in line and 'EV_bet=' in line and 'eq=' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_flop_thin_value_advice, test_required_fields,
        test_action_valid_values, test_high_equity_dry_board_bets,
        test_wet_board_lower_ev_for_bet, test_high_wtsd_villain_gets_larger_bet,
        test_fold_frequency_in_range, test_ev_bet_formula_positive_equity,
        test_recommended_bet_bb_equals_pct_times_pot,
        test_multiway_equity_penalty, test_draw_bleed_pct_reasonable,
        test_ev_advantage_equals_bet_minus_check, test_is_thin_value_spot,
        test_bet_pct_in_reasonable_range, test_oop_smaller_bet_than_ip,
        test_tight_villain_folds_more, test_tips_not_empty, test_one_liner,
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
