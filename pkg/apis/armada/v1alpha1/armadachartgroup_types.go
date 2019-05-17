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
	"reflect"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/runtime"
)

// ======= ArmadaChartGroupSpec Definition =======
// ArmadaChartGroupSpec defines the desired state of ArmadaChartGroup
type ArmadaChartGroupSpec struct {
	// reference to chart document
	Charts []string `json:"chart_group"`
	// description of chart set
	Description string `json:"description,omitempty"`
	// Name of the chartgroup
	Name string `json:"name,omitempty"`
	// enables sequenced chart deployment in a group
	Sequenced bool `json:"sequenced,omitempty"`
	// run pre-defined helm tests in a ChartGroup (DEPRECATED)
	TestCharts bool `json:"test_charts,omitempty"`

	// Target state of the Helm Custom Resources
	TargetState HelmResourceState `json:"target_state"`
	// revisionHistoryLimit is the maximum number of revisions that will
	// be maintained in the ArmadaChartGroup's revision history. The revision history
	// consists of all revisions not represented by a currently applied
	// ArmadaChartGroupSpec version. The default value is 10.
	RevisionHistoryLimit *int32 `json:"revisionHistoryLimit,omitempty"`
}

// ======= ArmadaChartGroupStatus Definition =======
// ArmadaChartGroupStatus defines the observed state of ArmadaChartGroup
type ArmadaChartGroupStatus struct {
	ArmadaStatus `json:",inline"`
}

// ======= ArmadaChartGroup Definition =======
// +k8s:deepcopy-gen:interfaces=k8s.io/apimachinery/pkg/runtime.Object

// ArmadaChartGroup is the Schema for the armadachartgroups API
// +k8s:openapi-gen=true
// +kubebuilder:subresource:status
// +kubebuilder:resource:path=armadachartgroups,shortName=acg
// +kubebuilder:printcolumn:name="State",type="string",JSONPath=".status.actual_state",description="State"
// +kubebuilder:printcolumn:name="Target State",type="string",JSONPath=".spec.target_state",description="Target State"
// +kubebuilder:printcolumn:name="Satisfied",type="boolean",JSONPath=".status.satisfied",description="Satisfied"
type ArmadaChartGroup struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   ArmadaChartGroupSpec   `json:"spec,omitempty"`
	Status ArmadaChartGroupStatus `json:"status,omitempty"`
}

// Init is used to initialize an ArmadaChart. Namely, if the state has not been
// specified, it will be set
func (obj *ArmadaChartGroup) Init() {
	if obj.Status.ActualState == "" {
		obj.Status.ActualState = StateUninitialized
	}
	if obj.Spec.TargetState == "" {
		obj.Spec.TargetState = StateDeployed
	}
	if obj.Spec.Charts == nil {
		obj.Spec.Charts = make([]string, 0)
	}
	obj.Status.Satisfied = (obj.Spec.TargetState == obj.Status.ActualState)
}

// Return the list of dependent resources to watch
func (obj *ArmadaChartGroup) GetDependentResources() []unstructured.Unstructured {
	var res = make([]unstructured.Unstructured, 0)
	for _, chartname := range obj.Spec.Charts {
		u := NewArmadaChartVersionKind(obj.GetNamespace(), chartname)
		res = append(res, *u)
	}
	return res
}

// Convert an unstructured.Unstructured into a typed ArmadaChartGroup
func ToArmadaChartGroup(u *unstructured.Unstructured) *ArmadaChartGroup {
	var obj *ArmadaChartGroup
	err := runtime.DefaultUnstructuredConverter.FromUnstructured(u.UnstructuredContent(), &obj)
	if err != nil {
		return &ArmadaChartGroup{
			ObjectMeta: metav1.ObjectMeta{
				Name:      u.GetName(),
				Namespace: u.GetNamespace(),
			},
		}
	}
	return obj
}

// Convert a typed ArmadaChartGroup into an unstructured.Unstructured
func (obj *ArmadaChartGroup) FromArmadaChartGroup() *unstructured.Unstructured {
	u := NewArmadaChartGroupVersionKind(obj.ObjectMeta.Namespace, obj.ObjectMeta.Name)
	tmp, err := runtime.DefaultUnstructuredConverter.ToUnstructured(*obj)
	if err != nil {
		return u
	}
	u.SetUnstructuredContent(tmp)
	return u
}

// JEB: Not sure yet if we really will need it
func (obj *ArmadaChartGroup) Equivalent(other *ArmadaChartGroup) bool {
	if other == nil {
		return false
	}
	return reflect.DeepEqual(obj.Spec.Charts, other.Spec.Charts)
}

// IsDeleted returns true if the chart group has been deleted
func (obj *ArmadaChartGroup) IsDeleted() bool {
	return obj.GetDeletionTimestamp() != nil
}

// IsTargetStateUnitialized returns true if the chart is not managed by the reconcilier
func (obj *ArmadaChartGroup) IsTargetStateUninitialized() bool {
	return obj.Spec.TargetState == StateUninitialized
}

// Returns a GKV for ArmadaChartGroup
func NewArmadaChartGroupVersionKind(namespace string, name string) *unstructured.Unstructured {
	u := &unstructured.Unstructured{}
	u.SetAPIVersion("armada.airshipit.org/v1alpha1")
	u.SetKind("ArmadaChartGroup")
	u.SetNamespace(namespace)
	u.SetName(name)
	return u
}

// GetMockCharts returns a mock list of ArmadaChart the same name/namespace as the cr
func (obj *ArmadaChartGroup) GetMockCharts() *ArmadaCharts {
	labels := map[string]string{
		"app": obj.ObjectMeta.Name,
	}

	var res = NewArmadaCharts(obj.ObjectMeta.Name)

	for _, chartname := range obj.Spec.Charts {
		res.List.Items = append(res.List.Items, ArmadaChart{
			ObjectMeta: metav1.ObjectMeta{
				Name:      chartname,
				Namespace: obj.ObjectMeta.Namespace,
				Labels:    labels,
			},
			Spec: ArmadaChartSpec{
				ChartName: chartname,
				Release:   chartname + "-release",
				Namespace: obj.ObjectMeta.Namespace,
				Upgrade: &ArmadaUpgrade{
					NoHooks: false,
				},
				Source: &ArmadaChartSource{
					Type:      "local",
					Location:  "/opt/armada/helm-charts/testchart",
					Subpath:   ".",
					Reference: "master",
				},
				Dependencies: make([]string, 0),
				TargetState:  StateUninitialized,
			},
		})
	}

	return res
}

// ======= ArmadaChartGroupList Definition =======
// +k8s:deepcopy-gen:interfaces=k8s.io/apimachinery/pkg/runtime.Object

// ArmadaChartGroupList contains a list of ArmadaChartGroup
type ArmadaChartGroupList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []ArmadaChartGroup `json:"items"`
}

// Convert an unstructured.Unstructured into a typed ArmadaChartGroupList
func ToArmadaChartGroupList(u *unstructured.Unstructured) *ArmadaChartGroupList {
	var obj *ArmadaChartGroupList
	err := runtime.DefaultUnstructuredConverter.FromUnstructured(u.UnstructuredContent(), &obj)
	if err != nil {
		return &ArmadaChartGroupList{}
	}
	return obj
}

// Convert a typed ArmadaChartGroupList into an unstructured.Unstructured
func (obj *ArmadaChartGroupList) FromArmadaChartGroupList() *unstructured.Unstructured {
	u := NewArmadaChartGroupListVersionKind("", "")
	tmp, err := runtime.DefaultUnstructuredConverter.ToUnstructured(*obj)
	if err != nil {
		return u
	}
	u.SetUnstructuredContent(tmp)
	return u
}

// JEB: Not sure yet if we really will need it
func (obj *ArmadaChartGroupList) Equivalent(other *ArmadaChartGroupList) bool {
	if other == nil {
		return false
	}
	return reflect.DeepEqual(obj.Items, other.Items)
}

// Let's check the reference are setup properly.
func (obj *ArmadaChartGroupList) CheckOwnerReference(refs []metav1.OwnerReference) bool {

	// Check that each sub resource is owned by the phase
	for _, item := range obj.Items {
		if !reflect.DeepEqual(item.GetOwnerReferences(), refs) {
			return false
		}
	}

	return true
}

// Returns a GKV for ArmadaChartGroupList
func NewArmadaChartGroupListVersionKind(namespace string, name string) *unstructured.Unstructured {
	u := &unstructured.Unstructured{}
	u.SetAPIVersion("armada.airshipit.org/v1alpha1")
	u.SetKind("ArmadaChartGroupList")
	u.SetNamespace(namespace)
	u.SetName(name)
	return u
}

// ======= ArmadaChartGroups Definition =======
// ArmadaChartGroups is a wrapper around ArmadaChartGroupList used for interface definitions
type ArmadaChartGroups struct {
	Name string
	List *ArmadaChartGroupList
}

// Instantiate new ArmadaChartGroups
func NewArmadaChartGroups(name string) *ArmadaChartGroups {
	var emptyList = &ArmadaChartGroupList{
		Items: make([]ArmadaChartGroup, 0),
	}
	var res = ArmadaChartGroups{
		Name: name,
		List: emptyList,
	}

	return &res
}

// Convert the Name of an ArmadaChartGroupList
func (obj *ArmadaChartGroups) GetName() string {
	return obj.Name
}

// Loop through the ChartGroup and return the first disabled one
func (obj *ArmadaChartGroups) GetNextToEnable() *ArmadaChartGroup {
	for _, act := range obj.List.Items {
		if !act.IsTargetStateUninitialized() && !act.Status.Satisfied {
			// The ChartGroup has been enabled but is still deploying
			return nil
		}
		if act.IsTargetStateUninitialized() {
			// The ChartGroup has not been enabled yet
			return &act
		}
	}

	// Everything was done
	return nil
}

// Loop through the chartgroups and return all the disabled ones
func (obj *ArmadaChartGroups) GetAllDisabledChartGroups() *ArmadaChartGroups {

	var res = NewArmadaChartGroups(obj.Name)

	for _, act := range obj.List.Items {
		if act.IsTargetStateUninitialized() {
			// The Chart has not been enabled yet
			res.List.Items = append(res.List.Items, act)
		}
	}

	return res
}

// ======= Schema Registration =======
func init() {
	SchemeBuilder.Register(&ArmadaChartGroup{}, &ArmadaChartGroupList{})
}
