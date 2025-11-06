#!/bin/bash

TEST=""
if [ "$1" == "-t" -o "$1" == "--test" ]; then
    TEST="test"
fi


python update_fbc.py -t fbc/op-catalog-template.json -c operator-bundle-2-5 --pullspecdir release-2.5/pullspecs -f release-2.5/build_settings.conf > op.tmp
python update_fbc.py -t fbc/hub-catalog-template.json -c hub-operator-bundle-2-5 --pullspecdir release-2.5/pullspecs -f release-2.5/build_settings.conf> hub.tmp

echo opm alpha render-template basic fbc/op-catalog-template.json
opm alpha render-template basic op.tmp > fbc/op/kernel-module-management/catalog.json

if [ $? -ne 0 ]; then
    echo "opm failed"
    exit 1
fi

echo opm alpha render-template basic fbc/op-catalog-template.json --migrate-level=bundle-object-to-csv-metadata
opm alpha render-template basic op.tmp --migrate-level=bundle-object-to-csv-metadata > fbc/op-migrated/kernel-module-management/catalog.json
if [ $? -ne 0 ]; then
    echo "opm failed"
    exit 1
fi

echo opm alpha render-template basic fbc/hub-catalog-template.json
opm alpha render-template basic hub.tmp > fbc/hub/kernel-module-management-hub/catalog.json
if [ $? -ne 0 ]; then
    echo "opm failed"
    exit 1
fi

echo opm alpha render-template basic fbc/hub-catalog-template.json --migrate-level=bundle-object-to-csv-metadata
opm alpha render-template basic hub.tmp --migrate-level=bundle-object-to-csv-metadata > fbc/hub-migrated/kernel-module-management-hub/catalog.json
if [ $? -ne 0 ]; then
    echo "opm failed"
    exit 1
fi
