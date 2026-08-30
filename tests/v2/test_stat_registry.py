from ullebets_v1.registry.stats import get_stat_definition


def test_goal_kicks_and_throw_ins_are_settlement_supported_non_model_stats() -> None:
    for stat_key in ("goalKicks", "throwIns"):
        definition = get_stat_definition(stat_key)
        assert definition is not None
        assert definition.settlement_supported is True
        assert definition.modeled_in_v1 is False
