#!/usr/bin/python

import os
import json
import re
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
    p = subprocess.Popen(params, stdout=subprocess.PIPE)

    output = p.stdout.read().decode("utf-8")
    try:
        return output.split(" ")[1][:7]
    except IndexError:
        return "unknown"

    for key,val in ver.items():
        out[key] = f"{key}.{val}"
    return out


def git_rev_parse():
    with open(".git/HEAD","r") as head:
        reffile = head.read().strip().split(" ")[1]
    with open(f".git/{reffile}","r") as ref:
        commit = ref.read().strip()
    return commit


def latest_versions(currconfig: dict):
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


parser = argparse.ArgumentParser()

#parser.add_argument('-n', '--namespace', default="rh-kmm-tenant", help='namespace to query')
#parser.add_argument('-k', '--kubeconfig', action='store', required=False, help='kubeconfig file ')
#parser.add_argument('-r', '--release', default=None, help='release number to fetch (e.g. r31)')
#parser.add_argument('-d', '--directory', required=True, help='directory containing config filesi (e.g. release-2.5/)')
#parser.add_argument('-g', '--commit', default="HEAD", help='')
#parser.add_argument('-o', '--output', default=None, help='file to write output to')
#opt = parser.parse_args()
parser.add_argument('-c', '--config', action='store', required=False,
                    default="config/pullspec_config.json",
                    help='json config file (default: config/pullspec_config.json) ')
parser.add_argument('-t', '--token', action='store', required=False,
                    default=None,
                    help='token to access k8s')

parser.add_argument('-g', '--git', default=None, help='git commit for releases')
parser.add_argument('-a', '--autogit', action='store_true', default=False, help='calculate git commit for HEAD')
parser.add_argument('-r', '--release', default=None, help='release number to fetch (e.g. r31)')
parser.add_argument('--test', '--debug', default=False, action='store_true',
                        help='file to write output to')
opt = parser.parse_args()


#outputfile = opt.output

#build_settings = kmm_konflux.config.read_key_value_file(f"{opt.directory}/build_settings.conf")
#build_settings = helpers.read_key_value_file(f"{opt.directory}/build_settings.conf")

#version = build_settings["VERSION"].replace(".","-")
#rel = helpers.Release(opt.kubeconfig, opt.namespace, label_selector=f"appstudio.openshift.io/application=kmm-{version}")
#relnum = rel.get_latest_rel()
#relnum = rel.get_latest_rel_number()
#relnum = rel.get_latest_rel()

#kmm = submodule_version(f"{opt.directory}/{build_settings['PRODUCT']}")

#build = build_version(opt.commit)
#build = helpers.get_commit(".", opt.commit)
#build = opt.commit

#output = {"version": build_settings.get("RELEASE", "unknown"), "release": relnum, "build_commit": build[:7], "kmm_commit": kmm,  "kmm": {}, "kmmhub": {}}
#fbc={}

#components = helpers.Component(opt.kubeconfig, opt.namespace, match="spec.application=fbc-*")
#components = helpers.Component(opt.kubeconfig, opt.namespace, label_selector="stage=fbc")
debug = opt.test
token = opt.token

try:
    #config = load_config(opt.config)
    config = kmm_konflux.config.load_config_dict(opt.config)
except ValueError as e:
    print(f"Failed to load config: {e}", file=sys.stderr)
    sys.exit(2)

if not config.get("api_url"):
    print(f"Config file {opt.config} must contain non-empty 'api_url'")
    sys.exit(2)


verify = resolve_tls_verify(config)


kube_components = Konflux(config['api_url'],
                        token,
                        config['namespace'],
                        "appstudio.redhat.com/v1alpha1",
                        "components",
                        verify)


supported_versions = latest_versions(config)

output = {
#        "release": release_list[0]["metadata"]["labels"].get("relnumber", "unknown"),
#        "kmm_commit": release_list[0]["metadata"]["labels"].get("kmmshort","unknown"),
        "version": None,
        "latest_versions": [],
        "build_commit": None ,
        "kmm_commit": None ,
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "kmm": {}, 
        "kmmhub": {}
        }

if opt.git:
    output["build_commit"] = opt.git
elif opt.autogit:
    output["build_commit"] = git_rev_parse()


components = kube_components.get(label_selector={"stage":"fbc"})
image_shas = {}
#for comp in components.items():
#for comp in components:
#    #    print(f"{comp.status.lastBuiltCommit}=={build}")
#    try:
#        if comp.status.lastBuiltCommit == build:
#            image_shas[comp.metadata.name] = comp.status.lastPromotedImage
#    except AttributeError as e:
#        print(f"failed to get comp.status.lastBuiltCommit for {comp.metadata.name}: {e}")
#        #exit(0)
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


for k,v in image_shas.items():
    if "hub" in k:
        ocp = k.replace("fbc-hub-","ocp")
        output['kmmhub'][ocp]=v
    if "op" in k:
        ocp = k.replace("fbc-op-","ocp")
        output['kmm'][ocp]=v

for version,z_stream in supported_versions.items(): #.keys():
    output["kmm_commit"] = get_kmm_commit(version, output["build_commit"] , short=False)
    output["version"] = z_stream
    output["latest_versions"] = list(supported_versions.values())
    outputfile = config['qe_control_files'][version]
    if not debug:
        with open(outputfile, 'w') as file:
            json.dump(output, file, indent=4)
    else:
        print(outputfile)
        print(json.dumps(output, indent=4))

#if outputfile:
#    with open(outputfile, 'w') as file:
#        json.dump(output, file, indent=4)
#else:
#    print(json.dumps(output, indent=4))


exit(0)
