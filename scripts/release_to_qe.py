#!/usr/bin/python

import sys
import json
import argparse
import datetime

import kmm_konflux.config
from kmm_konflux.konflux_api import Konflux, resolve_tls_verify

#def get_release_number(kube_releases, increment:bool = True, labels:dict = {}):
#    release_list = kube_releases.get(label_selector=labels)
#    if len(release_list)==1 and release_list[0].get('items', []) == []:
#        return 1
#    rel_regexp = r"-r([0-9]+)$"
#    last_release=0
#    for rel in release_list:
#        print(rel['metadata']['name'])
#        matches = re.search(rel_regexp, rel['metadata']['name'])
#        if matches and matches.group(1) and int(matches.group(1)) > last_release:
#            last_release = int(matches.group(1))
#            #print(int(matches.group(1)), last_release)
#    if increment:
#        return last_release+1
#    return last_release
#

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
        "build_commit": None ,
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

for version in supported_versions: #.keys():
    output["version"] = version
    outputfile = config['qe_control_files'][version]
    if not debug:
        with open(outputfile, 'w') as file:
            json.dump(output, file, indent=4)
    else:
        print(outputfile)
        print(json.dumps(output, indent=4))

sys.exit(0)
