// Copyright 2017 The Armada Authors.
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
	helmif "github.com/keleustes/armada-operator/pkg/services"
	corev1 "k8s.io/api/core/v1"

	"k8s.io/apimachinery/pkg/labels"
	"k8s.io/helm/pkg/manifest"
	cpb "k8s.io/helm/pkg/proto/hapi/chart"
	rpb "k8s.io/helm/pkg/proto/hapi/release"
	svc "k8s.io/helm/pkg/proto/hapi/services"
	"k8s.io/helm/pkg/releaseutil"
	"k8s.io/helm/pkg/tiller"
)

var (
	GRPC_EPSILON            int64 = 60
	LIST_RELEASES_PAGE_SIZE int64 = 32
	LIST_RELEASES_ATTEMPTS  int   = 3
)

// NOTE(seaneagan) { This has no effect on the message size limit that tiller
// sets for itself which can be seen here {
//   https://github.com/helm/helm/blob/2d77db11fa47005150e682fb13c3cf49eab98fbb/pkg/tiller/server.go#L34

// var MAX_MESSAGE_LENGTH = 429496729

// type CommonEqualityMixin struct {
// }

// func (self *CommonEqualityMixin) __eq__(other interface{}) {
// 	return (isinstance(other, self.__class__) &&
// 		self.__dict__ == other.__dict__)

// }
// func (self *CommonEqualityMixin) __ne__(other interface{}) {
// 	return !self.__eq__(other)
// }

type TillerResult struct {
	/// """Object to hold Tiller results for Armada."""
	// CommonEqualityMixin
	Release     string
	Namespace   string
	Status      string
	Description string
	Version     int32
}

type Tiller struct {
	// """
	// The Tiller class supports communication and requests to the Tiller Helm
	// service over gRPC
	// """
	tiller_host      string
	tiller_port      int    // JEB or CONF.tiller_port
	tiller_namespace string // JEB or CONF.tiller_namespace
	bearer_token     string
	dry_run          bool // JEB or false

	// init k8s connectivity
	k8s *K8s

	// init Tiller channel
	releaseServer *tiller.ReleaseServer

	// init timeout for all requests
	// and assume eventually this will
	// be fed at runtime as an override
	timeout int64
}

func (self *Tiller) __init__(tiller_host string, tiller_port int, tiller_namespace string, dry_run bool) {
	self.tiller_host = tiller_host
	self.tiller_port = tiller_port           // JEB or CONF.tiller_port
	self.tiller_namespace = tiller_namespace // JEB or CONF.tiller_namespace
	self.dry_run = dry_run                   // JEB or false

	// init k8s connectivity
	self.k8s = &K8s{}

	// init Tiller channel
	// self.channel = self.get_channel()

	// init timeout for all requests
	// and assume eventually this will
	// be fed at runtime as an override
	self.timeout = const_DEFAULT_TILLER_TIMEOUT

	LOG.Info("Armada is using Tiller at: %s:%s, namespace:=%s, timeout:=%s",
		self.tiller_host, self.tiller_port, self.tiller_namespace,
		self.timeout)
}

func (self *Tiller) _get_tiller_pod() (*corev1.Pod, error) {
	// """
	// Returns Tiller pod using the Tiller pod labels specified in the Armada
	// config
	// """
	namespace := self._get_tiller_namespace()
	pods, err := self.k8s.get_namespace_pod(
		namespace, CONF_tiller_pod_labels)
	// No Tiller pods found
	if pods == nil || err != nil {
		return nil, helmif.TillerPodNotFoundException
	}

	// Return first Tiller pod in running state
	for _, pod := range pods.Items {
		if pod.Status.Phase == "Running" {
			LOG.Info("Found at least one Running Tiller pod.")
			return &pod, nil
		}
	}

	// No Tiller pod found in running state
	return nil, helmif.TillerPodNotRunningException

}
func (self *Tiller) _get_tiller_ip() string {
	// """
	// Returns the Tiller pod"s IP address by searching all namespaces
	// """
	if self.tiller_host != "" {
		LOG.Info("Using Tiller host IP: %s", self.tiller_host)
		return self.tiller_host
	} else {
		pod, _ := self._get_tiller_pod()
		LOG.Info("Using Tiller pod IP: %s", pod.Status.PodIP)
		return pod.Status.PodIP
	}

}
func (self *Tiller) _get_tiller_port() int {
	// """Stub method to support arbitrary ports in the future"""
	LOG.Info("Using Tiller host port: %s", self.tiller_port)
	return self.tiller_port

}
func (self *Tiller) _get_tiller_namespace() string {
	LOG.Info("Using Tiller namespace: %s", self.tiller_namespace)
	return self.tiller_namespace

}
func (self *Tiller) tiller_status() bool {
	// """
	// return if Tiller exist or not
	// """
	if self._get_tiller_ip() != "" {
		LOG.Info("Getting Tiller Status: Tiller exists")
		return true
	}

	LOG.Info("Getting Tiller Status: Tiller does not exist")
	return false

}
func (self *Tiller) list_releases(ctx context.Context) ([]rpb.Release, error) {
	// """
	// List Helm Releases
	// """
	// TODO(MarshM possibly combine list_releases() with list_charts()
	// since they do the same thing, grouping output differently

	// NOTE(seaneagan) { Paging through releases to prevent hitting the
	// maximum message size limit that tiller sets for it"s reponses.

	// get_results inlined here

	latest_releases := make([]rpb.Release, 0)

	for index := 0; index < LIST_RELEASES_ATTEMPTS; index++ {
		attempt := index + 1
		releases, err := self.get_results(ctx)
		if err != nil {
			LOG.Info("List releases paging failed on attempt %s/%s",
				attempt, LIST_RELEASES_ATTEMPTS)
			if attempt == LIST_RELEASES_ATTEMPTS {
				return latest_releases, err
			}
		} else {
			// Filter out old releases, similar to helm cli {
			// https://github.com/helm/helm/blob/1e26b5300b5166fabb90002535aacd2f9cc7d787/cmd/helm/list.go#L196
			latest_versions := make(map[string]int32)

			for _, r := range releases {
				max := latest_versions[r.Name]
				if max != 0 {
					if max > r.Version {
						continue
					}
				}
				latest_versions[r.Name] = r.Version
			}

			for _, r := range releases {
				if latest_versions[r.Name] == r.Version {
					// LOG.Info("Found release %s, version %s, status: %s", r.Name, r.Version,
					//		self.get_release_status(ctx, r.Name, r.Version))
					latest_releases = append(latest_releases, r)
				}
			}

			return latest_releases, nil
		}
	}

	return latest_releases, nil
}

func (self *Tiller) get_results(ctx context.Context) ([]rpb.Release, error) {
	releases := make([]rpb.Release, 0)
	// done := false
	// next_release_expected := ""
	// initial_total := 0
	// for {
	// 	req := &svc.ListReleasesRequest{
	// 		Offset: next_release_expected,
	// 		Limit: LIST_RELEASES_PAGE_SIZE,
	// 		Filter: const_STATUS_ALL}

	// 	LOG.Info("Tiller ListReleases() with timeout:=%s, request:=%s",
	// 		self.timeout, req)
	// 	response := self.releaseServer.ListReleases(ctx, req)

	// 	found_message := false
	// 	for _, message := range response.Items {
	// 		found_message := true
	// 		page := message.releases

	// 		if initial_total {
	// 			if message.total != initial_total {
	// 				LOG.Info(
	// 					"Total releases changed between pages from (%s) to (%s)", initial_total,
	// 					message.count)
	// 				return releases, helmif.TillerListReleasesPagingException
	// 			}
	// 		} else {
	// 			initial_total := message.total
	// 		}

	// 		// Add page to results.
	// 		releases.extend(page)

	// 		if message.next {
	// 			next_release_expected := message.next
	// 		} else {
	// 			done := true
	// 		}
	// 	}

	// 	// Ensure we break out was no message found which
	// 	// is seen if there are no releases in tiller.
	// 	if !found_message {
	// 		done := true
	// 	}
	// }

	return releases, nil

}

func (self *Tiller) get_chart_templates(ctx context.Context, template_name string, name string, release_name string, namespace string, chart *cpb.Chart, disable_hooks bool, values *cpb.Config) (string, error) {
	// returns some info

	LOG.Info("Template( %s ) : %s ", template_name, name)

	release_request := &svc.InstallReleaseRequest{
		Chart:     chart,
		DryRun:    true,
		Values:    values,
		Name:      name,
		Namespace: namespace,
		Wait:      disable_hooks}

	// templates, err := self.releaseServer.InstallRelease(release_request, self.timeout, self.metadata)
	install_rsp, err := self.releaseServer.InstallRelease(ctx, release_request)
	if err != nil {
		LOG.Info("Error while fetching template release %s", name)
		return "", helmif.ReleaseException
	}

	listManifests := releaseutil.SplitManifests(install_rsp.Release.GetManifest())
	listTemplates := manifest.SplitManifests(listManifests)
	for _, template := range listTemplates {
		if template_name == template.Name {
			return template.Content, nil
		}
	}

	return "", nil

}
func (self *Tiller) _pre_update_actions(actions *av1.ArmadaUpgradePre, release_name string, namespace string, chart *cpb.Chart, disable_hooks bool, values *cpb.Config, timeout int64) {
	// """
	// :param actions: array of items actions
	// :param namespace: name of pod for actions
	// """

	// for action := range actions.get("update", make([]interface{}, 0)) {
	// 	name := action.get("name")
	// 	LOG.Info("Updating %s ", name)
	// 	action_type := action.get("type")
	// 	labels := action.get("labels")

	// 	err := self.rolling_upgrade_pod_deployment(
	// 		name, release_name, namespace, labels, action_type, chart,
	// 		disable_hooks, values, timeout)
	// 	if err != nil {
	// 		return nil, helmif.PreUpdateJobDeleteException(name, namespace)
	// 	}
	// }

	// for action := range actions.get("delete", make([]interface{}, 0)) {
	// 	name := action.get("name")
	// 	action_type := action.get("type")
	// 	labels := action.get("labels", None)

	// 	err := self.delete_resources(action_type, labels, namespace, timeout)
	// 	if err != nil {
	// 		return nil, helmif.PreUpdateJobDeleteException(name, namespace)
	// 	}
	// }

}
func (self *Tiller) list_charts(ctx context.Context) {
	// """
	// List Helm Charts from Latest Releases

	// Returns a list of tuples in the form {
	// (name, version, chart, values, status)
	// """
	// LOG.Info("Getting known releases from Tiller...")
	// charts := make([]interface{}, 0)
	// for latest_release := range self.list_releases(ctx) {
	// 	release := []string{latest_release.name, latest_release.version,
	// 			latest_release.chart, latest_release.config.raw,
	// 			latest_release.info.status.Code.Name(latest_release.info.status.code)}
	// 	charts.append(release)

	// 	if err != nil {
	// 		LOG.Info("%s while getting releases: %s, ex:=%s",
	// 			e.__class__.__name__, latest_release, e)
	// 		continue
	// 	}
	// }
	// return charts
}

func (self *Tiller) update_release(ctx context.Context, chart *cpb.Chart, release string, namespace string, pre_actions *av1.ArmadaUpgradePre, post_actions *av1.ArmadaUpgradePost, disable_hooks bool, values string, wait bool, timeout int64, force bool,
	recreate_pods bool) (*TillerResult, error) {
	// """
	// Update a Helm Release
	// """
	timeout = self._check_timeout(wait, timeout)

	LOG.Info(
		"Helm update release%s: wait:=%s, timeout:=%s, force:=%s, recreate_pods:=%s",
		// JEB (" (dry run)" if self.dry_run else ""), wait,
		timeout, force, recreate_pods)

	config := &cpb.Config{Raw: ""}
	if values != "" {
		config = &cpb.Config{Raw: values}
	}

	self._pre_update_actions(pre_actions, release, namespace, chart,
		disable_hooks, config, timeout)

	// build release install request
	release_request := &svc.UpdateReleaseRequest{
		Chart:        chart,
		DryRun:       self.dry_run,
		DisableHooks: disable_hooks,
		Values:       config,
		Name:         release,
		Wait:         wait,
		Timeout:      timeout,
		Force:        force,
		Recreate:     recreate_pods,
	}

	// update_msg, err := self.releaseServer.UpdateRelease( ctx, release_request, timeout+GRPC_EPSILON, self.metadata)
	update_msg, err := self.releaseServer.UpdateRelease(ctx, release_request)

	if err != nil {
		LOG.Info("Error while updating release %s", release)
		// status, _ := self.get_release_status(ctx, release, 0)
		return nil, helmif.ReleaseException
	}

	tiller_result := &TillerResult{
		Release:     update_msg.Release.Name,
		Namespace:   update_msg.Release.Namespace,
		Status:      rpb.Status_Code_name[int32(update_msg.Release.Info.Status.Code)],
		Description: update_msg.Release.Info.Description,
		Version:     update_msg.Release.Version,
	}

	return tiller_result, nil

}

func (self *Tiller) install_release(ctx context.Context, chart *cpb.Chart, release string,
	namespace string, values string,
	wait bool, timeout int64) (*TillerResult, error) {
	// """
	// Create a Helm Release
	// """
	timeout = self._check_timeout(wait, timeout)

	LOG.Info("Helm install release%s: wait:=%s, timeout:=%s",
		// JEB (" (dry run)" if self.dry_run else ""),
		wait, timeout)

	config := &cpb.Config{Raw: ""}
	if values != "" {
		config = &cpb.Config{Raw: values}
	}

	// build release install request
	release_request := &svc.InstallReleaseRequest{
		Chart:     chart,
		DryRun:    self.dry_run,
		Values:    config,
		Name:      release,
		Namespace: namespace,
		Wait:      wait,
		Timeout:   timeout,
	}

	// install_msg := self.releaseServer.InstallRelease(ctx, release_request, timeout+GRPC_EPSILON, self.metadata)
	install_msg, err := self.releaseServer.InstallRelease(ctx, release_request)

	if err != nil {
		LOG.Info("Error while installing release %s", release)
		// status, _ := self.get_release_status(ctx, release, 0)
		return nil, helmif.ReleaseException
	}

	tiller_result := &TillerResult{
		Release:     install_msg.Release.Name,
		Namespace:   install_msg.Release.Namespace,
		Status:      rpb.Status_Code_name[int32(install_msg.Release.Info.Status.Code)],
		Description: install_msg.Release.Info.Description,
		Version:     install_msg.Release.Version,
	}

	return tiller_result, nil
}

func (self *Tiller) test_release(ctx context.Context, release string, timeout int64, cleanup bool) *rpb.TestSuite {
	// """
	// :param release: name of release to test
	// :param timeout: runtime before exiting
	// :param cleanup: removes testing pod created

	// :returns: test suite run object
	// """

	LOG.Info("Running Helm test: release:=%s, timeout:=%s", release, timeout)

	// TODO: This timeout is redundant since we already have the grpc
	// timeout below, and it"s actually used by tiller for individual
	// k8s operations not the overall request, should we {
	//     1. Remove this timeout
	//     2. Add `k8s_timeout:=const_DEFAULT_K8S_TIMEOUT` arg and use
	release_request := &svc.TestReleaseRequest{Name: release, Timeout: timeout, Cleanup: cleanup}

	// test_message_stream := self.releaseServer.RunReleaseTest(ctx, release_request, timeout, self.metadata)
	var test_message_stream svc.ReleaseService_RunReleaseTestServer
	err := self.releaseServer.RunReleaseTest(release_request, test_message_stream)
	if err != nil {
		LOG.Info("Error while testing release %s", release)
		status, _ := self.get_release_status(ctx, release, 0)
		return status.LastTestSuiteRun
	}

	failed := 0
	// for test_message := range test_message_stream {
	// 	if test_message.status == helm.TESTRUN_STATUS_FAILURE {
	// 		failed += 1
	// 	}
	// 	LOG.Info(test_message.msg)
	// }

	if failed != 0 {
		LOG.Info("{} test(s) failed")
	}

	status, _ := self.get_release_status(ctx, release, 0)
	return status.LastTestSuiteRun
}

func (self *Tiller) get_release_status(ctx context.Context, release string, version int32) (*rpb.Status, error) {
	// ""
	// :param release: name of release to test
	// :param version: version of release status
	// """

	LOG.Info("Helm getting release status for release:=%s, version:=%s", release, version)
	status_request := &svc.GetReleaseStatusRequest{Name: release, Version: version}

	// release_status, err := self.releaseServer.GetReleaseStatus(ctx, status_request, self.timeout, self.metadata)
	release_status, err := self.releaseServer.GetReleaseStatus(ctx, status_request)

	if err != nil {
		LOG.Info("Cannot get tiller release status.")
		return nil, helmif.GetReleaseStatusException
	}
	LOG.Info("GetReleaseStatus:= %s", release_status)
	return release_status.Info.Status, nil

}
func (self *Tiller) get_release_content(ctx context.Context, release string, version int32) (*rpb.Release, error) {
	// """
	// :param release: name of release to test
	// :param version: version of release status
	// """

	LOG.Info("Helm getting release content for release:=%s, version:=%s", release, version)
	status_request := &svc.GetReleaseContentRequest{Name: release, Version: version}

	// release_content, err := self.releaseServer.GetReleaseContent(ctx, status_request, self.timeout, self.metadata)
	release_content, err := self.releaseServer.GetReleaseContent(ctx, status_request)

	if err != nil {
		LOG.Info("Cannot get tiller release content.")
		return nil, helmif.GetReleaseContentException
	}
	LOG.Info("GetReleaseContent:= %s", release_content)
	return release_content.Release, nil

}

func (self *Tiller) tiller_version(ctx context.Context) (string, error) {
	// """
	// :returns: Tiller version
	// """
	release_request := &svc.GetVersionRequest{}

	LOG.Info("Getting Tiller version, with timeout:=%s", self.timeout)

	// tiller_version := self.releaseServer.GetVersion(release_request, self.timeout, self.metadata)
	tiller_version, err := self.releaseServer.GetVersion(ctx, release_request)
	if err != nil {
		LOG.Info("Failed to get Tiller version.")
		return "", helmif.TillerVersionException
	}

	LOG.Info("Got Tiller version %s", tiller_version.Version.SemVer)
	return tiller_version.Version.SemVer, nil
}

func (self *Tiller) uninstall_release(ctx context.Context, release string, disable_hooks bool, purge bool, timeout int64) (*rpb.Release, error) {
	// """
	// :param: release - Helm chart release name
	// :param: purge - deep delete of chart
	// :param: timeout - timeout for the tiller call

	// Deletes a Helm chart from Tiller
	// """

	if timeout == 0 {
		timeout = const_DEFAULT_DELETE_TIMEOUT
	}

	// Helm client calls ReleaseContent in Delete dry-run scenario
	if self.dry_run {
		content, _ := self.get_release_content(ctx, release, 0)
		LOG.Info(
			"Skipping delete during `dry-run`, would have deleted release:=%s from namespace:=%s.", content.Name,
			content.Namespace)
		return nil, nil
	}

	// build release uninstall request

	LOG.Info("Delete %s release with disable_hooks:=%s, purge:=%s, timeout:=%s flags", release, disable_hooks, purge,
		timeout)
	release_request := &svc.UninstallReleaseRequest{Name: release, DisableHooks: disable_hooks, Purge: purge}
	// res, err := self.releaseServer.UninstallRelease(release_request, timeout, self.metadata)
	res, err := self.releaseServer.UninstallRelease(ctx, release_request)
	if err != nil {
		LOG.Info("Error while deleting release %s", release)
		// status, _ := self.get_release_status(ctx, release, 0)
		return nil, helmif.ReleaseException

	}

	return res.Release, nil
}

func (self *Tiller) delete_resources(resource_type string, label_selector *labels.Selector, namespace string, wait bool, timeout int64) {
	// """
	// Delete resources matching provided resource type, labels, and
	// namespace.

	// :param resource_type: type of resource e.g. job, pod, etc.
	// :param resource_labels: labels for selecting the resources
	// :param namespace: namespace of resources
	// """
	timeout = self._check_timeout(wait, timeout)

	LOG.Info(
		"Deleting resources in namespace %s matching selectors (%s).", namespace, label_selector)

	handled := false
	if resource_type == "job" {
		get_jobs, _ := self.k8s.get_namespace_job(namespace, label_selector)
		for _, jb := range get_jobs.Items {
			jb_name := jb.Name

			if self.dry_run {
				LOG.Info(
					"Skipping delete job during `dry-run`, would have deleted job %s in namespace:=%s.", jb_name,
					namespace)
				continue
			}

			LOG.Info("Deleting job %s in namespace: %s", jb_name,
				namespace)
			self.k8s.delete_job_action(jb_name, namespace, "", timeout)
		}
		handled = true
	}

	if resource_type == "cronjob" || resource_type == "job" {
		get_jobs, _ := self.k8s.get_namespace_cron_job(namespace, label_selector)
		for _, jb := range get_jobs.Items {
			jb_name := jb.Name

			if resource_type == "job" {
				// TODO: Eventually disallow this, allowing initially since
				//       some existing clients were expecting this behavior.
				LOG.Info("Deleting cronjobs via `type: job` is deprecated, use `type: cronjob` instead")
			}

			if self.dry_run {
				LOG.Info(
					"Skipping delete cronjob during `dry-run`, would have deleted cronjob %s in namespace:=%s.", jb_name,
					namespace)
				continue
			}

			LOG.Info("Deleting cronjob %s in namespace: %s", jb_name,
				namespace)
			self.k8s.delete_cron_job_action(jb_name, namespace, "", timeout)
		}
		handled = true
	}

	if resource_type == "pod" {
		release_pods, _ := self.k8s.get_namespace_pod(namespace, label_selector)
		for _, pod := range release_pods.Items {
			pod_name := pod.Name

			if self.dry_run {
				LOG.Info(
					"Skipping delete pod during `dry-run`, would have deleted pod %s in namespace:=%s.", pod_name,
					namespace)
				continue
			}

			LOG.Info("Deleting pod %s in namespace: %s", pod_name,
				namespace)
			self.k8s.delete_pod_action(pod_name, namespace, "", timeout)
			if wait {
				self.k8s.wait_for_pod_redeployment(pod_name, namespace)
			}
		}
		handled = true
	}

	if !handled {
		LOG.Info("No resources found with labels:=%s type:=%s namespace:=%s",
			"", resource_type, namespace)
	}

}
func (self *Tiller) rolling_upgrade_pod_deployment(ctx context.Context,
	name string, release_name string, namespace string, label_selector *labels.Selector, action_type interface{},
	chart *cpb.Chart, disable_hooks bool, values *cpb.Config, timeout int64) {
	// """
	// update statefullsets (daemon, stateful)
	// """

	if action_type == "daemonset" {

		LOG.Info("Updating: %s", action_type)

		get_daemonset, _ := self.k8s.get_namespace_daemon_set(namespace, label_selector)
		for _, ds := range get_daemonset.Items {
			ds_name := ds.Name
			//JEB ds_labels := ds.Labels
			if ds_name == name {
				LOG.Info("Deleting %s : %s in %s", action_type, ds_name,
					namespace)
				self.k8s.delete_daemon_action(ds_name, namespace, nil)

				// update the daemonset yaml
				template, _ := self.get_chart_templates(ctx,
					ds_name, name, release_name, namespace, chart,
					disable_hooks, values)
				//JEB template["metadata"]["labels"] = ds_labels
				//JEB template["spec"]["template"]["metadata"]["labels"] = ds_labels

				self.k8s.create_daemon_action(
					namespace, template)

				// delete pods
				self.delete_resources(
					"pod",
					label_selector,
					namespace,
					true,
					timeout)
			}
		}

	} else {
		LOG.Info("Unable to exectue name: % type: %s", name, action_type)
	}

}
func (self *Tiller) rollback_release(ctx context.Context, release_name string, version int32, wait bool, timeout int64, force bool, recreate_pods bool) (*rpb.Release, error) {
	// """
	// Rollback a helm release.
	// """

	timeout = self._check_timeout(wait, timeout)

	LOG.Info(
		"Helm rollback%s of release:=%s, version:=%s, wait:=%s, timeout:=%s",
		// JEB (" (dry run)" if self.dry_run else ""),
		release_name, version, wait, timeout)
	rollback_request := &svc.RollbackReleaseRequest{
		Name:     release_name,
		Version:  version,
		DryRun:   self.dry_run,
		Wait:     wait,
		Timeout:  timeout,
		Force:    force,
		Recreate: recreate_pods}

	// rollback_msg, err := self.releaseServer.RollbackRelease( rollback_request, timeout+GRPC_EPSILON, self.metadata)
	rollback_msg, err := self.releaseServer.RollbackRelease(ctx, rollback_request)
	if err != nil {
		LOG.Info("Error while rolling back tiller release.")
		return nil, helmif.RollbackReleaseException
	}

	LOG.Info("RollbackRelease:= %s", rollback_msg)
	return rollback_msg.Release, nil

}
func (self *Tiller) _check_timeout(wait bool, timeout int64) int64 {
	if timeout <= 0 {
		if wait {
			LOG.Info(
				"Tiller timeout is invalid or unspecified, using default %ss.", self.timeout)
		}
		timeout = self.timeout
	}
	return timeout
}
