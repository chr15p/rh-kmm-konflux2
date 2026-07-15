#!/bin/bash

MODULE=$1
CONFIG=$2

COMMIT=$(git submodule status ${MODULE} | cut -f 2 -d ' ')
echo "KMM_COMMIT=${COMMIT}"
echo "KMM_COMMIT=${COMMIT}" >> ${CONFIG}
echo "===="
cat ${CONFIG}
echo "===="
