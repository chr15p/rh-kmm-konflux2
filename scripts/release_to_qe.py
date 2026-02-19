#!/usr/bin/python

import os
import json
import re
import argparse
import subprocess

import rh_kmm_konflux.rh_kmm_konflux_helpers as helpers
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

parser.add_argument('-n', '--namespace', default="rh-kmm-tenant", help='namespace to query')
parser.add_argument('-k', '--kubeconfig', action='store', required=False, help='kubeconfig file ')
parser.add_argument('-r', '--release', default=None, help='release number to fetch (e.g. r31)')
parser.add_argument('-d', '--directory', required=True, help='directory containing config filesi (e.g. release-2.5/)')
parser.add_argument('-g', '--commit', default="HEAD", help='')
parser.add_argument('-o', '--output', default=None, help='file to write output to')
opt = parser.parse_args()

outputfile = opt.output

build_settings = helpers.read_key_value_file(f"{opt.directory}/build_settings.conf")

version = build_settings["VERSION"].replace(".","-")
rel = helpers.Release(opt.kubeconfig, opt.namespace, label_selector=f"appstudio.openshift.io/application=kmm-{version}")
#relnum = rel.get_latest_rel()
#relnum = rel.get_latest_rel_number()
relnum = rel.get_latest_rel()

kmm = submodule_version(f"{opt.directory}/{build_settings['PRODUCT']}")

#build = build_version(opt.commit)
build = helpers.get_commit(".", opt.commit)

output = {"version": build_settings.get("RELEASE", "unknown"), "release": relnum, "build_commit": build[:7], "kmm_commit": kmm,  "kmm": {}, "kmmhub": {}}
fbc={}

#components = helpers.Component(opt.kubeconfig, opt.namespace, match="spec.application=fbc-*")
components = helpers.Component(opt.kubeconfig, opt.namespace, label_selector="stage=fbc")

image_shas = {}
for comp in components.items():
    try:
        if comp.status.lastBuiltCommit == build:
            image_shas[comp.metadata.name] = comp.status.lastPromotedImage
    except AttributeError as e:
        print(f"failed to get comp.status.lastBuiltCommit for {comp.metadata.name}: {e}")
        #exit(0)

for k,v in image_shas.items():
    if "hub" in k:
        ocp = k.replace("fbc-hub-","ocp")
        output['kmmhub'][ocp]=v
    if "op" in k:
        ocp = k.replace("fbc-op-","ocp")
        output['kmm'][ocp]=v


if outputfile:
    with open(outputfile, 'w') as file:
        json.dump(output, file, indent=4)
else:
    print(json.dumps(output, indent=4))


exit(0)
