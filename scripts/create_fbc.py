#!/usr/bin/python3

import sys
import os
import os.path
import argparse
import json
import kmm_konflux.json_config
from kmm_konflux.konflux_api import Konflux, resolve_tls_verify

#def load_config_json(config_file):
#    with open(config_file) as f:
#        d = json.load(f)
#    return d


def get_shas(path, bundle_config, prod, stage):
    file_base = bundle_config['sha_file']
    package = bundle_config['package']

    bundles = {}
    for i in os.listdir(path):
        if i[:8]=="release-":
            for j in os.listdir(i):
                for extension in ['yaml', 'yml', 'yaml.released']:
                    if os.path.isfile(f"{i}/{j}/{file_base}.{extension}"):
                        pullspec_file=f"{i}/{j}/{file_base}.{extension}"
                        break 
                else:
                    continue

                version = j.split("-")[-1]
                if version in prod:
                    repo = bundle_config["repo"]
                elif stage and version in stage:
                    repo = bundle_config["stage"]
                else:
                    continue

                with open(pullspec_file) as fh:
                    sha = fh.read().strip().split("@")[-1]

                bundles[version] = {
                    "schema": "olm.bundle",
                    "name": f"{package}-operator-bundle.v{version}",
                    "image": f"{repo}@{sha}"
                }

    return bundles



def create_fbc_structure(bundle_shas, package):
    versions = list(bundle_shas.keys())

    versions.sort(key=lambda s: list(map(int, s.split('.'))))

    channels={}

    for i in versions:
        xy_version = ".".join(i.split(".")[0:2])
        #print(xy_version)
        channels[xy_version] = {
            "entries": [],  
            "name": f"release-{xy_version}",
            "package": package,
            "schema": "olm.channel"
        }

    stable=[]
    for i in range(0,len(versions)):
        xy_version = ".".join(versions[i].split(".")[0:2])
        entry={}
        entry["name"] = f"{package}.v{versions[i]}"
        if i> 0:
            entry['replaces'] = f"{package}.v{versions[i-1]}"
        entry["skipRange"] = f">=0.0.0 <{versions[i]}"


        for k in channels.keys():
            #print(k, xy_version)
            if float(k) >= float(xy_version):
                #print(f"channel={k}, {v[i]}  added f{entry}")
                channels[k]["entries"].append(entry)

        stable.append(entry)

    channels["stable"] = {
                "entries": stable,  
                "name": "stable",
                "package": package,
                "schema": "olm.channel"
                }

    fbc =  {"schema": "olm.template.basic",
            "entries": [
                {
                    "defaultChannel": "stable",
                    "icon": {
                        "base64data": "PHN2ZyBpZD0iTGF5ZXJfMSIgZGF0YS1uYW1lPSJMYXllciAxIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxOTIgMTQ1Ij48ZGVmcz48c3R5bGU+LmNscy0xe2ZpbGw6I2UwMDt9PC9zdHlsZT48L2RlZnM+PHRpdGxlPlJlZEhhdC1Mb2dvLUhhdC1Db2xvcjwvdGl0bGU+PHBhdGggZD0iTTE1Ny43Nyw2Mi42MWExNCwxNCwwLDAsMSwuMzEsMy40MmMwLDE0Ljg4LTE4LjEsMTcuNDYtMzAuNjEsMTcuNDZDNzguODMsODMuNDksNDIuNTMsNTMuMjYsNDIuNTMsNDRhNi40Myw2LjQzLDAsMCwxLC4yMi0xLjk0bC0zLjY2LDkuMDZhMTguNDUsMTguNDUsMCwwLDAtMS41MSw3LjMzYzAsMTguMTEsNDEsNDUuNDgsODcuNzQsNDUuNDgsMjAuNjksMCwzNi40My03Ljc2LDM2LjQzLTIxLjc3LDAtMS4wOCwwLTEuOTQtMS43My0xMC4xM1oiLz48cGF0aCBjbGFzcz0iY2xzLTEiIGQ9Ik0xMjcuNDcsODMuNDljMTIuNTEsMCwzMC42MS0yLjU4LDMwLjYxLTE3LjQ2YTE0LDE0LDAsMCwwLS4zMS0zLjQybC03LjQ1LTMyLjM2Yy0xLjcyLTcuMTItMy4yMy0xMC4zNS0xNS43My0xNi42QzEyNC44OSw4LjY5LDEwMy43Ni41LDk3LjUxLjUsOTEuNjkuNSw5MCw4LDgzLjA2LDhjLTYuNjgsMC0xMS42NC01LjYtMTcuODktNS42LTYsMC05LjkxLDQuMDktMTIuOTMsMTIuNSwwLDAtOC40MSwyMy43Mi05LjQ5LDI3LjE2QTYuNDMsNi40MywwLDAsMCw0Mi41Myw0NGMwLDkuMjIsMzYuMywzOS40NSw4NC45NCwzOS40NU0xNjAsNzIuMDdjMS43Myw4LjE5LDEuNzMsOS4wNSwxLjczLDEwLjEzLDAsMTQtMTUuNzQsMjEuNzctMzYuNDMsMjEuNzdDNzguNTQsMTA0LDM3LjU4LDc2LjYsMzcuNTgsNTguNDlhMTguNDUsMTguNDUsMCwwLDEsMS41MS03LjMzQzIyLjI3LDUyLC41LDU1LC41LDc0LjIyYzAsMzEuNDgsNzQuNTksNzAuMjgsMTMzLjY1LDcwLjI4LDQ1LjI4LDAsNTYuNy0yMC40OCw1Ni43LTM2LjY1LDAtMTIuNzItMTEtMjcuMTYtMzAuODMtMzUuNzgiLz48L3N2Zz4=",
                        "mediatype": "image/svg+xml"
                    },
                    "name": package,
                    "schema": "olm.package"
                },
            ]
        }

    fbc["entries"]+= list(channels.values())

    ## print the bundles in ascending order
    for i in versions:
        fbc["entries"].append(bundle_shas[i])

    return fbc


def get_shas_from_release(token: str, config: dict, to_build: dict, release_name: str):

    verify = resolve_tls_verify(config)

    kube_releases = Konflux(config['api_url'],
                        token,
                        config['namespace'],
                        "appstudio.redhat.com/v1alpha1",
                        "releases",
                        verify)

    kube_snapshots = Konflux(config['api_url'],
                        token,
                        config['namespace'],
                        "appstudio.redhat.com/v1alpha1",
                        "snapshots",
                        verify)

    release = kube_releases.get(release_name)

    snapshot_name = release[0]["spec"]["snapshot"]
    snapshot = kube_snapshots.get(snapshot_name)
    app = snapshot[0]["metadata"]["labels"]["kmm"]
    components = [f"{k['sha_file']}-{app}" for k in to_build]    

    images = {}
    for i in  snapshot[0]['spec']['components']:
        if i['name'] in components:
            print(f"{i['name']}  {i['containerImage']}")

    return



if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', action='store', required=False, default="config/pullspec_config.json", help='json config file (default: pullspec_config.json) ')
    #parser.add_argument('-e', '--env', action='store', required=False, default="prod", help='use different set of defaults releases (default: prod)')
    parser.add_argument('-x', '--extra', action='store', required=False, default=False, help='comma seperated list of staging versions to add to fbc')
    parser.add_argument('-d', '--outdir', action='store', required=False, default="fbc/", help='directory to write to (default: fbc/)')
    parser.add_argument('-s', '--stdout', '--test', action='store_true', required=False, default=False, help='print to stdout')
    parser.add_argument('-i', '--indir', action='store', required=False, default=".", help='directory to read versions from (default: ".")')
    parser.add_argument('-t', '--token', action='store', required=False, default=None, help='token to access k8s')
    parser.add_argument('--release', action='store', required=False, default=None, help='name of release to build for')
    parser.add_argument('--op', action='store_true', required=False, default=None, help='build fbc for operator')
    parser.add_argument('--hub', action='store_true', required=False, default=None, help='build fbc for hub-operator')

    opt = parser.parse_args()

    #env = opt.env
    if not opt.op and not opt.hub:
        opt.op = True
        opt.hub = True

    release_name = opt.release
    token = opt.token

    try:
        #config = kmm_konflux.config.load_config_dict(opt.config)
        config = kmm_konflux.json_config.load_config_json(opt.config)
    except ValueError as e:
        print(f"Failed to load config: {e}", file=sys.stderr)
        sys.exit(2)

    prod_versions = config.get("prod", [])
    stage_versions = config.get("stage", [])
    if opt.extra:
        stage_versions += opt.extra.split(",")
    #else:
    #    stage_versions = []


    to_build = []
    if opt.op:
        to_build.append({
            "package": "kernel-module-management",
            "sha_file": "operator-bundle",
            "out_basename": "op-catalog-template.json",
            "repo": config["operator-bundle"]["repo"],
            "stage": config["operator-bundle"]["stage"],
        })
    if opt.hub:
        to_build.append({
            "package": "kernel-module-management-hub",
            "sha_file": "hub-operator-bundle",
            "out_basename": "hub-catalog-template.json",
            "repo": config["hub-operator-bundle"]["repo"],
            "stage": config["hub-operator-bundle"]["stage"],
        })

    if release_name:
        get_shas_from_release(token, config, to_build, release_name)
        #print()

    for i in to_build:
        #bundle_shas = get_shas(opt.indir, i["sha_file"], i["package"], versions)
        bundle_shas = get_shas(opt.indir, i, prod_versions, stage_versions)
        fbc = create_fbc_structure(bundle_shas, i["package"])

        if opt.stdout:
            print(json.dumps(fbc, indent=4))
        else:
            OUTFILE = f"{opt.outdir}/{i['out_basename']}"
            print(f"writing to {OUTFILE}")
            with open(OUTFILE, 'w') as file:
                json.dump(fbc, file, indent=4)
