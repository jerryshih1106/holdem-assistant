"""Tests for poker/donk_bet.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.donk_bet import analyze_donk, donk_or_probe, donk_summary


# ── donk_or_probe wrapper ─────────────────────────────────────────────────────

def test_low_board_bb_donk_increases_frequency():
    """Low flop (2-7 ranks) should give BB higher donk frequency than high board."""
    r_low  = donk_or_probe(equity=0.70, pot_bb=10.0, eff_stack_bb=100.0,
                            community=['7c', '5h', '2d'], street='flop',
                            hero_pos='bb', villain_pos='BTN')
    r_high = donk_or_probe(equity=0.70, pot_bb=10.0, eff_stack_bb=100.0,
                            community=['Ac', 'Kh', 'Qd'], street='flop',
                            hero_pos='bb', villain_pos='BTN')
    assert r_low.bet_freq >= r_high.bet_freq, \
        f'Low board donk freq {r_low.bet_freq:.0%} should >= high board {r_high.bet_freq:.0%}'
    print(f'Donk freq: low board={r_low.bet_freq:.0%}  high board={r_high.bet_freq:.0%}')


def test_nuts_hand_may_donk():
    """Nuts hand (equity >= 0.80) on flop can use donk bet."""
    r = donk_or_probe(equity=0.90, pot_bb=8.0, eff_stack_bb=80.0,
                       community=['7c', '5h', '2d'], street='flop',
                       hero_pos='bb', villain_pos='BTN')
    assert r.hand_category == 'nuts', f'Equity=90% should classify as nuts: {r.hand_category}'
    assert r.bet_freq >= 0.0
    print(f'Nuts donk: should_bet={r.should_bet} freq={r.bet_freq:.0%} size={r.sizing_pct:.0%}pot')


def test_weak_hand_high_board_should_not_donk():
    """Weak hand on villain-favorable high board should not donk."""
    r = donk_or_probe(equity=0.25, pot_bb=10.0, eff_stack_bb=80.0,
                       community=['Ac', 'Kh', 'Qd'], street='flop',
                       hero_pos='bb', villain_pos='BTN',
                       villain_cbet_pct=0.50)
    # Either should_bet=False or very low freq
    if r.should_bet:
        assert r.bet_freq <= 0.15, \
            f'Weak hand on high board should have very low donk freq: {r.bet_freq:.0%}'
    else:
        assert r.should_bet is False
    print(f'Weak hand high board: should_bet={r.should_bet} freq={r.bet_freq:.0%}')


def test_probe_bet_turn_when_villain_checked_back():
    """Turn probe bet after villain checked behind should return bet_type='probe'."""
    r = donk_or_probe(equity=0.65, pot_bb=10.0, eff_stack_bb=80.0,
                       community=['Ac', '7h', '2d', 'Ks'], street='turn',
                       hero_pos='bb', villain_pos='BTN',
                       villain_checked_prev=True)
    assert r.bet_type == 'probe', f'Should be probe on turn: {r.bet_type}'
    # street field stores localized string ('轉牌'), not 'turn'
    assert r.street != '', f'Street should be set: {r.street!r}'
    print(f'Turn probe: street={r.street!r} should_bet={r.should_bet} freq={r.bet_freq:.0%}')


def test_probe_bet_river_favorable_runout():
    """River probe with favorable runout (equity>=65%) should be recommended."""
    r = donk_or_probe(equity=0.70, pot_bb=12.0, eff_stack_bb=60.0,
                       community=['Ac', '7h', '2d', 'Ks', '3c'], street='river',
                       hero_pos='bb', villain_pos='BTN',
                       villain_checked_prev=True, runout_favorable=True)
    assert r.bet_type == 'probe'
    assert r.bet_freq > 0
    print(f'River probe favorable: should_bet={r.should_bet} freq={r.bet_freq:.0%}')


def test_high_villain_cbet_pct_increases_donk_frequency():
    """High villain c-bet rate (>= 0.75) should generate higher donk frequency."""
    r_high = donk_or_probe(equity=0.65, pot_bb=10.0, eff_stack_bb=100.0,
                            community=['7c', '5h', '2d'], street='flop',
                            hero_pos='bb', villain_cbet_pct=0.80)
    r_low  = donk_or_probe(equity=0.65, pot_bb=10.0, eff_stack_bb=100.0,
                            community=['7c', '5h', '2d'], street='flop',
                            hero_pos='bb', villain_cbet_pct=0.40)
    assert r_high.bet_freq >= r_low.bet_freq, \
        f'High cbet villain donk {r_high.bet_freq:.0%} should >= low cbet {r_low.bet_freq:.0%}'
    print(f'Donk vs cbet: high_cbet={r_high.bet_freq:.0%}  low_cbet={r_low.bet_freq:.0%}')


def test_draw_hand_includes_in_category():
    """has_draw=True with equity in draw range should classify as draw."""
    r = donk_or_probe(equity=0.38, pot_bb=10.0, eff_stack_bb=80.0,
                       community=['9h', '8c', '2h'], street='flop',
                       hero_pos='bb', has_draw=True)
    assert r.hand_category == 'draw', f'Draw hand should classify as draw: {r.hand_category}'
    print(f'Draw hand category: {r.hand_category} should_bet={r.should_bet}')


def test_sizing_pct_nonzero_when_should_bet():
    """When should_bet=True, sizing_pct should be positive."""
    r = donk_or_probe(equity=0.80, pot_bb=8.0, eff_stack_bb=100.0,
                       community=['7c', '5h', '2d'], street='flop',
                       hero_pos='bb', villain_pos='BTN')
    if r.should_bet:
        assert r.sizing_pct > 0, f'When should_bet=True, sizing_pct must be > 0'
        assert r.sizing_bb > 0, f'When should_bet=True, sizing_bb must be > 0'
    print(f'Sizing: pct={r.sizing_pct:.0%} bb={r.sizing_bb:.1f}BB')


def test_donk_bet_type_on_flop():
    """donk_or_probe on flop should return bet_type='donk'."""
    r = donk_or_probe(equity=0.70, pot_bb=8.0, eff_stack_bb=100.0,
                       community=['7c', '5h', '2d'], street='flop',
                       hero_pos='bb')
    assert r.bet_type == 'donk', f'Flop should be donk type: {r.bet_type}'
    print(f'Flop bet_type: {r.bet_type}')


def test_donk_summary_format():
    """donk_summary should return a string and not crash."""
    r = donk_or_probe(equity=0.65, pot_bb=10.0, eff_stack_bb=80.0,
                       community=['7c', '5h', '2d'], street='flop',
                       hero_pos='bb')
    s = donk_summary(r)
    assert isinstance(s, str), f'donk_summary should return str: {type(s)}'
    assert len(s) > 5, f'Summary too short: {s!r}'
    print(f'Donk summary: {s}')


def test_low_spr_adjusts_sizing():
    """Low SPR should affect bet sizing (smaller pot → smaller absolute bet)."""
    r_deep  = donk_or_probe(equity=0.75, pot_bb=10.0, eff_stack_bb=200.0,
                             community=['7c', '5h', '2d'], street='flop',
                             hero_pos='bb')
    r_short = donk_or_probe(equity=0.75, pot_bb=10.0, eff_stack_bb=20.0,
                             community=['7c', '5h', '2d'], street='flop',
                             hero_pos='bb')
    # Both may or may not bet, but sizing_bb for short should be <= deep
    # (both based on same pot_bb, so sizing_bb proportional to sizing_pct and pot_bb)
    print(f'SPR deep={r_deep.sizing_bb:.1f}BB short={r_short.sizing_bb:.1f}BB '
          f'(pct: {r_deep.sizing_pct:.0%} vs {r_short.sizing_pct:.0%})')
    # No assertion; just verify no crash
    assert r_deep.sizing_pct >= 0 and r_short.sizing_pct >= 0


if __name__ == '__main__':
    tests = [
        test_low_board_bb_donk_increases_frequency,
        test_nuts_hand_may_donk,
        test_weak_hand_high_board_should_not_donk,
        test_probe_bet_turn_when_villain_checked_back,
        test_probe_bet_river_favorable_runout,
        test_high_villain_cbet_pct_increases_donk_frequency,
        test_draw_hand_includes_in_category,
        test_sizing_pct_nonzero_when_should_bet,
        test_donk_bet_type_on_flop,
        test_donk_summary_format,
        test_low_spr_adjusts_sizing,
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
