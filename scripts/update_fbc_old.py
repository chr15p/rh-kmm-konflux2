#!/usr/bin/python

import json
import argparse

#import getLastPromotedImage

import rh_kmm_konflux.rh_kmm_konflux_helpers as helpers


def get_bundles(buildags):
    return {
            f"{buildags['PRODUCT']}-{buildags['OP_BUNDLE']}.v{buildags['RELEASE']}": \
                f"{buildags['OP_BUNDLE']}-{buildags['VERSION'].replace('.','-')}", \
            f"{buildags['PRODUCT']}-{buildags['HUB_BUNDLE']}.v{buildags['RELEASE']}": \
                f"{buildags['HUB_BUNDLE']}-{buildags['VERSION'].replace('.','-')}"
            }
    

def read_key_value_file(filename="build_settings.conf"):
    data = {}
    with open(filename, "r") as file:
        for line in file:
            line = line.strip()
            if line and "=" in line:
                key, value = line.split("=", 1)
                data[key.strip()] = value.strip()
    return data


def image_name(production, name, image, buildargs):
    if production:
        sha = image.split("@")[1] 
        basename=name.split(".")[0]
        return f"{buildargs['REPO']}/{basename}@{sha}"
    else:
        return image


#bundles = {
#    "kernel-module-management-operator-bundle.v2.5.0": "operator-bundle-2-5",
#    "kernel-module-management-hub-operator-bundle.v2.5.0":  "hub-operator-bundle-2-5"
#}


parser = argparse.ArgumentParser()

parser.add_argument('-n', '--namespace', default="rh-kmm-tenant", help='namespace to query')
parser.add_argument('-t', '--template', default=None, help='template file to update')
parser.add_argument('-k', '--kubeconfig', action='store', required=False, help='kubeconfig file')
parser.add_argument('-o', '--output', action='store', required=False, default=None, help='file to write')
parser.add_argument('-c', '--component', action='store', required=True, help='file to write')
parser.add_argument('-p', '--pullspecdir', action='store', required=False, help='dir to write pullspecs to dir')
parser.add_argument('-f', '--config', action='store', required=True, help='location of buildargs file')
parser.add_argument('-r', '--release', action='store_true', required=False, help='build with pullspecs for release')
opt = parser.parse_args()
templatefile = opt.template
outputfile = opt.output
component = opt.component

buildargs = read_key_value_file(opt.config)
bundles = get_bundles(buildargs)

try:
    konflux = helpers.Konflux(opt.kubeconfig, opt.namespace)
except Exception as e:
    print(f"ERROR: getting client failed {e}")
    sys.exit(0) 

try:
    components = konflux.get_components()
    image_shas = helpers.get_last_promoted(components, [])
except Exception as e:
    print(f"ERROR: getting components failed {e}")
    sys.exit(0) 


#dyn_client = getLastPromotedImage.get_client(opt.kubeconfig)
##components = getLastPromotedImage.get_components(dyn_client, opt.namespace)
#image_shas = getLastPromotedImage.get_last_promoted(components, component )
#print(image_shas)

template = helpers.read_json_file(templatefile)

for i in template["entries"]:
    if i["schema"] == "olm.bundle":
        #print(f"i={i}")
        #print(bundles.get(i["name"]))
        bundle_name = bundles.get(i["name"])
        if bundle_name and image_shas.get(bundle_name):
            #i["image"] = image_shas.get(bundle_name)
            #print(opt.release, i["name"], image_shas.get(bundle_name), buildargs)
            i["image"] = image_name(opt.release, i["name"], image_shas.get(bundle_name), buildargs)
    
            #print(f"after={i}")


if outputfile:
    with open(outputfile, 'w') as file:
        json.dump(template, file, indent=4)
else:
    print(json.dumps(template, indent=4))


if opt.pullspecdir:
    helpers.write_pullspecs(image_shas, opt.pullspecdir)

