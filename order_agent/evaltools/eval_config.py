"""Swap a scenario's persona and judge LLM configs for another pair of YAML files."""

import dataclasses
from pathlib import Path

import yaml


def _load(path: str | Path) -> dict:
    p = Path(path)
    if not p.is_file():
        raise ValueError(f"{path}: file not found")
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: not valid YAML ({exc})") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a YAML mapping")
    return data


def load_simulator_config(path: str | Path) -> dict:
    """A persona LLM config file (like evals/simulator.yaml)."""
    return _load(path)


def load_judge_config(path: str | Path) -> dict:
    """The `eval:` block of a judge config file (like evals/judge.yaml)."""
    data = _load(path)
    if not isinstance(data.get("eval"), dict):
        raise ValueError(f"{path}: needs an 'eval:' mapping")
    return data["eval"]


def apply_eval_configs(scenario, simulator_path: str | Path | None, judge_path: str | Path | None):
    """The scenario with its persona (`simulator`) and/or judge replaced from the given files.

    A simulator file is the persona's LLM block (like evals/simulator.yaml). A judge file has an
    `eval:` block (like evals/judge.yaml); only that block is used by this Pipecat version.
    None keeps what the scenario already has.
    """
    changes = {}
    if simulator_path:
        changes["simulator"] = load_simulator_config(simulator_path)
    if judge_path:
        changes["judge"] = load_judge_config(judge_path)
    return dataclasses.replace(scenario, **changes) if changes else scenario
