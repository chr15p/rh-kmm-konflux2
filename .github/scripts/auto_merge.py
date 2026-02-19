#!/usr/bin/python

import argparse
import json
import yaml

import git_commands

TEST_MODE = False

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    #parser.add_argument('-c', '--config', action='store', required=True, default="nudges.yaml", help='yaml config file ')
    parser.add_argument('-l', '--label', action='store', required=False, default="ok-to-merge", help='label to merge')
    parser.add_argument('--test', action='store_true', default=False)

    opt = parser.parse_args()
    label = opt.label
    TEST_MODE = opt.test

    raw_prs = git_commands.call_gh(False, "pr","list","--json","number", "--search", f"label:{label}")
    try:
        pr_list = json.loads(raw_prs)
    except json.decoder.JSONDecodeError as e:
        print(f"pr list error: {e}")
        sys.exit(1)


    for pr in pr_list:
        print("call_gh", "pr", "merge", pr['number'], "--squash")
        out=git_commands.call_gh(TEST_MODE, "pr", "merge", pr['number'], "--squash", "--delete-branch")
        if out:
            print(out)
        #call_gh(test_mode, "pr", "edit", str(curr_pr_id), "--add-label", "ok-to-merge")
    
