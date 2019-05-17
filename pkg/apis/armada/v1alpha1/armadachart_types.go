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
	"strings"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/runtime"
)

type ArmadaChartValues struct {
	// anchor contains tbd
	Anchor *AVAnchor `json:"anchor,omitempty"`
	// apiserver contains tbd
	Apiserver *AVApiserver `json:"apiserver,omitempty"`
	// bootstrap contains tbd
	Bootstrap *AVBootstrap `json:"bootstrap,omitempty"`
	// bootstrapping contains tbd
	Bootstrapping *AVBootstrapping `json:"bootstrapping,omitempty"`
	// ceph_client contains tbd
	CephClient *map[string]string `json:"ceph_client,omitempty"`
	// ceph_mgr_modules_config contains tbd
	CephMgrModulesConfig *AVCephMgrModulesConfig `json:"ceph_mgr_modules_config,omitempty"`
	// command_prefix contains tbd
	CommandPrefix []string `json:"command_prefix,omitempty"`
	// conf contains tbd
	Conf *AVConf `json:"conf,omitempty"`
	// data contains tbd
	Data *AVData `json:"data,omitempty"`
	// deployment contains tbd
	Deployment *map[string]bool `json:"deployment,omitempty"`
	// development contains tbd
	Development *AVDevelopment `json:"development,omitempty"`
	// endpoints contains tbd.
	// JEB: Would have been too consistent. Different structures are
	// used depending on the direction of the wind.
	// Endpoints *map[string]AVEndpoint `json:"endpoints,omitempty"`
	Endpoints *AVEndpoints `json:"endpoints,omitempty"`
	// etcd contains tbd
	Etcd *map[string]string `json:"etcd,omitempty"`
	// images contains tbd
	Images *AVImages `json:"images,omitempty"`
	// jobs contains tbd
	Jobs *AVJobs `json:"jobs,omitempty"`
	// kube_service contains tbd
	KubeService *AVKubeService `json:"kube_service,omitempty"`
	// labels contains tbd
	Labels *map[string]map[string]string `json:"labels,omitempty"`
	// livenessProbe contains tbd
	Livenessprobe *AVLivenessprobe `json:"livenessProbe,omitempty"`
	// manifests contains tbd
	Manifests *map[string]bool `json:"manifests,omitempty"`
	// monitoring contains tbd
	Monitoring *AVMonitoring `json:"monitoring,omitempty"`
	// network contains tbd
	Network *AVNetwork `json:"network,omitempty"`
	// networking contains tbd
	Networking *AVNetworking `json:"networking,omitempty"`
	// pod contains tbd
	Pod *AVPod `json:"pod,omitempty"`
	// prod_environment contains tbd
	ProdEnvironment *bool `json:"prod_environment,omitempty"`
	// secrets contains tbd
	Secrets *AVSecrets `json:"secrets,omitempty"`
	// service contains tbd
	Service *AVService `json:"service,omitempty"`
	// storage contains tbd
	Storage *AVStorage `json:"storage,omitempty"`
	// storageclass contains tbd
	Storageclass *AVStorageclass `json:"storageclass,omitempty"`
}

// ======= ArmadaChartSpec Definition =======
// ArmadaChartSpec defines the desired state of ArmadaChart
type ArmadaChartSpec struct {
	// name for the chart
	ChartName string `json:"chart_name"`
	// namespace of your chart
	Namespace string `json:"namespace,omitempty"`
	// name of the release (Armada will prepend with ``release-prefix`` during processing)
	Release string `json:"release"`
	// provide a path to a ``git repo``, ``local dir``, or ``tarball url`` chart
	Source *ArmadaChartSource `json:"source"`
	// reference any chart dependencies before install
	Dependencies []string `json:"dependencies"`

	// override any default values in the charts
	Values *ArmadaChartValues `json:"values,omitempty"`
	// See Delete_.
	Delete *ArmadaDelete `json:"delete,omitempty"`
	// upgrade the chart managed by the armada yaml
	Upgrade *ArmadaUpgrade `json:"upgrade,omitempty"`

	// do not delete FAILED releases when encountered from previous run (provide the
	// 'continue_processing' bool to continue or halt execution (default: halt))
	Protected *ArmadaProtectedRelease `json:"protected,omitempty"`
	// See Test_.
	Test *ArmadaTest `json:"test,omitempty"`
	// time (in seconds) allotted for chart to deploy when 'wait' flag is set (DEPRECATED)
	Timeout int `json:"timeout,omitempty"`
	// See `ArmwadaWait`.
	Wait *ArmadaWait `json:"wait,omitempty"`

	// Target state of the Helm Custom Resources
	TargetState HelmResourceState `json:"target_state"`

	// revisionHistoryLimit is the maximum number of revisions that will
	// be maintained in the ArmadaChart's revision history. The revision history
	// consists of all revisions not represented by a currently applied
	// ArmadaChartSpec version. The default value is 10.
	RevisionHistoryLimit *int32 `json:"revisionHistoryLimit,omitempty"`
}

// ======= ArmadaChartStatus Definition =======
// ArmadaChartStatus defines the observed state of ArmadaChart
type ArmadaChartStatus struct {
	ArmadaStatus `json:",inline"`
}

// ======= ArmadaChartList Definition =======
// +k8s:deepcopy-gen:interfaces=k8s.io/apimachinery/pkg/runtime.Object

// ArmadaChart is the Schema for the armadacharts API
// +k8s:openapi-gen=true
// +kubebuilder:subresource:status
// +kubebuilder:resource:path=armadacharts,shortName=act
// +kubebuilder:printcolumn:name="State",type="string",JSONPath=".status.actual_state",description="State"
// +kubebuilder:printcolumn:name="Target State",type="string",JSONPath=".spec.target_state",description="Target State"
// +kubebuilder:printcolumn:name="Satisfied",type="boolean",JSONPath=".status.satisfied",description="Satisfied"
type ArmadaChart struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   ArmadaChartSpec   `json:"spec,omitempty"`
	Status ArmadaChartStatus `json:"status,omitempty"`
}

// Init is used to initialize an ArmadaChart. Namely, if the state has not been
// specified, it will be set
func (obj *ArmadaChart) Init() {
	if obj.Status.ActualState == "" {
		obj.Status.ActualState = StateUninitialized
	}
	if obj.Spec.TargetState == "" {
		// TODO(JEB): Big temporary kludge to deal with helm-toolkit
		if strings.Contains(obj.ObjectMeta.Name, "-htk") {
			obj.Spec.TargetState = StateUninitialized
		} else {
			obj.Spec.TargetState = StateDeployed
		}
	}
	obj.Status.Satisfied = (obj.Spec.TargetState == obj.Status.ActualState)
}

// Return the list of dependent resources to watch
func (obj *ArmadaChart) GetDependentResources() []unstructured.Unstructured {
	var res = make([]unstructured.Unstructured, 0)
	return res
}

// Convert an unstructured.Unstructured into a typed ArmadaChart
func ToArmadaChart(u *unstructured.Unstructured) *ArmadaChart {
	var obj *ArmadaChart
	err := runtime.DefaultUnstructuredConverter.FromUnstructured(u.UnstructuredContent(), &obj)
	if err != nil {
		return &ArmadaChart{
			ObjectMeta: metav1.ObjectMeta{
				Name:      u.GetName(),
				Namespace: u.GetNamespace(),
			},
		}
	}
	return obj
}

// Convert a typed ArmadaChart into an unstructured.Unstructured
func (obj *ArmadaChart) FromArmadaChart() *unstructured.Unstructured {
	u := NewArmadaChartVersionKind(obj.ObjectMeta.Namespace, obj.ObjectMeta.Name)
	tmp, err := runtime.DefaultUnstructuredConverter.ToUnstructured(*obj)
	if err != nil {
		return u
	}
	u.SetUnstructuredContent(tmp)
	return u
}

// JEB: Not sure yet if we really will need it
func (obj *ArmadaChart) Equivalent(other *ArmadaChart) bool {
	if other == nil {
		return false
	}
	return reflect.DeepEqual(obj.Spec, other.Spec)
}

// IsDeleted returns true if the chart has been deleted
func (obj *ArmadaChart) IsDeleted() bool {
	return obj.GetDeletionTimestamp() != nil
}

// IsTargetStateUnitialized returns true if the chart is not managed by the reconcilier
func (obj *ArmadaChart) IsTargetStateUninitialized() bool {
	return obj.Spec.TargetState == StateUninitialized
}

// IsSatisfied returns true if the chart's actual state meets its target state
func (obj *ArmadaChart) IsSatisfied() bool {
	return obj.Spec.TargetState == obj.Status.ActualState
}

// Returns a GKV for ArmadaChart
func NewArmadaChartVersionKind(namespace string, name string) *unstructured.Unstructured {
	u := &unstructured.Unstructured{}
	u.SetAPIVersion("armada.airshipit.org/v1alpha1")
	u.SetKind("ArmadaChart")
	u.SetNamespace(namespace)
	u.SetName(name)
	return u
}

// ======= ArmadaChartList Definition =======
// +k8s:deepcopy-gen:interfaces=k8s.io/apimachinery/pkg/runtime.Object

// ArmadaChartList contains a list of ArmadaChart
type ArmadaChartList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []ArmadaChart `json:"items"`
}

// Convert an unstructured.Unstructured into a typed ArmadaChartList
func ToArmadaChartList(u *unstructured.Unstructured) *ArmadaChartList {
	var obj *ArmadaChartList
	err := runtime.DefaultUnstructuredConverter.FromUnstructured(u.UnstructuredContent(), &obj)
	if err != nil {
		return &ArmadaChartList{}
	}
	return obj
}

// Convert a typed ArmadaChartList into an unstructured.Unstructured
func (obj *ArmadaChartList) FromArmadaChartList() *unstructured.Unstructured {
	u := NewArmadaChartListVersionKind("", "")
	tmp, err := runtime.DefaultUnstructuredConverter.ToUnstructured(*obj)
	if err != nil {
		return u
	}
	u.SetUnstructuredContent(tmp)
	return u
}

// JEB: Not sure yet if we really will need it
func (obj *ArmadaChartList) Equivalent(other *ArmadaChartList) bool {
	if other == nil {
		return false
	}
	return reflect.DeepEqual(obj.Items, other.Items)
}

// Let's check the reference are setup properly.
func (obj *ArmadaChartList) CheckOwnerReference(refs []metav1.OwnerReference) bool {

	// Check that each sub resource is owned by the phase
	for _, item := range obj.Items {
		if !reflect.DeepEqual(item.GetOwnerReferences(), refs) {
			return false
		}
	}

	return true
}

// Returns a GKV for ArmadaChartList
func NewArmadaChartListVersionKind(namespace string, name string) *unstructured.Unstructured {
	u := &unstructured.Unstructured{}
	u.SetAPIVersion("armada.airshipit.org/v1alpha1")
	u.SetKind("ArmadaChartList")
	u.SetNamespace(namespace)
	u.SetName(name)
	return u
}

// ======= ArmadaCharts Definition =======
// ArmadaCharts is a wrapper around ArmadaChartList used for interface definitions
type ArmadaCharts struct {
	List *ArmadaChartList
	Name string
}

// Instantiate new ArmadaCharts
func NewArmadaCharts(name string) *ArmadaCharts {
	var emptyList = &ArmadaChartList{
		Items: make([]ArmadaChart, 0),
	}
	var res = ArmadaCharts{
		Name: name,
		List: emptyList,
	}

	return &res
}

// Convert the Name of an ArmadaCharts
func (obj *ArmadaCharts) GetName() string {
	return obj.Name
}

// Loop through the Chartand return the first disabled one
func (obj *ArmadaCharts) GetNextToEnable() *ArmadaChart {
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
	return nil
}

// Loop through the charts and return all the disabled ones
func (obj *ArmadaCharts) GetAllDisabledCharts() *ArmadaCharts {

	var res = NewArmadaCharts(obj.Name)

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
	SchemeBuilder.Register(&ArmadaChart{}, &ArmadaChartList{})
}
