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
            params.append(i)

    print(f"run {' '.join(params)}")
    if test_mode:
        return ""
    p = subprocess.Popen(params,
                     stdout=subprocess.PIPE,
                     stderr=subprocess.STDOUT)

    return p.stdout.read()

def get_component(branch: str, prefix: str= r".*component-update"):

    branch_regexp=r"konflux/component-updates/" + prefix + "-([a-z-]+-[0-9]-[0-9])"
    #matches = re.match(r"konflux/component-updates/.*component-update-([a-z-]+-[0-9]-[0-9])", branch)
    matches = re.match(branch_regexp, branch)
    if matches is None:
        return None
    return matches.group(1)


#MASTER_COMPONENTS = {
#    "operator-2-4": ["worker-2-4", "must-gather-2-4", "hub-operator-2-4", "signing-2-4", "webhook-2-4"],
#    "operator-bundle-2-4": [],
#    "hub-operator-bundle-2-4": [],
#    }

parser = argparse.ArgumentParser()

parser.add_argument('-c', '--config', action='store', required=True, default="nudges.yaml", help='yaml config file ')
parser.add_argument('-b', '--branch', action='store', required=True, default=None, help='csv template')
parser.add_argument('-i', '--interval', action='store', type=int, default=60, help='interval between checks')
parser.add_argument('-r', '--retries', action='store', type=int, default=60, help='total retries')
parser.add_argument('--test', action='store_true')

opt = parser.parse_args()
curr_branch = opt.branch
interval = opt.interval
test_mode = opt.test
total_retries = opt.retries

try:
    with open(opt.config,"r") as config_fh:
         MASTER_COMPONENTS = yaml.safe_load(config_fh)
except Exception as e:
    print(f"unable to read config file \"{opt.config}\": {e}")
    exit(1)

print(MASTER_COMPONENTS)

for k,v in MASTER_COMPONENTS.items():
    master = get_component(curr_branch, v['prefix'])
    if master is not None: 
        prefix = v['prefix']
        components_to_combine =  v['combine']
        break 
else:
    print(f"{curr_branch} not in watched master components: { ','.join(MASTER_COMPONENTS.keys()) }")
    exit(0)

#print(f"prefix={prefix} components_to_combine={components_to_combine} master={master}")
#exit(0)

pr_list={}
merge_id = {}
curr_pr_id = 0
retries=0


while retries < total_retries:
    time.sleep(interval)

    retries += 1
    print(f"try {retries}")

    raw_prs = call_gh(False, "pr","list","--json","number,headRefName", "--search", "label:konflux-nudge")
    pr_list = json.loads(raw_prs)

    for pr in pr_list:

        component = get_component(pr["headRefName"])
    
        if component == master:
            print(f"setting curr_branch={curr_branch}")
            curr_pr_id = str(pr["number"])
            continue

        if component is None or component not in components_to_combine:
            continue

        if component in components_to_combine:
            merge_id[component] = str(pr["number"])


    not_found = list(set(components_to_combine).difference(merge_id.keys()))

    if not_found :
        print(f"not found components { ','.join(not_found)}")
    else:
        retries = total_retries + 1

if not_found:
   print(f"timeout, not found components { ','.join(not_found)}")
   exit(1) 

print(merge_id)

for pr_number in merge_id.values():
    print("call_gh", "pr", "edit", pr_number, "--base", curr_branch)
    out=call_gh(test_mode, "pr", "edit", pr_number, "--base", curr_branch)
    print(out)

    print("call_gh", "pr", "merge", pr_number, "--squash")
    out=call_gh(test_mode, "pr", "merge", pr_number, "--squash")
    print(out)

print("call_gh", "pr", "edit", curr_pr_id, "--add-label", "ok-to-merge")

call_gh(test_mode, "pr", "edit", str(curr_pr_id), "--add-label", "ok-to-merge")

 
exit(0)
