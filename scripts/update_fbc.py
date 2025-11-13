#!/usr/bin/python

import os
import json
import yaml
import argparse

import rh_kmm_konflux.rh_kmm_konflux_helpers as helpers


parser = argparse.ArgumentParser()

parser.add_argument('-n', '--namespace', default="rh-kmm-tenant", help='namespace to query')
parser.add_argument('-k', '--kubeconfig', action='store', required=False, help='kubeconfig file')
parser.add_argument('-r', '--release', action='store', required=True, default=None, help='name of release object for bundles')
parser.add_argument('-t', '--template', action='store', required=False, default="templates/hub-catalog-template.json,templates/op-catalog-template.json", help='comma seperated list of templates to process')
parser.add_argument('-o', '--outdir', action='store', required=False, default="fbc/", help='directory to write to')


opt = parser.parse_args()
#write = opt.write
template_list = opt.template.split(",")

try:
    release = helpers.Release(opt.kubeconfig, opt.namespace, name=opt.release)
except Exception as e:
    print(f"ERROR: getting client failed {e}")
    sys.exit(0) 


for r in release.objects:
    #print(r.metadata.name)
    kmm_version=f".v{r.metadata.labels.kmm}"
    try:
        filtered_snapshot = json.loads(r.status.artifacts.filtered_snapshot)
    except AttributeError:
       print(f"{r.metadata.name} does not have status.artifacts.filtered_snapshot, release failed?") 

if not kmm_version:
    print("no KMM version found")
    kmm_version=""


images = {}
for c in filtered_snapshot['components']:
    print(f"filtered_snapshot['components'] ={c}")
    sha = c["containerImage"].split("@")[1]
    try:
        name = f"{c["rh-registry-repo"].split("/")[-1]}{kmm_version}"
        images[name] = f"{c['rh-registry-repo']}@{sha}"
    except KeyError:
        name = f"{c["repositories"][0]["rh-registry-repo"].split("/")[-1]}{kmm_version}"
        images[name] = f"{c["repositories"][0]['rh-registry-repo']}@{sha}"


#print(images)


for t in template_list:
    template = helpers.read_json_file(t)
    for i in template["entries"]:
        if i["schema"] == "olm.bundle" and images.get(i["name"]):
            i["image"] = images.get(i["name"])

    if opt.outdir:
        filename = os.path.basename(t)
        outfile = f"{opt.outdir}/{filename}"
        print(f"{filename=} {outfile=}")
        with open(outfile, 'w') as file:
            json.dump(template, file, indent=4)
    else:
        print(json.dumps(template, indent=4))

exit(0)

#try:
#    with open(opt.command,"r") as config_fh:
#         OPM_CONFIG = yaml.safe_load(config_fh)
#except Exception as e:
#    print(f"unable to read config file \"{opt.command}\": {e}")
#    exit(1)
#
#
#for cmd in OPM_CONFIG:
#    print(cmd['template'])
#    template = helpers.read_json_file(cmd['template'])
#    for i in template["entries"]:
#        if i["schema"] == "olm.bundle" and images.get(i["name"]):
#            i["image"] = images.get(i["name"])
#
#
##exit(0)
#    tmp_file="tmp.fbc"
##    if opt.write:
#    with open(tmp_file, 'w') as file:
#        json.dump(template, file, indent=4)
##        print(f"{' '.join(cmd['args'])} {tmp_file} > {cmd['output']}")
##        os.system(f"{' '.join(cmd['args'])} {tmp_file} > {cmd['output']}")
##    else:
##        print(json.dumps(template, indent=4))
#
#    
#    
