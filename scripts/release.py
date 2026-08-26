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
#import kmm_konflux.yaml_config

#test_mode=False
current_versions = {}

def read_config_json(filename:str ="config/pullspec_config.json"):
    """
        read the data we need from config/pullspec_config.json 
        returns a dict[str,Any]
    """
    try:
        with open(filename,"r") as config_fh:
            config_dict = json.load(config_fh)
    except Exception as e:
        print(f"unable to read config file \"{filename}\": {e}", file=sys.stderr )
        sys.exit(1)
    return config_dict

class ReleaseContext:
    def __init__(self,
                    config: dict,
                    token:str,
                    pr_number=None,
                    application:str = None,
                    konflux_commit:str = None,
                    relnumber=None):
        if pr_number:
            self.pr_number = pr_number
            self._pr = self._get_pr()
            self.application = self._pr_application_number(self._pr["headRefName"])
            self.konflux_commit = self._pr_konflux_commit()
            self.application_name = self._pr_application_name()
        else:
            self.pr_number = None
            self.konflux_commit = konflux_commit
            self.application = self._pr_application_number(application)
            self.application_name = application
        self.relnumber = relnumber
        self.config = config
        self.kmm_commit = None
        self.token = token
        self.components = self.get_components()

    def get_components(self):
        kube_components = Konflux(self.config['api_url'],
                        self.token,
                        self.config['namespace'],
                        "appstudio.redhat.com/v1alpha1",
                        "components",
                        resolve_tls_verify(self.config))
        component_list = kube_components.get(label_selector={"application": self.application_name})
        try:
            if component_list[0].get('items') == []:
                print(f"no components found labelled \"application\": {self.application_name}")
                return None
        except (KeyError,IndexError):
            pass
        return component_list

    def get_relnumber(self):
        if self.relnumber:
            return self.relnumber
        kube_snapshots = Konflux(self.config['api_url'],
                        self.token,
                        self.config['namespace'],
                        "appstudio.redhat.com/v1alpha1",
                        "snapshots",
                        resolve_tls_verify(self.config))
        snap_list = kube_snapshots.get(label_selector={"application": self.application_name})
        #snap_list = kube_snapshots.get(label_selector={"application": "kmm-2-7"})
        try:
            if snap_list[0].get('items') == []:
                self.relnumber = 1
        except (KeyError,IndexError):
            self.relnumber = 1

        relnumber = 0
        for snap in snap_list:
            branch_regexp=r"-r([0-9]+)$"
            matches = re.search(branch_regexp, snap['metadata']['name'])
            if matches is not None:
                relnumber = max(relnumber, int(matches.group(1)))

        self.relnumber = relnumber+1
        return self.relnumber

    def _get_pr(self):
        try:
            raw_pr = git_commands.call_gh(False,
                                        "pr",
                                        "view",
                                        "--json","title,headRefName,body",
                                        self.pr_number)
        except Exception as e:
            print(f"raw pr list error: {e}")

        try:
            return json.loads(raw_pr)
        except json.decoder.JSONDecodeError as e:
            print(f"pr view error {self.pr_number}: {e}")
            print(raw_pr)
            sys.exit(1)

    def _pr_application_number(self, content:str):
        #branch_regexp=r"konflux/component-updates/.*-([0-9]-[0-9])$"
        branch_regexp=r"-([0-9-]+)$"
        #matches = re.match(branch_regexp, self._pr["headRefName"])
        matches = re.search(branch_regexp, content)
        if matches is None:
            return None
        return matches.group(1)

    def _pr_application_name(self):
        return f"kmm-{self.get_application_number()}"

    def _pr_konflux_commit(self) -> str:
        commit_regexp = r"=(.*)\'"
        matches = re.search(commit_regexp, self._pr['body'])
        if matches is None:
            return None
        return matches.group(1)

    def get_release_number(self):
        try:
            settings = kmm_konflux.config.read_key_value_file(
                       f"release-{self.get_application_number().replace('-','.')}/build_settings.conf")
            return settings['RELEASE'].replace(".","")
        except (FileNotFoundError, KeyError):
            if len(self.config['stage']):
                return self.config['stage'][-1].replace(".","")
            return self.config['prod'][-1].replace(".","")

    def get_application_number(self):
        return self.application

    def get_application_name(self):
        return self.application_name

    def get_namespace(self):
        return self.config['namespace']

    def get_konflux_commit(self, short=False) -> str:
        if short:
            return self.konflux_commit[:7]
        return self.konflux_commit

    def get_kmm_commit(self, short=False): #konflux_commit, version):
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
        if self.kmm_commit:
            if short:
                return self.kmm_commit[:7]
            return self.kmm_commit

        v = self.get_application_number().replace("-",".")
        konflux_commit = self.get_konflux_commit()
        #v = version.replace("-",".")
        out=git_commands.call_git(False,
                                    "diff",
                                    f"{konflux_commit}..HEAD",
                                    f"release-{v}/kernel-module-management")
        if out.startswith("fatal:"):
            return None
        if not out:
            out=git_commands.call_git(False,
                                    "submodule",
                                    "status",
                                    f"release-{v}/kernel-module-management")
            self.kmm_commit = out.split(" ")[1]
        else:
            self.kmm_commit = out.split(" ")[-1]

        if short:
            return self.kmm_commit[:7]
        return self.kmm_commit


class KonfluxResource:
    """Base for Snapshot / Release manifests."""

    def __init__(self, name, namespace, application, config:dict, token:str):
        self.manifest = {}
        self.name = name
        self.namespace = namespace
        self.application = application
        self.token = token
        self.client = None

    @property
    def name(self) -> str:
        return self.manifest["metadata"]["name"]

    @name.setter
    def name(self, name) -> str:
        self.manifest["metadata"]["name"] = name

    @property
    def namespace(self) -> str:
        return self.manifest["metadata"]["namespace"]

    @namespace.setter
    def namespace(self, namespace) -> str:
        self.manifest["metadata"]["namespace"] = namespace

    def add_labels(self, labels:dict):
        self.manifest['metadata']['labels'] = self.manifest['metadata'].get('labels',{}) | labels

    def get_labels(self):
        return self.manifest['metadata'].get('labels',{})

    def to_yaml(self) -> str:
        return yaml.dump(self.manifest, default_flow_style=False, sort_keys=False)

    def create(self, dry_run: bool = False) -> str:
        """Create via API (or print YAML). Returns the resource name."""
        print("---")
        print(self.to_yaml())
        if dry_run:
            return self.name

        resp = self.client.create(self.manifest)
        if isinstance(resp, list):
            created = resp[0]["metadata"]["name"]
        elif isinstance(resp, dict):
            created = resp.get("metadata", {}).get("name", self.name)
        else:
            raise RuntimeError(f"create {self.manifest['kind']} returned unusual result: {resp}")
        print(f"{self.manifest["kind"]}={created}")
        return created


class Snapshot(KonfluxResource):
    def __init__(self, name: str, namespace: str, application:str, config:dict, token:str):
        #self.name = name
        #self.namespace = namespace
        self.application = application
        self.client = Konflux(config['api_url'],
                        token,
                        config['namespace'],
                        "appstudio.redhat.com/v1alpha1",
                        "snapshots",
                        resolve_tls_verify(config))

        self.components = []
        self.manifest = yaml.safe_load(f"""
            apiVersion: appstudio.redhat.com/v1alpha1
            kind: Snapshot
            metadata:
              name: {name}
              namespace: {namespace}
              labels: 
                application: {self.application}
            spec:
              application: {self.application}
              components: []
        """)

    def add_component(self, component: dict):
        self.manifest['spec']['components'].append({
                "name": component['metadata']['name'],
                "containerImage": component['status']['lastPromotedImage'],
                "source": {
                   "git": { 
                       "context": component["spec"]["source"]["git"].get("context", "main"),
                       "dockerfileUrl": component["spec"]["source"]["git"]["dockerfileUrl"],
                       "revision": component["status"]["lastBuiltCommit"],
                       "url": component["spec"]["source"]["git"]["url"],
                       }
                   }
                })


class Release(KonfluxResource):
    def __init__(self,
                    namespace,
                    pr: ReleaseContext,
                    config:dict,
                    token:str,
                    environment:str,
                    release:int = None,
                    snapshot_name:str = None):
        self.pr= pr
        self.application = pr.get_application_name()
        self.config = config
        self.token = token
        self.components = []
        self.snapshot_name = snapshot_name
        self.snapshot = None
        self.env = environment
        if release:
            self.release = release
        else:
            self.release = pr.get_relnumber()

        self.client = Konflux(config['api_url'],
                        token,
                        config['namespace'],
                        "appstudio.redhat.com/v1alpha1",
                        "releases",
                        resolve_tls_verify(config))

        self.manifest = yaml.safe_load(f"""
            apiVersion: appstudio.redhat.com/v1alpha1
            kind: Release
            metadata:
              labels:
                appstudio.openshift.io/application: {self.application}
                application: {self.application}
                version: "{pr.get_application_number()}"
                commit: "{pr.get_konflux_commit()}"
                short: "{pr.get_konflux_commit(short=True)}"
                relnumber: "{pr.get_release_number()}"
              name: {pr.get_application_name()}-{self.env}-{pr.get_release_number()}-{pr.get_konflux_commit(short=True)}-r{self.release}
              namespace: {namespace}
            spec:
              releasePlan: {pr.get_application_name()}-release-{self.env}
              snapshot: {snapshot_name}
            """)
        if pr.get_kmm_commit():
            self.manifest['metadata']['labels']['kmmcommit'] = pr.get_kmm_commit()
            self.manifest['metadata']['labels']['kmmshort'] = pr.get_kmm_commit(short=True)

    def add_component(self, component: dict):
        self.components.append(component)

    def create_snapshot(self, dry_run):
        if not self.snapshot_name:
            self.snapshot = Snapshot(self.name,
                                    self.namespace,
                                    self.application,
                                    self.config,
                                    self.token)

            for c in self.components:
                self.snapshot.add_component(c)
            self.snapshot.add_labels(self.get_labels())
            for c in self.pr.components:
                self.snapshot.add_component(c)
            #self.snapshot_name = self.snapshot.create(dry_run=dry_run)
            self.snapshot_name=self.snapshot.name
        return self.snapshot_name

#    def add_release_notes(self, filename=None):
#        if not filename:
#            filename = f"release-{version.replace("-",".")}/release-{current_versions[version][-1]}/release_notes.yaml"
#
#        try:
#            new_release['spec']['data'] = kmm_konflux.yaml_config.load_config_dict(filename)
#        except FileNotFoundError:
#            pass

    def create(self, dry_run: bool = False) -> str:
        if not self.snapshot_name:
            self.create_snapshot(dry_run)
        self.snapshot_name = self.snapshot.create(dry_run)
        self.manifest['spec']['snapshot'] = self.snapshot_name
        super().create(dry_run)



if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', action='store', required=False,
                        default="config/pullspec_config.json",
                        help='json config file (default: config/pullspec_config.json) ')
    parser.add_argument('-n', '--namespace', action='store', required=False,
                        default=None,
                        help='namespace to create objects in')
    parser.add_argument('-t', '--token', action='store', required=False,
                        default=None,
                        help='token to access k8s')
    parser.add_argument('-e', '--env', action='store', required=False,
                        default="staging",
                        help='environment to release to (prod|staging)')
    parser.add_argument('-p', '--pr', action='store', required=False,
                        default="",
                        help='release application from pr')
    parser.add_argument('-r', '--release', action='store', required=False,
                        help='release number to apply (e.g. 10)')
    parser.add_argument('-a', '--application', action='store', required=False, default=None,
                        help='Application to release (e.g kmm-2-6)')
    parser.add_argument('-g', '--commit', action='store', required=False, default=None,
                        help='konflux commit to release')
    parser.add_argument('-s', '--snapshot', action='store', required=False,
                        default=None,
                        help='snapshot to release (requires --application)')
    parser.add_argument('--test', action='store_true', default=False)

    opt = parser.parse_args()

    token = opt.token
    if opt.env not in ("prod", "staging"):
        print("--env should be one of 'prod' or 'staging'")
        sys.exit(0)
    env = opt.env

    if not opt.pr:
        if not opt.application or not opt.commit:
            print("either --pr OR both --commit and --application are required")
            sys.exit(0)

    try:
        config = kmm_konflux.config.load_config_dict(opt.config)
    except ValueError as e:
        print(f"Failed to load config {opt.config}: {e}", file=sys.stderr)
        sys.exit(2)
    if not config.get("api_url"):
        print(f"Config file {opt.config} must contain non-empty 'api_url'")
        sys.exit(2)

    namespace = opt.namespace or config["namespace"]

    relpr = ReleaseContext(
                    config,
                    token,
                    pr_number=opt.pr,
                    application=opt.application,
                    konflux_commit=opt.commit)
    #print(relpr.get_relnumber())

    release = Release(
                namespace,
                relpr,
                config,
                token,
                opt.env,
                release=opt.release)

    release.create(dry_run=opt.test)
