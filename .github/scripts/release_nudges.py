import sys
import argparse
import os
import re
from typing import Any, Dict, List, Optional
import uuid
import yaml

import git_commands
from konflux_api import Konflux

#from kubernetes import config
#from openshift.dynamic import DynamicClient


test_mode=False

def snapshot_and_release(config, token, version, application, releaseplan, verify):

    commit = git_commands.get_git_commit(version)

    kube_snapshots = Konflux(config['api_url'],
                            token,
                            config['namespace'],
                            "appstudio.redhat.com/v1alpha1",
                            "snapshots",
                            verify)

    snapshot_list = kube_snapshots.get(label_selector={"appstudio.openshift.io/application": application})
    snap_regexp = r"-r([0-9]+)$"
    last_release=0
    for snap in snapshot_list:
        print(snap['metadata']['name'])
        matches = re.search(snap_regexp, snap['metadata']['name'])
        if matches and matches.group(1) and int(matches.group(1)) > last_release:
            last_release = int(matches.group(1))
            print(int(matches.group(1)), last_release)

    release_number = last_release +1
    snapshot_name = f"kmm-{version}-{commit[:7]}-r{release_number}"
    release_name = f"{releaseplan}-{commit[:7]}-r{release_number}"

    kube_components = Konflux(config['api_url'],
                        token,
                        config['namespace'],
                        "appstudio.redhat.com/v1alpha1",
                        "components",
                        verify)

    component_list = kube_components.get(label_selector={"application": application})

    new_snapshot = yaml.safe_load(f"""
        apiVersion: appstudio.redhat.com/v1alpha1
        kind: Snapshot
        metadata:
          name: {snapshot_name}
          namespace: {config['namespace']}
          labels: 
            kmm: {version}
            midstream-sha: {commit}
            short: {commit[:7]}
        spec:
          application: {application}
        """)

    new_snapshot['spec']['components']=[]
    for c in component_list:
        #print( c["spec"]["source"]["git"])
        new_snapshot['spec']['components'].append(
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

    print(yaml.dump(new_snapshot))

    if not test_mode:
        resp = kube_snapshots.create(new_snapshot)
        print(resp)



    release = Konflux(config['api_url'],
                        token,
                        config['namespace'],
                        "appstudio.redhat.com/v1alpha1",
                        "releases",
                        verify)

    new_release = yaml.safe_load(f"""
        apiVersion: appstudio.redhat.com/v1alpha1
        kind: Release
        metadata:
          labels:
            appstudio.openshift.io/application: {application}
            kmm: {version}
            midstream: {commit}
            short: {commit[:7]}
          name: {release_name}
          namespace: {config['namespace']}
        spec:
          releasePlan: {releaseplan}
          snapshot: {snapshot_name}
        """)
    print("---")
    print(yaml.dump(new_release))

    if not test_mode:
        kube_release = Konflux(config['api_url'],
                            token,
                            config['namespace'],
                            "appstudio.redhat.com/v1alpha1",
                            "releases",
                            verify)
        resp = kube_release.create(new_release)
        print(resp)



def get_component_from_branch(branch: str, prefix: str= r".*component-update"):

    branch_regexp=r"konflux/component-updates/" + prefix + "-([a-z-]+-([0-9]-[0-9]))"
    matches = re.match(branch_regexp, branch)
    if matches is None:
        return None, None
    return matches.group(1),matches.group(2)


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



if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument('-f', '--config', action='store', required=False, default="nudges.yaml", help='yaml config file ')
    parser.add_argument('-b', '--branch', action='store', required=False, default=None, help='source branch')
    parser.add_argument('-t', '--token', action='store', required=False, default=None, help='token to access k8s')
    parser.add_argument('--test', action='store_true', default=False)

    opt = parser.parse_args()
    test_mode = opt.test
    token = opt.token

    try:
        config = load_config(opt.config)
    except Exception as e:
        print(f"Failed to load config: {e}", file=sys.stderr)
        sys.exit(2)

    component, version = get_component_from_branch(opt.branch)

    try:
        if component not in config[f"release-{version}"][1]['operands'] \
            or "release" not in config[f"release-{version}"][1]['operation']:
                print(f"{component} not releaseable component")
                exit(0)
    except KeyError as e:
        print(f"release-{version} not found in {opt.config} {e}")
        exit(1)


    verify = resolve_tls_verify(config)

    application = f"kmm-{version}"
    releaseplan = f"{application}-release-staging"

    snapshot_and_release(config, token, version, application, releaseplan, verify)

    exit(0)

