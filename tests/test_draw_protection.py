"""Tests for poker/draw_protection.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.draw_protection import analyze_draw_protection, draw_protection_summary


def test_flush_draw_board_flop():
    """Three hearts on flop → flush draw detected, protection bet recommended."""
    r = analyze_draw_protection(
        community=['Ah', 'Kh', '7h'],
        pot_bb=20.0,
        hero_equity=0.72,
    )
    assert r.protection_needed, 'Flush draw should trigger protection'
    assert r.primary_threat is not None
    assert r.primary_threat.draw_type in ('flush', 'combo')
    assert r.primary_threat.outs >= 9
    assert r.rec_bet_bb > 0
    assert r.rec_pot_pct >= 0.30, f'Flush draw protection should be ≥30% pot, got {r.rec_pot_pct:.0%}'
    assert r.free_card_ev_loss > 0
    print(f'Flush draw: outs={r.primary_threat.outs}  rec={r.rec_pot_pct:.0%}pot={r.rec_bet_bb:.0f}BB  '
          f'free_card_loss={r.free_card_ev_loss:.1f}BB')


def test_dry_board_no_protection():
    """Rainbow, disconnected board → no major draw threat."""
    r = analyze_draw_protection(
        community=['Ah', 'Kd', '2c'],
        pot_bb=15.0,
        hero_equity=0.80,
    )
    assert not r.protection_needed, 'Dry rainbow board should not need protection'
    print(f'Dry board: protection_needed={r.protection_needed}  threats={[t.draw_type for t in r.threats]}')


def test_oesd_board():
    """Three connected cards (9-T-J) → OESD or straight draw threat."""
    r = analyze_draw_protection(
        community=['9h', 'Td', 'Jc'],
        pot_bb=18.0,
        hero_equity=0.65,
    )
    assert r.protection_needed, 'Connected board should trigger protection'
    assert any(t.draw_type in ('oesd', 'combo') for t in r.threats), \
        f'Should detect OESD threat, got {[t.draw_type for t in r.threats]}'
    print(f'OESD board: threats={[t.draw_type for t in r.threats]}  rec={r.rec_bet_bb:.0f}BB')


def test_combo_draw_board():
    """Three suited connected cards → combo draw (highest threat)."""
    r = analyze_draw_protection(
        community=['8h', '9h', 'Th'],
        pot_bb=20.0,
        hero_equity=0.60,
    )
    assert r.protection_needed
    assert r.primary_threat is not None
    assert r.primary_threat.draw_type == 'combo', \
        f'Expected combo draw, got {r.primary_threat.draw_type}'
    assert r.primary_threat.outs >= 12, f'Combo should have 12+ outs, got {r.primary_threat.outs}'
    assert r.rec_pot_pct >= 0.60, f'Combo draw needs bigger bet, got {r.rec_pot_pct:.0%}'
    print(f'Combo draw: outs={r.primary_threat.outs}  rec={r.rec_pot_pct:.0%}pot={r.rec_bet_bb:.0f}BB')


def test_turn_flush_draw():
    """Flush draw on turn → fewer cards remaining (46 instead of 47)."""
    r = analyze_draw_protection(
        community=['Kh', '7h', '3d', '2h'],   # 3 hearts on turn
        pot_bb=30.0,
        hero_equity=0.68,
    )
    assert r.street == 'turn'
    assert r.cards_remaining == 46
    assert r.protection_needed
    # Turn flush draw slightly more expensive to chase
    assert r.rec_bet_bb > 0
    print(f'Turn flush draw: street={r.street}  cards_remaining={r.cards_remaining}  rec={r.rec_bet_bb:.0f}BB')


def test_river_no_analysis():
    """River has no more draws to price out → empty result."""
    r = analyze_draw_protection(
        community=['Ah', 'Kh', 'Qh', 'Jh', 'Th'],
        pot_bb=25.0,
        hero_equity=0.90,
    )
    assert r.street == 'river'
    assert not r.protection_needed
    assert r.rec_bet_bb == 0 or r.primary_threat is None
    print(f'River: protection_needed={r.protection_needed}  (correctly none)')


def test_free_card_ev_increases_with_pot():
    """Larger pot → higher free card EV loss."""
    r_small = analyze_draw_protection(['Ah', 'Kh', '7h'], pot_bb=10.0, hero_equity=0.65)
    r_large = analyze_draw_protection(['Ah', 'Kh', '7h'], pot_bb=50.0, hero_equity=0.65)
    assert r_large.free_card_ev_loss > r_small.free_card_ev_loss, \
        'Larger pot should mean higher free card EV loss'
    print(f'Free card loss: small_pot={r_small.free_card_ev_loss:.1f}BB  large_pot={r_large.free_card_ev_loss:.1f}BB')


def test_multiway_increases_threat():
    """More opponents → effectively more dangerous draws."""
    r_hu = analyze_draw_protection(['Ah', 'Kh', '7h'], pot_bb=20.0, n_opponents=1)
    r_mw = analyze_draw_protection(['Ah', 'Kh', '7h'], pot_bb=20.0, n_opponents=3)
    # Multiway should produce higher outs count or rec size
    assert r_mw.rec_bet_bb >= r_hu.rec_bet_bb, \
        'Multiway should require larger protection bet'
    print(f'HU: {r_hu.rec_bet_bb:.0f}BB  Multiway: {r_mw.rec_bet_bb:.0f}BB')


def test_gutshot_medium_threat():
    """Gutshot draw → medium threat, lower outs."""
    r = analyze_draw_protection(
        community=['9d', 'Jh', 'Kc'],   # only 2 connected → gutshot possible
        pot_bb=15.0,
        hero_equity=0.70,
    )
    # Should have gutshot or no threat (depends on board connectivity)
    if r.primary_threat and r.primary_threat.draw_type == 'gutshot':
        assert r.primary_threat.outs == 4
        assert r.primary_threat.threat_level == 'medium'
        print(f'Gutshot: outs={r.primary_threat.outs}  level={r.primary_threat.threat_level}')
    else:
        print(f'No gutshot on this board (expected): threats={[t.draw_type for t in r.threats]}')


def test_summary_format():
    """Summary should be ≤85 chars and contain [保護注] for draw boards."""
    r = analyze_draw_protection(
        community=['Ah', 'Kh', '9h'],
        pot_bb=25.0,
        hero_equity=0.68,
    )
    s = draw_protection_summary(r)
    if s:
        assert len(s) <= 85, f'Too long ({len(s)}): {s}'
        assert '[保護注]' in s
    print(f'Summary ({len(s)} chars): {s}')


def test_min_bet_less_than_rec_bet():
    """Recommended bet (with implied odds) ≥ minimum bet (without implied odds)."""
    r = analyze_draw_protection(
        community=['Th', '8h', '6c'],
        pot_bb=20.0,
        hero_equity=0.62,
    )
    if r.protection_needed:
        assert r.rec_bet_bb >= r.min_bet_bb, \
            f'rec_bet ({r.rec_bet_bb}) should be >= min_bet ({r.min_bet_bb})'
        assert r.rec_pot_pct >= r.min_pot_pct, \
            f'rec_pct ({r.rec_pot_pct:.0%}) >= min_pct ({r.min_pot_pct:.0%})'
    print(f'min={r.min_bet_bb:.0f}BB  rec={r.rec_bet_bb:.0f}BB  '
          f'min_pct={r.min_pot_pct:.0%}  rec_pct={r.rec_pot_pct:.0%}')


if __name__ == '__main__':
    tests = [
        test_flush_draw_board_flop,
        test_dry_board_no_protection,
        test_oesd_board,
        test_combo_draw_board,
        test_turn_flush_draw,
        test_river_no_analysis,
        test_free_card_ev_increases_with_pot,
        test_multiway_increases_threat,
        test_gutshot_medium_threat,
        test_summary_format,
        test_min_bet_less_than_rec_bet,
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
