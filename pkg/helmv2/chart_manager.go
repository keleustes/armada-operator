// Copyright 2018 The Operator-SDK Authors
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

// +build v2

package helmv2

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"strings"

	av1 "github.com/keleustes/armada-crd/pkg/apis/armada/v1alpha1"
	helmif "github.com/keleustes/armada-operator/pkg/services"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"

	apierrors "k8s.io/apimachinery/pkg/api/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	apitypes "k8s.io/apimachinery/pkg/types"
	"k8s.io/cli-runtime/pkg/resource"
	"k8s.io/client-go/rest"

	// yaml "github.com/ghodss/yaml"
	"k8s.io/helm/pkg/chartutil"
	"k8s.io/helm/pkg/kube"
	cpb "k8s.io/helm/pkg/proto/hapi/chart"
	rpb "k8s.io/helm/pkg/proto/hapi/release"
	svc "k8s.io/helm/pkg/proto/hapi/services"
	"k8s.io/helm/pkg/storage"
	"k8s.io/helm/pkg/tiller"
	yaml "sigs.k8s.io/yaml"

	"github.com/mattbaird/jsonpatch"
)

type chartmanager struct {
	storageBackend     *storage.Storage
	tillerKubeClient   *kube.Client
	operatorKubeClient *kube.Client

	releaseManager *tiller.ReleaseServer
	releaseName    string
	namespace      string

	newValues interface{}
	spec      av1.ArmadaChartSpec
	status    *av1.ArmadaChartStatus

	isInstalled      bool
	isUpdateRequired bool
	deployedRelease  *helmif.HelmRelease
	chart            *cpb.Chart
	config           *cpb.Config
}

// ReleaseName returns the name of the release.
func (m chartmanager) ReleaseName() string {
	return m.releaseName
}

func (m chartmanager) IsInstalled() bool {
	return m.isInstalled
}

func (m chartmanager) IsUpdateRequired() bool {
	return m.isUpdateRequired
}

func notFoundErr(err error) bool {
	return strings.Contains(err.Error(), "not found")
}

// Sync ensures the Helm storage backend is in sync with the status of the
// custom resource.
func (m *chartmanager) Sync(ctx context.Context) error {
	if err := m.syncReleaseStatus(*m.status); err != nil {
		return fmt.Errorf("failed to sync release status to storage backend: %s", err)
	}

	// Get release history for this release name
	releases, err := m.storageBackend.History(m.releaseName)
	if err != nil && !notFoundErr(err) {
		return fmt.Errorf("failed to retrieve release history: %s", err)
	}

	// Cleanup non-deployed release versions. If all release versions are
	// non-deployed, this will ensure that failed installations are correctly
	// retried.
	for _, rel := range releases {
		if rel.GetInfo().GetStatus().GetCode() != rpb.Status_DEPLOYED {
			_, err := m.storageBackend.Delete(rel.GetName(), rel.GetVersion())
			if err != nil && !notFoundErr(err) {
				return fmt.Errorf("failed to delete stale release version: %s", err)
			}
		}
	}

	// Load the chart and config based on the current state of the custom resource.
	// Replace this with sources from armada
	chart, config, err := m.loadChartAndConfig()
	if err != nil {
		return fmt.Errorf("failed to load chart and config: %s", err)
	}
	m.chart = chart
	m.config = config

	// Load the most recently deployed release from the storage backend.
	deployedRelease, err := m.getDeployedRelease()
	if err == helmif.ErrNotFound {
		return nil
	}
	if err != nil {
		return fmt.Errorf("failed to get deployed release: %s", err)
	}
	m.deployedRelease = &helmif.HelmRelease{Release: deployedRelease}
	m.isInstalled = true

	// Get the next candidate release to determine if an update is necessary.
	candidateRelease, err := m.getCandidateRelease(ctx, m.releaseManager, m.releaseName, chart, config)
	if err != nil {
		return fmt.Errorf("failed to get candidate release: %s", err)
	}
	if deployedRelease.GetManifest() != candidateRelease.GetManifest() {
		// TODO(jeb): There is a bug here. Can't figure out the
		// infinite loop that seems to be happening when worflow are involved.
		// m.isUpdateRequired = true
		m.isUpdateRequired = false
	}

	return nil
}

func (m chartmanager) syncReleaseStatus(status av1.ArmadaChartStatus) error {
	var release *rpb.Release
	helper := av1.HelmResourceConditionListHelper{Items: status.Conditions}
	condition := helper.FindCondition(av1.ConditionDeployed, av1.ConditionStatusTrue)
	if condition == nil {
		return nil
	} else {
		// JEB: Big issue here. Original code was saving the release in the Condition
		// Still does not work right and cause fatal in the subsequent m.storageBackend.Create(release)
		// release = &rpb.Release{Name: condition.ResourceName, Version: condition.ResourceVersion}
		release = nil
	}
	if release == nil {
		return nil
	}

	name := release.GetName()
	version := release.GetVersion()
	_, err := m.storageBackend.Get(name, version)
	if err == nil {
		return nil
	}

	if !notFoundErr(err) {
		return err
	}
	return m.storageBackend.Create(release)
}

func (m chartmanager) loadChartAndConfig() (*cpb.Chart, *cpb.Config, error) {
	// chart is mutated by the call to processRequirements,
	// so we need to reload it every time.
	source := source{chartLocation: m.spec.Source, chartDependencies: m.spec.Dependencies}
	chart, err := source.getChart()
	if err != nil {
		return nil, nil, fmt.Errorf("failed to load chart: %s", err)
	}

	cr, err := yaml.Marshal(m.spec.Values)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to parse values: %s", err)
	}
	config, err := normalizeConfig(&cpb.Config{Raw: string(cr)})
	if err != nil {
		return nil, nil, fmt.Errorf("failed to parse values: %s", err)
	}

	// JEB: In order to check how tiller will merge the values
	// JEB: We should actually check the syntax of the values against a schema there
	log.Info("loadChartAndConfig", "config", string(cr))
	// vals, err := chartutil.CoalesceValues(chart, config)
	// if err != nil {
	// 	return nil, nil, err
	// } else {
	// 	merged, _ := vals.YAML()
	// 	log.Info("loadChartAndConfig", "merged", merged)
	// }

	err = m.processRequirements(chart, config)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to process chart requirements: %s", err)
	}

	return chart, config, nil
}

// processRequirements will process the requirements file
// It will disable/enable the charts based on condition in requirements file
// Also imports the specified chart values from child to parent.
func (m chartmanager) processRequirements(chart *cpb.Chart, values *cpb.Config) error {
	err := chartutil.ProcessRequirementsEnabled(chart, values)
	if err != nil {
		return err
	}
	err = chartutil.ProcessRequirementsImportValues(chart)
	if err != nil {
		return err
	}
	return nil
}

func (m chartmanager) getDeployedRelease() (*rpb.Release, error) {
	deployedRelease, err := m.storageBackend.Deployed(m.releaseName)
	if err != nil {
		if strings.Contains(err.Error(), "has no deployed releases") {
			return nil, helmif.ErrNotFound
		}
		return nil, err
	}
	return deployedRelease, nil
}

func (m chartmanager) getCandidateRelease(ctx context.Context, tiller *tiller.ReleaseServer, name string, chart *cpb.Chart, config *cpb.Config) (*rpb.Release, error) {
	dryRunReq := &svc.UpdateReleaseRequest{
		Name:   name,
		Chart:  chart,
		Values: config,
		DryRun: true,
	}
	dryRunResponse, err := tiller.UpdateRelease(ctx, dryRunReq)
	if err != nil {
		return nil, err
	}
	return dryRunResponse.GetRelease(), nil
}

// InstallRelease performs a "helm install" equivalent
func (m chartmanager) InstallRelease(ctx context.Context) (*helmif.HelmRelease, error) {
	installedRelease, err := m.installRelease(ctx, m.releaseManager, m.namespace, m.releaseName, m.chart, m.config)
	return &helmif.HelmRelease{Release: installedRelease}, err
}

func (m chartmanager) installRelease(ctx context.Context, releaseServer *tiller.ReleaseServer, namespace, name string, chart *cpb.Chart, config *cpb.Config) (*rpb.Release, error) {
	installReq := &svc.InstallReleaseRequest{
		Namespace: namespace,
		Name:      name,
		Chart:     chart,
		Values:    config,
	}

	releaseResponse, err := releaseServer.InstallRelease(ctx, installReq)
	if err != nil {
		// Workaround for helm/helm#3338
		if releaseResponse.GetRelease() != nil {
			uninstallReq := &svc.UninstallReleaseRequest{
				Name:  releaseResponse.GetRelease().GetName(),
				Purge: true,
			}
			_, uninstallErr := releaseServer.UninstallRelease(ctx, uninstallReq)
			if uninstallErr != nil {
				return nil, fmt.Errorf("failed to roll back failed installation: %s: %s", uninstallErr, err)
			}
		}
		return nil, err
	}
	return releaseResponse.GetRelease(), nil
}

// InstallRelease performs a "helm upgrade" equivalent
// Most likely the Values field in the ArmadaChart or the Version of the Chart may have change.
func (m chartmanager) UpdateRelease(ctx context.Context) (*helmif.HelmRelease, *helmif.HelmRelease, error) {
	updatedRelease, err := m.updateRelease(ctx, m.releaseManager, m.releaseName, m.chart, m.config)
	return m.deployedRelease, &helmif.HelmRelease{Release: updatedRelease}, err
}

func (m chartmanager) updateRelease(ctx context.Context, releaseServer *tiller.ReleaseServer, name string, chart *cpb.Chart, config *cpb.Config) (*rpb.Release, error) {
	updateReq := &svc.UpdateReleaseRequest{
		Name:   name,
		Chart:  chart,
		Values: config,
	}

	releaseResponse, err := releaseServer.UpdateRelease(ctx, updateReq)
	if err != nil {
		// Workaround for helm/helm#3338
		if releaseResponse.GetRelease() != nil {
			rollbackReq := &svc.RollbackReleaseRequest{
				Name:  name,
				Force: true,
			}
			_, rollbackErr := releaseServer.RollbackRelease(ctx, rollbackReq)
			if rollbackErr != nil {
				return nil, fmt.Errorf("failed to roll back failed update: %s: %s", rollbackErr, err)
			}
		}
		return nil, err
	}
	return releaseResponse.GetRelease(), nil
}

// ReconcileRelease creates or patches resources as necessary to match the
// deployed release's manifest.
func (m *chartmanager) ReconcileRelease(ctx context.Context) (*helmif.HelmRelease, error) {
	err := m.reconcileRelease(ctx, m.tillerKubeClient, m.namespace, m.deployedRelease.GetManifest())
	return m.deployedRelease, err
}

func (m *chartmanager) reconcileRelease(ctx context.Context, tillerKubeClient *kube.Client, namespace string, expectedManifest string) error {
	expectedInfos, err := tillerKubeClient.BuildUnstructured(namespace, bytes.NewBufferString(expectedManifest))
	if err != nil {
		return err
	}
	return expectedInfos.Visit(func(expected *resource.Info, err error) error {
		if err != nil {
			return err
		}

		expectedClient := resource.NewClientWithOptions(expected.Client, func(r *rest.Request) {
			*r = *r.Context(ctx)
		})
		helper := resource.NewHelper(expectedClient, expected.Mapping)

		existing, err := helper.Get(expected.Namespace, expected.Name, false)
		if apierrors.IsNotFound(err) {
			if _, err := helper.Create(expected.Namespace, true, expected.Object, &metav1.CreateOptions{}); err != nil {
				return fmt.Errorf("create error: %s", err)
			}
			return nil
		} else if err != nil {
			return err
		}

		// TODO(jeb): Let collect the status of the object at the same time
		// to undestand if the resources are still deploying
		existingU, err2 := m.toUnstructured(existing)
		if err2 != nil || existingU == nil {
			return fmt.Errorf("failed to convert to Unstructured : %s", err2)
		}
		m.deployedRelease.AddToCache(*existingU)

		patch, err := m.generatePatch(existing, expected.Object)
		if err != nil {
			return fmt.Errorf("failed to marshal JSON patch: %s", err)
		}

		if patch == nil {
			return nil
		}

		_, err = helper.Patch(expected.Namespace, expected.Name, apitypes.JSONPatchType, patch, &metav1.PatchOptions{})
		if err != nil {
			return fmt.Errorf("patch error: %s", err)
		}

		// TODO(jeb): We may have to refetch the state here
		// or keep the state of the HelmRelease to running since
		// we just changed something.

		return nil
	})
}

func (m chartmanager) toUnstructured(existing runtime.Object) (*unstructured.Unstructured, error) {
	existingJSON, err := json.Marshal(existing)
	if err != nil {
		return nil, err
	}

	u := &unstructured.Unstructured{}
	err = u.UnmarshalJSON(existingJSON)
	if err != nil {
		return nil, err
	}

	return u, nil

}

func (m chartmanager) generatePatch(existing, expected runtime.Object) ([]byte, error) {
	existingJSON, err := json.Marshal(existing)
	if err != nil {
		return nil, err
	}
	expectedJSON, err := json.Marshal(expected)
	if err != nil {
		return nil, err
	}

	ops, err := jsonpatch.CreatePatch(existingJSON, expectedJSON)
	if err != nil {
		return nil, err
	}

	// We ignore the "remove" operations from the full patch because they are
	// fields added by Kubernetes or by the user after the existing release
	// resource has been applied. The goal for this patch is to make sure that
	// the fields managed by the Helm chart are applied.
	patchOps := make([]jsonpatch.JsonPatchOperation, 0)
	for _, op := range ops {
		if op.Operation != "remove" {
			patchOps = append(patchOps, op)
		}
	}

	// If there are no patch operations, return nil. Callers are expected
	// to check for a nil response and skip the patch operation to avoid
	// unnecessary chatter with the API server.
	if len(patchOps) == 0 {
		return nil, nil
	}

	return json.Marshal(patchOps)
}

// UninstallRelease performs a "helm delete" equivalent
func (m chartmanager) UninstallRelease(ctx context.Context) (*helmif.HelmRelease, error) {
	uninstalledRelease, err := m.uninstallRelease(ctx, m.storageBackend, m.releaseManager, m.releaseName)
	return &helmif.HelmRelease{Release: uninstalledRelease}, err
}

func (m chartmanager) uninstallRelease(ctx context.Context, storageBackend *storage.Storage, releaseServer *tiller.ReleaseServer, releaseName string) (*rpb.Release, error) {
	// Get history of this release
	h, err := storageBackend.History(releaseName)
	if err != nil {
		return nil, fmt.Errorf("failed to get release history: %s", err)
	}

	// If there is no history, the release has already been uninstalled,
	// so return ErrNotFound.
	if len(h) == 0 {
		return nil, helmif.ErrNotFound
	}

	uninstallResponse, err := releaseServer.UninstallRelease(ctx, &svc.UninstallReleaseRequest{
		Name:  releaseName,
		Purge: true,
	})
	return uninstallResponse.GetRelease(), err
}
