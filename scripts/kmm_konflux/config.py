#import yaml
import json

def read_key_value_file(filename:str ="config.conf"):
    data = {}
    with open(filename, "r") as file:
        for line in file:
            line = line.strip()
            if line and "=" in line:
                key, value = line.split("=", 1)
                data[key.strip()] = value.strip()
    return data


def load_config_dict(path: str="config/pullspec_config.json"):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"invalid config {path} root must be a mapping/object")
    return data




