#!/usr/bin/python
import sys
import argparse
import re
import json
import yaml

from kmm_konflux import git_commands
from kmm_konflux.konflux_api import Konflux, resolve_tls_verify
import kmm_konflux.versions
import kmm_konflux.config
import kmm_konflux.yaml_config
import kmm_konflux.git_commands

test_mode=False
current_versions = {}


def create_snapshots(kube_components,
                        kube_snapshots,
                        namespace,
                        labels_to_apply,
                        labels={}):
    """
        create a snapshot from the components with the labels
        returns:
            dict { application: snapshot_name }
    """
    snapshot_extension = f"{commit[:7]}-r{release_number}"

    labels["stage!"] = "fbc"

    component_list = kube_components.get(label_selector=labels)

    try:
        if component_list[0].get('items') == []:
            print(f"no components found labelled {labels}")
            return None
    except KeyError:
        pass

    snapshot_images = {}
    revision = None
    for c in component_list:
        revision =  c["status"]["lastBuiltCommit"]

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
              name: {k}-{current_versions[version][-1].replace(".","")}-{snapshot_extension}
              namespace: {namespace}
              labels: 
            spec:
              application: {k}
        """)
        new_snapshot["metadata"]["labels"]=labels_to_apply[version]

        new_snapshot['spec']['components'] = v
        snapshots[k] = new_snapshot['metadata']['name']
        if test_mode:
            print("---")
            print(yaml.dump(new_snapshot))
        else:
            #print(new_snapshot['metadata']['name'])
            resp = kube_snapshots.create(new_snapshot)
            if isinstance(resp, list):
                print(f"snapshot={resp[0]['metadata']['name']}")
            elif isinstance(resp, dict):
                print(f"snapshot={resp['metadata']['name']}")
            else:
                print(f"create snapshot returnedi unusual result: {resp}")
                sys.exit(1)
        #print(resp)

    #ie.g. {'kmm-2-4': 'kmm-2-4-unknown-r13'}
    return snapshots


def get_default_labels(commit, release_number):
    default_labels = {}
    submodules = kmm_konflux.git_commands.get_all_git_commits()
    for k,v in submodules.items():
        default_labels[k] = {
            "application": f"kmm-{k}",
            "kmmcommit": v,
            "kmmshort": v[:7],
            "version": current_versions[k][-1],
            "commit": commit,
            "short": commit[:7],
            "relnumber": f"r{release_number}",
        }

    return default_labels


def create_release(kube_releases, snapshots, namespace,  environment, labels_to_apply):

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
              name: "{k}-{environment}-{current_versions[version][-1].replace(".","")}-{commit[:7]}-r{release_number}"
              namespace: {namespace}
            spec:
              releasePlan: {k}-release-{environment}
              snapshot: {v}
            """)
        new_release["metadata"]["labels"].update(labels_to_apply[version])

        try:
            data_file = f"release-{version.replace("-",".")}/release-{current_versions[version][-1]}/release_notes.yaml"
            #print(data_file)
            new_release['spec']['data'] = kmm_konflux.yaml_config.load_config_dict(data_file)
        except FileNotFoundError:
            pass

        if test_mode:
            print("---")
            print(yaml.dump(new_release))
        else:
            print(new_release['metadata']['name'])
            try:
                resp = kube_releases.create(new_release)
                print(f"release={resp['metadata']['name']}")
            except Exception as e:
                print(f"errror creating release: {e}")
                print(new_release)
                sys.exit(1)
        #print(resp)



def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("Config root must be a mapping/object")
    if "api_url" not in data or not data["api_url"]:
        raise ValueError("Config must contain non-empty 'api_url'")
    return data



def get_release_number(kube_releases, increment:bool = True, labels:dict = {}):
    release_list = kube_releases.get(label_selector=labels)
    if len(release_list)==1 and release_list[0].get('items', []) == []:
        return 1
    rel_regexp = r"-r([0-9]+)$"
    last_release=0
    for rel in release_list:
        #print(rel['metadata']['name'])
        matches = re.search(rel_regexp, rel['metadata']['name'])
        if matches and matches.group(1) and int(matches.group(1)) > last_release:
            last_release = int(matches.group(1))
            #print(int(matches.group(1)), last_release)
    if increment:
        return last_release+1
    return last_release


def get_application(pr_number:int):
    try:
        raw_pr = git_commands.call_gh(False, "pr", "view","--json","title,headRefName", pr_number)
    except Exception as e:
        print(f"raw pr list error: {e}")

    try:
        pr_list = json.loads(raw_pr)
    except json.decoder.JSONDecodeError as e:
        print("pr view --json title,headRefName {pr_number}")
        print(f"pr list error: {e}")
        print(raw_pr)
        sys.exit(1)

    branch_regexp=r"konflux/component-updates/.*-([0-9]-[0-9]+)"
    matches = re.match(branch_regexp, pr_list["headRefName"])
    if matches is None:
        return None
    return f"kmm-{matches.group(1)}"


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', action='store', required=False,
                        default="config/pullspec_config.json",
                        help='json config file (default: config/pullspec_config.json) ')
    parser.add_argument('-t', '--token', action='store', required=False,
                        default=None,
                        help='token to access k8s')
    parser.add_argument('-e', '--env', action='store', required=False,
                        default="staging",
                        help='environment to release to (prod|staging)')
    parser.add_argument('-a', '--application', action='store', required=False,
                        default="",
                        help='limit to a single application')
    parser.add_argument('-p', '--pr', action='store', required=False,
                        default="",
                        help='release application from pr')
    parser.add_argument('-g', '--git', action='store', required=False,
                        default="",
                        help='git commit to label objects with')
    parser.add_argument('-r', '--release', action='store', required=False,
                        default=None,
                        help='release number to apply (e.g. 10)')
    parser.add_argument('-s', '--snapshot', action='store', required=False,
                        default=None,
                        help='snapshot to release (requires --application)')
    parser.add_argument('--test', action='store_true', default=False)

    opt = parser.parse_args()
    test_mode = opt.test
    token = opt.token
    if opt.env not in ("prod", "staging"):
        print("--env should be one of 'prod' or 'staging'")
        sys.exit(0)
    env = opt.env
    commit = opt.git
    release_number = opt.release

    #breakpoint()
    release_snapshot = {}
    if opt.snapshot:
        if not opt.application:
            print("--snapshot requires --application")
            sys.exit(1)
        release_snapshot={opt.application: opt.snapshot}

    labels={}
    if opt.application:
        labels['application'] = opt.application
    elif opt.pr:
        labels['application'] = get_application(int(opt.pr))

    try:
        #config = load_config(opt.config)
        config = kmm_konflux.config.load_config_dict(opt.config)
    except ValueError as e:
        print(f"Failed to load config {opt.config}: {e}", file=sys.stderr)
        sys.exit(2)
    if not config.get("api_url"):
        print(f"Config file {opt.config} must contain non-empty 'api_url'")
        sys.exit(2)

    verify = resolve_tls_verify(config)

    current_versions = kmm_konflux.versions.get_version_mappings(".", dirsep="-")

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
        release_number = get_release_number(kube_releases, labels=labels)

    if not commit:
        commit = git_commands.call_git(False, "rev-parse", "main").decode("utf-8").strip()
        if commit.startswith("fatal:"):
            #commit="unknown"
            print("cannot determine commit (maybe try the --commit switch?)")
            sys.exit(1)

    default_labels = get_default_labels(commit, release_number)
    if not release_snapshot:
        snapshots = create_snapshots(kube_components,
                                    kube_snapshots,
                                    config['namespace'],
                                    default_labels,
                                    labels=labels)
    else:
        snapshots = release_snapshot
    if snapshots is not None:
        #create_release(kube_releases, snapshots, config['namespace'], env, release_number, commit)
        create_release(kube_releases, snapshots, config['namespace'], env, default_labels)
    else:
        print("no snapshots created")

    sys.exit(0)
