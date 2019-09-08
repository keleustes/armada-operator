// Copyright 2019 The OpenstackLcm Authors
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

package services

import (
	"fmt"
	"strings"

	batchv1 "k8s.io/api/batch/v1"
	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	runtime "k8s.io/apimachinery/pkg/runtime"
)

type KubernetesDependency struct {
}

// Is the status of the Unstructured ready
func (obj *KubernetesDependency) IsUnstructuredReady(u *unstructured.Unstructured) bool {
	if u == nil {
		return true
	}

	// TODO(jeb): Any better pattern possible here ?
	switch u.GetKind() {
	case "Pod":
		{
			return obj.IsPodReady(u)
		}
	case "Job":
		{
			return obj.IsJobReady(u)
		}
	case "Service":
		{
			return true
		}
	case "Deployment":
		{
			return true
		}
	case "StatefulSet":
		{
			return true
		}
	case "Workflow":
		{
			return obj.IsWorkflowReady(u)
		}
	case "ArmadaChart":
		{
			return obj.IsArmadaChartReady(u)
		}
	case "ArmadaChartGroup":
		{
			return obj.IsArmadaChartGroupReady(u)
		}
	case "ArmadaManifest":
		{
			return obj.IsArmadaManifestReady(u)
		}
	// case "PodDisruptionBudget":
	// case "ServiceAccount":
	// case "Role":
	// case "RoleBinding":
	// case "Secret":
	// case "ConfigMap":
	// case "Ingress":
	// case "CronJob":
	default:
		{
			return true
		}
	}
}

// Is the status of the Unstructured ready
func (obj *KubernetesDependency) IsUnstructuredFailedOrError(u *unstructured.Unstructured) bool {
	if u == nil {
		return false
	}

	// TODO(jeb): Any better pattern possible here ?
	switch u.GetKind() {
	case "Pod":
		{
			return obj.IsPodFailedOrError(u)
		}
	case "Job":
		{
			return obj.IsJobFailedOrError(u)
		}
	case "Service":
		{
			return false
		}
	case "Deployment":
		{
			return false
		}
	case "StatefulSet":
		{
			return false
		}
	case "Workflow":
		{
			return obj.IsWorkflowFailedOrError(u)
		}
	case "ArmadaChart":
		{
			return obj.IsArmadaChartFailedOrError(u)
		}
	case "ArmadaChartGroup":
		{
			return obj.IsArmadaChartGroupFailedOrError(u)
		}
	case "ArmadaManifest":
		{
			return obj.IsArmadaManifestFailedOrError(u)
		}
	// case "PodDisruptionBudget":
	// case "ServiceAccount":
	// case "Role":
	// case "RoleBinding":
	// case "Secret":
	// case "ConfigMap":
	// case "Ingress":
	// case "CronJob":
	default:
		{
			return false
		}
	}
}

// Did the status changed
func (obj *KubernetesDependency) UnstructuredStatusChanged(u *unstructured.Unstructured, v *unstructured.Unstructured) (bool, string, string) {
	if u == nil || v == nil {
		return true, "", ""
	}

	if u.GetKind() != v.GetKind() {
		return false, "", ""
	}

	// TODO(jeb): Any better pattern possible here ?
	switch u.GetKind() {
	case "Pod":
		{
			return obj.PodStatusChanged(u, v)
		}
	case "Job":
		{
			return obj.JobStatusChanged(u, v)
		}
	case "Service":
		{
			return false, "", ""
		}
	case "Deployment":
		{
			return false, "", ""
		}
	case "StatefulSet":
		{
			return false, "", ""
		}
	case "Workflow":
		{
			return obj.WorkflowStatusChanged(u, v)
		}
	case "ArmadaChart":
		{
			return obj.ArmadaChartStatusChanged(u, v)
		}
	case "ArmadaChartGroup":
		{
			return obj.ArmadaChartGroupStatusChanged(u, v)
		}
	case "ArmadaManifest":
		{
			return obj.ArmadaManifestStatusChanged(u, v)
		}
	// case "PodDisruptionBudget":
	// case "ServiceAccount":
	// case "Role":
	// case "RoleBinding":
	// case "Secret":
	// case "ConfigMap":
	// case "Ingress":
	// case "CronJob":
	default:
		{
			return false, "", ""
		}
	}
}

// Check the state of the ArmadaChart to figure out if it is still running
func (obj *KubernetesDependency) IsArmadaChartReady(u *unstructured.Unstructured) bool {
	return obj.IsCustomResourceReady("status.actual_state", []string{"Deployed"}, u)
}

// Check the state of the ArmadaChart to figure out if it is still running
func (obj *KubernetesDependency) IsArmadaChartFailedOrError(u *unstructured.Unstructured) bool {
	return obj.IsCustomResourceReady("status.actual_state", []string{"Error", "Failed"}, u)
}

func (obj *KubernetesDependency) ArmadaChartStatusChanged(u *unstructured.Unstructured, v *unstructured.Unstructured) (bool, string, string) {
	return obj.CustomResourceStatusChanged("status.actual_state", u, v)
}

// Check the state of the ArmadaChartGroup to figure out if it is still running
func (obj *KubernetesDependency) IsArmadaChartGroupReady(u *unstructured.Unstructured) bool {
	return obj.IsCustomResourceReady("status.actual_state", []string{"Deployed"}, u)
}

// Check the state of the ArmadaChartGroup to figure out if it failed
func (obj *KubernetesDependency) IsArmadaChartGroupFailedOrError(u *unstructured.Unstructured) bool {
	return obj.IsCustomResourceReady("status.actual_state", []string{"Error", "Failed"}, u)
}

func (obj *KubernetesDependency) ArmadaChartGroupStatusChanged(u *unstructured.Unstructured, v *unstructured.Unstructured) (bool, string, string) {
	return obj.CustomResourceStatusChanged("status.actual_state", u, v)
}

// Check the state of the ArmadaManifest to figure out if it is still running
func (obj *KubernetesDependency) IsArmadaManifestReady(u *unstructured.Unstructured) bool {
	return obj.IsCustomResourceReady("status.actual_state", []string{"Deployed"}, u)
}

// Check the state of the ArmadaManifest to figure out if it failed
func (obj *KubernetesDependency) IsArmadaManifestFailedOrError(u *unstructured.Unstructured) bool {
	return obj.IsCustomResourceReady("status.actual_state", []string{"Error", "Failed"}, u)
}

func (obj *KubernetesDependency) ArmadaManifestStatusChanged(u *unstructured.Unstructured, v *unstructured.Unstructured) (bool, string, string) {
	return obj.CustomResourceStatusChanged("status.actual_state", u, v)
}

// Check the state of the Main workflow to figure out
// if the phase is still running
// This code is inspired from the kubernetes-entrypoint project
func (obj *KubernetesDependency) IsWorkflowReady(u *unstructured.Unstructured) bool {
	return obj.IsCustomResourceReady("status.phase", []string{"Succeeded"}, u)
}

func (obj *KubernetesDependency) IsWorkflowFailedOrError(u *unstructured.Unstructured) bool {
	return obj.IsCustomResourceReady("status.phase", []string{"Error", "Failed"}, u)
}

// Compare the phase between to Workflow
func (obj *KubernetesDependency) WorkflowStatusChanged(u *unstructured.Unstructured, v *unstructured.Unstructured) (bool, string, string) {
	return obj.CustomResourceStatusChanged("status.phase", u, v)
}

// Check the state of a custom resource
// This code is inspired from the kubernetes-entrypoint project
func (obj *KubernetesDependency) IsCustomResourceReady(key string, expectedValues []string,
	u *unstructured.Unstructured) bool {
	actualValue := obj.extractField(key, u)
	for _, expectedValue := range expectedValues {
		if actualValue == expectedValue {
			return true
		}
	}
	return false
}

// Compare the status between two CustomResource
// A status of "" is considered as a default value, hence transition
// to and from "" is not considered as a status change.
func (obj *KubernetesDependency) CustomResourceStatusChanged(key string,
	u *unstructured.Unstructured,
	v *unstructured.Unstructured) (bool, string, string) {
	uValue := obj.extractField(key, u)
	vValue := obj.extractField(key, v)
	return uValue != "" && vValue != "" && uValue != vValue, uValue, vValue
}

// Utility function to extract a field value from an Unstructured object
// This code is inspired from the kubernetes-entrypoint project
func (obj *KubernetesDependency) extractField(key string, u *unstructured.Unstructured) string {

	if u == nil {
		return ""
	}

	customResource := u.UnstructuredContent()

	for i := strings.Index(key, "."); i != -1; i = strings.Index(key, ".") {
		first := key[:i]
		key = key[i+1:]
		if customResource[first] != nil {
			customResource = customResource[first].(map[string]interface{})
		} else {
			return ""
		}
	}

	if customResource != nil {
		return customResource[key].(string)
	} else {
		return ""
	}
}

// Check the state of a service
// This code is inspired from the kubernetes-entrypoint project
func (obj *KubernetesDependency) IsServiceReady(u *unstructured.Unstructured) bool {
	if u == nil {
		return false
	}

	endpointsu := corev1.Endpoints{}
	err1u := runtime.DefaultUnstructuredConverter.FromUnstructured(u.UnstructuredContent(), &endpointsu)
	if err1u != nil {
		return false
	}

	for _, subset := range endpointsu.Subsets {
		if len(subset.Addresses) > 0 {
			return true
		}
	}
	return false
}

func (obj *KubernetesDependency) IsServiceFailedOrError(u *unstructured.Unstructured) bool {
	if u == nil {
		return false
	}

	endpointsu := corev1.Endpoints{}
	err1u := runtime.DefaultUnstructuredConverter.FromUnstructured(u.UnstructuredContent(), &endpointsu)
	if err1u != nil {
		return false
	}

	for _, subset := range endpointsu.Subsets {
		if false {
			log.Info("%v", subset)
		}
	}

	return false
}

// Check the state of a container
// This code is inspired from the kubernetes-entrypoint project
func (obj *KubernetesDependency) IsContainerReady(containerName string, u *unstructured.Unstructured) bool {
	if u == nil {
		return false
	}

	podu := corev1.Pod{}
	err1u := runtime.DefaultUnstructuredConverter.FromUnstructured(u.UnstructuredContent(), &podu)
	if err1u != nil {
		return false
	}

	containers := podu.Status.ContainerStatuses
	for _, container := range containers {
		if container.Name == containerName && container.Ready {
			return true
		}
	}
	return false
}

// Check the state of a job
// This code is inspired from the kubernetes-entrypoint project
func (obj *KubernetesDependency) IsJobReady(u *unstructured.Unstructured) bool {
	if u == nil {
		return false
	}

	jobu := batchv1.Job{}
	err1u := runtime.DefaultUnstructuredConverter.FromUnstructured(u.UnstructuredContent(), &jobu)
	if err1u != nil {
		return false
	}

	if jobu.Status.Succeeded == 0 {
		return false
	}
	return true
}

func (obj *KubernetesDependency) IsJobFailedOrError(u *unstructured.Unstructured) bool {
	if u == nil {
		return false
	}

	jobu := batchv1.Job{}
	err1u := runtime.DefaultUnstructuredConverter.FromUnstructured(u.UnstructuredContent(), &jobu)
	if err1u != nil {
		return false
	}

	if jobu.Status.Failed == 0 {
		return false
	}
	return true
}

// Compare the status field between two Job
func (obj *KubernetesDependency) JobStatusChanged(u *unstructured.Unstructured, v *unstructured.Unstructured) (bool, string, string) {
	if u == nil || v == nil {
		return true, "", ""
	}

	jobu := batchv1.Job{}
	err1u := runtime.DefaultUnstructuredConverter.FromUnstructured(u.UnstructuredContent(), &jobu)
	if err1u != nil {
		return true, "", ""
	}

	jobv := batchv1.Job{}
	err1v := runtime.DefaultUnstructuredConverter.FromUnstructured(v.UnstructuredContent(), &jobv)
	if err1v != nil {
		return true, "", ""
	}

	return (jobu.Status.Succeeded != jobv.Status.Succeeded) || (jobu.Status.Failed != jobv.Status.Failed),
		fmt.Sprintf("%v|%v", jobu.Status.Succeeded, jobu.Status.Failed),
		fmt.Sprintf("%v|%v", jobv.Status.Succeeded, jobv.Status.Failed)
}

// Check the state of a pod
// This code is inspired from the kubernetes-entrypoint project
func (obj *KubernetesDependency) IsPodReady(u *unstructured.Unstructured) bool {
	if u == nil {
		return false
	}

	podu := corev1.Pod{}
	err1u := runtime.DefaultUnstructuredConverter.FromUnstructured(u.UnstructuredContent(), &podu)
	if err1u != nil {
		return false
	}

	for _, condition := range podu.Status.Conditions {
		if condition.Type == corev1.PodReady && condition.Status == "True" {
			return true
		}
	}
	return false
}

func (obj *KubernetesDependency) IsPodFailedOrError(u *unstructured.Unstructured) bool {
	if u == nil {
		return false
	}

	podu := corev1.Pod{}
	err1u := runtime.DefaultUnstructuredConverter.FromUnstructured(u.UnstructuredContent(), &podu)
	if err1u != nil {
		return false
	}

	for _, status := range podu.Status.Conditions {
		if false {
			log.Info("%v", status)
		}
	}

	return false
}

// PodStatus changed
func (obj *KubernetesDependency) PodStatusChanged(u *unstructured.Unstructured, v *unstructured.Unstructured) (bool, string, string) {
	if u == nil || v == nil {
		return true, "", ""
	}

	podu := corev1.Pod{}
	err1u := runtime.DefaultUnstructuredConverter.FromUnstructured(u.UnstructuredContent(), &podu)
	if err1u != nil {
		return false, "", ""
	}

	podv := corev1.Pod{}
	err1v := runtime.DefaultUnstructuredConverter.FromUnstructured(v.UnstructuredContent(), &podv)
	if err1v != nil {
		return false, "", ""
	}

	var conditionu corev1.ConditionStatus
	for _, condition := range podu.Status.Conditions {
		if condition.Type == corev1.PodReady {
			conditionu = condition.Status
		}
	}

	var conditionv corev1.ConditionStatus
	for _, condition := range podv.Status.Conditions {
		if condition.Type == corev1.PodReady {
			conditionv = condition.Status
		}
	}
	return conditionu != conditionv, fmt.Sprintf("%v", conditionu), fmt.Sprintf("%v", conditionv)
}
