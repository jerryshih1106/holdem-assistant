"""Tests for poker/multiway_board_texture.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.multiway_board_texture import (
    analyze_multiway_texture, multiway_texture_one_liner, MultiwayTexture
)


def _adv(**kw):
    defaults = dict(
        n_players=3, board_type='medium', hero_hand_class='top_pair',
        hero_equity=0.55, hero_pos='IP', n_draw_threats=1, hero_was_pfr=True,
    )
    defaults.update(kw)
    return analyze_multiway_texture(**defaults)


def test_returns_multiway_texture():
    r = _adv()
    assert isinstance(r, MultiwayTexture)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'n_players', 'board_type', 'hero_hand_class', 'hero_equity', 'hero_pos',
        'should_cbet', 'cbet_freq', 'cbet_size_pct', 'fold_equity',
        'needs_protection', 'protection_size_pct', 'can_bluff', 'bluff_freq',
        'value_hands_needed', 'check_trap_option', 'adjustments', 'reasoning',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_cbet_freq_drops_with_more_players():
    """More players → lower c-bet frequency."""
    r2 = _adv(n_players=2)
    r3 = _adv(n_players=3)
    r4 = _adv(n_players=4)
    assert r2.cbet_freq > r3.cbet_freq > r4.cbet_freq, (
        f'Freq should drop: {r2.cbet_freq:.0%} > {r3.cbet_freq:.0%} > {r4.cbet_freq:.0%}'
    )
    print(f'C-bet: 2way={r2.cbet_freq:.0%} 3way={r3.cbet_freq:.0%} 4way={r4.cbet_freq:.0%}')


def test_dry_board_higher_freq_than_wet():
    """Dry boards sustain higher c-bet frequency than wet boards."""
    r_dry = _adv(board_type='dry')
    r_wet = _adv(board_type='wet')
    assert r_dry.cbet_freq > r_wet.cbet_freq, (
        f'Dry > wet: {r_dry.cbet_freq:.0%} vs {r_wet.cbet_freq:.0%}'
    )
    print(f'Dry={r_dry.cbet_freq:.0%} wet={r_wet.cbet_freq:.0%}')


def test_fold_equity_lower_with_more_players():
    """More players → lower fold equity."""
    r2 = _adv(n_players=2)
    r4 = _adv(n_players=4)
    assert r2.fold_equity > r4.fold_equity
    print(f'Fold equity: 2way={r2.fold_equity:.0%} 4way={r4.fold_equity:.0%}')


def test_air_cannot_bluff_4way():
    """Pure air against 4 players: cannot bluff."""
    r = _adv(n_players=4, hero_hand_class='air', hero_equity=0.05)
    assert not r.can_bluff
    assert r.bluff_freq == 0.0
    print(f'4-way air: can_bluff={r.can_bluff}')


def test_protection_needed_tptk_wet_multiway():
    """TPTK on wet board with multiple draws: needs protection."""
    r = _adv(n_players=3, board_type='wet', hero_hand_class='tptk',
             n_draw_threats=2)
    assert r.needs_protection
    print(f'TPTK wet multiway: needs_protection={r.needs_protection}')


def test_no_protection_needed_dry_board():
    """Dry board: draws are rare, protection less urgent."""
    r = _adv(n_players=3, board_type='dry', hero_hand_class='top_pair',
             n_draw_threats=0)
    assert not r.needs_protection
    print(f'Dry board no draws: needs_protection={r.needs_protection}')


def test_protection_size_larger():
    """When protection needed, bet size should be larger."""
    r_no_prot = _adv(board_type='dry', n_draw_threats=0)
    r_prot = _adv(board_type='wet', n_draw_threats=2, hero_hand_class='tptk')
    if r_prot.needs_protection:
        assert r_prot.protection_size_pct >= r_no_prot.cbet_size_pct, (
            f'Protection size >= no-prot: {r_prot.protection_size_pct} >= {r_no_prot.cbet_size_pct}'
        )
    print(f'Size: no_prot={r_no_prot.cbet_size_pct:.0%} prot={r_prot.protection_size_pct:.0%}')


def test_set_check_trap_option():
    """Strong hands (set) multiway: check-trapping is viable."""
    r = _adv(n_players=3, hero_hand_class='set', hero_equity=0.82)
    assert r.check_trap_option
    print(f'Set multiway: check_trap={r.check_trap_option}')


def test_non_pfr_lower_cbet_freq():
    """Non-PFR bets less often in multiway pots."""
    r_pfr = _adv(hero_was_pfr=True)
    r_non = _adv(hero_was_pfr=False)
    assert r_pfr.cbet_freq >= r_non.cbet_freq, (
        f'PFR should cbet more: {r_pfr.cbet_freq:.0%} >= {r_non.cbet_freq:.0%}'
    )
    print(f'PFR={r_pfr.cbet_freq:.0%} non-PFR={r_non.cbet_freq:.0%}')


def test_ip_higher_freq_than_oop():
    """IP position maintains slightly higher c-bet frequency."""
    r_ip = _adv(hero_pos='IP')
    r_oop = _adv(hero_pos='OOP')
    assert r_ip.cbet_freq >= r_oop.cbet_freq
    print(f'IP={r_ip.cbet_freq:.0%} OOP={r_oop.cbet_freq:.0%}')


def test_4way_value_hands_minimum_higher():
    """4-way pot requires stronger hands for value betting."""
    r4 = _adv(n_players=4)
    r2 = _adv(n_players=2)
    assert 'two_pair' in r4.value_hands_needed or '+' in r4.value_hands_needed
    print(f'4way value min: {r4.value_hands_needed}')


def test_adjustments_not_empty_multiway():
    r = _adv(n_players=3)
    assert isinstance(r.adjustments, list) and len(r.adjustments) > 0
    print(f'Adjustments: {len(r.adjustments)}')


def test_cbet_freq_between_0_and_1():
    r = _adv()
    assert 0.0 <= r.cbet_freq <= 1.0
    print(f'C-bet freq in [0,1]: {r.cbet_freq:.0%}')


def test_one_liner():
    r = _adv()
    line = multiway_texture_one_liner(r)
    assert 'MW' in line and 'way' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_multiway_texture, test_required_fields,
        test_cbet_freq_drops_with_more_players, test_dry_board_higher_freq_than_wet,
        test_fold_equity_lower_with_more_players, test_air_cannot_bluff_4way,
        test_protection_needed_tptk_wet_multiway, test_no_protection_needed_dry_board,
        test_protection_size_larger, test_set_check_trap_option,
        test_non_pfr_lower_cbet_freq, test_ip_higher_freq_than_oop,
        test_4way_value_hands_minimum_higher, test_adjustments_not_empty_multiway,
        test_cbet_freq_between_0_and_1, test_one_liner,
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
