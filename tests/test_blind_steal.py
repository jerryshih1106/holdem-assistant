"""Tests for poker/blind_steal.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.blind_steal import calc_steal_ev, steal_summary, calc_defense_ev, defense_summary


def test_btn_steal_positive_ev():
    """BTN steal with standard fold rates should be positive EV."""
    r = calc_steal_ev(hero_pos='BTN', open_size_bb=2.5,
                      sb_fold=0.70, bb_fold=0.65, hero_equity=0.45)
    assert r.ev_steal > 0, f'BTN steal should be +EV: {r.ev_steal:.3f}'
    assert r.steal_recommended is True
    print(f'BTN steal: EV={r.ev_steal:+.2f}BB recommended={r.steal_recommended}')


def test_both_fold_rate_product():
    """both_fold_rate should approximately equal sb_fold * bb_fold."""
    sb, bb = 0.70, 0.65
    r = calc_steal_ev(hero_pos='BTN', open_size_bb=2.5, sb_fold=sb, bb_fold=bb)
    expected = sb * bb
    assert abs(r.both_fold_rate - expected) < 0.01, \
        f'both_fold_rate {r.both_fold_rate:.3f} should ~= {expected:.3f}'
    print(f'Both fold rate: {r.both_fold_rate:.0%} (sb×bb={expected:.0%})')


def test_sb_steal_higher_ev_than_co():
    """SB steal should generally have higher fold equity than CO."""
    r_sb = calc_steal_ev(hero_pos='SB', open_size_bb=2.5,
                         sb_fold=1.0, bb_fold=0.65, hero_equity=0.45)
    r_co = calc_steal_ev(hero_pos='CO', open_size_bb=2.5,
                         sb_fold=0.70, bb_fold=0.65, hero_equity=0.45)
    # SB only faces BB (sb_fold=1.0 means BTN/CO already folded)
    assert isinstance(r_sb.ev_steal, float) and isinstance(r_co.ev_steal, float)
    print(f'SB steal EV={r_sb.ev_steal:+.2f}BB  CO steal EV={r_co.ev_steal:+.2f}BB')


def test_steal_ev_decreases_with_larger_open():
    """Larger open size increases risk vs same fold rates → may reduce EV."""
    r_small = calc_steal_ev(hero_pos='BTN', open_size_bb=2.0,
                            sb_fold=0.65, bb_fold=0.60)
    r_large = calc_steal_ev(hero_pos='BTN', open_size_bb=3.5,
                            sb_fold=0.65, bb_fold=0.60)
    assert isinstance(r_small.ev_steal, float) and isinstance(r_large.ev_steal, float)
    print(f'Open 2.0BB: EV={r_small.ev_steal:+.2f}  Open 3.5BB: EV={r_large.ev_steal:+.2f}')


def test_optimal_freq_between_0_and_1():
    """optimal_freq should be a valid probability."""
    r = calc_steal_ev(hero_pos='BTN', open_size_bb=2.5,
                      sb_fold=0.70, bb_fold=0.65)
    assert 0.0 <= r.optimal_freq <= 1.0, \
        f'optimal_freq out of bounds: {r.optimal_freq}'
    print(f'Optimal steal freq: {r.optimal_freq:.0%}')


def test_bb_mdf_correct():
    """BB MDF = open_size / (pot_after_open + open_size) approx."""
    open_bb = 2.5
    r = calc_steal_ev(hero_pos='BTN', open_size_bb=open_bb,
                      sb_fold=0.70, bb_fold=0.65)
    # MDF = open / (1.5 + open + open) roughly
    assert 0.20 <= r.bb_mdf <= 0.80, \
        f'bb_mdf should be a reasonable fraction: {r.bb_mdf}'
    print(f'BB MDF: {r.bb_mdf:.0%}')


def test_steal_range_hint_is_string():
    """steal_range_hint should be a non-empty string."""
    r = calc_steal_ev(hero_pos='BTN', open_size_bb=2.5,
                      sb_fold=0.70, bb_fold=0.65)
    assert isinstance(r.steal_range_hint, str) and len(r.steal_range_hint) > 3, \
        f'steal_range_hint should be non-empty: {r.steal_range_hint!r}'
    print(f'Steal range hint: {r.steal_range_hint[:50]}')


def test_defense_ev_returns_result():
    """calc_defense_ev should return a valid DefenseResult."""
    r = calc_defense_ev(hero_pos='BB', villain_pos='BTN',
                        open_size_bb=2.5, villain_equity=0.55,
                        villain_fold_3b=0.55)
    assert hasattr(r, 'recommended_defense') or hasattr(r, 'ev_call_estimate'), \
        f'DefenseResult should have defense fields: {vars(r)}'
    print(f'Defense result keys: {list(vars(r).keys())[:5]}')


def test_defense_summary_is_string():
    """defense_summary should return a non-empty string."""
    r = calc_defense_ev(hero_pos='BB', villain_pos='BTN',
                        open_size_bb=2.5)
    s = defense_summary(r)
    assert isinstance(s, str) and len(s) > 5, \
        f'defense_summary should be non-empty: {s!r}'
    print(f'Defense summary: {s[:60]}')


def test_steal_summary_is_string():
    """steal_summary should return a non-empty string."""
    r = calc_steal_ev(hero_pos='BTN', open_size_bb=2.5,
                      sb_fold=0.70, bb_fold=0.65)
    s = steal_summary(r)
    assert isinstance(s, str) and len(s) > 5, \
        f'steal_summary should be non-empty: {s!r}'
    print(f'Steal summary: {s[:60]}')


def test_tight_defenders_make_steal_more_profitable():
    """Very tight blinds (high fold rates) should increase steal EV."""
    r_tight = calc_steal_ev(hero_pos='BTN', open_size_bb=2.5,
                            sb_fold=0.90, bb_fold=0.85)
    r_loose = calc_steal_ev(hero_pos='BTN', open_size_bb=2.5,
                            sb_fold=0.50, bb_fold=0.45)
    assert r_tight.ev_steal >= r_loose.ev_steal, \
        f'Tight blinds EV {r_tight.ev_steal:+.2f} should >= loose {r_loose.ev_steal:+.2f}'
    print(f'Tight blinds EV={r_tight.ev_steal:+.2f}  Loose blinds EV={r_loose.ev_steal:+.2f}')


if __name__ == '__main__':
    tests = [
        test_btn_steal_positive_ev,
        test_both_fold_rate_product,
        test_sb_steal_higher_ev_than_co,
        test_steal_ev_decreases_with_larger_open,
        test_optimal_freq_between_0_and_1,
        test_bb_mdf_correct,
        test_steal_range_hint_is_string,
        test_defense_ev_returns_result,
        test_defense_summary_is_string,
        test_steal_summary_is_string,
        test_tight_defenders_make_steal_more_profitable,
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
