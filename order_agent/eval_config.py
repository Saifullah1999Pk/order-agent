"""Swap a scenario's persona and judge LLM configs for another pair of YAML files."""

import dataclasses
from pathlib import Path

import yaml


def _load(path: str | Path) -> dict:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a YAML mapping")
    return data


def apply_eval_configs(scenario, simulator_path: str | Path | None, judge_path: str | Path | None):
    """The scenario with its persona (`simulator`) and/or judge replaced from the given files.

    A simulator file is the persona's LLM block (like evals/simulator.yaml). A judge file has an
    `eval:` block (like evals/judge.yaml); only that block is used by this Pipecat version.
    None keeps what the scenario already has.
    """
    changes = {}
    if simulator_path:
        changes["simulator"] = _load(simulator_path)
    if judge_path:
        data = _load(judge_path)
        if not isinstance(data.get("eval"), dict):
            raise ValueError(f"{judge_path}: needs an 'eval:' mapping")
        changes["judge"] = data["eval"]
    return dataclasses.replace(scenario, **changes) if changes else scenario
