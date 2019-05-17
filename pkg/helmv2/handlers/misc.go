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

// +build v2

package handlersv2

import (
	av1 "github.com/keleustes/armada-operator/pkg/apis/armada/v1alpha1"
	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/labels"
)

const (
	const_KEYWORD_ARMADA         string = "ArmadaManifest"
	const_KEYWORD_GROUPS         string = "ArmadaChartGroup"
	const_KEYWORD_CHARTS         string = "ArmadaChart"
	const_DEFAULT_K8S_TIMEOUT    int    = 30
	const_DEFAULT_TILLER_TIMEOUT int64  = 30
	const_STATUS_ALL             string = "all"
	const_DEFAULT_DELETE_TIMEOUT int64  = 30

	CONF_tiller_pod_labels string = "xxx"
)

type foo struct{}

func get_wait_labels(chart *av1.ArmadaChartSpec) *av1.ArmadaLabels {
	wait_config := chart.Wait
	return wait_config.Labels
}

func label_selectors(alabels *av1.ArmadaLabels) *labels.Selector {
	var res *labels.Selector
	return res
}

func is_test_pod(pod *corev1.Pod) bool {
	// annotations := pod.Annotations

	// Retrieve pod's Helm test hooks
	// if annotations != nil {
	//     hook_string = annotations.get(HELM_HOOK_ANNOTATION)
	//     if hook_string != "" {
	//         hooks = hook_string.split(',')
	// 		test_hooks = [h for h in hooks if h in HELM_TEST_HOOKS]
	// 	}
	// }

	// return bool(test_hooks)
	return false
}
