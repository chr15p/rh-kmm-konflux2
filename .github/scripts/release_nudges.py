#!/usr/bin/python
import sys
import argparse
import os
import re
from typing import Any, Dict
#, List, Optional
import yaml
import json

import git_commands
import helpers
from konflux_api import Konflux

test_mode=False
current_versions = {} #get_versions() 

#def get_versions() -> Dict(str,str):
#    return {"kmm-2-6": "2.6.0", "kmm-2-5": "2.5.2", "kmm-2-4": "2.4.3", "kmm-2-3": "2.3.2", "kmm-2-2": "2.2.2"}

def read_release(rel_dir):
    filename=f"{rel_dir}/build_settings.conf"
    data = {}
    with open(filename, "r") as file:
        for line in file:
            line = line.strip()
            if line.startswith("RELEASE"):
                key, value = line.split("=", 1)
                return value
    return None


def get_versions(path=".") -> Dict(str,str):
    all_versions = {}
    for i in os.listdir(path):
        if i[:8]=="release-":
            version = f"kmm-{i[8:].replace(".","-")}"
            release = read_release(i) 
            all_versions[version] = release 

    print(all_versions)
    return all_versions


def create_snapshots(kube_components, kube_snapshots, namespace, release_number, commit, labels={}):
    snapshot_extension = f"{commit[:7]}-r{release_number}"

    labels["stage!"] = "fbc"

    component_list = kube_components.get(label_selector=labels)
    snapshot_images = {}
    for c in component_list:
        if not snapshot_images.get(c["spec"]["application"]):
            snapshot_images[c["spec"]["application"]] = []

        snapshot_images[c["spec"]["application"]].append(
            {"name": c['metadata']['name'],
             "containerImage": c['status']['lastPromotedImage'],
             "source": {
                "git": { 
                    "context": c["spec"]["source"]["git"].get("context", "main"),
                    "dockerfileUrl": c["spec"]["source"]["git"]["dockerfileUrl"],
                    "revision": c["status"]["lastBuiltCommit"],
                    "url":  c["spec"]["source"]["git"]["url"],
                    }
                }
            })


    snapshots={}
    for k,v in snapshot_images.items():
        version = k[4:].strip()
        new_snapshot = yaml.safe_load(f"""
            apiVersion: appstudio.redhat.com/v1alpha1
            kind: Snapshot
            metadata:
              name: {k}-{snapshot_extension}
              namespace: {namespace}
              labels: 
                kmm: "{version}"
                version: "{current_versions[k]}"
                commit: "{commit}"
                short: "{commit[:7]}"
            spec:
              application: {k}
        """)
        new_snapshot['spec']['components'] = v
        snapshots[k] = new_snapshot['metadata']['name']
        if test_mode:
            print("---")
            print(yaml.dump(new_snapshot))
        else:
            print(new_snapshot['metadata']['name'])
            resp = kube_snapshots.create(new_snapshot)
            print(resp)

    return snapshots



def create_release(kube_releases, snapshots, namespace,  environment, release_number, commit):
    release_name_extension = f"release-{environment}-{commit[:7]}-r{release_number}"

    for k,v in snapshots.items():
        version = k[4:]
        new_release = yaml.safe_load(f"""
            apiVersion: appstudio.redhat.com/v1alpha1
            kind: Release
            metadata:
              labels:
                appstudio.openshift.io/application: {k}
                application: {k}
                version: "{current_versions[k]}"
                commit: "{commit}"
                short: "{commit[:7]}"
              name: {k}-{release_name_extension}
              namespace: {namespace}
            spec:
              releasePlan: {k}-release-{environment}
              snapshot: {v}
            """)

        if test_mode:
            print("---")
            print(yaml.dump(new_release))
        else:
            print(new_release['metadata']['name'])
            resp = kube_releases.create(new_release)
            print(resp)



def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("Config root must be a mapping/object")
    if "api_url" not in data or not data["api_url"]:
        raise ValueError("Config must contain non-empty 'api_url'")
    return data


def resolve_tls_verify(config: Dict[str, Any]) -> Any:
    """
    Returns verify which is either:
    - True/False
    - Path to a CA bundle file
    """
    # TLS verification
    skip_verify_env = os.getenv("OPENSHIFT_SKIP_TLS_VERIFY", "").lower() in ("1", "true", "yes")
    skip_verify_cfg = bool(config.get("skip_tls_verify", False))
    if skip_verify_env or skip_verify_cfg:
        verify = False
    else:
        ca_cert = os.getenv("OPENSHIFT_CA_CERT") or config.get("ca_cert")
        verify = ca_cert if ca_cert else True
    return verify


def get_release_number(kube_releases):
    release_list = kube_releases.get()
    rel_regexp = r"-r([0-9]+)$"
    last_release=0
    for rel in release_list:
        #print(rel['metadata']['name'])
        matches = re.search(rel_regexp, rel['metadata']['name'])
        if matches and matches.group(1) and int(matches.group(1)) > last_release:
            last_release = int(matches.group(1))
            #print(int(matches.group(1)), last_release)
    return last_release+1



def get_konflux(config, token, api, kind, verify):
    return Konflux(config['api_url'],
                        token,
                        config['namespace'],
                        api,
                        kind,
                        verify)



if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument('-c', '--config', action='store', required=False, default="nudges.yaml", help='yaml config file (default: nudges.yaml) ')
    parser.add_argument('-t', '--token', action='store', required=False, default=None, help='token to access k8s')
    parser.add_argument('-e', '--env', action='store', required=False, default="staging", help='environment to release to (prod|staging)')
    parser.add_argument('-a', '--application', action='store', required=False, default="", help='limit to a single application')
    parser.add_argument('-f', '--fbctemplate', action='store', required=False, default="templates/hub-catalog-template.json,templates/op-catalog-template.json", help='comma seperated list of templates to process')
    parser.add_argument('-o', '--outdir', action='store', required=False, default=None, help='directory to write to')
    parser.add_argument('--test', action='store_true', default=False)
    parser.add_argument('--release', action='store_true', default=False, help='Only run the release')
    parser.add_argument('--fbc', action='store_true', default=False, help='Only run the fbc create')

    opt = parser.parse_args()
    test_mode = opt.test
    token = opt.token
    if opt.env != "prod" and opt.env != "staging":
        print("--env should be one of 'prod' or 'staging'")
        sys.exit(0)
    env = opt.env
    template_list = opt.fbctemplate.split(",")
    fbc_dir = opt.outdir

    if not opt.release  and not opt.fbc:
        opt.release = True
        opt.fbc = True

    labels={}
    if opt.application:
        labels['application'] = opt.application


    try:
        config = load_config(opt.config)
    except Exception as e:
        print(f"Failed to load config: {e}", file=sys.stderr)
        sys.exit(2)



    #release_plan = f"release-staging"
    verify = resolve_tls_verify(config)
    current_versions = get_versions() 

    kube_components = get_konflux(config,
                        token,
                        "appstudio.redhat.com/v1alpha1",
                        "components",
                        verify)

    kube_releases = get_konflux(config,
                        token,
                        "appstudio.redhat.com/v1alpha1",
                        "releases",
                        verify)

    kube_snapshots = get_konflux(config,
                        token,
                        "appstudio.redhat.com/v1alpha1",
                        "snapshots",
                        verify)


    release_number = get_release_number(kube_releases)
    commit = git_commands.call_git(False, "rev-parse", "main").decode("utf-8").strip()

    if opt.release:
        snapshots = create_snapshots(kube_components, kube_snapshots, config['namespace'], release_number, commit, labels=labels)
        create_release(kube_releases, snapshots, config['namespace'], env, release_number, commit)

    exit(0)
