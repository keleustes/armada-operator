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
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"

	appsv1 "k8s.io/api/apps/v1"
	batchv1 "k8s.io/api/batch/v1"
	batchv1beta1 "k8s.io/api/batch/v1beta1"
	corev1 "k8s.io/api/core/v1"

	"k8s.io/client-go/kubernetes"
	cltappsv1 "k8s.io/client-go/kubernetes/typed/apps/v1"
	cltbatchv1 "k8s.io/client-go/kubernetes/typed/batch/v1"
	cltbatchv1beta1 "k8s.io/client-go/kubernetes/typed/batch/v1beta1"
	cltcorev1 "k8s.io/client-go/kubernetes/typed/core/v1"
	cltextensionsv1beta1 "k8s.io/client-go/kubernetes/typed/extensions/v1beta1"

	"sigs.k8s.io/controller-runtime/pkg/client"
)

// import re

// from kubernetes import client
// from kubernetes import config
// from kubernetes import watch
// from kubernetes.client import api_client
// from kubernetes.client.rest import ApiException
// from unittest.mock import Mock

// TODO: Remove after this bug is fixed and we have uplifted to a fixed version {
//       https://github.com/kubernetes-client/python/issues/411
// Avoid creating thread pools in kubernetes api_client.

// var _dummy_pool = Mock()
// var ThreadPool = nil // JEB lambda *args, **kwargs: _dummy_pool

type K8s struct {
	// """
	// Object to obtain the local kube config file
	// """
	kubeClient client.Client

	client            cltcorev1.CoreV1Interface
	batch_api         cltbatchv1.BatchV1Interface
	batch_v1beta1_api cltbatchv1beta1.BatchV1beta1Interface
	extension_api     cltextensionsv1beta1.ExtensionsV1beta1Interface
	apps_v1_api       cltappsv1.AppsV1Interface
}

func (self *K8s) init() {
	// """
	// Initialize connection to Kubernetes
	// """
	clientset := kubernetes.NewForConfigOrDie(nil) // c *rest.Config)
	self.client = clientset.CoreV1()
	self.batch_api = clientset.BatchV1()
	self.batch_v1beta1_api = clientset.BatchV1beta1()
	self.extension_api = clientset.ExtensionsV1beta1()
	self.apps_v1_api = clientset.AppsV1()

}

func (self *K8s) delete_job_action(name string, namespace string, propagation_policy string, timeout int64) {
	// 	// """
	// 	// Delete a job from a namespace (see _delete_item_action).

	// 	// :param name: name of job
	// 	// :param namespace: namespace
	// 	// :param propagation_policy: The Kubernetes propagation_policy to apply
	// 	//     to the delete.
	// 	// :param timeout: The timeout to wait for the delete to complete
	// 	// """
	// 	self._delete_item_action(
	// 		self.batch_api.Jobs(namespace).List(metav1.ListOptions{}),
	// 		self.batch_api.delete_namespaced_job, "job",
	// 		name, namespace, propagation_policy, timeout)

}
func (self *K8s) delete_cron_job_action(name string, namespace string, propagation_policy string, timeout int64) {
	// 	// """
	// 	// Delete a cron job from a namespace (see _delete_item_action).

	// 	// :param name: name of cron job
	// 	// :param namespace: namespace
	// 	// :param propagation_policy: The Kubernetes propagation_policy to apply
	// 	//     to the delete.
	// 	// :param timeout: The timeout to wait for the delete to complete
	// 	// """
	// 	self._delete_item_action(
	// 		self.batch_v1beta1_api.Jobs(namespace).List(metav1.ListOptions{}),
	// 		self.batch_v1beta1_api.delete_namespaced_cron_job, "cron job",
	// 		name, namespace, propagation_policy, timeout)

}
func (self *K8s) delete_pod_action(name string, namespace string, propagation_policy string, timeout int64) {
	// 	// """
	// 	// Delete a pod from a namespace (see _delete_item_action).

	// 	// :param name: name of pod
	// 	// :param namespace: namespace
	// 	// :param propagation_policy: The Kubernetes propagation_policy to apply
	// 	//     to the delete.
	// 	// :param timeout: The timeout to wait for the delete to complete
	// 	// """
	// 	self._delete_item_action(
	// 		self.client.Pods(namespace).List(metav1.ListOptions{}),
	// 		self.client.delete_namespaced_pod, "pod",
	// 		name, namespace, propagation_policy, timeout)

}
func (self *K8s) _delete_item_action(list_func interface{}, delete_func interface{}, object_type_description string,
	name string, namespace string, propagation_policy interface{}, timeout int64) {
	// 	// """
	// 	// This function takes the action to delete an object (job, cronjob, pod)
	// 	// from kubernetes. It will wait for the object to be fully deleted before
	// 	// returning to processing or timing out.

	// 	// :param list_func: The callback function to list the specified object
	// 	//     type
	// 	// :param delete_func: The callback function to delete the specified
	// 	//     object type
	// 	// :param object_type_description: The types of objects to delete,
	// 	//     in `job`, `cronjob`, or `pod`
	// 	// :param name: The name of the object to delete
	// 	// :param namespace: The namespace of the object
	// 	// :param propagation_policy: The Kubernetes propagation_policy to apply
	// 	//     to the delete. Default "Foreground" means that child objects
	// 	//     will be deleted before the given object is marked as deleted.
	// 	//     See: https://kubernetes.io/docs/concepts/workloads/controllers/garbage-collection/#controlling-how-the-garbage-collector-deletes-dependents  // noqa
	// 	// :param timeout: The timeout to wait for the delete to complete
	// 	// """
	// 	{
	// 		timeout := self._check_timeout(timeout)

	// 		LOG.debug("Watching to delete %s %s, Wait timeout:=%s",
	// 			object_type_description, name, timeout)
	// 		body := client.V1DeleteOptions()
	// 		w := watch.Watch()
	// 		issue_delete := true
	// 		found_events := false
	// 		for event := range w.stream(list_func, namespace, timeout) {
	// 			if issue_delete {
	// 				delete_func(
	// 					name,
	// 					namespace,
	// 					body,
	// 					propagation_policy)
	// 				issue_delete := false
	// 			}

	// 			event_type := event["type"].upper()
	// 			item_name := event["object"].metadata.name
	// 			LOG.debug("Watch event %s on %s", event_type, item_name)

	// 			if item_name == name {
	// 				found_events := true
	// 				if event_type == "DELETED" {
	// 					LOG.Info("Successfully deleted %s %s",
	// 						object_type_description, item_name)
	// 					return
	// 				}
	// 			}
	// 		}

	// 		if !found_events {
	// 			LOG.warn("Saw no delete events for %s %s in namespace:=%s",
	// 				object_type_description, name, namespace)
	// 		}

	// 		err_msg := "Reached timeout while waiting to delete %s: name:=%s, namespace:=%s % (object_type_description, name, namespace)"
	// 		LOG.Error(err_msg)
	// 		return helmif.KubernetesWatchTimeoutException(err_msg)
	// 	}

	// 	if err != nil {
	// 		LOG.exception("Exception when deleting %s: name:=%s, namespace:=%s", object_type_description, name, namespace)
	// 		return e
	// 	}
}
func (self *K8s) get_namespace_job(namespace string, kwargs interface{}) (*batchv1.JobList, error) {
	// """
	// :param label_selector: labels of the jobs
	// :param namespace: namespace of the jobs
	// """

	return self.batch_api.Jobs(namespace).List(metav1.ListOptions{})

}
func (self *K8s) get_namespace_cron_job(namespace string, kwargs interface{}) (*batchv1beta1.CronJobList, error) {
	// """
	// :param label_selector: labels of the cron jobs
	// :param namespace: namespace of the cron jobs
	// """

	return self.batch_v1beta1_api.CronJobs(namespace).List(metav1.ListOptions{})

}
func (self *K8s) get_namespace_pod(namespace string, kwargs interface{}) (*corev1.PodList, error) {
	// """
	// :param namespace: namespace of the Pod
	// :param label_selector: filters Pods by label

	// This will return a list of objects req namespace
	// """

	return self.client.Pods(namespace).List(metav1.ListOptions{})

}
func (self *K8s) get_namespace_deployment(namespace string, kwargs interface{}) (*appsv1.DeploymentList, error) {
	// """
	// :param namespace: namespace of target deamonset
	// :param labels: specify targeted deployment
	// """
	return self.apps_v1_api.Deployments(namespace).List(metav1.ListOptions{})

}
func (self *K8s) get_namespace_stateful_set(namespace string, kwargs interface{}) (*appsv1.StatefulSetList, error) {
	// """
	// :param namespace: namespace of target stateful set
	// :param labels: specify targeted stateful set
	// """
	return self.apps_v1_api.StatefulSets(namespace).List(metav1.ListOptions{})

}
func (self *K8s) get_namespace_daemon_set(namespace string, kwargs interface{}) (*appsv1.DaemonSetList, error) {
	// """
	// :param namespace: namespace of target deamonset
	// :param labels: specify targeted daemonset
	// """
	return self.apps_v1_api.DaemonSets(namespace).List(metav1.ListOptions{})

}
func (self *K8s) create_daemon_action(namespace string, template interface{}) (*appsv1.DaemonSet, error) {
	// """
	// :param: namespace - pod namespace
	// :param: template - deploy daemonset via yaml
	// """
	// we might need to load something here

	return self.apps_v1_api.DaemonSets(namespace).Create(nil)

}
func (self *K8s) delete_daemon_action(name string, namespace string, body interface{}) error {
	// """
	// :param: namespace - pod namespace

	// This will delete daemonset
	// """
	return self.apps_v1_api.DaemonSets(namespace).Delete(name, &metav1.DeleteOptions{})

}
func (self *K8s) wait_for_pod_redeployment(old_pod_name string, namespace string) {
	// """
	// :param old_pod_name: name of pods
	// :param namespace: kubernetes namespace
	// """

	// base_pod_pattern := re.compile("^(.+)-[a-zA-Z0-9]+$")

	// if !base_pod_pattern.match(old_pod_name) {
	// 	LOG.Error("Could not identify new pod after purging %s",
	// 		old_pod_name)
	// 	return
	// }

	// pod_base_name := base_pod_pattern.match(old_pod_name).group(1)

	// new_pod_name := ""

	// w := watch.Watch()
	// for event := range w.stream(self.client.list_namespaced_pod, namespace) {
	// 	event_name := event["object"].metadata.name
	// 	event_match := base_pod_pattern.match(event_name)
	// 	if !event_match || !event_match.group(1) == pod_base_name {
	// 		continue
	// 	}

	// 	pod_conditions := event["object"].status.conditions
	// 	// wait for new pod deployment
	// 	if event["type"] == "ADDED" && !pod_conditions {
	// 		new_pod_name := event_name
	// 	} else if new_pod_name {
	// 		for condition := range pod_conditions {
	// 			if condition.typef == "Ready" && condition.status == "true" {
	// 				LOG.Info("New pod %s deployed", new_pod_name)
	// 				w.stop()
	// 			}
	// 		}
	// 	}
	// }

}
func (self *K8s) wait_get_completed_podphase(release interface{}, timeout int64) {
	// """
	// :param release: part of namespace
	// :param timeout: time before disconnecting stream
	// """
	// timeout = self._check_timeout(timeout)

	// w := watch.Watch()
	// found_events := false
	// for event := range w.stream(self.client.list_pod_for_all_namespaces, timeout) {
	// 	resource_name := event["object"].metadata.name

	// 	// JEB if release in resource_name {
	// 	if true {
	// 		found_events := true
	// 		pod_state := event["object"].status.phase
	// 		if pod_state == "Succeeded" {
	// 			w.stop()
	// 			break
	// 		}
	// 	}
	// }

	// if !found_events {
	// 	LOG.warn("Saw no test events for release %s", release)
	// }

}
func (self *K8s) _check_timeout(timeout int) int {
	if timeout <= 0 {
		LOG.Info(
			"Kubernetes timeout is invalid or unspecified, using default %ss.", const_DEFAULT_K8S_TIMEOUT)
		timeout = const_DEFAULT_K8S_TIMEOUT
	}
	return timeout
}
