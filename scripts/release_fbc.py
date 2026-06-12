#!/usr/bin/python
import sys
import argparse
import re
from typing import Any, Dict
#, List, Optional
import yaml
#import json

from kmm_konflux import git_commands
from kmm_konflux.konflux_api import Konflux, resolve_tls_verify
import kmm_konflux.versions
import kmm_konflux.config

test_mode=False

def create_snapshots(kube_components, kube_snapshots, namespace, release_number, commit, labels={}) -> Dict(str,str):
    """
        create a snapshot from the components with the labels
        returns:
            dict { application: snapshot_name }
    """
    snapshot_extension = f"{commit[:7]}-r{release_number}"

    labels["stage"] = "fbc"

    component_list = kube_components.get(label_selector=labels)

    try:
        if component_list[0].get('items') == []:
            print(f"no components found labelled {labels}")
            return None
    except KeyError:
        pass

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

    #ie.g. {'kmm-2-4': 'kmm-2-4-unknown-r13'}
    return snapshots



def create_release(kube_releases, snapshots, namespace,  environment, release_number, commit):
    release_name_extension = f"release-{environment}-{commit[:7]}-r{release_number}"

    for k,v in snapshots.items():
        # k = application
        # v = snapshot_name
        # current_versions[version][-1] is latest release for application (e.g. 2.5.2 for kmm-2.5)
        version = k[4:].strip()
        new_release = yaml.safe_load(f"""
            apiVersion: appstudio.redhat.com/v1alpha1
            kind: Release
            metadata:
              labels:
                appstudio.openshift.io/application: {k}
                application: {k}
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



def get_release_number(kube_releases, increment:bool = True):

    release_list = kube_releases.get()
    if release_list[0].get('items', []) == []:
        return 1
    rel_regexp = r"-r([0-9]+)$"
    last_release=0
    print(release_list)
    for rel in release_list:
        print(rel)
        matches = re.search(rel_regexp, rel['metadata']['name'])
        if matches and matches.group(1) and int(matches.group(1)) > last_release:
            last_release = int(matches.group(1))
            print(int(matches.group(1)), last_release)
    if increment:
        return last_release+1
    return last_release


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', action='store', required=False, default="pullspec_config.yaml", help='yaml config file (default: pullspec_config.yaml) ')
    parser.add_argument('-t', '--token', action='store', required=False, default=None, help='token to access k8s')
    parser.add_argument('-e', '--env', action='store', required=False, default="staging", help='environment to release to (prod|staging)')
    parser.add_argument('-a', '--application', action='store', required=False, default="", help='limit to a single application')
    parser.add_argument('-g', '--git', action='store', required=False, default="", help='git commit to label objects with')
    parser.add_argument('-r', '--release', action='store', required=False, default=None, help='release number to apply (e.g. 10)')
    parser.add_argument('--test', action='store_true', default=False)

    opt = parser.parse_args()
    test_mode = opt.test
    token = opt.token
    if opt.env != "prod" and opt.env != "staging":
        print("--env should be one of 'prod' or 'staging'")
        sys.exit(0)
    env = opt.env
    commit = opt.git
    release_number = opt.release

    labels={}
    if opt.application:
        labels['application'] = opt.application

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

    if not release_number:
        release_number = get_release_number(kube_releases)

    if not commit:
        commit = git_commands.call_git(False, "rev-parse", "main").decode("utf-8").strip()
        if commit.startswith("fatal:"):
            commit="unknown"

    snapshots = create_snapshots(kube_components, kube_snapshots, config['namespace'], release_number, commit, labels=labels)
    if snapshots is not None:
        create_release(kube_releases, snapshots, config['namespace'], env, release_number, commit)
    else:
        print("no snapshots created")

    sys.exit(0)
