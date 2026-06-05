import argparse
import asyncio
from importlib import metadata as importlib_metadata
import json
from pathlib import Path
from typing import Any

import numpy as np


class _EntryPointsCompat:
    def __init__(self, entry_points: Any):
        self._entry_points = entry_points

    def get(self, group: str, default: Any = None) -> Any:
        selected = list(self._entry_points.select(group=group))
        if selected:
            return selected
        return [] if default is None else default

    def __getattr__(self, name: str) -> Any:
        return getattr(self._entry_points, name)

    def __iter__(self):
        return iter(self._entry_points)

    def __len__(self) -> int:
        return len(self._entry_points)

    def __getitem__(self, index: int) -> Any:
        return self._entry_points[index]


def patch_entry_points_compat() -> None:
    probe = importlib_metadata.entry_points()
    if hasattr(probe, "get") or not hasattr(probe, "select"):
        return

    original_entry_points = importlib_metadata.entry_points

    def compat_entry_points(*args: Any, **kwargs: Any) -> Any:
        result = original_entry_points(*args, **kwargs)
        if hasattr(result, "get"):
            return result
        return _EntryPointsCompat(result)

    importlib_metadata.entry_points = compat_entry_points


patch_entry_points_compat()

try:
    from stable_baselines3 import PPO
except ImportError as exc:
    raise SystemExit(
        "Missing dependency 'stable-baselines3'. Install it with: pip install stable-baselines3"
    ) from exc

try:
    import websockets
except ImportError as exc:
    raise SystemExit(
        "Missing dependency 'websockets'. Install it with: pip install websockets"
    ) from exc


DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parent / "default_hyper_ppo_aircraft.zip"
)
ACTION_LOW = np.array([-90.0, -180.0], dtype=np.float64)
ACTION_HIGH = np.array([90.0, 180.0], dtype=np.float64)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Serve a trained BLADE PPO aircraft agent over WebSocket."
    )
    parser.add_argument("--model", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--log-actions", action="store_true")
    parser.add_argument("--demo-goal", action="store_true")
    parser.add_argument("--goal-lat", type=float, default=4.5)
    parser.add_argument("--goal-lon", type=float, default=5.5)
    return parser.parse_args()


def validate_observation(data: dict[str, Any]) -> np.ndarray:
    observation = data.get("observation")
    if not isinstance(observation, list) or len(observation) < 2:
        raise ValueError("Expected 'observation' to contain at least latitude and longitude.")

    obs = np.array(observation[:2], dtype=np.float64)
    if obs.shape != (2,) or not np.all(np.isfinite(obs)):
        raise ValueError("Observation latitude and longitude must be finite numeric values.")
    return obs


def predict_response(
    model: PPO,
    data: dict[str, Any],
    demo_goal: tuple[float, float] | None = None,
) -> dict[str, Any]:
    obs = validate_observation(data)

    if demo_goal is None:
        action, _states = model.predict(obs, deterministic=True)
    else:
        action = np.array(demo_goal, dtype=np.float64)

    bounded_action = np.clip(np.array(action, dtype=np.float64), ACTION_LOW, ACTION_HIGH)

    latitude = float(bounded_action[0])
    longitude = float(bounded_action[1])

    return {
        "requestId": data.get("requestId"),
        "aircraftId": data.get("aircraftId"),
        "action": bounded_action.tolist(),
        "destination": {
            "latitude": latitude,
            "longitude": longitude,
        },
    }


async def handle_client(
    websocket: Any,
    model: PPO,
    log_actions: bool,
    demo_goal: tuple[float, float] | None,
) -> None:
    async for message in websocket:
        request_id = None
        try:
            data = json.loads(message)
            request_id = data.get("requestId")
            response = predict_response(model, data, demo_goal)
            if log_actions:
                print(
                    "Agent action "
                    f"mode={'demo-goal' if demo_goal is not None else 'ppo'} "
                    f"aircraft={response.get('aircraftId')} "
                    f"observation={data.get('observation')} "
                    f"action={response.get('action')} "
                    f"destination={response.get('destination')}"
                )
        except Exception as exc:
            print(f"Agent request failed: {exc}")
            response = {
                "requestId": request_id,
                "error": str(exc),
            }
        await websocket.send(json.dumps(response))


async def main() -> None:
    args = parse_args()
    model_path = Path(args.model)
    if not model_path.exists():
        raise SystemExit(f"Model file not found: {model_path}")

    model = PPO.load(str(model_path), device=args.device)
    demo_goal = (args.goal_lat, args.goal_lon) if args.demo_goal else None
    async with websockets.serve(
        lambda websocket: handle_client(
            websocket, model, args.log_actions, demo_goal
        ),
        args.host,
        args.port,
    ):
        print(f"RL agent server listening on ws://{args.host}:{args.port}")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
