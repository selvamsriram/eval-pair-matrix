"""Step registry. Each step is a class with a `name` and a `run_record` method.

To add a new step:
  1. Subclass Step in a new module.
  2. Append the name to STEP_ORDER in perturb.run.
  3. Register the class here.
"""
from __future__ import annotations

from .base import Step, StepContext  # re-exported
from .filter_step import FilterStep
from .perturb_step import PerturbStep
from .validate_step import ValidateStep

STEPS: dict[str, type[Step]] = {
    "filter": FilterStep,
    "perturb": PerturbStep,
    "validate": ValidateStep,
}


def get(name: str) -> type[Step]:
    if name not in STEPS:
        raise KeyError(f"Unknown step '{name}'. Available: {sorted(STEPS)}")
    return STEPS[name]


__all__ = ["Step", "StepContext", "STEPS", "get"]
