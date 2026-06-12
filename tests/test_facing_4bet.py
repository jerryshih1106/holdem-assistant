"""Tests for poker/facing_4bet.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.facing_4bet import analyze_facing_4bet, facing_4bet_summary


def test_aa_always_jam():
    """AA (top 0.5%) facing any 4-bet → always jam."""
    r = analyze_facing_4bet(
        villain_pos='BTN', fourbet_size_bb=24.0, threebet_size_bb=9.0,
        pot_pre_3bet_bb=5.0, hero_hand_pct=0.995, hero_stack_bb=100.0,
    )
    assert r.action == 'jam', f'AA should always jam: {r.action} / {r.verdict_zh}'
    assert r.jam_frequency >= 0.90, f'AA jam freq should be high: {r.jam_frequency}'
    print(f'AA: {r.action}  equity={r.hero_equity_vs_range:.0%}  required={r.required_equity:.0%}')


def test_kk_jam():
    """KK facing BTN 4-bet → jam or strong call."""
    r = analyze_facing_4bet(
        villain_pos='BTN', fourbet_size_bb=24.0, threebet_size_bb=9.0,
        pot_pre_3bet_bb=5.0, hero_hand_pct=0.990, hero_stack_bb=100.0,
    )
    assert r.action in ('jam', 'call'), f'KK should jam or call, not fold: {r.action}'
    assert r.hero_equity_vs_range >= 0.50, f'KK should have >50% equity vs 4-bet range'
    print(f'KK: {r.action}  equity={r.hero_equity_vs_range:.0%}')


def test_jj_vs_tight_utg_fold():
    """JJ facing UTG nit 4-bet (almost always QQ+/AK) → mostly fold."""
    r = analyze_facing_4bet(
        villain_pos='UTG', fourbet_size_bb=20.0, threebet_size_bb=8.0,
        pot_pre_3bet_bb=4.0, hero_hand_pct=0.975, hero_stack_bb=100.0,
        villain_vpip=0.14,  # nit
    )
    # JJ vs UTG nit range (KK+/AKs probably) → fold or marginal
    assert r.fold_frequency >= 0.50, \
        f'JJ vs UTG nit should fold often: fold_freq={r.fold_frequency:.0%}'
    print(f'JJ vs UTG nit: {r.action}  fold%={r.fold_frequency:.0%}  range={r.villain_4bet_range_pct:.0%}')


def test_btn_wider_range_than_utg():
    """BTN 4-bets wider than UTG at same stack."""
    r_btn = analyze_facing_4bet(villain_pos='BTN', fourbet_size_bb=24.0,
                                threebet_size_bb=9.0, pot_pre_3bet_bb=5.0,
                                hero_hand_pct=0.980, hero_stack_bb=100.0)
    r_utg = analyze_facing_4bet(villain_pos='UTG', fourbet_size_bb=24.0,
                                threebet_size_bb=9.0, pot_pre_3bet_bb=5.0,
                                hero_hand_pct=0.980, hero_stack_bb=100.0)
    assert r_btn.villain_4bet_range_pct > r_utg.villain_4bet_range_pct, \
        f'BTN should 4-bet wider: {r_btn.villain_4bet_range_pct:.0%} vs {r_utg.villain_4bet_range_pct:.0%}'
    print(f'BTN range: {r_btn.villain_4bet_range_pct:.0%}  UTG range: {r_utg.villain_4bet_range_pct:.0%}')


def test_required_equity_formula():
    """Required equity = call / (pot + call) by definition."""
    r = analyze_facing_4bet(
        villain_pos='BTN', fourbet_size_bb=24.0, threebet_size_bb=9.0,
        pot_pre_3bet_bb=5.0, hero_hand_pct=0.980, hero_stack_bb=100.0,
    )
    # pot_before = 5 + 9 + 24 = 38, hero_call = 24 - 9 = 15, total = 38 + 15 = 53
    expected_req = 15.0 / 53.0
    assert abs(r.required_equity - expected_req) < 0.005, \
        f'Required equity: {r.required_equity:.3f} vs expected {expected_req:.3f}'
    print(f'Required equity: {r.required_equity:.3f} = call({r.hero_call_bb:.0f}) / pot({r.total_pot_if_call:.0f})')


def test_short_stack_call_is_allin():
    """With short stack, calling the 4-bet may be all-in."""
    r = analyze_facing_4bet(
        villain_pos='BTN', fourbet_size_bb=28.0, threebet_size_bb=9.0,
        pot_pre_3bet_bb=4.0, hero_hand_pct=0.985, hero_stack_bb=35.0,
    )
    # hero_call = 28 - 9 = 19, remaining = 35 - 19 = 16... not all-in yet but short SPR
    # Actually at 35BB, fourbet to 28BB, hero 3-bet 9BB: call = 19BB, remaining = 16BB
    # spr_if_call = 16 / (41+19) = 16/60 = 0.27 → very low → should jam or fold
    assert r.spr_if_call < 3.0 or r.is_all_in_if_call, \
        f'Short stack should have low SPR or be all-in: spr={r.spr_if_call}'
    print(f'Short stack (35BB): is_allin={r.is_all_in_if_call}  spr={r.spr_if_call:.1f}  action={r.action}')


def test_fish_villain_advice():
    """Fish 4-bet (high VPIP) → widened range estimate."""
    r_fish = analyze_facing_4bet(villain_pos='BTN', fourbet_size_bb=24.0,
                                 threebet_size_bb=9.0, pot_pre_3bet_bb=5.0,
                                 hero_hand_pct=0.980, hero_stack_bb=100.0,
                                 villain_vpip=0.45)
    r_nit  = analyze_facing_4bet(villain_pos='BTN', fourbet_size_bb=24.0,
                                 threebet_size_bb=9.0, pot_pre_3bet_bb=5.0,
                                 hero_hand_pct=0.980, hero_stack_bb=100.0,
                                 villain_vpip=0.14)
    assert r_fish.villain_4bet_range_pct >= r_nit.villain_4bet_range_pct, \
        f'Fish should have wider or equal range: {r_fish.villain_4bet_range_pct:.0%} vs {r_nit.villain_4bet_range_pct:.0%}'
    print(f'Fish range: {r_fish.villain_4bet_range_pct:.0%}  Nit range: {r_nit.villain_4bet_range_pct:.0%}')


def test_strong_hand_positive_ev():
    """Premium hands should have positive EV margin vs typical 4-bet range."""
    for hand_pct, label in [(0.995, 'AA'), (0.990, 'KK'), (0.985, 'QQ')]:
        r = analyze_facing_4bet(villain_pos='BTN', fourbet_size_bb=24.0,
                                threebet_size_bb=9.0, pot_pre_3bet_bb=5.0,
                                hero_hand_pct=hand_pct, hero_stack_bb=100.0,
                                villain_vpip=0.28)
        assert r.ev_margin >= 0.0, f'{label} should have non-negative EV: {r.ev_margin:+.1%}'
        print(f'{label}: equity={r.hero_equity_vs_range:.0%}  EV margin={r.ev_margin:+.1%}  {r.action}')


def test_fold_frequency_increases_weaker_hand():
    """Weaker hands should fold more."""
    r_strong = analyze_facing_4bet(villain_pos='BTN', fourbet_size_bb=24.0,
                                   threebet_size_bb=9.0, pot_pre_3bet_bb=5.0,
                                   hero_hand_pct=0.990, hero_stack_bb=100.0)  # KK
    r_weak   = analyze_facing_4bet(villain_pos='BTN', fourbet_size_bb=24.0,
                                   threebet_size_bb=9.0, pot_pre_3bet_bb=5.0,
                                   hero_hand_pct=0.965, hero_stack_bb=100.0)  # TT
    assert r_weak.fold_frequency >= r_strong.fold_frequency, \
        f'Weaker hand should fold more: TT={r_weak.fold_frequency:.0%} vs KK={r_strong.fold_frequency:.0%}'
    print(f'KK fold: {r_strong.fold_frequency:.0%}  TT fold: {r_weak.fold_frequency:.0%}')


def test_hud_4bet_pct_used_when_available():
    """HUD 4-bet % should override position-based estimate."""
    r_hud_tight = analyze_facing_4bet(villain_pos='BTN', fourbet_size_bb=24.0,
                                      threebet_size_bb=9.0, pot_pre_3bet_bb=5.0,
                                      hero_hand_pct=0.980, hero_stack_bb=100.0,
                                      villain_4bet_pct=0.02, villain_hands=50)
    r_hud_wide  = analyze_facing_4bet(villain_pos='BTN', fourbet_size_bb=24.0,
                                      threebet_size_bb=9.0, pot_pre_3bet_bb=5.0,
                                      hero_hand_pct=0.980, hero_stack_bb=100.0,
                                      villain_4bet_pct=0.10, villain_hands=50)
    assert r_hud_tight.villain_4bet_range_pct < r_hud_wide.villain_4bet_range_pct, \
        f'HUD should affect range: tight={r_hud_tight.villain_4bet_range_pct:.0%} vs wide={r_hud_wide.villain_4bet_range_pct:.0%}'
    print(f'HUD tight (2%): {r_hud_tight.villain_4bet_range_pct:.0%}  HUD wide (10%): {r_hud_wide.villain_4bet_range_pct:.0%}')


def test_summary_format():
    """Summary should be <=85 chars and contain [面對4bet]."""
    r = analyze_facing_4bet(
        villain_pos='BTN', fourbet_size_bb=24.0, threebet_size_bb=9.0,
        pot_pre_3bet_bb=5.0, hero_hand_pct=0.985, hero_stack_bb=100.0,
    )
    s = facing_4bet_summary(r)
    assert len(s) <= 85, f'Too long ({len(s)}): {s}'
    assert '[面對4bet]' in s, f'Missing [面對4bet]: {s}'
    print(f'Summary ({len(s)} chars): {s}')


if __name__ == '__main__':
    tests = [
        test_aa_always_jam,
        test_kk_jam,
        test_jj_vs_tight_utg_fold,
        test_btn_wider_range_than_utg,
        test_required_equity_formula,
        test_short_stack_call_is_allin,
        test_fish_villain_advice,
        test_strong_hand_positive_ev,
        test_fold_frequency_increases_weaker_hand,
        test_hud_4bet_pct_used_when_available,
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
