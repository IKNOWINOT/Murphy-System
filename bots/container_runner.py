"""Container-based task execution helper."""
from __future__ import annotations

from dataclasses import dataclass
import subprocess
from subprocess import CompletedProcess
from typing import List


@dataclass
class ContainerTask:
    """Representation of a task to run inside a container."""

    image: str
    command: List[str]
    cpus: float = 1.0
    memory: str = "1g"
    gpus: str | None = None


def run_container(task: ContainerTask) -> CompletedProcess:
    """Run the given task in a Docker container.

    Parameters
    ----------
    task:
        The container task specifying image, command, and resource limits.
    """
    args = [
        "docker",
        "run",
        "--rm",
        "--cpus",
        str(task.cpus),
        "--memory",
        task.memory,
    ]
    if task.gpus:
        args.extend(["--gpus", task.gpus])
    args.extend([task.image, *task.command])
    return subprocess.run(args, capture_output=True, text=True, check=False)
