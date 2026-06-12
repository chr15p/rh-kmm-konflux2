import os

def get_version_mappings(path=".", dirsep=".", subdirsep="."):
    all_versions = {}
    for directory in os.listdir(path):
        if directory[:8] == "release-":
            version = directory[8:].replace(".",dirsep)
            all_versions.setdefault(version, [])

            for subdir in os.listdir(f"{path}/{directory}"):
                if subdir[:8] == "release-":
                    all_versions[version].append(subdir[8:].replace(".",subdirsep))

    return all_versions


def get_versions_list(path="."):
    versions = [j for i in get_version_mappings().values() for j in i]
    versions.sort(key=lambda s: tuple(map(int, s.split('.'))))
    #versions.sort(key=StrictVersion)
    return versions

def get_next_version(curr_version: str, path:str=".") -> str:
    versions = get_versions_list(path)
    i = versions.index(curr_version)
    try:
        return versions[i+1]
    except IndexError:
        return versions[i]

def get_prev_version(curr_version: str, path:str=".") -> str:
    versions = get_versions_list(path)
    i = versions.index(curr_version)
    if i == 0:
        return versions[i]
    return versions[i-1]

def increment_version(version):
    xyz = version.split(".")
    xyz[-1]+=1
    return ".".join(xyz)
    #return f"{xyz[0]}.{xyz[1]}.{xyz[2]+1}"

if __name__ == "__main__":
    print(get_version_mappings())
    print(get_versions_list())
    print(get_next_version("2.5.1"))
    print(get_next_version("2.6.0"))
    print(get_prev_version("2.5.1"))
    #print(get_prev_version("2.0.0"))
