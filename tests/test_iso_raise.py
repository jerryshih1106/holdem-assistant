"""Tests for poker/iso_raise.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.iso_raise import analyze_iso_raise, iso_raise_summary


def test_btn_fish_limper_should_iso():
    """BTN vs 1 fish limper with decent hand → should iso raise."""
    r = analyze_iso_raise(
        hero_pos='BTN', n_limpers=1, hero_hand_pct=0.55,
        villain_vpip=0.45, hero_is_ip=True,
    )
    assert r.should_iso, f'BTN vs fish limper should iso: {r.key_reason}'
    assert r.hand_qualifies, f'Hand should qualify'
    assert r.iso_size_bb >= 4.0, f'ISO size should be at least 4BB, got {r.iso_size_bb}'
    print(f'BTN vs fish: iso={r.iso_size_bb}BB  p_fold={r.p_all_fold:.0%}  EV={r.ev_vs_limp:+.1f}BB')


def test_fish_limper_bigger_size():
    """Fish limper → larger iso size than TAG limper."""
    r_fish = analyze_iso_raise(hero_pos='BTN', n_limpers=1, hero_hand_pct=0.60,
                               villain_vpip=0.50, hero_is_ip=True)
    r_tag  = analyze_iso_raise(hero_pos='BTN', n_limpers=1, hero_hand_pct=0.60,
                               villain_vpip=0.22, hero_is_ip=True)
    assert r_fish.iso_size_bb >= r_tag.iso_size_bb, \
        f'Fish should need bigger iso: {r_fish.iso_size_bb} vs {r_tag.iso_size_bb}'
    print(f'Fish iso: {r_fish.iso_size_bb}BB  TAG iso: {r_tag.iso_size_bb}BB')


def test_more_limpers_bigger_size():
    """More limpers → bigger iso size needed."""
    r1 = analyze_iso_raise(hero_pos='BTN', n_limpers=1, hero_hand_pct=0.60, villain_vpip=0.30)
    r2 = analyze_iso_raise(hero_pos='BTN', n_limpers=2, hero_hand_pct=0.60, villain_vpip=0.30)
    r3 = analyze_iso_raise(hero_pos='BTN', n_limpers=3, hero_hand_pct=0.60, villain_vpip=0.30)
    assert r2.iso_size_bb >= r1.iso_size_bb, f'2 limpers should need bigger size'
    assert r3.iso_size_bb >= r2.iso_size_bb, f'3 limpers should need bigger size'
    print(f'Sizes: 1L={r1.iso_size_bb}  2L={r2.iso_size_bb}  3L={r3.iso_size_bb}')


def test_oop_premium_added():
    """OOP hero → larger iso size than IP hero."""
    r_ip  = analyze_iso_raise(hero_pos='CO', n_limpers=1, hero_hand_pct=0.60,
                              villain_vpip=0.35, hero_is_ip=True)
    r_oop = analyze_iso_raise(hero_pos='SB', n_limpers=1, hero_hand_pct=0.60,
                              villain_vpip=0.35, hero_is_ip=False)
    assert r_oop.iso_size_bb >= r_ip.iso_size_bb, \
        f'OOP should iso bigger: {r_oop.iso_size_bb} vs {r_ip.iso_size_bb}'
    print(f'IP iso: {r_ip.iso_size_bb}BB  OOP iso: {r_oop.iso_size_bb}BB')


def test_weak_hand_does_not_qualify():
    """Weak hand should not qualify for iso at UTG."""
    r = analyze_iso_raise(
        hero_pos='UTG', n_limpers=1, hero_hand_pct=0.10,
        villain_vpip=0.30, hero_is_ip=False,
    )
    assert not r.hand_qualifies, f'Weak hand at UTG should not qualify: {r.hand_threshold_zh}'
    assert not r.should_iso, f'Should not iso with weak hand'
    print(f'UTG weak hand: qualifies={r.hand_qualifies}  min_pct={r.min_hand_pct:.0%}')


def test_short_stack_no_iso():
    """Short stack (<=20BB) → should not iso, should push/fold."""
    r = analyze_iso_raise(
        hero_pos='BTN', n_limpers=1, hero_hand_pct=0.75,
        hero_stack_bb=18.0, villain_vpip=0.40,
    )
    assert not r.should_iso, f'Short stack should not iso'
    assert '短籌碼' in r.summary_zh or 'push' in r.summary_zh.lower() or '推牌' in r.summary_zh, \
        f'Should mention push/fold: {r.summary_zh}'
    print(f'Short stack: {r.summary_zh}')


def test_four_limpers_no_iso():
    """4+ limpers → very low fold equity, should not iso with marginal hand."""
    r = analyze_iso_raise(
        hero_pos='BTN', n_limpers=4, hero_hand_pct=0.40,
        villain_vpip=0.35, hero_is_ip=True,
    )
    assert not r.should_iso, f'4 limpers with marginal hand should not iso'
    print(f'4 limpers: should_iso={r.should_iso}  p_fold={r.p_all_fold:.0%}')


def test_nit_limper_tighter_threshold():
    """Nit limper → need stronger hand to iso than vs fish."""
    r_vs_fish = analyze_iso_raise(hero_pos='BTN', n_limpers=1, hero_hand_pct=0.50,
                                  villain_vpip=0.50, hero_is_ip=True)
    r_vs_nit  = analyze_iso_raise(hero_pos='BTN', n_limpers=1, hero_hand_pct=0.50,
                                  villain_vpip=0.12, hero_is_ip=True)
    assert r_vs_nit.min_hand_pct >= r_vs_fish.min_hand_pct, \
        f'Nit should require stronger hand: nit_min={r_vs_nit.min_hand_pct:.0%} fish_min={r_vs_fish.min_hand_pct:.0%}'
    print(f'Min hand vs fish: {r_vs_fish.min_hand_pct:.0%}  vs nit: {r_vs_nit.min_hand_pct:.0%}')


def test_iso_ev_positive_vs_good_hand():
    """Good hand vs fish limper → positive EV vs limping."""
    r = analyze_iso_raise(
        hero_pos='BTN', n_limpers=1, hero_hand_pct=0.75,
        villain_vpip=0.45, hero_is_ip=True,
    )
    assert r.ev_vs_limp > 0, f'Iso should be +EV vs limping: {r.ev_vs_limp}'
    print(f'ISO EV advantage over limp: {r.ev_vs_limp:+.1f}BB')


def test_fold_probability_decreases_with_more_limpers():
    """More limpers → lower probability of taking pot immediately."""
    r1 = analyze_iso_raise(hero_pos='BTN', n_limpers=1, hero_hand_pct=0.60, villain_vpip=0.30)
    r2 = analyze_iso_raise(hero_pos='BTN', n_limpers=2, hero_hand_pct=0.60, villain_vpip=0.30)
    r3 = analyze_iso_raise(hero_pos='BTN', n_limpers=3, hero_hand_pct=0.60, villain_vpip=0.30)
    assert r1.p_all_fold > r2.p_all_fold > r3.p_all_fold, \
        f'Fold prob should decrease with more limpers: {r1.p_all_fold:.2f} {r2.p_all_fold:.2f} {r3.p_all_fold:.2f}'
    print(f'P(all fold): 1L={r1.p_all_fold:.0%}  2L={r2.p_all_fold:.0%}  3L={r3.p_all_fold:.0%}')


def test_summary_format():
    """Summary should be <=85 chars and contain [孤立]."""
    r = analyze_iso_raise(hero_pos='BTN', n_limpers=1, hero_hand_pct=0.55, villain_vpip=0.40)
    s = iso_raise_summary(r)
    assert len(s) <= 85, f'Too long ({len(s)}): {s}'
    assert '[孤立]' in s, f'Missing [孤立]: {s}'
    print(f'Summary ({len(s)} chars): {s}')


if __name__ == '__main__':
    tests = [
        test_btn_fish_limper_should_iso,
        test_fish_limper_bigger_size,
        test_more_limpers_bigger_size,
        test_oop_premium_added,
        test_weak_hand_does_not_qualify,
        test_short_stack_no_iso,
        test_four_limpers_no_iso,
        test_nit_limper_tighter_threshold,
        test_iso_ev_positive_vs_good_hand,
        test_fold_probability_decreases_with_more_limpers,
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
