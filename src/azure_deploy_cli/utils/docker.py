"""Docker utility functions for image operations."""

import subprocess
from pathlib import Path


def image_exists(full_image_name: str) -> bool:
    """
    Check if a Docker image exists locally.

    Args:
        full_image_name: Full image name including registry, repository, and tag

    Returns:
        True if the image exists locally, False otherwise
    """
    check_image_result = subprocess.run(
        ["docker", "image", "inspect", full_image_name],
        capture_output=True,
        text=True,
    )
    return check_image_result.returncode == 0


def push_image(full_image_name: str) -> None:
    """
    Push a Docker image to the registry.

    Args:
        full_image_name: Full image name including registry, repository, and tag

    Raises:
        RuntimeError: If the docker push command fails
    """
    push_result = subprocess.run(
        ["docker", "push", full_image_name],
        capture_output=True,
        text=True,
    )
    if push_result.returncode != 0:
        raise RuntimeError(f"Docker push failed {push_result.stderr}")


def pull_image(full_image_name: str) -> None:
    """
    Pull a Docker image from the registry.

    Args:
        full_image_name: Full image name including registry, repository, and tag

    Raises:
        RuntimeError: If the docker pull command fails
    """
    pull_result = subprocess.run(
        ["docker", "pull", full_image_name],
        capture_output=True,
        text=True,
    )
    if pull_result.returncode != 0:
        raise RuntimeError(f"Docker pull failed: {pull_result.stderr}")


def tag_image(source_image: str, target_image: str) -> None:
    """
    Tag a Docker image locally.

    Args:
        source_image: Full name of the source image
        target_image: Full name of the target image

    Raises:
        RuntimeError: If the docker tag command fails
    """
    tag_result = subprocess.run(
        ["docker", "tag", source_image, target_image],
        capture_output=True,
        text=True,
    )
    if tag_result.returncode != 0:
        raise RuntimeError(f"Docker tag failed: {tag_result.stderr}")


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
    build_result = subprocess.run(
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
        ],
        capture_output=True,
        text=True,
    )
    if build_result.returncode != 0:
        raise RuntimeError(f"Docker build and push failed: {build_result.stderr}")
