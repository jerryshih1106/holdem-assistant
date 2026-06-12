"""Tests for poker/overbet_response.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.overbet_response import (
    respond_to_overbet, overbet_response_one_liner, OverbetResponse
)


def _resp(**kw):
    defaults = dict(
        hero_hand_class='top_pair', hero_equity=0.55,
        hero_has_blocker=True, villain_bet_pct=1.50,
        pot_bb=20.0, eff_stack_bb=80.0,
        street='river', villain_af=2.0, villain_wtsd=0.30,
    )
    defaults.update(kw)
    return respond_to_overbet(**defaults)


def test_returns_overbet_response():
    r = _resp()
    assert isinstance(r, OverbetResponse)
    print(f'type: {type(r).__name__}')


def test_required_fields():
    r = _resp()
    fields = [
        'villain_bet_pct', 'villain_bet_bb', 'pot_bb', 'eff_stack_bb', 'street',
        'alpha', 'mdf', 'villain_bluff_freq', 'required_equity',
        'hero_hand_class', 'hero_equity', 'hero_has_blocker',
        'action', 'ev', 'raise_to_bb', 'action_reasoning',
        'key_concepts', 'range_notes',
    ]
    for f in fields:
        assert hasattr(r, f), f'Missing: {f}'
    print(f'All {len(fields)} fields present')


def test_alpha_formula():
    """alpha = bet / (pot + bet); 150%pot bet => alpha = 1.5/2.5 = 0.60"""
    r = _resp(villain_bet_pct=1.50)
    assert abs(r.alpha - 0.60) < 0.01, f'Alpha should be 0.60: {r.alpha}'
    print(f'Alpha 150%pot: {r.alpha:.3f}')


def test_mdf_plus_alpha_equals_1():
    r = _resp(villain_bet_pct=1.50)
    assert abs(r.alpha + r.mdf - 1.0) < 0.001
    print(f'alpha={r.alpha:.2f} + mdf={r.mdf:.2f} = {r.alpha + r.mdf:.3f}')


def test_100pct_pot_alpha():
    """100%pot bet => alpha = 0.50"""
    r = _resp(villain_bet_pct=1.0)
    assert abs(r.alpha - 0.50) < 0.01
    print(f'Alpha 100%pot: {r.alpha:.3f}')


def test_valid_actions():
    valid = {'fold', 'call', 'raise'}
    for hand, eq in [('air', 0.10), ('top_pair', 0.55),
                     ('two_pair', 0.72), ('flush', 0.92)]:
        r = _resp(hero_hand_class=hand, hero_equity=eq)
        assert r.action in valid, f'Invalid action {r.action} for {hand}'
    print('All actions valid')


def test_nutted_hand_raises():
    """Straight/flush/full_house should raise vs overbet."""
    for hand, eq in [('straight', 0.92), ('flush', 0.95), ('full_house', 0.97)]:
        r = _resp(hero_hand_class=hand, hero_equity=eq, villain_bet_pct=1.5)
        assert r.action == 'raise', f'{hand} should raise: {r.action}'
    print('Nutted hands raise vs overbet')


def test_air_folds():
    """Air should fold to overbet."""
    r = _resp(hero_hand_class='air', hero_equity=0.10, villain_bet_pct=1.5)
    assert r.action == 'fold', f'Air should fold: {r.action}'
    print(f'Air action: {r.action}')


def test_medium_strength_folds_to_large_overbet():
    """Middle pair folds to 200%pot overbet."""
    r = _resp(hero_hand_class='middle_pair', hero_equity=0.38,
              villain_bet_pct=2.0, hero_has_blocker=False)
    assert r.action == 'fold', f'Middle pair should fold to 200%: {r.action}'
    print(f'Middle pair vs 200%: {r.action}')


def test_blocker_helps_marginal_call():
    """With blocker, marginal hand can call; without it, should fold."""
    r_block = _resp(hero_hand_class='top_pair', hero_equity=0.58,
                    hero_has_blocker=True, villain_bet_pct=1.5)
    r_no_block = _resp(hero_hand_class='top_pair', hero_equity=0.58,
                       hero_has_blocker=False, villain_bet_pct=1.5)
    # Blocker version should be at least as willing to call
    action_rank = {'fold': 0, 'call': 1, 'raise': 2}
    assert action_rank[r_block.action] >= action_rank[r_no_block.action], (
        f'Blocker should not fold when no-blocker calls: {r_block.action} vs {r_no_block.action}'
    )
    print(f'Block={r_block.action} no_block={r_no_block.action}')


def test_raise_to_bb_set_when_raising():
    r = _resp(hero_hand_class='straight', hero_equity=0.93, villain_bet_pct=1.5)
    assert r.action == 'raise'
    assert r.raise_to_bb > 0, f'raise_to_bb should be > 0: {r.raise_to_bb}'
    print(f'Raise to: {r.raise_to_bb:.0f}BB')


def test_raise_to_bb_zero_when_not_raising():
    r = _resp(hero_hand_class='middle_pair', hero_equity=0.38)
    assert r.action != 'raise'
    assert r.raise_to_bb == 0.0
    print(f'No raise: raise_to_bb={r.raise_to_bb}')


def test_villain_bluff_freq_reasonable():
    r = _resp()
    assert 0.0 < r.villain_bluff_freq < 1.0
    print(f'Villain bluff freq: {r.villain_bluff_freq:.0%}')


def test_aggressive_villain_bluffs_more():
    """High AF villain overbets with more bluffs."""
    r_passive = _resp(villain_af=0.8, villain_wtsd=0.40)
    r_aggro   = _resp(villain_af=3.5, villain_wtsd=0.25)
    assert r_aggro.villain_bluff_freq >= r_passive.villain_bluff_freq, (
        f'Aggro villain bluffs more: {r_aggro.villain_bluff_freq} >= {r_passive.villain_bluff_freq}'
    )
    print(f'Bluff freq: passive={r_passive.villain_bluff_freq:.0%} aggro={r_aggro.villain_bluff_freq:.0%}')


def test_larger_overbet_means_higher_alpha():
    """Bigger overbet = more folds needed = higher alpha."""
    r_small = _resp(villain_bet_pct=1.0)
    r_large = _resp(villain_bet_pct=2.0)
    assert r_large.alpha > r_small.alpha, (
        f'Larger overbet has higher alpha: {r_large.alpha} > {r_small.alpha}'
    )
    print(f'Alpha: 100%={r_small.alpha:.2f} 200%={r_large.alpha:.2f}')


def test_key_concepts_not_empty():
    r = _resp()
    assert isinstance(r.key_concepts, list) and len(r.key_concepts) > 0
    print(f'Key concepts: {len(r.key_concepts)}')


def test_range_notes_not_empty():
    r = _resp()
    assert isinstance(r.range_notes, str) and len(r.range_notes) > 10
    print(f'Range notes: {r.range_notes[:60]}')


def test_two_pair_calls():
    """Two pair should call villain overbet (strong hand)."""
    r = _resp(hero_hand_class='two_pair', hero_equity=0.72, villain_bet_pct=1.5)
    assert r.action in ('call', 'raise'), f'Two pair should not fold: {r.action}'
    print(f'Two pair action: {r.action}')


def test_action_reasoning_not_empty():
    r = _resp()
    assert isinstance(r.action_reasoning, str) and len(r.action_reasoning) > 5
    print(f'Reasoning: {r.action_reasoning[:60]}')


def test_villain_bet_bb():
    """villain_bet_bb should equal villain_bet_pct * pot_bb."""
    r = _resp(villain_bet_pct=1.5, pot_bb=20.0)
    assert abs(r.villain_bet_bb - 30.0) < 0.5, f'Expected 30BB: {r.villain_bet_bb}'
    print(f'Bet BB: {r.villain_bet_bb:.1f}')


def test_one_liner():
    r = _resp()
    line = overbet_response_one_liner(r)
    assert isinstance(line, str) and len(line) > 10
    assert 'MDF' in line
    print(f'one_liner: {line}')


if __name__ == '__main__':
    tests = [
        test_returns_overbet_response, test_required_fields,
        test_alpha_formula, test_mdf_plus_alpha_equals_1,
        test_100pct_pot_alpha, test_valid_actions,
        test_nutted_hand_raises, test_air_folds,
        test_medium_strength_folds_to_large_overbet,
        test_blocker_helps_marginal_call,
        test_raise_to_bb_set_when_raising,
        test_raise_to_bb_zero_when_not_raising,
        test_villain_bluff_freq_reasonable,
        test_aggressive_villain_bluffs_more,
        test_larger_overbet_means_higher_alpha,
        test_key_concepts_not_empty, test_range_notes_not_empty,
        test_two_pair_calls, test_action_reasoning_not_empty,
        test_villain_bet_bb, test_one_liner,
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
