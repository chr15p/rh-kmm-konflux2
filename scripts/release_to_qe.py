#!/usr/bin/python

import os
import sys
import json
import re
import argparse
import subprocess

from kmm_konflux.konflux_api import Konflux, resolve_tls_verify
import kmm_konflux.config

#import rh_kmm_konflux.rh_kmm_konflux_helpers as helpers
#from kubernetes import client, config
#from openshift.dynamic import DynamicClient

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

def build_version(commit):
    params=["git", "rev-parse", commit]
    p = subprocess.Popen(params, stdout=subprocess.PIPE)

    output = p.stdout.read().decode("utf-8")
    #print(output)
    try:
        return output.strip() #[:7]
    except IndexError:
        return "unknown"




parser = argparse.ArgumentParser()

parser.add_argument('-c', '--config', action='store', required=False, default="pullspec_config.yaml", help='yaml config file (default: pullspec_config.yaml) ')
parser.add_argument('-t', '--token', action='store', required=False, default=None, help='token to access k8s')
parser.add_argument('-r', '--release', default=None, help='release number to fetch (e.g. r31)')
parser.add_argument('-d', '--directory', required=True, help='directory containing config filesi (e.g. release-2.5/)')
parser.add_argument('-g', '--commit', default=None, help='')
parser.add_argument('-o', '--output', default=None, help='file to write output to')
opt = parser.parse_args()

outputfile = opt.output
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

#build_settings = helpers.read_key_value_file(f"{opt.directory}/build_settings.conf")

#version = build_settings["VERSION"].replace(".","-")
version ="2.6.0"
#rel = helpers.Release(opt.kubeconfig, opt.namespace, label_selector=f"appstudio.openshift.io/application=kmm-{version}")
rel="YY"
#relnum = rel.get_latest_rel()
#relnum = rel.get_latest_rel_number()
#relnum = rel.get_latest_rel()

relnum="99"

#kmm = submodule_version(f"{opt.directory}/{build_settings['PRODUCT']}")
kmm_commit = "XXXX"
#build = build_version(opt.commit)
build_commit = "1234567890"
build = "0a9f65da632c05d838f3184be837e17e4149c4e2"
#if opt.commit:
#    build=opt.commit.split(",")
#else:
#    build = [helpers.get_commit(".", "HEAD")]


output = {
    "version": version,
    "release": relnum,
    "build_commit": build_commit,
    "kmm_commit": kmm_commit,
    "kmm": {},
    "kmmhub": {}
}
fbc={}

#components = helpers.Component(opt.kubeconfig, opt.namespace, match="spec.application=fbc-*")
#components = helpers.Component(opt.kubeconfig, opt.namespace, label_selector="stage=fbc")
verify = resolve_tls_verify(config)
kube_components = Konflux(config['api_url'],
                        token,
                        config['namespace'],
                        "appstudio.redhat.com/v1alpha1",
                        "components",
                        verify)
labels = {"stage": "fbc"}
#breakpoint()
component_list = kube_components.get(label_selector=labels)

image_shas = {}
for comp in component_list:
    try:
        #if comp.status.lastBuiltCommit == build:
        print(comp["metadata"]["name"], comp["status"]["lastBuiltCommit"])
        if comp["status"]["lastBuiltCommit"] in build:
            image_shas[comp["metadata"]["name"]] = comp["status"]["lastPromotedImage"]
    except AttributeError as e:
        print(f"failed to get comp.status.lastBuiltCommit for {comp["metadata"]["name"]}: {e}")
        #exit(0)

for k,v in image_shas.items():
    if "op" in k:
        ocp = k.replace("fbc-op-","ocp")
        output['kmm'][ocp]=v
    if "hub" in k:
        ocp = k.replace("fbc-hub-","ocp")
        output['kmmhub'][ocp]=v


if outputfile:
    with open(outputfile, 'w') as file:
        json.dump(output, file, indent=4)
else:
    print(json.dumps(output, indent=4))


exit(0)
