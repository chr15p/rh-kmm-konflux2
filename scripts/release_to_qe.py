#!/usr/bin/python

import sys
import json
import argparse
import subprocess
import datetime

import kmm_konflux.config
from kmm_konflux import git_commands
from kmm_konflux.konflux_api import Konflux, resolve_tls_verify

def get_kmm_commit(application, konflux_commit, short=False):
    """
        the konflux repo commit is embedded in the body text of a nudge PR,
        so parse that with a regexp
        then use that to diff the release-2.X/kernel-module-management submodule mount point
        either it returns nothing and we use the current submodule commit
        or it returns a value (meaning the submodule has been updated since this PR was built)
        in which case we parse it out of the diff response.
        this works around an issue where if building multiple versions at the same time the
        konflux commit might change between PRs for the same kmm commit
        (e.g you build 2-6 and 2-7, operator-2-7 fails so you merge the 2-6 operands and
        rebuild operator-2-7, now the konflux commit has changed so operator-2-7 would been seen
         as a differnet build and not combine)
    """
    out=git_commands.call_git(False,
                                "diff",
                                f"{konflux_commit}..HEAD",
                                f"release-{application}/kernel-module-management")
    if out.startswith("fatal:"):
        return None
    if not out:
        out=git_commands.call_git(False,
                                "submodule",
                                "status",
                                f"release-{application}/kernel-module-management")
        kmm_commit = out[1:].split(" ")[0]
    else:
        kmm_commit = out.split(" ")[-1]

    if short:
        return kmm_commit[:7]
    return kmm_commit.strip()


def submodule_version(submodule=None):
    if submodule:
        params=["git", "submodule", "status", submodule]
    else:
        params=["git", "submodule"]

    #p = subprocess.Popen(params, stdout=subprocess.PIPE)
    with subprocess.Popen(params, stdout=subprocess.PIPE) as p:
        cmd_output = p.stdout.read().decode("utf-8")
    try:
        return cmd_output.split(" ")[1][:7]
    except IndexError:
        return "unknown"


def git_rev_parse():
    with open(".git/HEAD","r", encoding="utf-8") as head:
        reffile = head.read().strip().split(" ")[1]
    with open(f".git/{reffile}","r", encoding="utf-8") as ref:
        commit = ref.read().strip()
    return commit


def latest_versions(currconfig: dict) -> dict:
    """
        go though the versions listed in pullspec_config.json and
        return a dict of the latest x.y -> x.y.z version mappings for versions that have
        qe_control_files, e.g "2.5"->"2.5.4", "2.7"->"2.7.2", "2.8"->"2,8,0"
    """
    versions = currconfig["prod"] + config["stage"]
    ver={}
    out = {}
    for i in versions:
        y, z = i.rsplit(".", 1)
        if currconfig.get('qe_control_files') and y in currconfig['qe_control_files'].keys() \
            or not currconfig.get('qe_control_files'):
            if int(z) > ver.get(y,-1):
                ver[y]=int(z)

    for key,val in ver.items():
        out[key] = f"{key}.{val}"

    return out


def get_lastPromotedImages(config_dict, kmm_token):
    verify = resolve_tls_verify(config_dict)
    kube_components = Konflux(config_dict['api_url'],
                        kmm_token,
                        config_dict['namespace'],
                        "appstudio.redhat.com/v1alpha1",
                        "components",
                        verify)

    components = kube_components.get(label_selector={"stage":"fbc"})
    image_shas = {}
    for comp in components:
        try:
            if not output["build_commit"]:
                output["build_commit"] = comp["status"]["lastBuiltCommit"]

            if comp["status"]["lastBuiltCommit"] != output["build_commit"]:
                print(f"{comp["metadata"]["name"]} is out of sync with other builds ",
                        f"{comp["status"]["lastBuiltCommit"]} != {output["build_commit"]}")
                continue

            image_shas[comp["metadata"]["name"]] = comp["status"]["lastPromotedImage"]

        except AttributeError as e:
            print(f"failed to get comp.status.lastBuiltCommit for {comp["metadata"]["name"]}: {e}")
    return image_shas


def get_image_shas(config_dict, kmm_token):
    images = {'kmmhub': {}, 'kmm': {}}
    image_shas = get_lastPromotedImages(config_dict, kmm_token)

    for k,v in image_shas.items():
        if "hub" in k:
            ocp = k.replace("fbc-hub-","ocp")
            images['kmmhub'][ocp]=v
        if "op" in k:
            ocp = k.replace("fbc-op-","ocp")
            images['kmm'][ocp]=v

    return images



if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument('-c', '--config', action='store', required=False,
                        default="config/pullspec_config.json",
                        help='json config file (default: config/pullspec_config.json) ')
    parser.add_argument('-t', '--token', action='store', required=False,
                        default=None,
                        help='token to access k8s')
    parser.add_argument('-g', '--git', default=None, help='git commit for releases')
    parser.add_argument('-a', '--autogit', action='store_true',
                                 default=False, help='calculate git commit for HEAD')
    parser.add_argument('-r', '--release', default=None, help='release number to fetch (e.g. r31)')
    parser.add_argument('--test', '--debug', default=False, action='store_true',
                            help='file to write output to')
    opt = parser.parse_args()

    debug = opt.test
    token = opt.token

    try:
        config = kmm_konflux.config.load_config_dict(opt.config)
    except ValueError as e:
        print(f"Failed to load config: {e}", file=sys.stderr)
        sys.exit(2)

    if not config.get("api_url"):
        print(f"Config file {opt.config} must contain non-empty 'api_url'")
        sys.exit(2)


    supported_versions = latest_versions(config)

    output = {
            "version": None,
            "latest_versions": [],
            "build_commit": None ,
            "kmm_commit": None ,
            "kmm": {}, 
            "kmmhub": {}
            }
    #"date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

    if opt.git:
        output["build_commit"] = opt.git
    elif opt.autogit:
        output["build_commit"] = git_rev_parse()


    output = {**output, **get_image_shas(config, token)}

    for version,z_stream in supported_versions.items():
        output["kmm_commit"] = get_kmm_commit(version, output["build_commit"] , short=False)
        output["version"] = z_stream
        output["latest_versions"] = list(supported_versions.values())
        outputfile = config['qe_control_files'][version]
        if not debug:
            with open(outputfile, 'w', encoding="utf-8") as file:
                json.dump(output, file, indent=4)
        else:
            print(outputfile)
            print(json.dumps(output, indent=4))


    sys.exit(0)
