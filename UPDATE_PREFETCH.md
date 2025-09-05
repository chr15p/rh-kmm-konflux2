

All these commands need to be run in a ubi container with access to the files inteh git repo

 1. enter the container  
>    podman run --rm -it -v $(pwd):/source:Z registry.access.redhat.com/ubi9
 1. find the entitlement key files:  
>    [root@63e8cb226313 source]#  ls -l /etc/pki/entitlement  
>    total 232  
>    -rw-r--r--. 1 root root   3272 Jun 30 14:54 4971055572028229871-key.pem  
>    -rw-r--r--. 1 root root 233324 Jun 30 14:54 4971055572028229871.pem  

 1. update the `sslclientcert` and `sslclientcert` keys in  `redhat.repo` with the keyfiles  

 1. subscribe the container to Red Hat  
>    subscription-manager register --activationkey=rh-kmm-konflux  --org=5318211

 1. install rpm-lockfile-prototype and pre-reqs:  
>    dnf install -y pip skopeo  
>
>    pip install --user https://github.com/konflux-ci/rpm-lockfile-prototype/archive/refs/tags/v0.13.1.tar.gz  

 1. Generate rpms.lock.yaml  
>    rpm-lockfile-prototype -f Dockerfile.operator rpms.in.yaml

 1. exit the container and commit `rpms.lock.yaml`
