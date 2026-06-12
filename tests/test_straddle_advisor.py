"""Tests for poker/straddle_advisor.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.straddle_advisor import advise_straddle, straddle_one_liner, StraddleAdvice


def _adv(**kw):
    defaults = dict(
        hero_pos='CO', straddle_pos='UTG', straddle_bb=2.0,
        hero_stack_bb=100.0, n_players=6, villain_vpip=0.28,
        n_callers=0, hero_is_straddler=False,
    )
    defaults.update(kw)
    return advise_straddle(**defaults)


def test_returns_straddle_advice():
    r = _adv()
    assert isinstance(r, StraddleAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'hero_pos', 'straddle_pos', 'straddle_bb', 'hero_stack_bb', 'n_players',
        'recommended_open_bb', 'threeBet_ip_bb', 'threeBet_oop_bb',
        'effective_big_blind', 'spr_on_flop_if_opens', 'spr_vs_standard',
        'straddler_last_preflop', 'positional_notes',
        'tighten_calling_range', 'calling_range_adj_pct', 'strategic_notes',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_open_size_larger_than_standard():
    """Open-raise should be larger than standard 2.5BB when straddle=2BB."""
    r = _adv(straddle_bb=2.0)
    assert r.recommended_open_bb > 2.5, (
        f'Open vs straddle should exceed 2.5BB: {r.recommended_open_bb}'
    )
    print(f'Open vs 2BB straddle: {r.recommended_open_bb:.1f}BB')


def test_effective_bb_equals_straddle():
    r = _adv(straddle_bb=2.0)
    assert r.effective_big_blind == 2.0
    print(f'Effective BB: {r.effective_big_blind}')


def test_utg_straddle_acts_last():
    r = _adv(straddle_pos='UTG')
    assert r.straddler_last_preflop
    print(f'UTG straddle acts last: {r.straddler_last_preflop}')


def test_spr_lower_with_straddle():
    """With straddle, opening bigger → lower SPR on flop."""
    r = _adv(straddle_bb=2.0)
    assert r.spr_on_flop_if_opens < r.spr_vs_standard, (
        f'Straddle SPR should be lower: {r.spr_on_flop_if_opens} < {r.spr_vs_standard}'
    )
    print(f'SPR: straddle={r.spr_on_flop_if_opens:.2f} vs standard={r.spr_vs_standard:.2f}')


def test_threeBet_oop_larger_than_ip():
    """OOP 3-bet should be larger than IP 3-bet."""
    r = _adv()
    assert r.threeBet_oop_bb >= r.threeBet_ip_bb, (
        f'OOP 3-bet >= IP: {r.threeBet_oop_bb} >= {r.threeBet_ip_bb}'
    )
    print(f'3-bet: IP={r.threeBet_ip_bb:.1f}BB OOP={r.threeBet_oop_bb:.1f}BB')


def test_loose_game_bigger_open():
    """Vs loose players, open bigger to build the pot."""
    r_tight = _adv(villain_vpip=0.20)
    r_loose  = _adv(villain_vpip=0.50)
    assert r_loose.recommended_open_bb >= r_tight.recommended_open_bb, (
        f'Loose game: bigger open {r_loose.recommended_open_bb} >= {r_tight.recommended_open_bb}'
    )
    print(f'Open: tight={r_tight.recommended_open_bb:.1f}BB loose={r_loose.recommended_open_bb:.1f}BB')


def test_calling_range_tightens():
    """Calling range should tighten vs a straddle."""
    r = _adv(straddle_bb=2.0)
    assert r.tighten_calling_range
    assert r.calling_range_adj_pct <= 0, f'Should tighten (negative adj): {r.calling_range_adj_pct}'
    print(f'Call range adj: {r.calling_range_adj_pct:.1%}')


def test_straddler_defense_when_hero_is_straddler():
    r = _adv(hero_is_straddler=True)
    assert r.straddler_defense is not None
    assert 'mdf' in r.straddler_defense
    assert 0.0 < r.straddler_defense['mdf'] < 1.0
    print(f'Straddler defense MDF: {r.straddler_defense["mdf"]:.0%}')


def test_no_straddler_defense_when_not_straddler():
    r = _adv(hero_is_straddler=False)
    assert r.straddler_defense is None
    print('No defense info when not straddler: OK')


def test_squeeze_analysis_with_callers():
    r = _adv(n_callers=2)
    assert r.squeeze_analysis is not None
    assert 'dead_money_bb' in r.squeeze_analysis
    assert r.squeeze_analysis['dead_money_bb'] > 0
    print(f'Squeeze: dead_money={r.squeeze_analysis["dead_money_bb"]:.1f}BB')


def test_no_squeeze_without_callers():
    r = _adv(n_callers=0)
    assert r.squeeze_analysis is None
    print('No squeeze analysis without callers: OK')


def test_strategic_notes_not_empty():
    r = _adv()
    assert isinstance(r.strategic_notes, list) and len(r.strategic_notes) > 0
    print(f'Strategic notes: {len(r.strategic_notes)}')


def test_positional_notes_is_string():
    r = _adv()
    assert isinstance(r.positional_notes, str) and len(r.positional_notes) > 5
    print(f'Notes: {r.positional_notes[:60]}')


def test_larger_straddle_bigger_open():
    r1 = _adv(straddle_bb=2.0)
    r2 = _adv(straddle_bb=4.0)
    assert r2.recommended_open_bb > r1.recommended_open_bb
    print(f'Open: 2x straddle={r1.recommended_open_bb:.1f}BB 4x straddle={r2.recommended_open_bb:.1f}BB')


def test_one_liner():
    r = _adv()
    line = straddle_one_liner(r)
    assert isinstance(line, str) and 'STRDL' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_straddle_advice, test_required_fields,
        test_open_size_larger_than_standard, test_effective_bb_equals_straddle,
        test_utg_straddle_acts_last, test_spr_lower_with_straddle,
        test_threeBet_oop_larger_than_ip, test_loose_game_bigger_open,
        test_calling_range_tightens,
        test_straddler_defense_when_hero_is_straddler,
        test_no_straddler_defense_when_not_straddler,
        test_squeeze_analysis_with_callers,
        test_no_squeeze_without_callers,
        test_strategic_notes_not_empty, test_positional_notes_is_string,
        test_larger_straddle_bigger_open, test_one_liner,
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
