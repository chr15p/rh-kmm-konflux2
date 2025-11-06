#!/usr/bin/python

import os
import sys
import argparse
import yaml

#import rh_kmm_konflux_helpers as helpers
import rh_kmm_konflux.rh_kmm_konflux_helpers as helpers

def read_pullspec_file(filename):
    with open(filename, "r") as file:
        pullspec = file.readline().strip()
    return pullspec


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument('-n', '--namespace', default="rh-kmm-tenant", help='namespace to query')
    parser.add_argument('-k', '--kubeconfig', action='store', required=False, help='kubeconfig file')
    parser.add_argument('-a', '--application', action='store', required=False, help='applications to get snapshots for')
    parser.add_argument('-p', '--prod', action='store_true', required=False, help='release to prod (not staging)')
    parser.add_argument('-o', '--outdir', action='store', required=False, help='directory to write yaml to')
    parser.add_argument('-r', '--release', action='store', default="r1-1", required=False, help='string to append to releases')
    parser.add_argument('--pullspecs', action='store', required=False, help='read pullspecs from directory, if not set use last built from component')
    parser.add_argument('-v', '--verbose', action='store_true', required=False, help='write to stdout as well as file')

    opt = parser.parse_args()

    wanted_apps = None
    component_glob  = None

    labels=[]
    if opt.application:
        labels.append(f"application={opt.application}")

    env='staging'
    if opt.prod:
        env = 'prod'

    components = helpers.Component(opt.kubeconfig, opt.namespace, label_selector=",".join(labels))
    if components.items() == []:
        print(f"no components found for {','.join(labels)}")
        exit(1)

    try:
        context = components.items()[0]['spec']["source"]["git"]["context"]
        build_config = helpers.read_key_value_file(f"{context}/build_settings.conf")
    except KeyError:
        build_config['RELEASE']="unknown"

    if not opt.pullspecs:
        image_shas = components.get_last_promoted([])
    else:
        try:
            with open(opt.pullspecs, "r") as file:
                pullspec_config=yaml.safe_load(file)
        except yaml.YAMLError as exc:
            print(exc)               
            exit(1)

        image_shas={}
        for k,v in pullspec_config.items():
            image_shas[v['component']] = read_pullspec_file(v['pullspecfile'])

    applications = components.by_application(wanted_apps)
    if not applications:
        print(f"no applications found in {opt.applications}")
        sys.exit(1)

    try:
        snapshots = helpers.Snapshot(opt.kubeconfig, opt.namespace)
    except Exception as e:
        print(f"ERROR: getting snapshots failed {e}")
        sys.exit(0) 


    release_snapshots = snapshots.latest_snapshots(applications, image_shas)
    if release_snapshots == {}:
        print(f"no snapshot found for:\n\t{'\n\t'.join(image_shas.values())}")
        exit(0)

    releases = helpers.Release(opt.kubeconfig, opt.namespace)
    if not opt.release:
        relnum = releases.get_next_rel_number()
    else:
        relnum= opt.release    

    all_releases: list = []
    for app, snap in release_snapshots.items():
        all_releases.append(releases.new_yaml(
                {
                "name": f"{app}-{env}-{relnum}",
                "namespace": opt.namespace,
                "labels": {
                    "appstudio.openshift.io/application": app,
                    "kmm": build_config['RELEASE']
                    },
                },
                {
                "releasePlan": f"{app}-release-{env}",
                "snapshot": snap,
                }))
    
    if opt.outdir:
        outfile = f"{opt.outdir}/{relnum}-{env}.yaml"
        #with open(opt.outfile, "w") as file:
        with open(outfile, "w") as file:
            for i in all_releases:
                file.write(yaml.dump(i, explicit_start=True))
        
    if opt.verbose or opt.outdir is None:
        for i in all_releases:
            print(yaml.dump(i, explicit_start=True))
