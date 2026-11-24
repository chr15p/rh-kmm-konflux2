# KMM on Konflux — beginner tutorial

A customer installs KMM from the OpenShift console (OperatorHub). That UI is
**not** talking to GitHub. It is talking to a **catalog image** Red Hat
published. This repo turns midstream Git commits into those catalog images,
plus the container images they point at, in a way that is signed, scanned,
digest-pinned, and legal to ship.

Three worlds:

1. **Write Go** → `[kernel-module-management](https://github.com/rh-ecosystem-edge/kernel-module-management)` (midstream).
2. **Build and ship containers** → this repo + Konflux (`rh-kmm-tenant`).
3. **Customer installs** → OpenShift OLM reads a catalog on `registry.redhat.io`.

The internal docs URL is SSO-gated:
[konflux.pages.redhat.com](https://konflux.pages.redhat.com/docs/users/getting-started.html).
The same material lives publicly at
[konflux-ci.dev/docs/getting-started](https://konflux-ci.dev/docs/getting-started/).

If the terms below feel like a pile of acronyms, skip to
[If this still feels like a mess](#if-this-still-feels-like-a-mess-read-this-first)
and come back to the glossary later. You do not need to memorize it.

---

## Contents

- [If this still feels like a mess (read this first)](#if-this-still-feels-like-a-mess-read-this-first)
- [0. The 30-second picture](#0-the-30-second-picture)
- [1. Glossary](#1-glossary)
- [2. What a customer actually installs](#2-what-a-customer-actually-installs)
- [3. The three git repos](#3-the-three-git-repos)
- [4. What lives in this repo](#4-what-lives-in-this-repo)
- [5. The eight images per y-stream](#5-the-eight-images-per-y-stream)
- [6. Konflux objects, mapped onto KMM](#6-konflux-objects-mapped-onto-kmm)
- [7. Behind the scenes of one build](#7-behind-the-scenes-of-one-build)
- [8. The full KMM release loop](#8-the-full-kmm-release-loop)
- [9. How the bundle CSV is built](#9-how-the-bundle-csv-is-built)
- [10. How to actually release KMM](#10-how-to-actually-release-kmm)
- [11. Script map](#11-script-map)
- [12. Registries](#12-registries)
- [13. What “good” looks like in the UIs](#13-what-good-looks-like-in-the-uis)
- [14. Onboarding blockers](#14-onboarding-blockers)
- [15. Mental model](#15-mental-model)
- [Further reading](#further-reading)

---

## If this still feels like a mess (read this first)

You do not need to learn OLM, Konflux, and Red Hat catalogs as three separate
subjects. They are three rooms in the same house. The house has one job:

> A customer clicks **Install** in OpenShift. The right version of KMM appears
> on their cluster, and it is the same bits we tested.

Everything else is plumbing for that click.

### Forget the product for a minute: think App Store

You already know this system. You have used it on your phone.


| Thing you already know                                                  | Our name                                       | What it is here                                                                                   |
| ----------------------------------------------------------------------- | ---------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| The App Store app on your phone                                         | **OperatorHub** (the OpenShift console page)   | Where the customer browses and clicks Install                                                     |
| Apple’s list of apps in the store                                       | **Catalog** (FBC)                              | A list: “these operator versions exist, here is how to upgrade”                                   |
| An app’s store page (screenshots, version, “what’s new”, download link) | **Bundle** + **CSV**                           | A tiny box of *paperwork*, not the app itself. “KMM 2.7.1 replaces 2.7.0, deploy *these* images.” |
| The actual `.ipa` / `.apk` you download                                 | **Operand images**                             | The real programs: operator, worker, webhook, …                                                   |
| “This app needs iOS 17+”                                                | Bundle label `com.redhat.openshift.versions`   | “This operator works on OpenShift 4.14 and newer”                                                 |
| Production track vs Beta track                                          | **Channel** (`stable`, `release-2.6`)          | Which upgrade line the customer subscribed to                                                     |
| The App Store software that installs and auto-updates                   | **OLM**                                        | Software *on the customer cluster* that reads the catalog and deploys the bundle                  |
| Build number `8145` vs marketing version “Instagram 392”                | **Digest** (`@sha256:…`) vs **tag** (`:2.7.1`) | Digest = exact bits. Tag = a sticky note that can be moved to a new box. We ship digests.         |


The confusing part, if you come from “we ship a binary”:

**The catalog is not KMM. The bundle is not KMM. KMM is the six running
images.** The catalog and bundle are the store listing so OLM knows *which*
images to start.

If the store page still says “download engine serial 111” after the factory
built engine serial 222, customers install last week’s engine. That is why
this repo is obsessed with updating SHA files.

### What KMM actually is (one sentence)

Some hardware (GPUs, NICs, storage adapters) needs a Linux **kernel module** —
a driver that is not in the OS by default.

KMM is the robot on an OpenShift cluster that says: “this node needs driver X
for kernel Y” and then builds/signs/loads it. You are not writing that robot
in this repo. You are **putting that robot on the App Store**.

Two listings exist because some customers have one cluster (spoke) and some
have a management cluster that controls many (hub), like a headquarters IT
team pushing software to branch offices.

### Now the factory: Konflux is not GitHub, it is the warehouse

GitHub is where code lives. Konflux is the factory that turns that code into
signed boxes and puts them on trucks.

Imagine a car plant:


| Factory                                                                         | Konflux / this repo                                                       |
| ------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| Engineering drawings                                                            | Midstream git (`kernel-module-management`, branch `release-2.7`)          |
| “We are building drawing revision `4bc589d` today”                              | **Git submodule** pin in this repo                                        |
| Workstations: engine, body, electronics, glass, …                               | **Components**: operator, worker, webhook, signing, …                     |
| One car model year (2026 Civic)                                                 | **Application** `kmm-2-7`                                                 |
| A packing list: “this car used engine #aaa, gearbox #bbb, …”                    | **Snapshot**                                                              |
| “Ship this packing list to the test track”                                      | **Release** to **staging**                                                |
| “Ship this packing list to dealerships”                                         | **Release** to **prod**                                                   |
| The test-track lot                                                              | `registry.stage.redhat.io` (QE)                                           |
| Dealership lots                                                                 | `registry.redhat.io` (customers)                                          |
| Scrap / work-in-progress lot                                                    | `quay.io/redhat-user-workloads/…` (Konflux builds; nobody buys from here) |
| Inspector who refuses unsigned parts                                            | **Conforma / Enterprise Contract**                                        |
| “No running to the hardware store mid-build; parts must already be in the cage” | **Hermetic build** + `rpms.lock.yaml`                                     |
| Intern who notices the recipe still says last week’s steel batch                | **MintMaker** (opens PRs to bump UBI tags and submodule SHAs)             |


A **tenant namespace** (`rh-kmm-tenant`) is just “our team’s floor of the
factory.” A **managed namespace** is the shipping dock we are not allowed to
wander around — we fill out a **Release** form and *their* pipeline copies
boxes to the customer registry.

### The one idea that makes “nudge” click

The bundle (store page) contains **serial numbers** of the parts, not “whatever
is called latest.”

So the sequence is always:

1. Factory builds a new **worker** → gets serial `@sha256:aaa`.
2. Someone must edit the store page: “worker is now `aaa`.”
3. That edit is a GitHub PR. Konflux opens it for you. That PR is a **nudge**.

If six parts rebuilt, you get six PRs. `combine_nudges.py` waits until
all six serials are from the **same production run** (same midstream commit),
then merges them as one, so the store page never says “new engine + old
gearbox.”

Then the store page itself is rebuilt (the **bundle** image), and *that* new
serial is written into the **catalog** (another nudge). Then the catalog is
what OperatorHub shows.

```
new engine built
    → PR updates the parts list          (operand nudge)
    → all 6 parts listed, merge
    → print a new store page             (bundle rebuild)
    → PR updates the App Store index     (catalog / FBC nudge)
    → QE installs from the staging store
    → we copy the same boxes to the real store
```

### Three git repos, like a book


| Repo                                         | Like                                                                  | You do                                             |
| -------------------------------------------- | --------------------------------------------------------------------- | -------------------------------------------------- |
| `kubernetes-sigs/kernel-module-management`   | The novel the community writes                                        | Rarely touch                                       |
| `rh-ecosystem-edge/kernel-module-management` | Red Hat’s edition of that novel (`release-2.7` = “the 2.7 hardcover”) | Bugfixes, cherry-picks                             |
| **this repo**                                | The print shop: covers, ISBN, boxes, shipping labels                  | Submodule pin + Dockerfiles + “print this edition” |


This repo does not contain the story. It contains the **instructions to print
today’s edition** of each hardcover (`release-2.5`, `release-2.6`, `release-2.7`).

### Stage vs prod, with food

You would not put a new recipe on the restaurant menu the same afternoon the
kitchen tried it.

1. Kitchen cooks a batch → Konflux build (Quay).
2. Staff tasting / health inspector → **stage** registry, QE.
3. Printed on the customer menu → **prod** registry, OperatorHub.

Same food. Different rooms. A **Release** object is the ticket that moves a
batch from one room to the next. We do **not** auto-print the menu on every
kitchen experiment.

### Digest vs tag, with milk

- Tag `:2.7.1` is the cardboard label on the fridge: “semi-skimmed.” Tomorrow
someone can stick that label on a different carton.
- Digest `@sha256:abc` is the batch code printed on the carton. It will never
be another carton.

Air-gapped customers (no internet) mirror exact cartons. If we shipped tags,
their mirror could silently become a different carton. So catalogs must list
digests, and Konflux refuses catalogs that do not.

### A walk-through you can picture on Monday morning

A customer files “worker crashes on 2.7.” A developer fixes it on midstream
branch `release-2.7` and merges.

Nothing has shipped yet. The print shop is still pinning last week’s commit.

1. **MintMaker** opens a PR here: “print shop, use commit `4bc589d`.” You
  glance at it, merge.
2. Konflux builds six images. Green checks in the UI. Still not on any store.
3. Six **nudge** PRs appear: each is one line, a new `@sha256:…` in
  `release-2.7/release-2.7.1/worker.yaml` (etc.). The GitHub Action waits
   until all six exist, smashes them into one PR, merges.
4. Bundle rebuilds. Two more nudge PRs (spoke + hub store pages). Action
  labels `ok-to-release` and `release.py` files a shipping ticket to **stage**.
5. QE installs from `registry.stage.redhat.io` like a customer would.
6. You file the same ticket to **prod**. Rename the SHA files
  `*.released` so nobody overwrites history. Refresh the catalog. OperatorHub
   shows 2.7.1.

If step 3 is stuck, one of the six builds failed. That is the usual fire.
You do not debug OLM; you open the failed PipelineRun.

### How to use the rest of this file

You do not need the glossary in your head. Use it as a dictionary when a
Slack message says “the snapshot failed Conforma” or “FBC didn’t nudge.”


| When someone says…                               | Jump to                                  |
| ------------------------------------------------ | ---------------------------------------- |
| “look at the application / component / snapshot” | [§6](#6-konflux-objects-mapped-onto-kmm) |
| “why did this pipeline run / not run?”           | [§7](#7-behind-the-scenes-of-one-build)  |
| “what’s the full loop?”                          | [§8](#8-the-full-kmm-release-loop)       |
| “what do I actually click?”                      | [§10](#10-how-to-actually-release-kmm)   |
| “what is this Python file?”                      | [§11](#11-script-map)                    |


---

## 0. The 30-second picture

A “KMM release” is not one image. It is a graph:

```
midstream commit
      → submodule bump in this repo
      → operand images (operator, hub, worker, webhook, signing, must-gather)
      → digest YAML files
      → bundle images (OLM metadata)
      → FBC catalog images (one per OpenShift version)
      → stage registry (QE)
      → prod registry (customers / OperatorHub)
```

If any digest in that chain is wrong, customers install the wrong bits, or
disconnected clusters cannot pull. That is why this repo is obsessed with SHA
files and nudges.

---

## 1. Glossary

### Kubernetes / OpenShift


| Term                         | Meaning                                                                                                                                                                                                                          |
| ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Operator**                 | A controller that manages other Kubernetes objects. KMM’s operator watches `Module` CRs and loads kernel modules on nodes.                                                                                                       |
| **OLM**                      | Operator Lifecycle Manager. The OpenShift machinery that installs, upgrades, and removes operators from catalogs.                                                                                                                |
| **Operand**                  | Anything the operator *manages* or *deploys*, as opposed to the operator binary itself. In this repo that means: operator, hub-operator, worker, webhook, building/signing.                                                      |
| **CSV**                      | ClusterServiceVersion. YAML inside a bundle that says “this is KMM 2.7.1, here are the images, here is how to deploy them, this version replaces 2.7.0.”                                                                         |
| **Bundle**                   | A tiny container whose only job is to carry the CSV + CRDs + metadata. Not a running program. OLM reads it.                                                                                                                      |
| **Catalog / FBC**            | File-Based Catalog. A container that is a *list of bundles* plus *upgrade channels* (`stable`, `release-2.7`, …). This is what OperatorHub queries.                                                                              |
| **Channel**                  | An upgrade track. `stable` always points at the newest shipped KMM. `release-2.6` stays on the 2.6 line.                                                                                                                         |
| `replaces` **/** `skipRange` | How OLM knows 2.7.0 can upgrade from 2.6.1, and that it may skip older versions.                                                                                                                                                 |
| **CatalogSource**            | Cluster object pointing at a catalog image. Built-in ones serve `registry.redhat.io`.                                                                                                                                            |
| **Hub vs spoke**             | KMM has two operators. **Spoke** (`kernel-module-management`) runs on the cluster that loads modules. **Hub** (`kernel-module-management-hub`) runs on a management cluster (ACM) and fans `ManagedClusterModule` out to spokes. |
| **must-gather**              | Image `oc adm must-gather` pulls when Support asks for logs.                                                                                                                                                                     |


### Images and registries


| Term                                      | Meaning                                                                                                                                     |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| **Pullspec**                              | Full image reference. Tag: `repo:2.7.1`. Digest: `repo@sha256:abc…`. Digests are immutable; tags can move. **Konflux/FBC require digests.** |
| **OCI / OCI artifact**                    | The container-image format. Konflux stores images *and* SBOMs/attestations as OCI artifacts.                                                |
| **Digest / SHA**                          | Hash of the image contents. Same bits → same digest.                                                                                        |
| **Image index (manifest list)**           | One tag that points at amd64 + arm64 + ppc64le + s390x. KMM builds all four.                                                                |
| **UBI**                                   | Red Hat Universal Base Image. `ubi9/ubi-minimal` is the runtime base; `ubi9/go-toolset` is the build base.                                  |
| **Quay (user-workloads)**                 | `quay.io/redhat-user-workloads/rh-kmm-tenant/…` — Konflux *build* registry. Not for customers.                                              |
| **Stage registry**                        | `registry.stage.redhat.io/kmm/…` — QE / pre-prod.                                                                                           |
| **Prod registry**                         | `registry.redhat.io/kmm/…` — what customers pull.                                                                                           |
| **Hermetic build**                        | Build with **no network**. Dependencies must already be on disk (RPM lockfile). Required for SLSA-style supply chain.                       |
| **SBOM**                                  | Software Bill of Materials. “This image contains these RPMs and Go modules.”                                                                |
| **SLSA / Conforma (Enterprise Contract)** | Policy gate: unsigned, unscanned, or unpinned images cannot ship.                                                                           |


### Konflux

Konflux is Red Hat’s internal CI/CD for *product* containers. It is Kubernetes:
everything you click in the UI is a Custom Resource in namespace `rh-kmm-tenant`.


| Term                              | Meaning                                                                                                                                                                         |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Tenant namespace**              | Your team’s workspace. Ours: `rh-kmm-tenant` on cluster `stone-prd-rh01`. [UI](https://konflux-ui.apps.stone-prd-rh01.pg1f.p1.openshiftapps.com/ns/rh-kmm-tenant/applications). |
| **Managed namespace**             | Where *release* pipelines and registry credentials live. You do not run those yourself; you create a Release that *asks* that namespace to copy images to `registry.redhat.io`. |
| **Application**                   | A group of components released together. `kmm-2-7` is “all KMM 2.7 images.” `fbc-op-423` is “the OCP 4.23 operator catalog.”                                                    |
| **Component**                     | One image, one Dockerfile, one Tekton pipeline. Example: `operator-2-7`.                                                                                                        |
| **Pipeline / PipelineRun**        | Tekton: a Pipeline is the recipe; a PipelineRun is one execution. Definitions live in `.tekton/`.                                                                               |
| **Pipelines as Code (PaC)**       | GitHub webhook → cluster reads `.tekton/*.yaml` → runs matching PipelineRun. CEL expressions decide *when*.                                                                     |
| **Snapshot**                      | Immutable bag: “these exact image digests, from these git commits, belong together.” You test and release snapshots, not “latest.”                                              |
| **IntegrationTestScenario (ITS)** | Test pipeline run against a snapshot. Default one is Conforma/Enterprise Contract.                                                                                              |
| **ReleasePlan**                   | “How do we ship application `kmm-2-7`?” Points at a managed namespace. Named `kmm-2-7-release-staging` and `kmm-2-7-release-prod`.                                              |
| **ReleasePlanAdmission**          | The managed-side twin: “yes, we accept releases of `kmm-2-7`, here is the pipeline, here is the destination registry mapping.”                                                  |
| **Release**                       | One *intent* to ship one Snapshot via one ReleasePlan. Creating it starts the copy to stage/prod.                                                                               |
| **Nudge**                         | After component A builds, Konflux opens a PR that updates digest references in files that *point at* A. Operator images nudge the bundle; bundles nudge FBC.                    |
| **MintMaker**                     | Konflux’s Renovate. Opens PRs to bump UBI tags and **git submodule SHAs**.                                                                                                      |
| **Prefetch / Hermeto (Cachi2)**   | Before a hermetic build, download RPMs listed in `rpms.lock.yaml` so the build can install them offline.                                                                        |


Official definitions:

- [Getting started](https://konflux-ci.dev/docs/getting-started/)
- [Glossary](https://konflux-ci.dev/docs/glossary/)
- [Nudging](https://konflux-ci.dev/docs/building/component-nudges/)
- [OLM in Konflux](https://konflux-ci.dev/docs/end-to-end/building-olm/)
- [Releasing](https://konflux-ci.dev/docs/releasing/)

---

## 2. What a customer actually installs

On an OpenShift cluster:

```
Console "OperatorHub"
        │
        ▼
  CatalogSource  ──pulls──►  catalog image (FBC)
                                │
                                │  "package kernel-module-management,
                                │   channel stable → bundle 2.7.0"
                                ▼
                           Bundle image
                                │
                                │  CSV says: deploy operator@sha256:…,
                                │  worker@sha256:…, webhook@sha256:…, …
                                ▼
                    Running pods on the cluster
```

So a “KMM release” is:

1. Six **operand** images (binaries).
2. Two **bundle** images (OLM metadata that *points at* those six, by digest).
3. Many **FBC** images (one per OpenShift version × spoke/hub) that *point at* the bundles.

---

## 3. The three git repos

```
kubernetes-sigs/kernel-module-management     community upstream
              │
              ▼  (downstreaming / productization)
rh-ecosystem-edge/kernel-module-management   MIDSTREAM
  branches: main, release-2.5, release-2.6, release-2.7, …
              │
              │  git submodule, one per product line
              ▼
chr15p/rh-kmm-konflux2                       THIS REPO (release/build)
  release-2.7/kernel-module-management  →  midstream @ some SHA
  release-2.6/kernel-module-management  →  midstream @ some SHA
```

Midstream is where bugs are fixed. This repo almost never contains Go. It contains:

- Dockerfiles that `COPY` the submodule and `go build`
- Tekton that tells Konflux how to build
- YAML files that store the resulting image digests
- Scripts that create Konflux Snapshot/Release objects and FBC templates

Shipping a midstream commit = bump the submodule pointer here, then let Konflux rebuild.

If your clone’s `origin` is a personal fork, add this repo as `upstream`:

```bash
git remote add upstream git@github.com:chr15p/rh-kmm-konflux2.git
```

---

## 4. What lives in this repo

```
rh-kmm-konflux2/
├── .tekton/                    Konflux build recipes (the CI)
│   ├── operator-2-7-push.yaml  build operator 2.7 on merge to main
│   ├── operator-2-7-pull-request.yaml   same, but for PRs (throwaway)
│   ├── multi-arch-pipelineref.yaml      shared operand pipeline
│   ├── bundle-pipelineref.yaml          shared bundle pipeline
│   └── catalogue-pipelineref.yaml       shared FBC pipeline
├── release-2.7/
│   ├── kernel-module-management/        SUBMODULE (often not checked out)
│   ├── Dockerfile.operator
│   ├── Dockerfile.hub-operator
│   ├── Dockerfile.worker
│   ├── Dockerfile.webhook
│   ├── Dockerfile.signing
│   ├── Dockerfile.must-gather
│   ├── Dockerfile.operator-bundle
│   ├── Dockerfile.hub-operator-bundle
│   ├── build_settings.conf              VERSION=2.7 RELEASE=2.7.1
│   ├── release-2.7.0/*.yaml.released    frozen SHAs that already shipped
│   └── release-2.7.1/*.yaml             SHAs for the in-progress z-stream
├── release-2.6/ … same shape …
├── fbc/
│   ├── op-catalog-template.json         “which bundles, which channels”
│   ├── hub-catalog-template.json
│   └── Containerfile.catalogue          wraps that JSON in an opm image
├── config/
│   ├── pullspec_config.json             source of truth: registries, stage vs prod lists
│   ├── rpms.in.yaml                     which RPMs hermetic builds may use
│   └── namespace-wide-nudging-renovate-config.yaml
├── scripts/                             release automation
├── .github/workflows/                   combine nudge PRs; trigger stage release
└── rpms.lock.yaml                       pinned RPM NVRs (generated, committed)
```

`build_settings.conf` for current 2.7:

```
PRODUCT=kernel-module-management
REPO=registry.redhat.io/kmm
OP_BUNDLE=operator-bundle
HUB_BUNDLE=hub-operator-bundle
VERSION=2.7
RELEASE=2.7.1
OLD_VERSION=2.7.0
DIRECTORY=release-2.7
SUBMODULE=HEAD
```

`VERSION` is the y-stream (2.7). `RELEASE` is the z-stream being built (2.7.1).
Bumping `RELEASE` is how you start a new z-stream directory.

---

## 5. The eight images per y-stream

For `kmm-2-7` (and the same for 2.2–2.6):


| Component               | What it is                                        | Built from                                      |
| ----------------------- | ------------------------------------------------- | ----------------------------------------------- |
| **operator**            | Spoke controller (`cmd/manager`)                  | Go in the submodule                             |
| **hub-operator**        | Hub controller (`cmd/manager-hub`)                | Same submodule, different `main`                |
| **worker**              | pod that `insmod`s modules on the node            | `cmd/worker` + `kmod` RPM                       |
| **webhook**             | Admission webhook                                 | `cmd/webhook-server`                            |
| **signing**             | `sign-file` from `kernel-devel` (kmod signatures) | RPM only, almost no Go                          |
| **must-gather**         | Support data collector                            | Scripts in the submodule + `oc`                 |
| **operator-bundle**     | OLM CSV for the spoke operator                    | Submodule `bundle/`, rewritten by `make-csv.py` |
| **hub-operator-bundle** | OLM CSV for the hub operator                      | Same idea as the spoke bundle                   |


Plus FBC apps, **one Konflux application per OpenShift version per catalog**:

- `fbc-op-414` … `fbc-op-423`, `fbc-op-50` → spoke catalog for OCP 4.14 … 4.23 and 5.0
- `fbc-hub-*` → same for hub

Why many catalogs? Each OCP version ships its own OperatorHub index. The
`com.redhat.openshift.versions="v4.14"` label on the bundle says “this operator
is valid from 4.14 up”; the FBC images are still built per OCP so `opm` matches
that OCP’s operator-registry.

---

## 6. Konflux objects, mapped onto KMM

Imagine the cluster as folders:

```
namespace rh-kmm-tenant
├── Application kmm-2-7
│   ├── Component operator-2-7
│   ├── Component worker-2-7
│   ├── … (8 components)
│   ├── Snapshot kmm-2-7-<commit>-r42     "these 8 digests together"
│   ├── ReleasePlan kmm-2-7-release-staging
│   ├── ReleasePlan kmm-2-7-release-prod
│   └── Release kmm-2-7-staging-271-<sha>-r42
├── Application fbc-op-423
│   └── Component fbc-op-423
└── (managed namespace, not yours)
    └── ReleasePlanAdmission  →  copies snapshot images to registry.redhat.io
```

Flow from the [getting-started docs](https://konflux-ci.dev/docs/getting-started/):

1. Push to git → **build PipelineRun** produces an image in Quay.
2. Integration service makes a **Snapshot**.
3. **ITS** (Conforma) runs on the snapshot.
4. If you want it shipped, you create a **Release** pointing at that Snapshot + a **ReleasePlan**.
5. The managed namespace runs the **release pipeline**: copy, sign, push to `registry.stage.redhat.io` or `registry.redhat.io`.

KMM does **not** auto-release every snapshot. `scripts/release.py` creates
Release objects on purpose.

---

## 7. Behind the scenes of one build

Take `operator-2-7`. Two PipelineRuns exist.

### PR build (`.tekton/operator-2-7-pull-request.yaml`)

- Fires when a GitHub PR touches `release-2.7/**` but *not* the digest YAML dirs.
- Image: `…/operator-2-7:on-pr-<sha>`, expires in 5 days.
- `cancel-in-progress: true` — new push cancels the old run.

### Push build (`.tekton/operator-2-7-push.yaml`)

- Fires on merge to `main`.
- Image: `…/operator-2-7:<git-sha>` — this is the real artifact.
- `cancel-in-progress: false`.
- **Only push builds nudge.** PR builds never update digest files.

CEL on the push pipeline (plain language): run if someone changed the shared
pipeline, any `*-2-7-push.yaml`, or anything under `release-2.7/` *except*
`release-2.7/release-2.7*/` (the SHA files). Changing a SHA file must **not**
rebuild the operator (that would loop). Changing a SHA file *does* rebuild the
**bundle**, because the bundle CSV embeds those SHAs.

What the pipeline actually does
([prefetch docs](https://konflux-ci.dev/docs/building/prefetching-dependencies/)):

1. Clone this git repo (with submodule).
2. **Prefetch RPMs** from `rpms.lock.yaml` (Hermeto). Network is allowed here only.
3. **Hermetic buildah**: no network. Dockerfile copies submodule, `go build`, copies binary onto `ubi-minimal`.
4. Multi-arch: amd64, arm64, ppc64le, s390x, then an image **index**.
5. SAST (Snyk), Clair CVE scan, antivirus, source image, SBOM.
6. Push to Quay. Tekton Chains signs provenance.
7. If this is a push build and the Component CR has `spec.build-nudges-ref`, Konflux’s nudge controller runs **Renovate** and opens a GitHub PR that replaces the old `@sha256:…` with the new one.

That last step is the whole “nudge” idea from
[component relationships](https://konflux-ci.dev/docs/building/component-nudges/).

---

## 8. The full KMM release loop

Concrete example: a bugfix lands on midstream `release-2.7`.

```
 midstream PR merged on release-2.7
              │
              ▼
 MintMaker notices submodule SHA is stale
 opens PR: "Update release-2.7/kernel-module-management digest to 4bc589d"
              │
              ▼
 human merges it  (this is a real decision: "yes, build this commit")
              │
              ▼
 Konflux rebuilds all 6 operands for 2.7 (push pipelines)
 images land in quay.io/redhat-user-workloads/rh-kmm-tenant/kmm-2-7/…
              │
              ▼
 Nudge PRs appear, one per operand, labelled konflux-nudge
 e.g. "Update operator-2-7 to be0b5a0"
 each PR writes ONE line into release-2.7/release-2.7.1/operator.yaml
              │
              ▼
 GitHub Action combine-nudges.yaml
 scripts/combine_nudges.py waits until ALL 6 operand PRs exist
 for the same KMM commit, then squash-merges them into one PR
 and labels it  ok-to-merge
              │
              ▼
 same Action squash-merges that combined PR
              │
              ▼
 SHA files are on main → operator-bundle and hub-operator-bundle rebuild
 (Dockerfile.operator-bundle runs make-csv.py, which reads those YAML files
  and rewrites the CSV so relatedImages are digest-pinned)
              │
              ▼
 Bundle nudge PRs appear (2 of them)
 combine_nudges.py waits for both, labels  ok-to-release
              │
              ▼
 GitHub Action calls scripts/release.py
 which talks to the Konflux API and creates:
    Snapshot  (the 8 image digests)
    Release   (spec.releasePlan: kmm-2-7-release-staging)
              │
              ▼
 Managed-namespace pipeline copies Quay images → registry.stage.redhat.io
 QE tests from stage
              │
              ▼
 human: python scripts/release.py --env prod --pr …   (or equivalent)
 images → registry.redhat.io
 SHA files renamed *.yaml.released
              │
              ▼
 scripts/create_fbc.py rewrites fbc/*-catalog-template.json
 listing every shipped bundle (prod SHAs + in-stage SHAs)
              │
              ▼
 FBC components rebuild (fbc-op-414 … fbc-op-423, hub twins)
 those catalogs get their own Release to stage, then prod
              │
              ▼
 QE / customers: OperatorHub shows the new KMM
 scripts/release_to_qe.py dumps the catalog pullspecs for QE
```

Two-phase merge is the clever bit. Operands must not ship until all six match
the same midstream commit (otherwise the CSV would mix old worker + new
operator). Bundles must not ship until both spoke and hub bundles exist.
Labels encode that:


| Label           | Meaning                                  |
| --------------- | ---------------------------------------- |
| `ok-to-merge`   | operands ready — auto-merge              |
| `ok-to-release` | bundles ready — create a Konflux Release |


Config for that is `config/pullspec_config.json`:

```json
"bundle": [
  "operator-bundle",
  "hub-operator-bundle"
],
"operand": [
  "worker",
  "must-gather",
  "operator",
  "hub-operator",
  "signing",
  "webhook"
]
```

Prod vs stage version lists in the same file decide which SHAs `create_fbc.py`
puts in the catalog as `registry.redhat.io` vs `registry.stage.redhat.io`.
**JSON is what the scripts use.** The YAML copy can lag behind.

`.yaml` vs `.yaml.released`: in-progress z-stream stays `.yaml` so nudges can
keep updating it. Once that version has shipped to prod, files are renamed
`.released` so a later nudge cannot overwrite history. `create_fbc.py` accepts
either filename.

---

## 9. How the bundle CSV is built

The bundle Dockerfile does not just copy midstream `bundle/`. It runs
`scripts/make-csv.py`, which:

1. Reads `release-2.7/release-2.7.1/{operator,worker,webhook,signing,must-gather,hub-operator}.yaml` (one digest each).
2. Rewrites every `quay.io/edge-infrastructure/…:tag` in the midstream CSV to the **prod** `registry.redhat.io/kmm/…@sha256:…` pullspec (so disconnected clusters pull from the customer registry, not Quay).
3. Sets `spec.version`, `spec.replaces` (previous z-stream from `versions.py`), `olm.skipRange`, `relatedImages`, disconnected/FIPS annotations, arches.

That is why **operands must be nudged and merged before the bundle build**. If
those YAML files still have the previous SHA, the CSV ships yesterday’s operator.

FBC validation then requires every `olm.bundle` image in the catalog to be
digest-pinned **and** from `registry.redhat.io` or `registry.stage.redhat.io` —
never Quay. That is a Konflux `validate-fbc` rule.

`scripts/create_fbc.py` builds the catalog template:

- One `olm.package`
- Channels `release-2.0` … `release-2.7` plus `stable`
- Each newer channel includes all older bundles (`replaces` chain), so you can install 2.7 on a 4.23 catalog and still see history
- Each `olm.bundle` entry is `registry.redhat.io/…@sha256:…` (or stage, if the version is still in `stage:`)

The FBC Containerfile is tiny: base `ose-operator-registry`, `ADD` the rendered
catalog, `opm serve --cache-only` so the image is a ready CatalogSource.

---

## 10. How to actually release KMM

There is no other README for the day-to-day. Work is mostly **merge the right
PRs in the right order**, then run one script. Automation covers the rest.

### A. Ship a midstream bugfix (most common)

1. Fix lands on midstream `release-2.7` (or you cherry-pick it there).
2. Wait for MintMaker PR: *Update release-2.7/kernel-module-management digest…*
3. Review: SHA matches the midstream commit you want. Merge.
4. Watch Konflux: `kmm-2-7` components should all go green (push pipelines).
5. Watch GitHub: six `konflux-nudge` PRs. The combine Action should collapse them and merge when complete. If a build failed, one PR is missing and combine **exits 0 without merging** — that is intentional waiting, not a bug.
6. Watch bundle builds, then two bundle nudge PRs → `ok-to-release`.
7. Confirm a **Release** appears in the Konflux UI for `kmm-2-7` targeting **staging**.
8. Give QE the stage catalog pullspecs (`release_to_qe.py` once you have cluster credentials).
9. After QE: `python scripts/release.py -t $KONFLUX_TOKEN --env prod --application kmm-2-7 --commit <sha>` (or `--pr <bundle-pr>`).
10. Move `2.7.1` from `stage` to `prod` in `pullspec_config.json`, rename SHA files to `.released`, bump `RELEASE` to `2.7.2` and mkdir `release-2.7/release-2.7.2/` when you start the next z-stream.
11. Regen FBC templates, merge, wait for `fbc-op-*` / `fbc-hub-*` builds, release those catalogs.

### B. Rebuild because UBI / RPMs moved (CVE rebuild)

MintMaker opens “Update ubi-minimal to 9.8-…” PRs. Merge → all Dockerfiles that
`FROM` that tag rebuild → same nudge chain. No midstream change. After ship,
you may need to regenerate `rpms.lock.yaml` (`UPDATE_PREFETCH.md`: UBI
container + `subscription-manager` + `rpm-lockfile-prototype`).

### C. New y-stream (2.8)

Copy `release-2.7/` → `release-2.8/`, new submodule on `release-2.8`, new
`.tekton/*-2-8-*.yaml`, new Application `kmm-2-8` in Konflux UI, new
ReleasePlans. This is onboarding a whole Application, not a script.

### D. New OpenShift version (4.24 catalogs)

Copy `fbc-op-423` / `fbc-hub-423` Tekton + Konflux components, bump `OCP=4.24`
build-arg. FBC pipeline already rebuilds whenever any `*-bundle.yaml` changes.

### Commands (once you have tokens)

```bash
# dry-run a stage release from a bundle nudge PR
python scripts/release.py -t "$KONFLUX_TOKEN" --pr 1888 --env staging --test

# real stage release
python scripts/release.py -t "$KONFLUX_TOKEN" --pr 1888 --env staging

# rebuild FBC JSON from SHA files (no cluster needed)
python scripts/create_fbc.py --op --hub

# ship FBC snapshots
python scripts/release_fbc.py -t "$KONFLUX_TOKEN" --env staging

# dump catalog pullspecs for QE
python scripts/release_to_qe.py -d release-2.7/ -k "$KUBECONFIG"
```

`scripts/kmm_konflux/konflux_api.py` is a thin REST client against:

```
https://api.stone-prd-rh01.pg1f.p1.openshiftapps.com:6443/apis/appstudio.redhat.com/v1alpha1/namespaces/rh-kmm-tenant/{snapshots|releases|components}
```

Same objects the UI shows.

---

## 11. Script map


| Script                                  | Job                                                                                                                                                                                                                                                |
| --------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `scripts/combine_nudges.py`             | Wait for a full set of operand *or* bundle nudge PRs; squash into one; apply `ok-to-merge` / `ok-to-release`. Matches on **KMM submodule commit**, not Konflux repo commit (so a 2.6 merge that happens while 2.7 is building does not split 2.7). |
| `scripts/release.py`                    | From a PR or `--application`+`--commit`: build Snapshot + Release CRs.                                                                                                                                                                             |
| `scripts/make-csv.py`                   | Dockerfile helper: pin CSV images.                                                                                                                                                                                                                 |
| `scripts/create_fbc.py`                 | SHA files + prod/stage lists → `fbc/*-catalog-template.json`.                                                                                                                                                                                      |
| `scripts/release_fbc.py`                | Snapshot+Release for applications labelled `stage=fbc`.                                                                                                                                                                                            |
| `scripts/release_to_qe.py`              | JSON of FBC image pullspecs for the last build of this git commit.                                                                                                                                                                                 |
| `scripts/get_kmm_commit.sh`             | Pipeline helper: write submodule SHA into build-args.                                                                                                                                                                                              |
| `.github/workflows/combine-nudges.yaml` | On every `konflux-nudge` PR: run combiner; maybe auto-merge; maybe call `release.yml`.                                                                                                                                                             |
| `.github/workflows/release.yml`         | `release.py` with `secrets.KONFLUX_TOKEN`.                                                                                                                                                                                                         |


Nudging itself is **not** in this repo. It is a Konflux controller. This repo
only *receives* those PRs. Relationships (`operator-2-7` nudges
`operator-bundle-2-7`, bundle nudges `fbc-op-*`) are stored on Component CRs in
the cluster. You will not find `build-nudges-ref` in git.

MintMaker submodule bumps are also not this repo’s code — they are Konflux
Renovate looking at `.gitmodules`.

---

## 12. Registries

```
build (Konflux)
  quay.io/redhat-user-workloads/rh-kmm-tenant/kmm-2-7/operator-2-7@sha256:aaa
                          │
                          │  Release pipeline (managed namespace)
                          ▼
stage (QE)
  registry.stage.redhat.io/kmm/kernel-module-management-rhel9-operator@sha256:aaa
                          │
                          │  prod Release
                          ▼
customers
  registry.redhat.io/kmm/kernel-module-management-rhel9-operator@sha256:aaa
```

`.tekton/images-mirror-set.yaml` is an ImageDigestMirrorSet so that **during
FBC/bundle builds**, when the CSV says `registry.redhat.io/…@sha256:…` but that
digest only exists in Quay yet, the build cluster can still pull it. Customers
never see that file.

---

## 13. What “good” looks like in the UIs

**GitHub** `[chr15p/rh-kmm-konflux2](https://github.com/chr15p/rh-kmm-konflux2/pulls)`
typically has:

- MintMaker: submodule digest bumps, UBI tag bumps, Konflux pipeline-ref bumps
- Nudges: `konflux/component-updates/…` PRs (operand → SHA file, or bundle → catalog)

**Konflux UI** → Applications:

- `kmm-2-2` … `kmm-2-7`: click through to Components, Activity (PipelineRuns), Snapshots, Releases
- `fbc-op-*` / `fbc-hub-*`: catalog builds

A healthy ship: all 8 components of `kmm-2-7` have a recent *push* PipelineRun
Succeeded, a Snapshot exists with all 8 digests, a Release to staging is
Complete, FBC apps rebuilt after the bundle YAML changed.

---

## 14. Onboarding blockers

1. **Konflux UI** — open [the tenant](https://konflux-ui.apps.stone-prd-rh01.pg1f.p1.openshiftapps.com/ns/rh-kmm-tenant/applications) with SSO. If 403, you need RBAC on `rh-kmm-tenant`.
2. **GitHub write** on `chr15p/rh-kmm-konflux2`. Without it you cannot merge nudges (and the GitHub Action that merges them runs in *that* repo, not a fork).
3. `KONFLUX_TOKEN` — service account token `release.py` uses. You need one (or `oc login` + token) to create Releases by hand.
4. **This clone** — `git remote add upstream git@github.com:chr15p/rh-kmm-konflux2.git`. Submodules show as `-` (not initialized); `git submodule update --init` if you need to read the Go that a Dockerfile copies.

Until 1–3 exist you can read and review, but you cannot ship.

---

## 15. Mental model

Konflux is “GitHub Actions, but the runners are an OpenShift cluster, the
artifacts are signed OCI images, and ‘deploy’ means ‘copy to the Red Hat catalog
registries under policy.’”

KMM’s twist is **OLM**: you do not ship one image. You ship a **graph**
(operands → bundles → catalogs) and Konflux **nudges** walk that graph by
opening PRs. The Python in `scripts/` exists because vanilla nudging would
merge six PRs independently and rebuild six times; they are batched so one
Snapshot is one consistent KMM commit.

If you remember only this chain, you can follow any release:

**midstream commit → submodule bump → operand images → digest YAML → bundle images → FBC images → stage registry → prod registry → OperatorHub.**

The highest-value walkthrough with someone who already ships this: pick an open
nudge PR, click from that PR to the Konflux PipelineRun, to the Snapshot, to
the ReleasePlan. After you have seen that once, the scripts make sense.

---

## Further reading


| Topic                     | Link                                                                                                                                                                                             |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Konflux getting started   | [https://konflux-ci.dev/docs/getting-started/](https://konflux-ci.dev/docs/getting-started/)                                                                                                     |
| Konflux glossary          | [https://konflux-ci.dev/docs/glossary/](https://konflux-ci.dev/docs/glossary/)                                                                                                                   |
| Component nudging         | [https://konflux-ci.dev/docs/building/component-nudges/](https://konflux-ci.dev/docs/building/component-nudges/)                                                                                 |
| Building OLM operators    | [https://konflux-ci.dev/docs/end-to-end/building-olm/](https://konflux-ci.dev/docs/end-to-end/building-olm/)                                                                                     |
| Releasing an application  | [https://konflux-ci.dev/docs/releasing/](https://konflux-ci.dev/docs/releasing/)                                                                                                                 |
| Hermetic prefetch         | [https://konflux-ci.dev/docs/building/prefetching-dependencies/](https://konflux-ci.dev/docs/building/prefetching-dependencies/)                                                                 |
| File-based catalogs (OLM) | [https://olm.operatorframework.io/docs/reference/file-based-catalogs/](https://olm.operatorframework.io/docs/reference/file-based-catalogs/)                                                     |
| This team’s Konflux UI    | [https://konflux-ui.apps.stone-prd-rh01.pg1f.p1.openshiftapps.com/ns/rh-kmm-tenant/applications](https://konflux-ui.apps.stone-prd-rh01.pg1f.p1.openshiftapps.com/ns/rh-kmm-tenant/applications) |
| Midstream (source)        | [https://github.com/rh-ecosystem-edge/kernel-module-management](https://github.com/rh-ecosystem-edge/kernel-module-management)                                                                   |
| This release repo         | [https://github.com/chr15p/rh-kmm-konflux2](https://github.com/chr15p/rh-kmm-konflux2)                                                                                                           |
| RPM lockfile regen        | `[UPDATE_PREFETCH.md](UPDATE_PREFETCH.md)`                                                                                                                                                       |


