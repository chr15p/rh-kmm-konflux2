import yaml

def load_config_dict(path: str):
    with open(path, "r", encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f) or {}
        except yaml.YAMLError as exc:
            raise ValueError(f"invalid yaml {path}: {exc}")
    if not isinstance(data, dict):
        raise ValueError(f"invalid config {path} root must be a mapping/object")
    return data


