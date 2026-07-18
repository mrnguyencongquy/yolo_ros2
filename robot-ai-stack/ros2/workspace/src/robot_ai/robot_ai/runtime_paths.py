import re
from pathlib import PurePath


def model_identifier(model_path: str) -> str:
    """Build a stable, safe identifier from a configured model filename.

    The identifier is used both as an /output subdirectory and inside a ROS 2
    topic name; ROS topics only allow alphanumerics and '_', so '-' and '.'
    must be replaced too.
    """
    stem = PurePath(model_path).stem
    safe_stem = re.sub(r"[^A-Za-z0-9_]", "_", stem)
    safe_stem = re.sub(r"_+", "_", safe_stem).strip("_")
    if not safe_stem:
        raise ValueError("model path must include a usable filename")
    return safe_stem


def model_output_dir(model_path: str, output_root: str = "/output") -> str:
    """Build a stable, safe output directory from a configured model filename."""
    return str(PurePath(output_root) / model_identifier(model_path))


def model_output_topic(model_path: str) -> str:
    """Build an isolated ROS output topic from a configured model filename."""
    return f"/models/{model_identifier(model_path)}/detected_instances"
