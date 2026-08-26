#!/usr/bin/python

"""
    merge several nudge PRs into one to reduce git log noise and konflue rebuilds
    run as:
        ./combine_nudges.py  --pr $PR_NUMBER_TO_MERGE_INTO
    e.g.
        ./combine_nudges.py  --pr 1700
"""

import sys
import re
import argparse
import json
import time
#import yaml
#import subprocess

#import scripts.kmm_konflux.git_commands as git_commands
from kmm_konflux import git_commands


TEST_MODE = True

def read_config_json(filename:str ="config/pullspec_config.json"):
    """
        read the data we need from config/pullspec_config.json 
        returns a dict[str,Any]
    """
    release_config = {}
    try:
        with open(filename,"r") as config_fh:
            #master_components = yaml.safe_load(config_fh)
            config_dict = json.load(config_fh)
        release_config["bundle"] = config_dict["bundle"]
        release_config["operand"] = config_dict["operand"]
        release_config["operand-label"] = config_dict["operand-label"]
        release_config["bundle-label"] = config_dict["bundle-label"]
    except Exception as e:
        print(f"unable to read config file \"{filename}\": {e}", file=sys.stderr )
        sys.exit(1)
    return release_config


class NudgePullRequest:
    """
        instance of a single github PR
    """
    def __init__(self, pr_json):
        self._json = pr_json
        self._version = None
        self._component = None
        self._kmm_commit = None

    def get_number(self):
        return self._json['number']

    def get_source_branch(self):
        return self._json['headRefName']

    def get_labels(self):
        return [ l['name']  for l in self._json['labels']]

    def get_author(self):
        return self._json['author']['login']

    def get_bot(self):
        return self._json['author']['is_bot']

    def get_konflux_commit(self) -> str:
        commit_regexp = r"=(.*)\'"
        matches = re.search(commit_regexp, self._json['body'])
        if matches is None:
            return None
        #print(f"{self.get_number()} {matches.group(1)}")
        #print(get_kmm_commit(matches.group(1), self.get_version()))
        return matches.group(1)

    def get_kmm_commit(self): #konflux_commit, version):
        """
            the konflux repo commit is embedded in the body text of a nudge PR, 
            so parse that with a regexp
            then use that to diff the release-2.X/kernel-module-management submodule mount point
            either it returns nothing and we use the current submodule commit
            or it returns a value (meaning the submodule has been updated since this PR was built)
            in which case we parse it out of the diff response.
            this works around an issue where if building multiple versions at the same time the 
            konflux commit might change between PRs for the same kmm commit
            (e.g you build 2-6 and 2-7, operator-2-7 fails so you merge the 2-6 operands and 
            rebuild operator-2-7, now the konflux commit has changed so operator-2-7 would been seen
             as a differnet build and not combine) 
        """
        if self._kmm_commit:
            #print(f"cached {self._kmm_commit}")
            return self._kmm_commit

        v = self.get_version().replace("-",".")
        konflux_commit = self.get_konflux_commit()
        #v = version.replace("-",".")
        out=git_commands.call_git(False,
                                    "diff",
                                    f"{konflux_commit}..HEAD",
                                    f"release-{v}/kernel-module-management")
        if not out:
            out=git_commands.call_git(False,
                                    "submodule",
                                    "status",
                                    f"release-{v}/kernel-module-management")
            self._kmm_commit = out.split(" ")[1]
        else:
            self._kmm_commit = out.split(" ")[-1]

        return self._kmm_commit


    def get_component_name(self):
        if self._component is None:
            branch_regexp=r"konflux/component-updates/.*component-update-([a-zA-Z-]+)-([0-9]-[0-9])"
            matches = re.match(branch_regexp, self._json['headRefName'])
            if matches is None:
                self._component=None
                self._version=None
            self._component = matches.group(1)
            self._version = matches.group(2)
        return self._component

    def get_version(self):
        if self._version is None:
            self.get_component_name()
        return self._version

    def get_component_stage(self):
        #if self.get_component_name() in config.get("operand", []):
        if "bundle" in self.get_component_name():
            return "bundle"
        return "operand"




class NudgeCombiner:
    def __init__(self,
                    curr_pr_number: int,
                    config: dict,
                    dry_run:bool = False,
                    labels:str ="konflux-nudge"):
        self.dry_run = dry_run
        self.curr_pr_number = curr_pr_number
        self.config = config
        self.labels = f"label:{labels}"
        ## self.curr_pull_request is a NudgePullRequest() object for the current pr
        self.curr_pull_request = None

        ## a dict of {int(pr_number): NudgePullRequest()}
        ## of all the PRs except curr_pull_request
        self.pull_requests = {}
        self.fetch_nudge_prs()

    def fetch_nudge_prs(self):
        pr_list=[]
        for i in [10,20, 40]:
            #  "--search", "label:konflux-nudge",
            raw_prs = git_commands.call_gh(
                            False,
                            "pr", "list",
                            "--search", self.labels,
                            "--json","number,headRefName,files,commits,labels,author,body")
            try:
                pr_list = json.loads(raw_prs)
                break
            except (TypeError, KeyError, json.decoder.JSONDecodeError) as e:
                print(f"pr list error retry in {i}s: {e}", file=sys.stderr)
                time.sleep(i)
        else:
            print(f"no relevant PRs found for label {self.labels}", file=sys.stderr )
            sys.exit(1)

        for i in pr_list:
            if i.get('number') == self.curr_pr_number:
                self.curr_pull_request = NudgePullRequest(i)
            else:
                self.pull_requests[ i.get('number')] = NudgePullRequest(i)
        if not self.curr_pull_request:
            print(f"unable to find PR {self.curr_pr_number} in open PRs", file=sys.stderr)
            sys.exit(2)

    #def get_pr(self, number):
    #    return self.pull_requests.get(number, None)

    #def get_pr_numbers(self):
    #    return self.pull_requests.keys()

    def _versions_filter(self, pr: NudgePullRequest):
        """ filter out other kmm versions"""
        #return self.pull_requests[pr_number].get_version() == self.curr_pull_request.get_version()
        return pr.get_version() == self.curr_pull_request.get_version()

    def _commit_filter(self, pr: NudgePullRequest):
        """ 
            filter out non-matching kmm_commits (presumably unmerged PRs for old builds)
            done by looking at the build commit and mapping that to a kmm submodule for this version
            then comparing that
        """
        #return self.pull_requests[pr_number].get_kmm_commit() == \
        #             self.curr_pull_request.get_kmm_commit()
        return pr.get_kmm_commit() == self.curr_pull_request.get_kmm_commit()

    def _stage_filter(self, pr: NudgePullRequest):
        """ filter out none matching stages (operands, or bundles)"""
        #return self.pull_requests[pr_number].get_component_stage() == \
        #            self.curr_pull_request.get_component_stage()
        return pr.get_component_stage() == self.curr_pull_request.get_component_stage()

    def _component_filter(self, pr: NudgePullRequest):
        """ filter out any component not in the wanted listi for this stage type"""
        stage = self.curr_pull_request.get_component_stage()
        #return self.pull_requests[pr_number].get_component_name() in self.config[stage]
        return pr.get_component_name() in self.config[stage]

    def filter(self, filters=None):
        """
            loop through all the prs aplly a series of filters to compare them to the current_pr
            and remove any that dont return True
            leaves self.pull_requests with just prs that are candidates for merging
        """
        to_drop=[]
        if not filters:
            filters = [self._versions_filter,
                        self._stage_filter,
                        self._commit_filter,
                        self._component_filter,
                        ]

        for filter_to_apply in filters:
            for k,v in self.pull_requests.items():
                if k in to_drop:
                    continue
                if not filter_to_apply(v):
                    print(f"dropping {k} due to {filter_to_apply.__name__}", file=sys.stderr)
                    #        f"{v.get_version()} !=" \
                    #        f"{self.curr_pull_request.get_version()})")
                    to_drop.append(k)

        for i in to_drop:
            #print(f"dropping {i}")
            del self.pull_requests[i]


    def ready_to_merge(self):
        """
            loop through prs in self.pull_requests and if we have all the ones listed 
            in the config file for this stage (operand or bundle) then return True
            otherwise we are still waiting for something so return False
        """
        missing = []
        component_names = [ i.get_component_name() for i in self.pull_requests.values() ]
        component_names.append(self.curr_pull_request.get_component_name())
        stage = self.curr_pull_request.get_component_stage()
        for c in self.config[stage]:
            if c not in component_names:
                missing.append(c)
        if not missing:
            print("all components ready to merge", file=sys.stderr)
            return True

        print(f"missing components: {missing}", file=sys.stderr)
        return False


    def get_label_to_apply(self):
        stage = self.curr_pull_request.get_component_stage()
        return self.config[f"{stage}-label"]

    def merge(self):
        """
            loop through the prs in self.pull_requests, change their target branch to be the 
            same as current_pr, then merge them into it
            this leaves us with one big PR which is labelled "ok-to-merge" or "ok-to-relase"
        """
        branch = self.curr_pull_request.get_source_branch()

        #for pr_number in self.pull_requests.keys():
        for pr_number in self.pull_requests:
            out=git_commands.call_gh(TEST_MODE, "pr", "edit", pr_number, "--base", branch)

        ## merge seperatly in case something went wrong with the edit
        #for pr_number in self.pull_requests.keys():
        for pr_number in self.pull_requests:
            out=git_commands.call_gh(TEST_MODE, "pr", "merge", pr_number, "--squash")

        label = self.get_label_to_apply()
        out=git_commands.call_gh(TEST_MODE,
                                    "pr",
                                    "edit",
                                    self.curr_pr_number,
                                    "--add-label",
                                    label)
        print(f"APPLIED={label}")
 

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument('-c', '--config', action='store', required=False,
                        default="config/pullspec_config.json",
                        help='json config file (default: config/pullspec_config.json')
    parser.add_argument('-p', '--pr', action='store', required=True,
                        default=None, help='pr number')
    parser.add_argument('--test', action='store_true', default=False)

    opt = parser.parse_args()
    CONFIG = read_config_json(opt.config)

    TEST_MODE = opt.test

    combiner = NudgeCombiner(int(opt.pr), CONFIG, labels="konflux-nudge")

    ## if the PR is already correctly labelled just return that
    ## this should facilitate rerunning
    label_to_apply = combiner.get_label_to_apply()
    if label_to_apply in combiner.curr_pull_request.get_labels():
        print(f"APPLIED={label_to_apply}")
        sys.exit(0)

    combiner.filter()
    #print(f"combiner:{combiner.pull_requests.keys()}")

    if combiner.ready_to_merge():
        print(f"no components missing: merge {combiner.pull_requests.keys()}", file=sys.stderr)
        combiner.merge()
