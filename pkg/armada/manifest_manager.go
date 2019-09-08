// Copyright 2019 The Armada Authors
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package armada

import (
	"context"

	av1 "github.com/keleustes/armada-operator/pkg/apis/armada/v1alpha1"
	armadaif "github.com/keleustes/armada-operator/pkg/services"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/types"

	"sigs.k8s.io/controller-runtime/pkg/client"
	logf "sigs.k8s.io/controller-runtime/pkg/runtime/log"
)

var amflog = logf.Log.WithName("amf-manager")

type manifestmanager struct {
	kubeClient       client.Client
	resourceName     string
	namespace        string
	spec             *av1.ArmadaManifestSpec
	status           *av1.ArmadaManifestStatus
	deployedResource *av1.ArmadaChartGroups

	isInstalled      bool
	isUpdateRequired bool
}

// ResourceName returns the name of the release.
func (m manifestmanager) ResourceName() string {
	return m.resourceName
}

func (m manifestmanager) IsInstalled() bool {
	return m.isInstalled
}

func (m manifestmanager) IsUpdateRequired() bool {
	return m.isUpdateRequired
}

// Sync detects which ArmadaChartGroup listed this ArmadaManifest are already present in
// the K8s cluster.
func (m *manifestmanager) Sync(ctx context.Context) error {
	m.deployedResource = av1.NewArmadaChartGroups(m.resourceName)
	errs := make([]error, 0)
	targetResourceList := m.expectedChartGroupList()
	for _, existingResource := range targetResourceList.List.Items {
		err := m.kubeClient.Get(context.TODO(), types.NamespacedName{Name: existingResource.Name, Namespace: existingResource.Namespace}, &existingResource)
		if err != nil {
			if !apierrors.IsNotFound(err) {
				// Don't want to trace is the error is not a NotFound.
				amflog.Error(err, "Can't not retrieve ArmadaChartGroup")
			}
			errs = append(errs, err)
		} else {
			m.deployedResource.List.Items = append(m.deployedResource.List.Items, existingResource)
		}
	}

	amflog.Info("ChartGroups", "deployedResources", m.deployedResource.States())

	// The ChartGroup manager is not in charge of creating the ArmaChart since it
	// only contains the name of the charts.
	if len(errs) != 0 {
		// Regardless if the error is NotFound or something else,
		// we can't sync the ArmadaChartGroup with content of Kubernetes.
		m.isUpdateRequired = false
		return errs[0]
	}

	// TODO(jeb): We should check that the ArmadaManifest is still not the "owner" of
	// chartgroups which are not listed in its Spec anymore. In such as case we should put
	// the isUpdateRequired to true.
	m.isUpdateRequired = false
	m.isInstalled = true
	if m.status.ActualState != av1.StateDeployed {
		for _, deployedResource := range m.deployedResource.List.Items {
			existingRefs := deployedResource.GetOwnerReferences()
			if len(existingRefs) == 0 {
				m.isInstalled = false
			}
		}
	}

	return nil
}

// InstallResource checks that the corresponding chartgroups are present
// TODO(jeb): We should most likely update the target_state is not already done.
// TODO(jeb): We should also update the the owner of the charts.
func (m manifestmanager) InstallResource(ctx context.Context) (*av1.ArmadaChartGroups, error) {
	installedResources := av1.NewArmadaChartGroups(m.resourceName)
	targetResourceList := m.expectedChartGroupList()
	for _, existingResource := range targetResourceList.List.Items {
		err := m.kubeClient.Get(context.TODO(), types.NamespacedName{Name: existingResource.GetName(), Namespace: existingResource.GetNamespace()}, &existingResource)
		if err == nil {
			installedResources.List.Items = append(installedResources.List.Items, existingResource)
		}
	}

	return installedResources, nil
}

// UpdateResource performs an update of an ArmadaManifest.
// Currently either the list of ChartGroupss or the "prefix" attribute may have changed.
func (m manifestmanager) UpdateResource(ctx context.Context) (*av1.ArmadaChartGroups, *av1.ArmadaChartGroups, error) {
	errs := make([]error, 0)
	toUpdateList := m.expectedChartGroupList()
	for _, toUpdate := range (*toUpdateList).List.Items {
		err := m.kubeClient.Update(context.TODO(), &toUpdate)
		if err != nil {
			amflog.Error(err, "Can't not Update ArmadaChartGroup")
			errs = append(errs, err)
		}
	}

	if len(errs) != 0 {
		if apierrors.IsNotFound(errs[0]) {
			return nil, nil, armadaif.ErrNotFound
		} else {
			return nil, nil, errs[0]
		}
	}
	return m.deployedResource, toUpdateList, nil
}

// ReconcileResource enables the ArmadaChartGroups which are listed in its list and not enabled yet
func (m manifestmanager) ReconcileResource(ctx context.Context) (*av1.ArmadaChartGroups, error) {
	errs := make([]error, 0)

	// The main goal of the ArmadaManifest is to group together all the ChartGroups that need to
	// be deployed. The concept of sequencing is implicit here
	chartGroupsToEnable := av1.NewArmadaChartGroups(m.resourceName)
	nextToEnable := m.deployedResource.GetNextToEnable()
	if nextToEnable != nil {
		chartGroupsToEnable.List.Items = append(chartGroupsToEnable.List.Items, *nextToEnable)
	}

	for _, nextToEnable := range (*chartGroupsToEnable).List.Items {
		found := nextToEnable.FromArmadaChartGroup()
		err := m.kubeClient.Get(context.TODO(), types.NamespacedName{Name: found.GetName(), Namespace: found.GetNamespace()}, &nextToEnable)
		if err == nil {
			nextToEnable.Spec.TargetState = av1.StateDeployed
			if err2 := m.kubeClient.Update(context.TODO(), &nextToEnable); err2 != nil {
				amflog.Error(err, "Can't get enable of ArmadaChartGroup", "name", found.GetName())
				errs = append(errs, err)
			}
			amflog.Info("Enabled ArmadaChartGroup", "name", found.GetName())
		} else {
			amflog.Error(err, "Can't enable ArmadaChartGroup", "name", found.GetName())
			errs = append(errs, err)
		}
	}

	if len(errs) != 0 {
		return m.deployedResource, errs[0]
	}
	return m.deployedResource, nil
}

// UninstallResource currently delete ChartGroups matching the manifest.
// This is probably not the behavior we want to maitain in the long run.
func (m manifestmanager) UninstallResource(ctx context.Context) (*av1.ArmadaChartGroups, error) {
	errs := make([]error, 0)
	toDeleteList := m.expectedChartGroupList()
	for _, toDelete := range (*toDeleteList).List.Items {
		err := m.kubeClient.Delete(context.TODO(), &toDelete)
		if err != nil {
			amflog.Error(err, "Can't not Delete ArmadaChartGroup")
			errs = append(errs, err)
		}
	}

	if len(errs) != 0 {
		if apierrors.IsNotFound(errs[0]) {
			return nil, armadaif.ErrNotFound
		} else {
			return nil, errs[0]
		}
	}
	return toDeleteList, nil
}

// expectedChartGroupList returns a dummy list of ArmadaChartGroup the same name/namespace as the cr
// TODO(jeb): We should be able to delete this function and use the GetMockChartGroups
// method of the ArmadaManifest.
func (m manifestmanager) expectedChartGroupList() *av1.ArmadaChartGroups {
	labels := map[string]string{
		"app": m.resourceName,
	}

	var res = av1.NewArmadaChartGroups(m.resourceName)

	for _, chartgroupname := range m.spec.ChartGroups {
		res.List.Items = append(res.List.Items,
			av1.ArmadaChartGroup{
				ObjectMeta: metav1.ObjectMeta{
					Name:      chartgroupname,
					Namespace: m.namespace,
					Labels:    labels,
				},
				Spec: av1.ArmadaChartGroupSpec{
					Charts:      make([]string, 0),
					Description: "Created by " + m.resourceName,
					Name:        chartgroupname,
					Sequenced:   false,
					TestCharts:  false,
					TargetState: av1.StateUninitialized,
				},
			},
		)
	}

	return res
}
