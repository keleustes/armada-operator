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

// +build wip

package handlersv2

import (
	av1 "github.com/keleustes/armada-crd/pkg/apis/armada/v1alpha1"
	helmif "github.com/keleustes/armada-operator/pkg/services"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
)

// import time
// import yaml

// from armada.handlers.chartbuilder import ChartBuilder
// from armada.handlers.release_diff import ReleaseDiff
// from armada.handlers.chart_delete import ChartDelete
// from armada.handlers.test import Test
// from armada.handlers.wait import ChartWait
// import armada.utils.release as r

type ChartDeploy struct {
	disable_update_pre     bool
	disable_update_post    bool
	dry_run                bool
	k8s_wait_attempts      int
	k8s_wait_attempt_sleep int
	timeout                int
	tiller                 *Tiller
}

func (self *ChartDeploy) init(chart *av1.ArmadaChartSpec, cg_test_all_charts bool, prefix string, known_releases []string) {
	self.disable_update_pre = disable_update_pre
	self.disable_update_post = disable_update_post
	self.dry_run = dry_run
	self.k8s_wait_attempts = k8s_wait_attempts
	self.k8s_wait_attempt_sleep = k8s_wait_attempt_sleep
	self.timeout = timeout
	self.tiller = tiller
}

func (self *ChartDeploy) execute(chart *av1.ArmadaChartSpec, cg_test_all_charts bool, prefix string, known_releases []string) {
	namespace := chart.get("namespace")
	release := chart.get("release")
	release_name := r.release_prefixer(prefix, release)
	LOG.Info("Processing Chart, release:=%s", release_name)

	values := chart.get("values", &foo{})
	pre_actions := &foo{}
	post_actions := &foo{}

	result := &foo{}

	old_release := self.find_chart_release(known_releases, release_name)

	status := None
	if old_release {
		status := r.get_release_status(old_release)
	}

	chart_wait := ChartWait{
		self.tiller.k8s,
		release_name,
		chart,
		namespace,
		k8s_wait_attempts:      self.k8s_wait_attempts,
		k8s_wait_attempt_sleep: self.k8s_wait_attempt_sleep,
		timeout:                self.timeout,
	}

	native_wait_enabled := chart_wait.is_native_enabled()

	// Begin Chart timeout deadline
	deadline := time.time() + chart_wait.get_timeout()

	chartbuilder := ChartBuilder(chart)
	new_chart := chartbuilder.get_helm_chart()

	// TODO(mark-burnett) { It may be more robust to directly call
	// tiller status to decide whether to install/upgrade rather
	// than checking for list membership.
	if status == const_STATUS_DEPLOYED {

		// indicate to the end user what path we are taking
		LOG.Info("Existing release %s found in namespace %s", release_name,
			namespace)

		// extract the installed chart and installed values from the
		// latest release so we can compare to the intended state
		old_chart := old_release.chart
		old_values_string := old_release.config.raw

		upgrade := chart.Upgrade
		disable_hooks := upgrade.NoHooks
		options := upgrade.Options
		force := options.Force
		recreate_pods := options.RecreatePods

		if upgrade {
			upgrade_pre := upgrade.Pre
			upgrade_post := upgrade.Post

			if !self.disable_update_pre && upgrade_pre {
				pre_actions := upgrade_pre
			}
			if !self.disable_update_post && upgrade_post {
				LOG.warning("Post upgrade actions are ignored by Armada and will not affect deployment.")
				post_actions := upgrade_post
			}
		}

		old_values, err := yaml.safe_load(old_values_string)
		if err != nil {
			chart_desc := "{} (previously deployed)".format(old_chart.metadata.name)
			return armada_exceptions.InvalidOverrideValuesYamlException(chart_desc)
		}

		LOG.Info("Checking for updates to chart release inputs.")
		diff := self.get_diff(old_chart, old_values, new_chart, values)

		if !diff {
			LOG.Info("Found no updates to chart release inputs")
		} else {
			LOG.Info("Found updates to chart release inputs")
			LOG.debug("%s", diff)
			result["diff"] = &foo{chart["release"]: str(diff)}

			// TODO(MarshM) { Add tiller dry-run before upgrade and
			// consider deadline impacts

			// do actual update
			timer := int(round(deadline - time.time()))
			LOG.Info(
				"Upgrading release %s in namespace %s, wait:=%s, timeout:=%ss", release_name, namespace,
				native_wait_enabled, timer)
			tiller_result := self.tiller.update_release(
				new_chart,
				release_name,
				namespace,
				pre_actions,
				post_actions,
				disable_hooks,
				yaml.safe_dump(values),
				native_wait_enabled,
				timer,
				force,
				recreate_pods)

			LOG.Info("Upgrade completed with results from Tiller: %s",
				tiller_result.__dict__)
			result["upgrade"] = release_name
		}
	} else {
		// Check for release with status other than DEPLOYED
		if status {
			if status != const_STATUS_FAILED {
				LOG.warn(
					"Unexpected release status encountered release:=%s, status:=%s", release_name, status)

				// Make best effort to determine whether a deployment is
				// likely pending, by checking if the last deployment
				// was started within the timeout window of the chart.
				last_deployment_age := r.get_last_deployment_age(
					old_release)
				wait_timeout := chart_wait.get_timeout()
				likely_pending := last_deployment_age <= wait_timeout
				if likely_pending {
					// Give up if a deployment is likely pending, we do not
					// want to have multiple operations going on for the
					// same release at the same time.
					return armada_exceptions.DeploymentLikelyPendingException(
						release_name, status, last_deployment_age,
						wait_timeout)
				} else {
					// Release is likely stuck in an unintended (by tiller)
					// state. Log and continue on with remediation steps
					// below.
					LOG.Info(
						"Old release %s likely stuck in status %s, (last deployment age:=%ss) >:= (chart wait timeout:=%ss)", release, status,
						last_deployment_age, wait_timeout)
				}
			}

			protected := chart.get("protected", &foo{})
			if protected {
				p_continue := protected.get("continue_processing", false)
				if p_continue {
					LOG.warn(
						"Release %s is `protected`, continue_processing:=true. Operator must handle %s release manually.", release_name,
						status)
					result["protected"] = release_name
					return result
				} else {
					LOG.Error(
						"Release %s is `protected`, continue_processing:=false.", release_name)
					return armada_exceptions.ProtectedReleaseException(
						release_name, status)
				}
			} else {
				// Purge the release
				LOG.Info("Purging release %s with status %s", release_name,
					status)
				chart_delete := ChartDelete(chart, release_name,
					self.tiller)
				chart_delete.delete()
				result["purge"] = release_name
			}
		}

		timer := int(round(deadline - time.time()))
		LOG.Info(
			"Installing release %s in namespace %s, wait:=%s, timeout:=%ss", release_name, namespace, native_wait_enabled,
			timer)
		tiller_result := self.tiller.install_release(
			new_chart,
			release_name,
			namespace,
			yaml.safe_dump(values),
			native_wait_enabled,
			timer)

		LOG.Info("Install completed with results from Tiller: %s",
			tiller_result.__dict__)
		result["install"] = release_name
	}

	// Wait
	timer := int(round(deadline - time.time()))
	chart_wait.wait(timer)

	// Test
	// JEB just_deployed := ("install" in result) || ("upgrade" in result)
	just_deployed := false
	last_test_passed := old_release && r.get_last_test_result(old_release)

	test_handler := Test(
		chart,
		release_name,
		self.tiller,
		cg_test_all_charts)

	run_test := test_handler.test_enabled && (just_deployed || !last_test_passed)
	if run_test {
		self._test_chart(release_name, test_handler)
	}

	return result

}
func (self *ChartDeploy) _test_chart(release_name string, test_handler interface{}) {
	if self.dry_run {
		LOG.Info(
			"Skipping test during `dry-run`, would have tested release:=%s", release_name)
		return true
	}

	success := test_handler.test_release_for_success()
	if !success {
		return tiller_exceptions.TestFailedException(release_name)
	}
}

func (self *ChartDeploy) get_diff(old_chart interface{}, old_values interface{}, new_chart interface{}, values interface{}) {
	return ReleaseDiff(old_chart, old_values, new_chart, values).get_diff()
}

func (self *ChartDeploy) find_chart_release(known_releases []string, release_name string) {
	// """
	// Find a release given a list of known_releases and a release name
	// """
	for release := range known_releases {
		if release.name == release_name {
			return release
		}
	}
	// JEB LOG.Info("known: %s, release_name: %s", list(map(lambda r: r.name, known_releases)), release_name)
	return None
}
