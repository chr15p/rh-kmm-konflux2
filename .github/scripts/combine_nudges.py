#!/usr/bin/python
import json
import yaml
import subprocess
import argparse
import time
import re


def call_git(test_mode, *args, **kwargs):
    """
        wrapper for calls to git
        *args: one or more strings to be arguements to the git command
    """
    params=["git"]
    for i in args:
        if isinstance(i, list):
            params+=i
        else:
            params.append(i)

    if test_mode:
        print(" ".join(params))
        return ""
    #subprocess.run(params, check=True)
    p = subprocess.Popen(params,
                     stdout=subprocess.PIPE,
                     stderr=subprocess.STDOUT)
    return p.stdout.read()


def call_gh(test_mode, *args, **kwargs):
    """
        wrapper for calls to git
        *args: one or more strings to be arguements to the git command
    """
    params=["gh"]
    for i in args:
        if isinstance(i, list):
            params+=i
        else:
            params.append(str(i))

    print(f"run {' '.join(params)}")
    if test_mode:
        return ""
    p = subprocess.Popen(params,
                     stdout=subprocess.PIPE,
                     stderr=subprocess.STDOUT)

    return p.stdout.read()


def get_component(branch: str, prefix: str= r".*component-update"):

    branch_regexp=r"konflux/component-updates/" + prefix + "-([a-z-]+-([0-9]-[0-9]))"
    matches = re.match(branch_regexp, branch)
    if matches is None:
        return None, None
    return matches.group(1),matches.group(2)


def get_commit(msg: str):

    #commit_regexp = r"Image created from \'https://github.com/chr15p/rh-kmm-konflux2?rev=([0-9a-fA-F]+)\'"
    commit_regexp = r"=(.*)\'"
    matches = re.search(commit_regexp, msg)
    if matches is None:
        return None
    return matches.group(1)


def merge_prs(branch, master_pr, nudged_prs):
    for pr_number in nudged_prs:
        if int(pr_number) == int(master_pr):
            continue
        out=call_gh(test_mode, "pr", "edit", pr_number, "--base", curr_branch)
        out=call_gh(test_mode, "pr", "merge", pr_number, "--squash")

    print("call_gh", "pr", "edit", curr_pr, "--add-label", "ok-to-merge")
    call_gh(test_mode, "pr", "edit", str(master_pr),"--add-label", "ok-to-merge")



parser = argparse.ArgumentParser()

parser.add_argument('-c', '--config', action='store', required=True, default="nudges.yaml", help='yaml config file ')
parser.add_argument('-p', '--pr', action='store', required=True, default=None, help='pr number')
parser.add_argument('--test', action='store_true')

opt = parser.parse_args()
curr_pr = opt.pr
test_mode = opt.test


raw_curr_pr = call_gh(False, "pr", "view","--json","headRefName,commits,labels", opt.pr )
curr_pr_details = json.loads(raw_curr_pr)
curr_branch = curr_pr_details['headRefName']

for label in curr_pr_details['labels']:
    if label['name'] == "ok-to-merge":
        print(f"all components already added and ok-to-merge label applied")
        exit(0) 

for commit in curr_pr_details['commits']:
    curr_commit = get_commit(commit['messageBody'])

try:
    with open(opt.config,"r") as config_fh:
         MASTER_COMPONENTS = yaml.safe_load(config_fh)
except Exception as e:
    print(f"unable to read config file \"{opt.config}\": {e}")
    exit(1)

#print(MASTER_COMPONENTS)

curr_component, curr_release = get_component(curr_branch)
if not curr_component:
    print("not a valid nudge PR")
    exit(0)

try:
    for i in MASTER_COMPONENTS[f"release-{curr_release}"]:
        if curr_component in i['operands']:
            PLAN=i
            break
    #print(PLAN)
except:
    print(f"release-{curr_release} not found in {opt.config}")
    exit(1)


raw_prs = call_gh(False, "pr","list","--json","number,headRefName,commits", "--search", "label:konflux-nudge")
pr_list = json.loads(raw_prs)

#print(f"{curr_component=} {curr_release=} {curr_pr=}")

nudged_components = {}
for pr in pr_list:
    component, version = get_component(pr["headRefName"])
    if component == None or component not in PLAN['operands'] :
        continue

    if pr['number'] > int(curr_pr):
        print(f"a newer PR exists for release-{curr_release}, defer to thati ({pr['number']} newer than {curr_pr})")
        exit(0)

    for commit in pr['commits']:
        commit = get_commit(commit['messageBody'])
        if commit != curr_commit:
            continue        

    number = pr['number']
    nudged_components[component] = number



not_nudged = [arg for arg in PLAN["operands"] if arg not in nudged_components.keys() ]
if not_nudged:
    print(f"not all components found (missing {' '.join(not_nudged)})")
    exit(0)

for action in PLAN["operation"]:

    if action == "merge":
        print(f"do mergy stuff for {nudged_components}")
        merge_prs(curr_branch, curr_pr, nudged_components.values())
        print("call_gh", "pr", "edit", curr_pr, "--add-label", "ok-to-merge")
        #call_gh(test_mode, "pr", "edit", str(curr_pr_id), "--add-label", "ok-to-merge")
    elif action == "release":
        print("do releasy stuff")

