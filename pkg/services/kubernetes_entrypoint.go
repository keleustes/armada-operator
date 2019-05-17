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
	case "Workflow":
		{
			return obj.IsWorkflowReady(u)
		}
	default:
		{
			return true
		}
	}
}

// Did the status changed
func (obj *KubernetesDependency) UnstructuredStatusChanged(u *unstructured.Unstructured, v *unstructured.Unstructured) bool {
	if u == nil || v == nil {
		return true
	}

	if u.GetKind() != v.GetKind() {
		return false
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
	case "Workflow":
		{
			return obj.WorkflowStatusChanged(u, v)
		}
	default:
		{
			return false
		}
	}
}

// Check the state of the Main workflow to figure out
// if the phase is still running
// This code is inspired from the kubernetes-entrypoint project
func (obj *KubernetesDependency) IsWorkflowReady(u *unstructured.Unstructured) bool {
	return obj.IsCustomResourceReady("status.phase", "Succeeded", u)
}

// Compare the phase between to Workflow
func (obj *KubernetesDependency) WorkflowStatusChanged(u *unstructured.Unstructured, v *unstructured.Unstructured) bool {
	return obj.CustomResourceStatusChanged("status.phase", u, v)
}

// Check the state of a custom resource
// This code is inspired from the kubernetes-entrypoint project
func (obj *KubernetesDependency) IsCustomResourceReady(key string, expectedValue string,
	u *unstructured.Unstructured) bool {
	return obj.extractField(key, u) == expectedValue
}

// Compare the status between two CustomResource
func (obj *KubernetesDependency) CustomResourceStatusChanged(key string,
	u *unstructured.Unstructured,
	v *unstructured.Unstructured) bool {
	return obj.extractField(key, u) != obj.extractField(key, v)
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

// Compare the status field between two Job
func (obj *KubernetesDependency) JobStatusChanged(u *unstructured.Unstructured, v *unstructured.Unstructured) bool {
	if u == nil || v == nil {
		return true
	}

	jobu := batchv1.Job{}
	err1u := runtime.DefaultUnstructuredConverter.FromUnstructured(u.UnstructuredContent(), &jobu)
	if err1u != nil {
		return true
	}

	jobv := batchv1.Job{}
	err1v := runtime.DefaultUnstructuredConverter.FromUnstructured(v.UnstructuredContent(), &jobv)
	if err1v != nil {
		return true
	}

	return jobu.Status.Succeeded != jobv.Status.Succeeded
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

// PodStatus changed
func (obj *KubernetesDependency) PodStatusChanged(u *unstructured.Unstructured, v *unstructured.Unstructured) bool {
	if u == nil || v == nil {
		return true
	}

	podu := corev1.Pod{}
	err1u := runtime.DefaultUnstructuredConverter.FromUnstructured(u.UnstructuredContent(), &podu)
	if err1u != nil {
		return false
	}

	podv := corev1.Pod{}
	err1v := runtime.DefaultUnstructuredConverter.FromUnstructured(v.UnstructuredContent(), &podv)
	if err1v != nil {
		return false
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
	return conditionu != conditionv
}
