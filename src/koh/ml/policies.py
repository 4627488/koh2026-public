from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Tuple

import numpy as np
import torch
from safetensors.torch import load_file as safetensors_load_file

from koh.game.koh_env import (
    ACTION_STAY,
    OBSERVATION_DIM,
    PLAYER_OBS_DIM,
    TEAM_ACTION_COUNT,
)
from koh.ml.model import DQN


class WeightPolicy:
    def __init__(
        self,
        weight_path: str | Path,
        input_dim: int = OBSERVATION_DIM,
        output_dim: int = TEAM_ACTION_COUNT,
    ):
        self.weight_path = str(weight_path)
        self.device = torch.device("cpu")
        self.model = DQN(input_dim, output_dim).to(self.device)
        payload = safetensors_load_file(self.weight_path, device="cpu")
        self.model.load_state_dict(payload)
        self.model.eval()

    def choose_action(self, observation: np.ndarray) -> Tuple[int, int]:
        tensor = torch.as_tensor(
            observation, dtype=torch.float32, device=self.device
        ).unsqueeze(0)
        with torch.no_grad():
            logits = self.model(tensor)[0]  # shape (18,)
        # 死亡角色强制 ACTION_STAY，不依赖模型自行学会忽略
        p1_alive = observation[0] > 0.5
        p2_alive = observation[PLAYER_OBS_DIM] > 0.5
        a1 = int(logits[:9].argmax().item()) if p1_alive else ACTION_STAY
        a2 = int(logits[9:].argmax().item()) if p2_alive else ACTION_STAY
        return a1, a2

    @classmethod
    def validate_submission(
        cls,
        weight_path: str | Path,
        input_dim: int = OBSERVATION_DIM,
        output_dim: int = TEAM_ACTION_COUNT,
    ) -> tuple[bool, str]:
        try:
            cls(weight_path=weight_path, input_dim=input_dim, output_dim=output_dim)
        except Exception as error:
            return False, str(error)
        return True, "ok"


@lru_cache(maxsize=256)
def load_weight_policy(
    weight_path: str | Path,
    input_dim: int = OBSERVATION_DIM,
    output_dim: int = TEAM_ACTION_COUNT,
) -> WeightPolicy:
    return WeightPolicy(weight_path, input_dim=input_dim, output_dim=output_dim)


__all__ = [
    "WeightPolicy",
    "load_weight_policy",
]
