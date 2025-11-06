import json
import os
import sys
import fnmatch
import re
from kubernetes import config
from openshift.dynamic import DynamicClient

class Konflux:
    def __init__(self, kubeconfig, namespace):
        self.kubeconfig = kubeconfig

        self.dyn_client = self.get_client()
        self.namespace = namespace

        self.k8s_objects = {
            'Component': 'appstudio.redhat.com/v1alpha1',
            'Snapshot': 'appstudio.redhat.com/v1alpha1',
            'Application': 'appstudio.redhat.com/v1alpha1',
            'Release': 'appstudio.redhat.com/v1alpha1',
            }

    def get_client(self):
        if not self.kubeconfig:
            kubeconfig = os.getenv("KUBECONFIG")

        try:
            k8s_client = config.new_client_from_config(kubeconfig)
            return DynamicClient(k8s_client)
        except Exception as e:
            print(f"ERROR: get_client:  getting client failed {e}")


    def get_objects(self, kind, name=None, label_selector=None, field_selector=None):
        if not self.k8s_objects.get(kind):
            print(f"kind {kind} not found")
            return None

        try:
            objects = self.dyn_client.resources.get(api_version = self.k8s_objects[kind],
                                kind=kind)
            return objects.get(namespace = self.namespace,
                                label_selector=label_selector,
                                field_selector=field_selector)
        except Exception as e:
            print(f"ERROR: get_objects: getting {kind} failed {e}")
            sys.exit(1)
    
    def get_components(self, label_selector=None, field_selector=None):
        return self.get_objects('Component', label_selector=label_selector, field_selector=field_selector)

    def get_snapshots(self, label_selector=None, field_selector=None):
        return self.get_objects('Snapshot', label_selector=label_selector, field_selector=field_selector)

    def get_applications(self, label_selector=None, field_selector=None):
        return self.get_objects('Application', label_selector=label_selector, field_selector=field_selector)



class KonfluxObj():
    def __init__(self, kubeconfig, namespace, api, kind,
                            name=None,
                            label_selector=None,
                            field_selector=None,
                            match=None):

        self.kubeconfig = kubeconfig

        self.dyn_client = self.get_client()
        self.namespace = namespace
        self.api = api
        self.kind = kind

        self.objects = self.get_objects( name=name,
                                        label_selector=label_selector,
                                        field_selector=field_selector,
                                        match=match)

    def get_client(self):
        if not self.kubeconfig:
            kubeconfig = os.getenv("KUBECONFIG")

        try:
            k8s_client = config.new_client_from_config(kubeconfig)
            return DynamicClient(k8s_client)
        except Exception as e:
            print(f"ERROR: get_client:  getting client failed {e}")

    def items(self):
        #return self.objects['items']
        return self.objects

    def get_objects(self, name=None, label_selector=None, field_selector=None, match = None):
        try:
            resources = self.dyn_client.resources.get(api_version = self.api,
                                kind=self.kind)
            objects = resources.get(name= name, namespace = self.namespace,
                                label_selector=label_selector,
                                field_selector=field_selector)

            if not match:
                return objects.get('items', [objects])
                #return objects['items']
                        
            out = []
            (path, value) = match.split("=")
            for obj in objects['items']:
                if fnmatch.fnmatch( self._get_value(obj, path), value):
                    out.append(obj)
            return out

        except Exception as e:
            print(f"ERROR: get_objects: {e}")
            sys.exit(1)

    def _get_value(self, obj, path):
        for c in path.split("."):
            obj = obj.__getattr__(c)
        return obj

    def new_yaml(self, metadata: dict, spec: dict):
        return {
            "apiVersion": self.api,
            "kind": self.kind,
            "metadata": metadata,
            "spec": spec
        }

    
    def create(self, metadata: dict, spec: dict):
        self.releases.create(body=self.new_yaml(metadata, spec), namespace=self.namespace) 



#class Release(KonfluxObj):
#    def __init__(self, kubeconfig, namespace, name=None, label_selector=None, field_selector=None, match=None):
#        super().__init__(kubeconfig, 
#                            namespace, 
#                            'appstudio.redhat.com/v1alpha1', 
#                            'Release',
#                            name=name,
#                            label_selector=label_selector,
#                            field_selector=field_selector,
#                            match=match)

 
class Component(KonfluxObj):
    def __init__(self, kubeconfig, namespace, name=None, label_selector=None, field_selector=None, match=None):
        super().__init__(kubeconfig, 
                            namespace, 
                            'appstudio.redhat.com/v1alpha1', 
                            'Component',
                            name=name,
                            label_selector=label_selector,
                            field_selector=field_selector,
                            match=match)

    def get_last_promoted(self, wanted_components=[], wanted_commit=None):
        image_shas={}
        for comp in self.items():
            #print(f"comp.metadata.name={comp.metadata.name}")
            #breakpoint()
            if wanted_commit is not None:
                try:
                    if not comp.status.lastBuiltCommit.startswith(wanted_commit):
                        continue
                except AttributeError:
                    continue 

            if wanted_components and comp.metadata.name in wanted_components:
                image_shas[comp.metadata.name] = comp.status.lastPromotedImage
            elif not wanted_components:
                image_shas[comp.metadata.name] = comp.status.lastPromotedImage

        return image_shas
    

    def by_application(self, wanted_apps: list[str] =None) -> dict[str,list[str]]:
        """
            wanted_apps: a list of application names to return.
            returns:
                a dict - key: applications value: list of components in that application
        """
        applications = {}
        for comp in self.items():
            app = comp['spec']['application'] 

            if wanted_apps is None or (app in wanted_apps):
                if applications.get(app):
                    applications[app].append(comp['metadata']['name'])
                else:
                    applications[app] = [comp['metadata']['name']]

        return applications



class Snapshot(KonfluxObj):
    def __init__(self, kubeconfig, namespace, name=None, label_selector=None, field_selector=None, match=None):
        super().__init__(kubeconfig, 
                            namespace, 
                            'appstudio.redhat.com/v1alpha1', 
                            'Snapshot',
                            name=name,
                            label_selector=label_selector,
                            field_selector=field_selector,
                            match=match)

    def latest_snapshots(self, applications: dict[str, list[str]], last_promoted: dict[str,str]) -> dict[str,str]:
        """
            applications:  dict - key: applications value: list of components in that application
            last_promoted: dict - key: component_name, value: image_name
            return:
                dict - key: application_name, value: snapshot_name
        """
        release_snapshots={}

        #for snap in snapshotList['items']:
        for snap in self.items():
            if not applications.get(snap['spec']['application']):
                continue

            expect_components = applications[snap['spec']['application']]

            if len(snap['spec']['components']) != len(expect_components):
                continue

            for i in snap['spec']['components']:
                if last_promoted.get(i['name']) !=  i['containerImage']:
                    break
            else:
                release_snapshots[snap['spec']['application']] = snap['metadata']['name']

        return release_snapshots

    


class Release(KonfluxObj):
    def __init__(self, kubeconfig, namespace, name=None, label_selector=None, field_selector=None, match=None):
        super().__init__(kubeconfig, 
                            namespace, 
                            'appstudio.redhat.com/v1alpha1', 
                            'Release',
                            name=name,
                            label_selector=label_selector,
                            field_selector=field_selector,
                            match=match)

    def _get_latest_rel(self) -> (str,int):
        latest = 0.1
        name = ""
        for o in self.objects:
            #m = re.search(r".*-r([0-9]+-[0-9]+$", o.metadata.name)
            m = re.search(r".*-r([0-9]+([-.][0-9]+)*)$", o.metadata.name)
            if m:  #.group:
                relnum = float(m.group(1).replace("-", "."))
                if relnum > latest:
                    latest = relnum
                    name = o.metadata.name
        return (name,latest)

    def get_next_rel_number(self) -> str:
        relnum = int(self._get_latest_rel()[1]) 
        return f"r{relnum + 1}-1" 

    def get_latest_rel(self) -> str:
        relnum = int(self._get_latest_rel()[1]) 
        return f"r{relnum}-1" 

    def get_latest_rel_number(self) -> float:
        return self._get_latest_rel()[1]

    def get_latest_rel_name(self) -> str:
        return self._get_latest_rel()[0]

#    def get_latest_rel_number(self) -> int:
#        latest = 0.0
#        for o in self.objects:
#            #m = re.search(r".*-r([0-9]+-[0-9]+$", o.metadata.name)
#            m = re.search(r".*-r([0-9]+([-.][0-9]+)*)$", o.metadata.name)
#            if m.group:
#                relnum = float(m.group(1).replace("-"))
#                if relnum > latest:
#                    latest = relnum
#                #if int(m.group(1)) > latest:
#                #    latest = int(m.group(1))
#        return latest
#
#    def get_latest_rel_name(self) -> str:
#        latest = 0
#        name = ""
#        for o in self.objects:
#            m = re.search(r".*-r([0-9]+)-[0-9]+$", o.metadata.name)
#            if m.group:
#                if int(m.group(1)) > latest:
#                    latest = int(m.group(1))
#                    name = o.metadata.name
#        return name
#
def get_last_promoted(componentList, wanted_components=[]):
    image_shas={}
    for comp in componentList['items']:
        if wanted_components and comp.metadata.name in wanted_components:
            image_shas[comp.metadata.name] = comp.status.lastPromotedImage
        elif not wanted_components:
            image_shas[comp.metadata.name] = comp.status.lastPromotedImage

    return image_shas



def write_pullspecs(image_shas, outdir):
    for k,v in image_shas.items():

        OUTFILE = f"{outdir}/{k}.yaml"
        try:
            with open(OUTFILE, "w") as file:
                file.write(v)
        except  OSError as e:
            print(f"Error writing Pullspecs to {OUTFILE}: {e}")


def read_json_file(filename: str):
    """Read a YAML file and return its contents."""
    try:
        with open(filename) as stream:
            return json.load(stream)
    except FileNotFoundError:
        print(f"Error: JSON file '{filename}' not found")
        return None
    except (json.JSONDecodeError, UnicodeDecodeError)  as exc:
        print(f"Error decoding JSON file '{filename}': {exc}")
        return None
    except Exception as e:
        print(f"Error reading JSON file '{filename}': {e}")
        return None

def read_key_value_file(filename="build_settings.conf"):
    data = {}
    with open(filename, "r") as file:
        for line in file:
            line = line.strip()
            if line and "=" in line:
                key, value = line.split("=", 1)
                data[key.strip()] = value.strip()
    return data


