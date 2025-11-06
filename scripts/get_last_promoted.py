#!/usr/bin/python

import os
import sys
import argparse
import rh_kmm_konflux.rh_kmm_konflux_helpers as helpers



if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument('-n', '--namespace', default="rh-kmm-tenant", help='namespace to query')
    parser.add_argument('-k', '--kubeconfig', action='store', required=False, help='kubeconfig file ')
    parser.add_argument('-o', '--outputdir', action='store', required=False, help='directory to write to')
    parser.add_argument('-c', '--components', action='store', required=False, help='components to write for')
    parser.add_argument('-a', '--application', action='store', required=False, help='get all components for application')
    parser.add_argument('-s', '--stage', action='store', required=False, help='stage to get')
    parser.add_argument('-g', '--git', action='store', required=False, help='git commit to write for')

    opt = parser.parse_args()

    outdir = opt.outputdir
    wanted_components = []
    labels=[]
    if opt.stage:
        labels.append(f"stage={opt.stage}")

    if opt.application:
        labels.append(f"application={opt.application}")

    if opt.components:
        wanted_components = opt.components.split(",")

    try:
        components = helpers.Component(opt.kubeconfig, opt.namespace, label_selector=",".join(labels))
        image_shas = components.get_last_promoted(wanted_components, wanted_commit=opt.git)
    except Exception as e:
        print(f"ERROR: getting components failed for {','.join(labels)}:\n {e}")
        sys.exit(0) 

    if outdir:
        helpers.write_pullspecs(image_shas, outdir)
    else:
        for k,v in image_shas.items():
            print(f"{k} {v}")
