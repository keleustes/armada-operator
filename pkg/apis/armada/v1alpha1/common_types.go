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

package v1alpha1

import (
	// "encoding/json"
	yaml "gopkg.in/yaml.v2"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	runtime "k8s.io/apimachinery/pkg/runtime"
)

// HelmResourceState is the status of a release/chart/chartgroup/manifest
type HelmResourceState string

type HelmResourceConditionType string

// HelmResourceConditionStatus represents the current status of a Condition
type HelmResourceConditionStatus string

type HelmResourceConditionReason string

// String converts a HelmResourceState to a printable string
func (x HelmResourceState) String() string { return string(x) }

// String converts a HelmResourceConditionType to a printable string
func (x HelmResourceConditionType) String() string { return string(x) }

// String converts a HelmResourceConditionState to a printable string
func (x HelmResourceConditionStatus) String() string { return string(x) }

// String converts a HelmResourceConditionReason to a printable string
func (x HelmResourceConditionReason) String() string { return string(x) }

// Describe the status of a release
const (
	// StateUninitialied indicates that a release/chart/chartgroup/manifest exists, but has not been acted upon
	StateUninitialized HelmResourceState = "uninitialized"
	// StateUnknown indicates that a release/chart/chartgroup/manifest is in an uncertain state.
	StateUnknown HelmResourceState = "unknown"
	// StateInitialized indicates that a release/chart/chartgroup/manifest is in an Kubernetes
	StateInitialized HelmResourceState = "initialized"
	// StateDeployed indicates that the release/chart/chartgroup/manifest has been pushed to Kubernetes.
	StateDeployed HelmResourceState = "deployed"
	// StateUninstalled indicates that a release/chart/chartgroup/manifest has been uninstalled from Kubermetes.
	StateUninstalled HelmResourceState = "uninstalled"
	// StateFailed indicates that the release/chart/chartgroup/manifest was not successfully deployed.
	StateFailed HelmResourceState = "failed"
	// StatePending indicates that resource was xxx
	StatePending HelmResourceState = "pending"
	// StateRunning indicates that resource was xxx
	StateRunning HelmResourceState = "running"
	// StateError indicates that resource was xxx
	StateError HelmResourceState = "error"
)

// These represent acceptable values for a HelmResourceConditionStatus
const (
	ConditionStatusTrue    HelmResourceConditionStatus = "True"
	ConditionStatusFalse                               = "False"
	ConditionStatusUnknown                             = "Unknown"
)

// These represent acceptable values for a HelmResourceConditionType
const (
	ConditionIrreconcilable HelmResourceConditionType = "Irreconcilable"
	ConditionPending                                  = "Pending"
	ConditionInitialized                              = "Initializing"
	ConditionError                                    = "Error"
	ConditionRunning                                  = "Running"
	ConditionDeployed                                 = "Deployed"
	ConditionFailed                                   = "Failed"
)

// The following represent the more fine-grained reasons for a given condition
const (
	// Successful Conditions Reasons
	ReasonInstallSuccessful        HelmResourceConditionReason = "InstallSuccessful"
	ReasonReconcileSuccessful                                  = "ReconcileSuccessful"
	ReasonUninstallSuccessful                                  = "UninstallSuccessful"
	ReasonUpdateSuccessful                                     = "UpdateSuccessful"
	ReasonUnderlyingResourcesReady                             = "UnderlyingResourcesReady"

	// Error Condition Reasons
	ReasonInstallError   HelmResourceConditionReason = "InstallError"
	ReasonReconcileError                             = "ReconcileError"
	ReasonUninstallError                             = "UninstallError"
	ReasonUpdateError                                = "UpdateError"
)

// HelmResourceCondition represents one current condition of an Helm resource
// A condition might not show up if it is not happening.
// For example, if a chart is not deploying, the Deploying condition would not show up.
// If a chart is deploying and encountered a problem that prevents the deployment,
// the Deploying condition's status will would be False and communicate the problem back.
type HelmResourceCondition struct {
	Type               HelmResourceConditionType   `json:"type"`
	Status             HelmResourceConditionStatus `json:"status"`
	Reason             HelmResourceConditionReason `json:"reason,omitempty"`
	Message            string                      `json:"message,omitempty"`
	ResourceName       string                      `json:"resourceName,omitempty"`
	ResourceVersion    int32                       `json:"resourceVersion,omitempty"`
	LastTransitionTime metav1.Time                 `json:"lastTransitionTime,omitempty"`
}

type HelmResourceConditionListHelper struct {
	Items []HelmResourceCondition `json:"items"`
}

// ArmadaStatus represents the common attributes shared amongst armada resources
type ArmadaStatus struct {
	// Satisfied indicates if the release's ActualState satisfies its target state
	Satisfied bool `json:"satisfied"`
	// Reason indicates the reason for any related failures.
	Reason string `json:"reason,omitempty"`
	// Actual state of the Helm Custom Resources
	ActualState HelmResourceState `json:"actual_state"`
	// List of conditions and states related to the resource. JEB: Feature kind of overlap with event recorder
	Conditions []HelmResourceCondition `json:"conditions,omitempty"`
}

// SetCondition sets a condition on the status object. If the condition already
// exists, it will be replaced. SetCondition does not update the resource in
// the cluster.
func (s *ArmadaStatus) SetCondition(cond HelmResourceCondition, tgt HelmResourceState) {

	// Add the condition to the list
	chelper := HelmResourceConditionListHelper{Items: s.Conditions}
	s.Conditions = chelper.SetCondition(cond)

	// Recompute the state
	s.ComputeActualState(cond, tgt)
}

// RemoveCondition removes the condition with the passed condition type from
// the status object. If the condition is not already present, the returned
// status object is returned unchanged. RemoveCondition does not update the
// resource in the cluster.
func (s *ArmadaStatus) RemoveCondition(conditionType HelmResourceConditionType) {
	for i, cond := range s.Conditions {
		if cond.Type == conditionType {
			s.Conditions = append(s.Conditions[:i], s.Conditions[i+1:]...)
			return
		}
	}
}

// SetCondition sets a condition on the status object. If the condition already
// exists, it will be replaced. SetCondition does not update the resource in
// the cluster.
func (s *HelmResourceConditionListHelper) SetCondition(condition HelmResourceCondition) []HelmResourceCondition {

	// Initialize the Items array if needed
	if s.Items == nil {
		s.Items = make([]HelmResourceCondition, 0)
	}

	now := metav1.Now()
	for i := range s.Items {
		if s.Items[i].Type == condition.Type {
			if s.Items[i].Status != condition.Status {
				condition.LastTransitionTime = now
			} else {
				condition.LastTransitionTime = s.Items[i].LastTransitionTime
			}
			s.Items[i] = condition
			return s.Items
		}
	}

	// If the condition does not exist,
	// initialize the lastTransitionTime
	condition.LastTransitionTime = now
	s.Items = append(s.Items, condition)
	return s.Items
}

// RemoveCondition removes the condition with the passed condition type from
// the status object. If the condition is not already present, the returned
// status object is returned unchanged. RemoveCondition does not update the
// resource in the cluster.
func (s *HelmResourceConditionListHelper) RemoveCondition(conditionType HelmResourceConditionType) []HelmResourceCondition {

	// Initialize the Items array if needed
	if s.Items == nil {
		s.Items = make([]HelmResourceCondition, 0)
	}

	for i := range s.Items {
		if s.Items[i].Type == conditionType {
			s.Items = append(s.Items[:i], s.Items[i+1:]...)
			return s.Items
		}
	}
	return s.Items
}

// Initialize the HelmResourceCondition list
func (s *HelmResourceConditionListHelper) InitIfEmpty() []HelmResourceCondition {

	// Initialize the Items array if needed
	if s.Items == nil {
		s.Items = make([]HelmResourceCondition, 0)
	}

	return s.Items
}

// Utility function to print an HelmResourceCondition list
func (s *HelmResourceConditionListHelper) PrettyPrint() string {
	// res, _ := json.MarshalIndent(s.Items, "", "\t")
	res, _ := yaml.Marshal(s.Items)
	return string(res)
}

// Utility function to find an HelmResourceCondition within the List
func (s *HelmResourceConditionListHelper) FindCondition(conditionType HelmResourceConditionType, conditionStatus HelmResourceConditionStatus) *HelmResourceCondition {
	var found *HelmResourceCondition
	for _, condition := range s.Items {
		if condition.Type == conditionType && condition.Status == conditionStatus {
			found = &condition
			break
		}
	}
	return found
}

func (s *ArmadaStatus) ComputeActualState(cond HelmResourceCondition, target HelmResourceState) {
	// TODO(Ian): finish this
	if cond.Status == ConditionStatusTrue {
		if cond.Type == ConditionPending {
			s.ActualState = StatePending
			s.Satisfied = (s.ActualState == target)
			s.Reason = ""
		} else if cond.Type == ConditionInitialized {
			// Since that condition is set almost systematically
			// let's do not recompute the state.
			if (s.ActualState == "") || (s.ActualState == StateUnknown) {
				s.ActualState = StateInitialized
				s.Satisfied = (s.ActualState == target)
				s.Reason = ""
			}
		} else if cond.Type == ConditionRunning {
			// The deployment is still running
			s.ActualState = StateRunning
			s.Satisfied = false
			s.Reason = ""
		} else if cond.Type == ConditionDeployed {
			// No change is expected anymore. It is deployed
			s.ActualState = StateDeployed
			s.Satisfied = (s.ActualState == target)
			s.Reason = ""
		} else if cond.Type == ConditionFailed {
			// No change is expected anymore. It is failed
			s.ActualState = StateFailed
			s.Satisfied = false
			s.Reason = cond.Reason.String()
		} else if cond.Type == ConditionIrreconcilable {
			// We can't reconcile the subresources and the CRD
			s.ActualState = StateError
			s.Satisfied = false
			s.Reason = cond.Reason.String()
		} else if cond.Type == ConditionError {
			// We have a bug somewhere.
			s.ActualState = StateError
			s.Satisfied = false
			s.Reason = cond.Reason.String()
		} else {
			s.Satisfied = (s.ActualState == target)
			s.Reason = ""
		}
	} else {
		if cond.Type == ConditionDeployed {
			s.ActualState = StateUninstalled
			s.Satisfied = (s.ActualState == target)
			s.Reason = ""
		} else {
			s.Satisfied = (s.ActualState == target)
			s.Reason = ""
		}
	}
}

// +k8s:deepcopy-gen:interfaces=k8s.io/apimachinery/pkg/runtime.Object

// ControllerRevision implements an immutable snapshot of state data. Clients
// are responsible for serializing and deserializing the objects that contain
// their internal state.
// Once a ControllerRevision has been successfully created, it can not be updated.
// The API Server will fail validation of all requests that attempt to mutate
// the Data field. ControllerRevisions may, however, be deleted. Note that, due to its use by both
// the DaemonSet and StatefulSet controllers for update and rollback, this object is beta. However,
// it may be subject to name and representation changes in future releases, and clients should not
// depend on its stability. It is primarily for internal use by controllers.
type ControllerRevision struct {
	metav1.TypeMeta `json:",inline"`
	// Standard object's metadata.
	// More info: https://git.k8s.io/community/contributors/devel/api-conventions.md#metadata
	// +optional
	metav1.ObjectMeta `json:"metadata,omitempty" protobuf:"bytes,1,opt,name=metadata"`

	// Data is the serialized representation of the state.
	Data runtime.RawExtension `json:"data,omitempty" protobuf:"bytes,2,opt,name=data"`

	// Revision indicates the revision of the state represented by Data.
	Revision int64 `json:"revision" protobuf:"varint,3,opt,name=revision"`
}

// +k8s:deepcopy-gen:interfaces=k8s.io/apimachinery/pkg/runtime.Object

// ControllerRevisionList is a resource containing a list of ControllerRevision objects.
type ControllerRevisionList struct {
	metav1.TypeMeta `json:",inline"`

	// More info: https://git.k8s.io/community/contributors/devel/api-conventions.md#metadata
	// +optional
	metav1.ListMeta `json:"metadata,omitempty" protobuf:"bytes,1,opt,name=metadata"`

	// Items is the list of ControllerRevisions
	Items []ControllerRevision `json:"items" protobuf:"bytes,2,rep,name=items"`
}
