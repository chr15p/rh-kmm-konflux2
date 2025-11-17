To add packages to the prefetch list first we need to ensure the repos are correct, then setup the list of packages to prefetch, then generate the `rpms.lock.yaml` file itself.

### Setup Repos and  package list

1. check the repo files are up to date/correct and add any new ones (`ubi.repo` and `redhat.repo`)

2. update `rpms.in.yaml` to list all the rpms we need, the repos to pull them from and the archs to pull them for.


### Generate rpms.lock.yaml

All these commands need to be run in a ubi container with access to the files in the git repo

1. enter the container
>    podman run --rm -it -v $(pwd):/source:Z registry.access.redhat.com/ubi9

2. subscribe the container to Red Hat
>    subscription-manager register --activationkey=rh-kmm-konflux  --org=5318211

3. find the entitlement key files:
>    [root@63e8cb226313 source]#  ls -l /etc/pki/entitlement
>    total 232
>    -rw-r--r--. 1 root root   3272 Jun 30 14:54 4971055572028229871-key.pem
>    -rw-r--r--. 1 root root 233324 Jun 30 14:54 4971055572028229871.pem

4. update the `sslclientcert` and `sslclientcert` keys in  `redhat.repo` with the keyfiles

5. kick dnf to pick up the new repos
>  dnf repolist

6. install rpm-lockfile-prototype and pre-reqs:
>    dnf install -y pip skopeo
>
>    pip install --user https://github.com/konflux-ci/rpm-lockfile-prototype/archive/refs/tags/v0.17.1.tar.gz

7. login to registry.redhat.io
>    skopeo login registry.redhat.io

7. Generate rpms.lock.yaml
>    rpm-lockfile-prototype -f Dockerfile.operator rpms.in.yaml

8. exit the container and commit `rpms.lock.yaml`
