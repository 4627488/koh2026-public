import tempfile
from pathlib import Path

import numpy as np
import torch
from safetensors.torch import save_file

from koh.game.koh_env import OBSERVATION_DIM, TEAM_ACTION_COUNT
from koh.ml.model import DQN
from koh.ml.policies import WeightPolicy


def _make_weight_file(path: Path) -> None:
    model = DQN(OBSERVATION_DIM, TEAM_ACTION_COUNT)
    tensors = {k: v.contiguous() for k, v in model.state_dict().items()}
    save_file(tensors, str(path))


def test_dqn_output_shape():
    model = DQN(OBSERVATION_DIM, TEAM_ACTION_COUNT)
    x = torch.zeros(1, OBSERVATION_DIM)
    out = model(x)
    assert out.shape == (1, TEAM_ACTION_COUNT)


def test_weight_policy_returns_two_actions():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "weights.safetensors"
        _make_weight_file(path)
        policy = WeightPolicy(path)
        obs = np.zeros(OBSERVATION_DIM, dtype=np.float32)
        a1, a2 = policy.choose_action(obs)
        assert 0 <= a1 < 9
        assert 0 <= a2 < 9


def test_weight_policy_validate_good():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "weights.safetensors"
        _make_weight_file(path)
        valid, msg = WeightPolicy.validate_submission(path)
        assert valid, msg


def test_weight_policy_validate_bad():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "bad.safetensors"
        bad_model = DQN(13, 5)
        tensors = {k: v.contiguous() for k, v in bad_model.state_dict().items()}
        save_file(tensors, str(path))
        valid, _ = WeightPolicy.validate_submission(path)
        assert not valid

