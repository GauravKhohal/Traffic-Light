"""Train a DQN agent to control intersection B1 in SUMO (Phase 5).

Modest CPU training budget — the goal is a working RL pipeline and an honest
fixed vs rule-based vs RL comparison, not a maximally-tuned agent (published
work reaches 20-40% wait reduction with far longer training).

Run from anywhere with the project venv active:
    python simulation/rl/train.py --scenario asymmetric --timesteps 30000
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from stable_baselines3 import DQN
from stable_baselines3.common.monitor import Monitor

from simulation.rl.sumo_env import SumoIntersectionEnv

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(HERE, "models")


def train(scenario, timesteps, seed, episode_seconds):
    os.makedirs(MODELS_DIR, exist_ok=True)
    env = Monitor(
        SumoIntersectionEnv(scenario=scenario, episode_seconds=episode_seconds, seed=seed)
    )

    model = DQN(
        "MlpPolicy",
        env,
        learning_rate=1e-3,
        buffer_size=50_000,
        learning_starts=1_000,
        batch_size=64,
        gamma=0.99,
        train_freq=4,
        target_update_interval=500,
        exploration_fraction=0.3,
        exploration_final_eps=0.05,
        policy_kwargs={"net_arch": [64, 64]},
        seed=seed,
        verbose=1,
    )
    model.learn(total_timesteps=timesteps, progress_bar=False)

    path = os.path.join(MODELS_DIR, f"dqn_{scenario}.zip")
    model.save(path)
    env.close()
    print(f"Saved model -> {path}")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", default="asymmetric")
    parser.add_argument("--timesteps", type=int, default=30_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--episode-seconds", type=int, default=1200)
    args = parser.parse_args()
    train(args.scenario, args.timesteps, args.seed, args.episode_seconds)
