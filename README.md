# Kubernetes Operator for Armada and Helm

# Introduction

This README is mainly used a log / wiki of results and challenges encounted during the POC

## operator-sdk vs kubebuilder.

Things to clean up:
Did not had time to sort how to completly migrate from operator-sdh to kubebuilder.
Most of the scaffolding is done using the operator-sdk but once the default files are created,
the build process mainly relies on kubebuilder

## armada-operator code directory structure

###  cmd

Contains the main.go for the armada operator

###  pkg/apis/

Contains the golang definition of the CRDs. `make generate` will recreate the yaml definitions
of the CRDs that have to be provided to kubectl in order to deploy the new CRDs.
This current version of the operator uses "act" for shortname of ArmadaChart,
"acg" as shortname for ArmadaChartGroup and "amf" as shortname for ArmadaManifest.

The first version of the golang code has generated using tool such as "schema-generate" from
the schema definition provided with airship-armada project.

###  pkg/services

Contains the bulk of the interfaces used by the armada controller.

###  pkg/helm, pkg/helmv2 and pkg/helmv3

To get the process doing, some of the code for ArmadaChart handling is coming from the 
operator-sdk helm-operator. That code is relying on tiller component which is gone for Helm3.
Hence the three directory helm (Interface and Common code), helmv2 (tiller) and helmv3.

The golang package structure is different between helmv2 and helmv3. The Armada Operator will
most likely ultimatly have support two branches. In order to delay that milestone, the golang
code has been instrumentated with "v2" and "v3" tags which allows to compile either the
helm v3 version of the operator or the helm v3 version.

###  pkg/armada directory

Mainly contain the code for ArmadaChartGroup, ArmadaManifest as will ArmadaBackupLocation handling

###  pkg/controller directory

Contains the controller and the "Reconcile" functions for ArmadaChart, ArmadaChartGroup and ArmadaManifest.
There are currently three controllers (act-controller, acg-controller and amf-controller).

# Code changes.

## Adjusting the ArmadaOperator CRDs

Upon change of the CRD golang definition, the yaml files have to be regenerated

Note 1: Don't understand yet how to build using operator-sdk operator with the same level of detailes than
controller-gen. Big hack that have to be included in Makefile.

Note 2: The generation tool seems to comply with some of OpenAPI specs. The "validation" schema added
to in the CRD yaml definition does not contain fields using underscore. 
Most of those fields containing underscore where defined such a way in the original airship-armada.

```bash
make generate
```

## Compiling the armada-operator

To keep the directory tree ligthweight, the vendor directory is not checked in in the current repo.
TODO: Since the operator is only using one git branch, the developer has to comment out the helmv2
and add the helmv3 in Gopkg.toml if he wants to build the helmv3 version of the operator. This is still WIP.

```bash
dep ensure
```

To build the v2 version
```bash
make docker-build-v2
```

To build the v3 version
```bash
make docker-build-v3
```

## Run unit test and preintegration tests.

If you installed kubebuilder on your system, you will have access
to a standalone apiserver, etcd server and kubectl.

Because of a lack of time, the current makefile test statement,
will attempt to stop your kubelet and associated container in your local
kubernetes cluster, before starting apiserver, etcdserver.
TODO: We still need to figure out if it necessary

In order to run the unit tests and the e2e integration tests:
```bash
make unittest
```

# Deploying the operator.

Note the current deployment of the operator relies itself on helm.

To install the helm v2 version
```bash
make install-v2
```

To install the helm v3 version
```bash
make install-v3
```

# Testing the armada-controller

##  helm-charts/testchart directory

For testing purpose the current Docker file includes a dummy chart deliverd under armada-charts.
This removes the needs to access external chart repository which is also an aspect of helm changing from 2 to 3.

## examples/armada

In that directory, the ArmadaChart are enabled by default and the charts
are installed as soon as the ArmadaChart CRD are created.

### Deployment

Upon creation of the custom resource, the controller will
- Deploy the Armada Manifest described in the CRD
- Update status of the custom resources.
- Add events to the custom resources.

```bash
kubectl create -f examples/armada
kubectl describe amf/simple-armada
kubectl get amf
kubectl get acg
kubectl get act
```

### Test controller reconcilation logic (for depending resources)

Upon deletion of its depending resources, the controller will recreate it,

```bash
kubectl delete deployment.apps/blog-2-testchart
kubectl get all
kubectl describe act blog-2
```

### Test controller reconcilation logic (for CRD)

When deleting the CRD, the corresponding Armada Manifest should be uninstalled.

```bash
kubectl delete -f simple/armada
```

## examples/stepbystep

This directory contains invidual act,acg and amf files which allow the "step" by "step" testing of the deployment.

## examples/argo

In that directory, the ArmadaChart (act) are disabled by default and the charts not installed
automatically when the act CR are created.
This example assumes that the argo controller has been installed. When the "argo worflow"
CR is created, the "argo controller" is waked up and it orchestrates the enablement of the ArmadaChart
according to the worflow.

Note: You need to have argo installed in your cluster.

```bash
kubectl apply -f example/argo

armadachart.armada.airshipit.org/blog-1 created
armadachart.armada.airshipit.org/blog-2 created
workflow.argoproj.io/wf-blog-group created
```

The first ArmadaChart is installed:

```bash
kubectl get all

pod/armada-operator-cbbc7d7f7-zxj5n     1/1     Running             0          60s
pod/blog-1-testchart-5dd8c474f4-26574   0/1     ContainerCreating   0          6s
pod/wf-blog-group-1193326311            0/1     Completed           0          8s
pod/wf-blog-group-2026876860            0/1     ContainerCreating   0          1s
pod/wf-blog-group-2432013970            0/1     Completed           0          4s

NAME                       TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)    AGE
service/armada-operator    ClusterIP   10.98.2.253    <none>        8383/TCP   57s
service/blog-1-testchart   ClusterIP   10.104.240.7   <none>        80/TCP     6s
service/kubernetes         ClusterIP   10.96.0.1      <none>        443/TCP    7m43s

NAME                               READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/armada-operator    1/1     1            1           60s
deployment.apps/blog-1-testchart   0/1     1            0           6s

NAME                                          DESIRED   CURRENT   READY   AGE
replicaset.apps/armada-operator-cbbc7d7f7     1         1         1       60s
replicaset.apps/blog-1-testchart-5dd8c474f4   1         1         0       6s
```

Later both charts have been installed

```bash
NAME                                    READY   STATUS      RESTARTS   AGE
pod/armada-operator-cbbc7d7f7-zxj5n     1/1     Running     0          44m
pod/blog-1-testchart-5dd8c474f4-26574   1/1     Running     0          43m
pod/blog-2-testchart-57f86dd9c5-xmhd7   1/1     Running     0          43m
pod/wf-blog-group-1193326311            0/1     Completed   0          43m
pod/wf-blog-group-2026876860            0/1     Completed   0          43m
pod/wf-blog-group-2234690393            0/1     Completed   0          43m
pod/wf-blog-group-2432013970            0/1     Completed   0          43m

NAME                       TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)    AGE
service/armada-operator    ClusterIP   10.98.2.253      <none>        8383/TCP   44m
service/blog-1-testchart   ClusterIP   10.104.240.7     <none>        80/TCP     43m
service/blog-2-testchart   ClusterIP   10.110.160.242   <none>        80/TCP     43m
service/kubernetes         ClusterIP   10.96.0.1        <none>        443/TCP    51m

NAME                               READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/armada-operator    1/1     1            1           44m
deployment.apps/blog-1-testchart   1/1     1            1           43m
deployment.apps/blog-2-testchart   1/1     1            1           43m

NAME                                          DESIRED   CURRENT   READY   AGE
replicaset.apps/armada-operator-cbbc7d7f7     1         1         1       44m
replicaset.apps/blog-1-testchart-5dd8c474f4   1         1         1       43m
replicaset.apps/blog-2-testchart-57f86dd9c5   1         1         1       43m
```

argo is tracing the steps take to sequence the deployment of the charts:

```bash
argo get wf-blog-group

Name:                wf-blog-group
Namespace:           default
ServiceAccount:      armada-argo-sa
Status:              Succeeded
Created:             Fri Mar 22 10:27:28 -0500 (26 seconds ago)
Started:             Fri Mar 22 10:27:28 -0500 (26 seconds ago)
Finished:            Fri Mar 22 10:27:42 -0500 (12 seconds ago)
Duration:            14 seconds

STEP                  PODNAME                   DURATION  MESSAGE
 ✔ wf-blog-group
 ├---✔ enable-blog-1  wf-blog-group-1193326311  2s
 ├---✔ blog-1-ready   wf-blog-group-2432013970  3s
 ├---✔ enable-blog-2  wf-blog-group-2026876860  3s
 └---✔ blog-2-ready   wf-blog-group-2234690393  3s
 ```

We can check the state of the ArmadaChart

```bash
kubectl get act

NAME     STATE      TARGET STATE   SATISFIED
blog-1   deployed   deployed       true
blog-2   deployed   deployed       true
```

Run the cleanup
```bash

kubectl delete -f examples/argo
```

## examples/sequenced

In that directory, the ArmadaChart (act) are disabled by default and the charts not installed
automatically when the act CR are created.
When the "ArmadaChartGroup" CR is created, the "chartgroup controller" receives an event and it
orchestrate the order of deployment/enablement of the ArmadaChart. The ArmadaChartGroup also
becomes owner of the ArmadaChart. 

This is basically the same sequencing that above except that it is implemented using an
ArmadaChartGroup and an ArmadaManifest

## examples/backup

This directory contains the CR definitions involved during an ArmadaBackup procedure.

- WIP

## examples/restore

This directory contains the CR definitions involved during an ArmadaRestore procedure.

- WIP

# Appendix

[POCs](./pocs/README.md) contains additional notes regarding successful and failed attempts.