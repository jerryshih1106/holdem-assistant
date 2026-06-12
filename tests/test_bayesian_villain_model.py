"""Tests for bayesian_villain_model.py"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from poker.bayesian_villain_model import (
    build_villain_model, BayesianVillainResult, bvm_one_liner,
    HAND_CATEGORIES, _uniform_prior, _update_posterior, _get_likelihood,
)


def _bvm(**kw):
    defaults = dict(
        villain_af=2.0,
        villain_vpip=0.30,
        board_texture='dry',
        actions_observed=[],
    )
    defaults.update(kw)
    return build_villain_model(**defaults)


def test_returns_bayesian_villain_result():
    r = _bvm()
    assert isinstance(r, BayesianVillainResult)


def test_prior_sums_to_one():
    prior = _uniform_prior(0.30)
    assert abs(sum(prior.values()) - 1.0) < 0.01


def test_tight_prior_has_more_strong_hands():
    tight = _uniform_prior(0.18)
    loose = _uniform_prior(0.50)
    assert tight.get('overpair', 0) >= loose.get('overpair', 0)


def test_distribution_sums_to_one():
    r = _bvm(actions_observed=['bet'])
    total = sum(r.distribution.values())
    assert abs(total - 1.0) < 0.01


def test_bet_increases_strong_hand_probability():
    r_prior = _bvm()
    r_bet = _bvm(actions_observed=['bet'])
    set_prob_prior = r_prior.distribution.get('set', 0)
    set_prob_bet = r_bet.distribution.get('set', 0)
    assert set_prob_bet >= set_prob_prior


def test_check_increases_draw_probability():
    r_bet = _bvm(actions_observed=['bet'])
    r_check = _bvm(actions_observed=['check'])
    draw_check = r_check.distribution.get('flush_draw', 0)
    draw_bet = r_bet.distribution.get('flush_draw', 0)
    assert draw_check >= draw_bet


def test_raise_concentrates_on_strong_hands():
    r = _bvm(actions_observed=['raise'])
    nuts_prob = r.distribution.get('nuts', 0) + r.distribution.get('set', 0) + r.distribution.get('near_nuts', 0)
    air_prob = r.distribution.get('air', 0)
    assert nuts_prob > air_prob


def test_fold_probability_near_zero_for_nuts():
    likelihood = _get_likelihood('fold', 'nuts', 'dry', 2.0)
    assert likelihood < 0.05


def test_check_likelihood_high_for_air():
    likelihood = _get_likelihood('check', 'air', 'dry', 2.0)
    assert likelihood >= 0.70


def test_multiple_updates_change_distribution():
    r_empty = _bvm(actions_observed=[])
    r_multi = _bvm(actions_observed=['bet', 'bet', 'bet'])
    assert r_empty.distribution != r_multi.distribution


def test_top3_has_3_entries():
    r = _bvm(actions_observed=['bet'])
    assert len(r.top3_categories) == 3


def test_most_likely_category_in_top3():
    r = _bvm(actions_observed=['raise'])
    assert r.most_likely_category in r.top3_categories


def test_most_likely_prob_positive():
    r = _bvm(actions_observed=['bet'])
    assert r.most_likely_prob > 0.0


def test_confidence_level_set():
    r = _bvm(actions_observed=['bet', 'raise'])
    assert r.confidence in ('high', 'medium', 'low', 'prior_only')


def test_no_actions_prior_only():
    r = _bvm()
    assert r.confidence == 'prior_only'


def test_hero_action_advice_populated():
    r = _bvm(actions_observed=['raise'])
    assert len(r.hero_action_advice) > 0


def test_tips_populated():
    r = _bvm(actions_observed=['bet'])
    assert len(r.tips) >= 2


def test_aggressive_villain_more_bluffs():
    r_agg = _bvm(villain_af=3.5, actions_observed=['bet'])
    r_pas = _bvm(villain_af=1.0, actions_observed=['bet'])
    air_agg = r_agg.distribution.get('air', 0)
    air_pas = r_pas.distribution.get('air', 0)
    assert air_agg >= air_pas


def test_one_liner_format():
    r = _bvm(actions_observed=['bet'])
    line = bvm_one_liner(r)
    assert '[BVM' in line
    assert 'top3:' in line


def test_all_hand_categories_covered():
    r = _bvm()
    for cat in ['nuts', 'flush_draw', 'air', 'set', 'top_pair']:
        assert cat in r.distribution


def test_bet_bet_sequence_strong():
    r = _bvm(actions_observed=['bet', 'bet'])
    strong = sum(r.distribution.get(c, 0) for c in ['nuts', 'near_nuts', 'set', 'flush', 'straight', 'full_house'])
    weak = sum(r.distribution.get(c, 0) for c in ['air', 'gutshot'])
    assert strong > weak


def test_monotone_board_increases_flush():
    r_mon = _bvm(board_texture='monotone', actions_observed=['bet'])
    r_dry = _bvm(board_texture='dry', actions_observed=['bet'])
    fd_mon = r_mon.distribution.get('flush_draw', 0) + r_mon.distribution.get('flush', 0)
    fd_dry = r_dry.distribution.get('flush_draw', 0) + r_dry.distribution.get('flush', 0)
    assert fd_mon >= fd_dry


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t()
            print(f'[OK] {t.__name__}')
        except Exception as e:
            print(f'[FAIL] {t.__name__}: {e}')
            failed += 1
    print(f'\n{len(tests)-failed}/{len(tests)} passed')
    sys.exit(failed)
