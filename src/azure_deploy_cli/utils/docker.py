"""Docker utility functions for image operations."""

import subprocess
from pathlib import Path

from .logging import get_logger

logger = get_logger(__name__)


def _run_and_stream(cmd: list[str], show_output: bool = True) -> int:
    """Run a command and stream output to stderr in real-time.

    Args:
        cmd: Command and arguments to run
        show_output: Whether to display output to stderr

    Returns:
        The return code of the process
    """
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if process.stdout is not None:
        for line in iter(process.stdout.readline, ""):
            if line and show_output:
                logger.info(line.rstrip("\n"))
        process.stdout.close()
    return process.wait()


def image_exists(full_image_name: str) -> bool:
    """
    Check if a Docker image exists locally.

    Args:
        full_image_name: Full image name including registry, repository, and tag

    Returns:
        True if the image exists locally, False otherwise
    """
    returncode = _run_and_stream(["docker", "image", "inspect", full_image_name], show_output=False)
    return returncode == 0


def push_image(full_image_name: str) -> None:
    """
    Push a Docker image to the registry.

    Args:
        full_image_name: Full image name including registry, repository, and tag

    Raises:
        RuntimeError: If the docker push command fails
    """
    returncode = _run_and_stream(["docker", "push", full_image_name])
    if returncode != 0:
        raise RuntimeError("Docker push failed")


def pull_image(full_image_name: str) -> None:
    """
    Pull a Docker image from the registry.

    Args:
        full_image_name: Full image name including registry, repository, and tag

    Raises:
        RuntimeError: If the docker pull command fails
    """
    returncode = _run_and_stream(["docker", "pull", full_image_name])
    if returncode != 0:
        raise RuntimeError("Docker pull failed")


def tag_image(source_image: str, target_image: str) -> None:
    """
    Tag a Docker image locally.

    Args:
        source_image: Full name of the source image
        target_image: Full name of the target image

    Raises:
        RuntimeError: If the docker tag command fails
    """
    returncode = _run_and_stream(["docker", "tag", source_image, target_image])
    if returncode != 0:
        raise RuntimeError("Docker tag failed")


def pull_retag_and_push_image(
    source_full_image_name: str,
    target_full_image_name: str,
) -> None:
    """
    Pull an existing image, retag it, and push to registry.

    Args:
        source_full_image_name: Full name of the source image (registry/image:tag)
        target_full_image_name: Full name of the target image (registry/image:new_tag)

    Raises:
        RuntimeError: If the source image doesn't exist or operations fail
    """
    if not image_exists(source_full_image_name):
        pull_image(source_full_image_name)

    tag_image(source_full_image_name, target_full_image_name)
    push_image(target_full_image_name)


def build_and_push_image(
    dockerfile: str,
    full_image_name: str,
) -> None:
    """
    Build a Docker image using buildx and push to registry.

    Args:
        dockerfile: Path to the Dockerfile
        full_image_name: Full image name including registry, repository, and tag

    Raises:
        RuntimeError: If the docker build and push command fails
    """
    src_folder = str(Path(dockerfile).parent)
    returncode = _run_and_stream(
        [
            "docker",
            "buildx",
            "build",
            "--platform",
            "linux/amd64",
            "-t",
            full_image_name,
            "-f",
            dockerfile,
            src_folder,
            "--push",
        ]
    )
    if returncode != 0:
        raise RuntimeError("Docker build and push failed")
