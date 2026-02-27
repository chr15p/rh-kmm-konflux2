#!/usr/bin/python
import sys
import re
import argparse
import json
import yaml
#import subprocess
#import time

import git_commands

TEST_MODE = False
def get_component_name(branch: str, prefix: str= r".*component-update") -> (str,str):

    branch_regexp=r"konflux/component-updates/" + prefix + "-([a-z-]+-([0-9]-[0-9]))"
    matches = re.match(branch_regexp, branch)
    if matches is None:
        return None, None
    return matches.group(1),matches.group(2)


def get_commit(msg: str) -> str:

    #commit_regexp = r"Image created from \'https://github.com/chr15p/rh-kmm-konflux2?rev=([0-9a-fA-F]+)\'"
    commit_regexp = r"=(.*)\'"
    matches = re.search(commit_regexp, msg)
    if matches is None:
        return None
    return matches.group(1)


def merge_prs(branch, master_pr, nudged_prs, label_to_apply=None):
    for pr_number in nudged_prs.values():
        if int(pr_number) == int(master_pr):
            continue
        out=git_commands.call_gh(TEST_MODE, "pr", "edit", pr_number, "--base", branch)
        print(out)


    for pr_number in nudged_prs.values():
        if int(pr_number) == int(master_pr):
            continue
        out=git_commands.call_gh(TEST_MODE, "pr", "merge", pr_number, "--squash")
        print(out)

    if label_to_apply:
        print("call_gh", "pr", "edit", str(master_pr), "--add-label", label_to_apply)
        out=git_commands.call_gh(TEST_MODE, "pr", "edit", str(master_pr),"--add-label", label_to_apply)
        print(out)



def get_pr(pr_list, branch, number):

    for pr in pr_list:
        if (branch and branch == pr['headRefName']) or \
            (number and int(number) == pr['number']):
            #print(pr)
            return pr
    return None


def parse_pr(pr):
    component, version = get_component_name(pr["headRefName"])
    commit = get_commit(pr['commits'][-1]['messageBody'])
    number = pr['number']

    return component, version, commit, number


def read_config_yaml(filename):
    try:
        with open(filename,"r") as config_fh:
            master_components = yaml.safe_load(config_fh)
    except Exception as e:
        print(f"unable to read config file \"{filename}\": {e}")
        sys.exit(1)
    return master_components



if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument('-c', '--config', action='store', required=True, default="nudges.yaml", help='yaml config file ')
    parser.add_argument('-p', '--pr', action='store', required=False, default=None, help='pr number')
    parser.add_argument('-b', '--branch', action='store', required=False, default=None, help='pr number')
    parser.add_argument('-n', '--nocommit', action='store_true', required=False, default=False, help='do not check commit numbers when merging')
    parser.add_argument('--test', action='store_true', default=False)

    opt = parser.parse_args()
    curr_number = opt.pr
    curr_branch = opt.branch
    commit_check = not opt.nocommit   # True if we want commit checking
    TEST_MODE = opt.test
    if not curr_branch and not curr_number:
        print("either --pr or --branch is required")
        sys.exit(1)


    ## read config
    CONFIG = read_config_yaml(opt.config)

    #print(MASTER_COMPONENTS)
    ########
    raw_prs = git_commands.call_gh(False, "pr","list","--json","number,headRefName,commits", "--search", "label:konflux-nudge")
    try:
        pr_list = json.loads(raw_prs)
    except json.decoder.JSONDecodeError as e:
        print(f"pr list error: {e}")
        sys.exit(1)

    curr_pr = get_pr(pr_list, curr_branch, curr_number)
    curr_branch=curr_pr['headRefName']
    curr_number=curr_pr['number']

    nudged_components = {}
    curr_component, curr_version, curr_commit, curr_number = parse_pr(curr_pr)
    nudged_components[curr_component] = curr_number
    for pr in pr_list:
        component, version, commit, number = parse_pr(pr)
        if version != curr_version or \
            number == curr_number:
            continue
        if commit_check and commit != curr_commit:
            continue
        if number > curr_number:
            print(f"a newer PR exists for {curr_version} defer to that ({number} > {curr_number})")
            print(f"{version=} {curr_version=} {commit=} {curr_commit=}")
            sys.exit(0)

        nudged_components[component] = number

    print(nudged_components)
    ## do we have everything we need?
    not_nudged = []
    label_to_apply = None
    #for c in CONFIG[f"release-{curr_version}"]["components"]:
    #    if not nudged_components.get(c):
    #        not_nudged.append(c)
    if CONFIG.get(f"release-{curr_version}"):
        if curr_component in CONFIG[f"release-{curr_version}"].get("operands", []):
            for c in CONFIG[f"release-{curr_version}"]["operands"]:
                if not nudged_components.get(c):
                    not_nudged.append(c)
            label_to_apply=CONFIG["operand-label"]
        elif curr_component in CONFIG[f"release-{curr_version}"].get("bundles", []):
            for c in CONFIG[f"release-{curr_version}"]["bundles"]:
                if not nudged_components.get(c):
                    not_nudged.append(c)
            label_to_apply=CONFIG["bundle-label"]

    if not_nudged:
        print(f"not all components found for release-{curr_version}: {label_to_apply} (missing {' '.join(not_nudged)})")
        sys.exit(0)

    print(f"merge {nudged_components}")
    merge_prs(curr_branch, curr_number, nudged_components, label_to_apply)
    #print("call_gh", "pr", "edit", curr_number, "--add-label", label_to_apply)
    #git_commands.call_gh(TEST_MODE, "pr", "edit", str(curr_number), "--add-label", "ok-to-merge")

