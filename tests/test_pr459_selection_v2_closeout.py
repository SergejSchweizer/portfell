from pathlib import Path

from portfell.multivariate_candidates import METHODS
from portfell.multivariate_risk_model_comparison import COMPARISON_METHODS
from portfell.multivariate_risk_spec import PRODUCTION_RISK_MODEL_SPECS
from portfell.multivariate_validation import _SCENARIO_NAMES

ROOT = Path(__file__).resolve().parents[1]


def test_selection_v2_frozen_invariants() -> None:
    assert "highest_monthly_return" not in METHODS
    assert len(METHODS) == 6
    assert _SCENARIO_NAMES == ("historical", "seeded_block_bootstrap", "distribution_cut")
    assert len(PRODUCTION_RISK_MODEL_SPECS) == 3
    assert sum(len(specs) for specs in COMPARISON_METHODS.values()) == 14
    assert not (ROOT / "src/portfell/scorecard.py").exists()


def test_selection_action_has_no_hardcoded_return_risk_override() -> None:
    source = (ROOT / "src/portfell/dash_app/callbacks.py").read_text()
    action = source[source.index('elif action == "multivariate-optimize"') :]
    assert 'objective="return_risk"' not in action
