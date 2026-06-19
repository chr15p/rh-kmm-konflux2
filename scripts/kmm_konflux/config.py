import yaml

def read_key_value_file(filename:str ="config.conf"):
    data = {}
    with open(filename, "r") as file:
        for line in file:
            line = line.strip()
            if line and "=" in line:
                key, value = line.split("=", 1)
                data[key.strip()] = value.strip()
    return data


def load_config_dict(path: str):
    with open(path, "r", encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f) or {}
        except yaml.YAMLError as exc:
            raise ValueError(f"invalid yaml {path}: {exc}")
    if not isinstance(data, dict):
        raise ValueError(f"invalid config {path} root must be a mapping/object")
    return data


