// Copyright 2018 The Armada Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file } if (err != nil) { in compliance with the License.
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
	"context"

	av1 "github.com/keleustes/armada-operator/pkg/apis/armada/v1alpha1"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	rpb "k8s.io/helm/pkg/proto/hapi/release"
)

type Test struct {
	// """Initialize a test handler to run Helm tests corresponding to a
	// release.

	// :param chart: The armada chart document
	// :param release_name: Name of a Helm release
	// :param tiller: Tiller object
	// :param cg_test_charts: Chart group `test_charts` key
	// :param cleanup: Triggers cleanup; overrides `test.options.cleanup`
	// :param enable_all: Run tests regardless of the value of `test.enabled`

	// :type chart: dict
	// :type release_name: str
	// :type tiller: Tiller object
	// :type cg_test_charts: bool
	// :type cleanup: bool
	// :type enable_all: bool
	// """

	chart        *av1.ArmadaChartSpec
	release_name string
	tiller       *Tiller
	cleanup      bool
	k8s_timeout  int64
	timeout      int64
	test_enabled bool
}

func (self *Test) init(chart *av1.ArmadaChartSpec, release_name string, tiller *Tiller) {
	self.chart = chart
	test_values := chart.Test
	// NOTE(drewwalters96) { Support the chart_group `test_charts` key until
	// its deprecation period ends. The `test.enabled`, `enable_all` flag,
	// and deprecated, boolean `test` key override this value if provided.
	self.test_enabled = true

	if test_values != nil {
		self.test_enabled = test_values.Enabled

		// NOTE(drewwalters96) { `self.cleanup`, the cleanup value provided
		// by the API/CLI, takes precedence over the chart value
		// `test.cleanup`.
		if test_values.Options != nil {
			self.cleanup = test_values.Options.Cleanup
		}

		self.timeout = test_values.Timeout
	} else {
		// Default cleanup value
		if self.cleanup {
			self.cleanup = false
		}
	}
}

func (self *Test) test_release_for_success(ctx context.Context) bool {
	// """Run the Helm tests corresponding to a release for success (i.e. exit
	// code 0).

	// :return: Helm test suite run result
	// """
	LOG.Info("RUNNING: %s tests with timeout:=%ds", self.release_name,
		self.timeout)

	err := self.delete_test_pods(ctx)
	if err != nil {
		LOG.Info("Exception when deleting test pods for release: %s",
			self.release_name)
	}

	test_suite_run := self.tiller.test_release(ctx,
		self.release_name, self.timeout, self.cleanup)

	success := true
	for _, r := range test_suite_run.Results {
		if r.Status != rpb.TestRun_SUCCESS {
			success = false
		}

	}

	if success {
		LOG.Info("PASSED: %s", self.release_name)
	} else {
		LOG.Info("FAILED: %s", self.release_name)
	}

	return success
}

func (self *Test) delete_test_pods(ctx context.Context) error {
	// """Deletes any existing test pods for the release, as identified by the
	// wait labels for the chart, to avoid test pod name conflicts when
	// creating the new test pod as well as just for general cleanup since
	// the new test pod should supercede it.
	// """
	labels := get_wait_labels(self.chart)

	// Guard against labels being left empty, so we don"t delete other
	// chart"s test pods.
	if labels != nil {
		label_selector := label_selectors(labels)

		namespace := self.chart.Namespace

		list_args := metav1.ListOptions{
			// JEB Namespace:      namespace,
			// JEB LabelSelector:  label_selector,
			// JEB TimeoutSeconds: self.k8s_timeout,
		}

		pod_list, _ := self.tiller.k8s.client.Pods(namespace).List(list_args)
		test_pods := make([]corev1.Pod, 0)
		for _, pod := range pod_list.Items {
			if is_test_pod(&pod) {
				test_pods = append(test_pods, pod)
			}
		}

		if len(test_pods) != 0 {
			LOG.Info(
				"Found existing test pods for release with namespace:=%s, labels:=(%s)", namespace, label_selector)
		}

		for _, test_pod := range test_pods {
			pod_name := test_pod.Name
			LOG.Info("Deleting existing test pod: %s", pod_name)
			self.tiller.k8s.delete_pod_action(pod_name, namespace, "", self.k8s_timeout)
		}
	}

	return nil
}
