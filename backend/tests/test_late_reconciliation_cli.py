from app.cli.sync_market_spot import LATE_MARKET_SPOT_DATASETS, selected_datasets


def test_market_spot_dataset_selection_is_bounded_to_late_inputs() -> None:
    selected = selected_datasets(set(LATE_MARKET_SPOT_DATASETS))

    assert set(selected) == LATE_MARKET_SPOT_DATASETS
    assert "MARKET_BREADTH" not in selected
    assert "SECURITY_INSTITUTIONAL" not in selected
