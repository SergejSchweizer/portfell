"""Deterministic expanding-window walk-forward split generation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WalkForwardSplit:
    split_id: str
    training_dates: tuple[str, ...]
    test_dates: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.training_dates or not self.test_dates:
            raise ValueError("walk-forward split requires non-empty train and test ranges")
        if self.training_dates[-1] >= self.test_dates[0]:
            raise ValueError("training range must precede test range")


def expanding_splits(
    dates: tuple[str, ...],
    *,
    split_count: int = 5,
    minimum_training_observations: int = 60,
) -> tuple[WalkForwardSplit, ...]:
    """Create up to split_count stable chronological expanding-window splits."""

    ordered = tuple(sorted(set(dates)))
    if split_count < 1 or minimum_training_observations < 2:
        raise ValueError("invalid walk-forward settings")
    remaining = len(ordered) - minimum_training_observations
    if remaining < split_count:
        raise ValueError("insufficient observations for requested walk-forward splits")
    test_size = max(1, remaining // split_count)
    splits: list[WalkForwardSplit] = []
    for index in range(split_count):
        train_end = minimum_training_observations + index * test_size
        test_end = len(ordered) if index == split_count - 1 else min(len(ordered), train_end + test_size)
        training = ordered[:train_end]
        test = ordered[train_end:test_end]
        if not test:
            break
        splits.append(WalkForwardSplit(f"wf-{index + 1:02d}", training, test))
    if len(splits) != split_count:
        raise ValueError("unable to build exact requested walk-forward split count")
    return tuple(splits)
