#!/usr/bin/python

import yaml
import argparse
from string import Template
import os
import re

def read_key_value_file(filename="config.conf"):
    data = {}
    with open(filename, "r") as file:
        for line in file:
            line = line.strip()
            if line and "=" in line:
                key, value = line.split("=", 1)
                data[key.strip()] = value.strip()
    return data

def read_pullspec_file(filename, repo=None):
    with open(filename, "r") as file:
        pullspec = file.readline().strip() 

    if repo != None:
        sha = pullspec.split("@")[1]
        pullspec = f"{repo}@{sha}"

    return pullspec

def generate_pipeline(TEMPLATE, config, outputfile):
    #outputfile = f"{outdir}/{ config['COMPONENT']}-{config['X']}-{config['Y']}-push.yaml"

    with open(TEMPLATE, 'r') as file:
        data = Template( file.read() )

    #if pull:
    #    outputfile = f"{outdir}/{ config['COMPONENT']}-{config['X']}-{config['Y']}-pull-request.yaml"

    subs = {
        "PRODUCT": config["PRODUCT"],
        "DIRECTORY": config["DIRECTORY"],
        "COMPONENT": config['COMPONENT'],
        "X": config['X'],
        "Y": config['Y'] 
    }

    out = data.safe_substitute(**subs)

    with open(outputfile, 'w') as file:
        file.write(out)


parser = argparse.ArgumentParser()

#parser.add_argument('--template', action='store', default="pipeline_template.yaml", help='csv template')
parser.add_argument('--name', action='store', default="worker", help='component name')
parser.add_argument('--outdir', action='store', default=".tekton", help='directoy to write pipelines to')
parser.add_argument('--configdir', action='store', default="release-2.5", help='directory containing config files (e.g. release-2.5')
#parser.add_argument('--pull', action='store_true', default=False, help='is this a pull-request pipeline')
#parser.add_argument('--pullspecs', action='store', default="pullspec_config.yaml", help='file icontaining location of pullspecs')

opt = parser.parse_args()

outputdir = opt.outdir
config = read_key_value_file(f"{opt.configdir}/build_settings.conf")
config['X'], config['Y'] = config['VERSION'].split(".")


componentList=["hub-operator", "must-gather", "webhook", "operator", "signing", "worker"] 

for component in componentList:
    config['COMPONENT'] = component
    outputfile = f"{outputdir}/{ config['COMPONENT']}-{config['X']}-{config['Y']}-push.yaml"
    generate_pipeline(config['PIPELINE_PUSH'], config, outputfile)

for component in componentList:
    config['COMPONENT'] = component
    outputfile = f"{outputdir}/{ config['COMPONENT']}-{config['X']}-{config['Y']}-pull-request.yaml"
    generate_pipeline(config['PIPELINE_PULL'], config, outputfile)

for component in [config["OP_BUNDLE"], config["HUB_BUNDLE"]]:
    config['COMPONENT'] = component
    outputfile = f"{outputdir}/{ config['COMPONENT']}-{config['X']}-{config['Y']}-push.yaml"
    generate_pipeline(config['BUNDLE_PUSH'], config, outputfile)

for component in [config["OP_BUNDLE"], config["HUB_BUNDLE"]]:
    config['COMPONENT'] = component
    outputfile = f"{outputdir}/{ config['COMPONENT']}-{config['X']}-{config['Y']}-pull-request.yaml"
    generate_pipeline(config['BUNDLE_PULL'], config, outputfile)


exit(0)

