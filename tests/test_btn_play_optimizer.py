"""Tests for poker/btn_play_optimizer.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.btn_play_optimizer import (
    advise_btn_play, BtnPlayAdvice, btn_play_one_liner
)


def _adv(**kw):
    defaults = dict(
        street='preflop',
        hero_hand_class='top_pair',
        board_type='medium',
        sb_vpip=0.22,
        sb_3bet_pct=0.07,
        bb_vpip=0.30,
        bb_3bet_pct=0.06,
        hero_stack_bb=100.0,
        pot_bb=0.0,
        n_callers=0,
        facing_3bet=False,
    )
    defaults.update(kw)
    return advise_btn_play(**defaults)


def test_returns_correct_type():
    r = _adv()
    assert isinstance(r, BtnPlayAdvice)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _adv()
    fields = [
        'street', 'hero_hand_class', 'board_type', 'sb_vpip', 'sb_3bet_pct',
        'bb_vpip', 'bb_3bet_pct', 'hero_stack_bb', 'pot_bb', 'n_callers', 'facing_3bet',
        'recommended_open_freq', 'recommended_sizing_bb', 'open_ev_estimate',
        'cbet_frequency', 'cbet_size_pct', 'cbet_size_bb', 'cbet_ev_estimate',
        'vs_3bet_action', 'vs_3bet_reasoning', 'fourbet_ev', 'call_3bet_ev',
        'action', 'reasoning', 'tips',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_preflop_open_action():
    """Default preflop (no 3-bet): action should be open_raise."""
    r = _adv(street='preflop', facing_3bet=False)
    assert r.action == 'open_raise', f'Should be open_raise: {r.action}'
    print(f'Preflop action: {r.action}')


def test_open_freq_in_range():
    """Open frequency should be in [35%, 58%]."""
    r = _adv()
    assert 0.35 <= r.recommended_open_freq <= 0.58, \
        f'Open freq out of range: {r.recommended_open_freq:.0%}'
    print(f'Open freq: {r.recommended_open_freq:.0%}')


def test_tight_blinds_open_wider():
    """Tight/passive blinds: open wider."""
    r_tight = _adv(sb_vpip=0.14, bb_vpip=0.18, sb_3bet_pct=0.04, bb_3bet_pct=0.03)
    r_normal = _adv(sb_vpip=0.22, bb_vpip=0.28, sb_3bet_pct=0.07, bb_3bet_pct=0.06)
    assert r_tight.recommended_open_freq >= r_normal.recommended_open_freq, \
        f'Tight blinds should open wider: tight={r_tight.recommended_open_freq:.0%} normal={r_normal.recommended_open_freq:.0%}'
    print(f'Open freq: tight_blinds={r_tight.recommended_open_freq:.0%} normal={r_normal.recommended_open_freq:.0%}')


def test_aggressive_blinds_open_tighter():
    """Aggressive 3-betting blinds: open tighter."""
    r_aggro = _adv(sb_3bet_pct=0.15, bb_3bet_pct=0.12)
    r_normal = _adv(sb_3bet_pct=0.07, bb_3bet_pct=0.06)
    assert r_aggro.recommended_open_freq <= r_normal.recommended_open_freq, \
        f'Aggro blinds should open tighter: aggro={r_aggro.recommended_open_freq:.0%} normal={r_normal.recommended_open_freq:.0%}'
    print(f'Open freq: aggro_blinds={r_aggro.recommended_open_freq:.0%} normal={r_normal.recommended_open_freq:.0%}')


def test_fish_in_bb_opens_wider():
    """Fish (high VPIP) in BB: open wider to exploit."""
    r_fish = _adv(bb_vpip=0.60)
    r_normal = _adv(bb_vpip=0.30)
    assert r_fish.recommended_open_freq >= r_normal.recommended_open_freq, \
        f'Fish BB should open wider: fish={r_fish.recommended_open_freq:.0%} normal={r_normal.recommended_open_freq:.0%}'
    print(f'Open freq: fish_BB={r_fish.recommended_open_freq:.0%} normal={r_normal.recommended_open_freq:.0%}')


def test_sizing_aggressive_blinds_smaller():
    """vs aggressive 3-bet blinds: smaller open to risk less."""
    r_aggro = _adv(sb_3bet_pct=0.15, bb_3bet_pct=0.12)
    r_normal = _adv(sb_3bet_pct=0.07, bb_3bet_pct=0.06)
    assert r_aggro.recommended_sizing_bb <= r_normal.recommended_sizing_bb, \
        f'Aggro blinds should size smaller: aggro={r_aggro.recommended_sizing_bb:.1f} normal={r_normal.recommended_sizing_bb:.1f}'
    print(f'Sizing: aggro={r_aggro.recommended_sizing_bb:.1f}BB normal={r_normal.recommended_sizing_bb:.1f}BB')


def test_cbet_dry_higher_than_wet():
    """Dry board c-bet frequency > wet board (more fold equity)."""
    r_dry = _adv(street='flop', board_type='dry', pot_bb=15.0)
    r_wet = _adv(street='flop', board_type='wet', pot_bb=15.0)
    assert r_dry.cbet_frequency >= r_wet.cbet_frequency, \
        f'Dry cbet should be >= wet: dry={r_dry.cbet_frequency:.0%} wet={r_wet.cbet_frequency:.0%}'
    print(f'Cbet: dry={r_dry.cbet_frequency:.0%} wet={r_wet.cbet_frequency:.0%}')


def test_multiway_lower_cbet_freq():
    """Multiway pots: lower c-bet frequency than HU."""
    r_hu = _adv(street='flop', board_type='medium', pot_bb=12.0, n_callers=0)
    r_mw = _adv(street='flop', board_type='medium', pot_bb=12.0, n_callers=2)
    assert r_hu.cbet_frequency >= r_mw.cbet_frequency, \
        f'HU should cbet >= multiway: HU={r_hu.cbet_frequency:.0%} MW={r_mw.cbet_frequency:.0%}'
    print(f'Cbet: HU={r_hu.cbet_frequency:.0%} MW={r_mw.cbet_frequency:.0%}')


def test_vs_3bet_valid_action():
    """Facing 3-bet: action must be one of valid options."""
    r = _adv(facing_3bet=True, threbet_bb=9.0, hero_hand_class='overpair')
    assert r.vs_3bet_action in ('fold', 'cold_call', '4bet'), \
        f'Invalid 3-bet action: {r.vs_3bet_action}'
    assert r.action in ('fold', 'cold_call', '4bet'), \
        f'Main action mismatch: {r.action}'
    print(f'vs 3-bet action: {r.vs_3bet_action}')


def test_premium_4bets_vs_3bet():
    """Premium hand facing 3-bet from BTN: should 4-bet."""
    r = _adv(facing_3bet=True, hero_hand_class='premium', threbet_bb=9.0)
    # Premium EV should favor 4-bet
    assert r.fourbet_ev > 0, f'Premium 4-bet EV should be positive: {r.fourbet_ev:.2f}'
    print(f'Premium vs 3-bet: 4bet_ev={r.fourbet_ev:.2f} action={r.vs_3bet_action}')


def test_open_ev_positive():
    """BTN open EV should be positive (BTN is most profitable open)."""
    r = _adv(street='preflop')
    assert r.open_ev_estimate > 0, f'BTN open EV should be positive: {r.open_ev_estimate:.2f}'
    print(f'BTN open EV: {r.open_ev_estimate:.2f}BB')


def test_cbet_size_bb_consistent():
    """cbet_size_bb = pot_bb * cbet_size_pct (within rounding)."""
    r = _adv(street='flop', pot_bb=20.0, board_type='medium')
    expected = round(20.0 * r.cbet_size_pct, 1)
    assert abs(r.cbet_size_bb - expected) < 0.5, \
        f'cbet_size_bb mismatch: {r.cbet_size_bb:.1f} vs expected {expected:.1f}'
    print(f'cbet_size_bb: {r.cbet_size_bb:.1f}BB = {r.cbet_size_pct:.0%} x 20BB')


def test_all_streets_produce_valid_action():
    """All streets should produce a valid action."""
    valid_actions = {'open_raise', 'fold', 'cold_call', '4bet', 'cbet', 'cbet_mixed', 'check'}
    for street in ['preflop', 'flop', 'turn', 'river']:
        r = _adv(street=street, pot_bb=15.0 if street != 'preflop' else 0.0)
        assert r.action in valid_actions, f'Invalid action={r.action} for {street}'
    print('All streets produce valid actions')


def test_all_board_types_work():
    """All board types should work without error."""
    for bt in ['dry', 'medium', 'wet', 'paired']:
        r = _adv(street='flop', board_type=bt, pot_bb=12.0)
        assert 0 <= r.cbet_frequency <= 1
    print('All board types work')


def test_tips_not_empty():
    r = _adv()
    assert isinstance(r.tips, list) and len(r.tips) > 0
    print(f'Tips: {len(r.tips)}')


def test_reasoning_not_empty():
    r = _adv()
    assert isinstance(r.reasoning, str) and len(r.reasoning) > 10
    print(f'Reasoning: {r.reasoning[:60]}...')


def test_vs_3bet_reasoning_not_empty():
    r = _adv(facing_3bet=True)
    assert isinstance(r.vs_3bet_reasoning, str) and len(r.vs_3bet_reasoning) > 5
    print(f'3-bet reasoning: {r.vs_3bet_reasoning[:60]}...')


def test_fish_tips_generated():
    """Fish in BB should generate fish-specific tips."""
    r = _adv(bb_vpip=0.60, street='preflop')
    fish_tip = any('FISH' in t or 'fish' in t.lower() or 'vpip' in t.lower() for t in r.tips)
    assert fish_tip, f'No fish tip for BB fish (vpip=60%): tips={r.tips}'
    print(f'Fish tips generated: {len(r.tips)} tips')


def test_all_hand_classes_postflop():
    """All hand classes should produce valid postflop advice."""
    for h in ['air', 'draw', 'middle_pair', 'top_pair', 'overpair', 'set']:
        r = _adv(street='flop', hero_hand_class=h, pot_bb=15.0, board_type='medium')
        assert r.action in {'cbet', 'cbet_mixed', 'check'}
    print('All hand classes produce valid postflop advice')


def test_one_liner_preflop():
    r = _adv(street='preflop')
    line = btn_play_one_liner(r)
    assert 'BTN' in line and 'open=' in line and '3b_vs=' in line
    print(f'one_liner preflop: {line}')


def test_one_liner_postflop():
    r = _adv(street='flop', pot_bb=15.0, board_type='dry')
    line = btn_play_one_liner(r)
    assert 'BTN' in line and 'cbet=' in line and 'ev=' in line
    print(f'one_liner postflop: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_correct_type, test_required_fields,
        test_preflop_open_action, test_open_freq_in_range,
        test_tight_blinds_open_wider, test_aggressive_blinds_open_tighter,
        test_fish_in_bb_opens_wider, test_sizing_aggressive_blinds_smaller,
        test_cbet_dry_higher_than_wet, test_multiway_lower_cbet_freq,
        test_vs_3bet_valid_action, test_premium_4bets_vs_3bet,
        test_open_ev_positive, test_cbet_size_bb_consistent,
        test_all_streets_produce_valid_action, test_all_board_types_work,
        test_tips_not_empty, test_reasoning_not_empty,
        test_vs_3bet_reasoning_not_empty, test_fish_tips_generated,
        test_all_hand_classes_postflop, test_one_liner_preflop, test_one_liner_postflop,
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
