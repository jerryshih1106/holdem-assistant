"""Tests for poker/gto_deviation.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.gto_deviation import check_deviation


def test_over_cbetting_is_detected():
    """Hero cbetting 80% vs GTO 65% should be flagged as 'over'."""
    r = check_deviation(action_type='cbet', position='IP', street='flop',
                        board_texture='dry', hero_freq=0.80)
    assert r.direction == 'over', f'80% cbet vs GTO 65% should be over: {r.direction}'
    assert r.is_balanced is False
    print(f'Over cbet: direction={r.direction} deviation={r.deviation:.0%}')


def test_gto_freq_within_range():
    """GTO frequency should be between 0 and 1."""
    r = check_deviation(action_type='cbet', position='IP', street='flop',
                        board_texture='dry', hero_freq=0.65)
    assert 0.0 <= r.gto_freq <= 1.0, f'gto_freq out of bounds: {r.gto_freq}'
    print(f'GTO freq: {r.gto_freq:.0%}')


def test_deviation_equals_hero_minus_gto():
    """deviation field should equal |hero_freq - gto_freq|."""
    r = check_deviation(action_type='cbet', position='IP', street='flop',
                        board_texture='dry', hero_freq=0.80)
    expected = abs(r.hero_freq - r.gto_freq)
    assert abs(r.deviation - expected) < 0.001, \
        f'deviation {r.deviation:.3f} != |{r.hero_freq:.2f} - {r.gto_freq:.2f}|={expected:.3f}'
    print(f'Deviation: {r.deviation:.0%} (hero={r.hero_freq:.0%} gto={r.gto_freq:.0%})')


def test_under_cbetting_is_detected():
    """Hero cbetting 30% vs GTO freq should be flagged as 'under' when GTO is higher."""
    r = check_deviation(action_type='cbet', position='IP', street='flop',
                        board_texture='dry', hero_freq=0.30)
    if r.gto_freq > 0.30:
        assert r.direction == 'under', \
            f'30% cbet vs GTO {r.gto_freq:.0%} should be under: {r.direction}'
    print(f'Under cbet: direction={r.direction}')


def test_balanced_when_hero_at_gto():
    """Hero freq matching GTO freq should be balanced."""
    r_ref = check_deviation(action_type='cbet', position='IP', street='flop',
                            board_texture='dry', hero_freq=0.50)
    gto = r_ref.gto_freq
    r = check_deviation(action_type='cbet', position='IP', street='flop',
                        board_texture='dry', hero_freq=gto)
    assert r.is_balanced is True, \
        f'Hero at GTO freq {gto:.0%} should be balanced: {r.is_balanced}'
    print(f'Balanced at {gto:.0%}: is_balanced={r.is_balanced}')


def test_ev_loss_nonnegative():
    """ev_loss_bb100 should be non-negative (losses reduce EV)."""
    r = check_deviation(action_type='cbet', position='IP', street='flop',
                        board_texture='dry', hero_freq=0.80)
    assert r.ev_loss_bb100 >= 0.0, \
        f'ev_loss_bb100 should be >= 0: {r.ev_loss_bb100}'
    print(f'EV loss: {r.ev_loss_bb100:.2f}BB/100')


def test_ev_loss_zero_when_balanced():
    """When balanced, EV loss should be near zero."""
    r_ref = check_deviation(action_type='cbet', position='IP', street='flop',
                            board_texture='dry', hero_freq=0.50)
    gto = r_ref.gto_freq
    r = check_deviation(action_type='cbet', position='IP', street='flop',
                        board_texture='dry', hero_freq=gto)
    assert r.ev_loss_bb100 < 0.5, \
        f'Balanced play should have near-zero EV loss: {r.ev_loss_bb100:.2f}'
    print(f'Balanced EV loss: {r.ev_loss_bb100:.2f}BB/100')


def test_exploit_risk_valid_value():
    """exploit_risk should be one of: low, medium, high."""
    r = check_deviation(action_type='cbet', position='IP', street='flop',
                        board_texture='dry', hero_freq=0.80)
    assert r.exploit_risk in ('low', 'medium', 'high'), \
        f'exploit_risk must be low/medium/high: {r.exploit_risk!r}'
    print(f'Exploit risk: {r.exploit_risk}')


def test_large_deviation_has_high_risk():
    """Very large deviation should yield medium or high exploit risk."""
    r = check_deviation(action_type='cbet', position='IP', street='flop',
                        board_texture='dry', hero_freq=1.0)
    assert r.exploit_risk in ('medium', 'high'), \
        f'Large deviation should be medium/high risk: {r.exploit_risk}'
    print(f'Large deviation: risk={r.exploit_risk} ev_loss={r.ev_loss_bb100:.2f}BB/100')


def test_recommendation_is_string():
    """recommendation field should be a non-empty string."""
    r = check_deviation(action_type='cbet', position='IP', street='flop',
                        board_texture='dry', hero_freq=0.80)
    assert isinstance(r.recommendation, str), \
        f'recommendation should be str: {type(r.recommendation)}'
    assert len(r.recommendation) > 5, f'recommendation too short: {r.recommendation!r}'
    print(f'Recommendation length: {len(r.recommendation)} chars')


def test_gto_rationale_is_string():
    """gto_rationale field should be a non-empty string."""
    r = check_deviation(action_type='cbet', position='IP', street='flop',
                        board_texture='dry', hero_freq=0.65)
    assert isinstance(r.gto_rationale, str), \
        f'gto_rationale should be str: {type(r.gto_rationale)}'
    assert len(r.gto_rationale) > 5, f'gto_rationale too short: {r.gto_rationale!r}'
    print(f'Rationale: {r.gto_rationale[:60]}')


if __name__ == '__main__':
    tests = [
        test_over_cbetting_is_detected,
        test_gto_freq_within_range,
        test_deviation_equals_hero_minus_gto,
        test_under_cbetting_is_detected,
        test_balanced_when_hero_at_gto,
        test_ev_loss_nonnegative,
        test_ev_loss_zero_when_balanced,
        test_exploit_risk_valid_value,
        test_large_deviation_has_high_risk,
        test_recommendation_is_string,
        test_gto_rationale_is_string,
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
