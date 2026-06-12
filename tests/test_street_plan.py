"""Tests for poker/street_plan.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.street_plan import plan_streets, street_plan_summary, _equity_to_category


def test_category_mapping():
    assert _equity_to_category(0.80) == 'nuts'
    assert _equity_to_category(0.65) == 'strong'
    assert _equity_to_category(0.55) == 'tpgk'
    assert _equity_to_category(0.42) == 'medium'
    assert _equity_to_category(0.30, has_draw=True) == 'draw'
    assert _equity_to_category(0.20) == 'weak'
    print('Category mapping: OK')


def test_nuts_flop_geometric():
    p = plan_streets(equity=0.82, pot_bb=10.0, stack_bb=90.0, community_len=3)
    assert p.hand_category == 'nuts'
    assert p.current.action == 'BET'
    assert p.current.size_pct > 0
    assert p.next_street is not None
    print(f'Nuts flop plan: {street_plan_summary(p)}')


def test_nuts_shove_low_spr():
    # SPR = 5/10 = 0.5 → committed, should shove
    p = plan_streets(equity=0.82, pot_bb=10.0, stack_bb=5.0, community_len=3)
    assert p.current.action == 'ALL_IN'
    print(f'Nuts low SPR shove: {street_plan_summary(p)}')


def test_strong_three_streets():
    p = plan_streets(equity=0.68, pot_bb=8.0, stack_bb=80.0, community_len=3)
    assert p.hand_category == 'strong'
    assert p.current.action == 'BET'
    assert p.current.size_bb > 0
    print(f'Strong 3-street plan: {street_plan_summary(p)}')


def test_tpgk_pot_control():
    p = plan_streets(equity=0.55, pot_bb=10.0, stack_bb=80.0, community_len=3)
    assert p.hand_category == 'tpgk'
    # TPGK should bet smaller than nuts
    nuts_plan = plan_streets(equity=0.82, pot_bb=10.0, stack_bb=80.0, community_len=3)
    assert p.current.size_pct <= nuts_plan.current.size_pct
    print(f'TPGK pot control: {street_plan_summary(p)}')


def test_draw_semibluff():
    p = plan_streets(equity=0.35, pot_bb=10.0, stack_bb=80.0,
                     community_len=3, has_draw=True)
    assert p.hand_category == 'draw'
    assert p.current.action == 'BET'
    print(f'Draw semi-bluff plan: {street_plan_summary(p)}')
    assert p.next_street is not None
    assert p.next_street.condition  # should have conditional plan


def test_weak_check_fold():
    p = plan_streets(equity=0.18, pot_bb=10.0, stack_bb=80.0, community_len=3)
    assert p.hand_category == 'weak'
    assert p.current.action in ('CHECK', 'BET')  # bluff or fold
    print(f'Weak check/fold: {street_plan_summary(p)}')


def test_oop_size_capped():
    p_ip  = plan_streets(equity=0.70, pot_bb=10.0, stack_bb=80.0,
                         community_len=3, is_oop=False)
    p_oop = plan_streets(equity=0.70, pot_bb=10.0, stack_bb=80.0,
                         community_len=3, is_oop=True)
    # OOP should bet <= IP sizing
    assert p_oop.current.size_pct <= p_ip.current.size_pct + 0.05, \
        f'OOP {p_oop.current.size_pct:.2f} should be <= IP {p_ip.current.size_pct:.2f}'
    print(f'OOP cap: {p_oop.current.size_pct:.0%} vs IP {p_ip.current.size_pct:.0%}')


def test_fish_sizing_bigger():
    p_reg = plan_streets(equity=0.68, pot_bb=10.0, stack_bb=80.0,
                         community_len=3, villain_vpip=0.25)
    p_fish = plan_streets(equity=0.68, pot_bb=10.0, stack_bb=80.0,
                          community_len=3, villain_vpip=0.50)
    assert p_fish.current.size_pct >= p_reg.current.size_pct, \
        f'vs fish {p_fish.current.size_pct:.2f} should be >= vs reg {p_reg.current.size_pct:.2f}'
    print(f'vs fish: {p_fish.current.size_pct:.0%}  vs reg: {p_reg.current.size_pct:.0%}')


def test_turn_plan():
    p = plan_streets(equity=0.70, pot_bb=15.0, stack_bb=60.0, community_len=4)
    assert p.streets_left == 2
    assert p.current.action in ('BET', 'ALL_IN')
    print(f'Turn plan: {street_plan_summary(p)}')


def test_river_plan():
    p = plan_streets(equity=0.72, pot_bb=20.0, stack_bb=40.0, community_len=5)
    assert p.streets_left == 1
    print(f'River plan: {street_plan_summary(p)}')


def test_summary_format():
    p = plan_streets(equity=0.68, pot_bb=10.0, stack_bb=80.0, community_len=3)
    s = street_plan_summary(p)
    assert '[三街]' in s
    assert len(s) <= 90
    print(f'Summary length OK: {len(s)} chars  "{s}"')


if __name__ == '__main__':
    tests = [
        test_category_mapping,
        test_nuts_flop_geometric,
        test_nuts_shove_low_spr,
        test_strong_three_streets,
        test_tpgk_pot_control,
        test_draw_semibluff,
        test_weak_check_fold,
        test_oop_size_capped,
        test_fish_sizing_bigger,
        test_turn_plan,
        test_river_plan,
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
