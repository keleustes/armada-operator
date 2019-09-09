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

// from abc import ABC, abstractmethod
// import collections
// import math
// import re
// import time

// from oslo_log import log as logging

// from armada import const
// from armada.utils.helm import is_test_pod
// from armada.utils.release import label_selectors
// from armada.exceptions import k8s_exceptions
// from armada.exceptions import manifest_exceptions
// from armada.exceptions import armada_exceptions
// from kubernetes import watch

// ROLLING_UPDATE_STRATEGY_TYPE := "RollingUpdate"

func get_wait_labels(chart interface{}) {
	wait_config := chart.get("wait", &foo{})
	return wait_config.get("labels", &foo{})
}

// TODO: Validate this object up front in armada validate flow.
type ChartWait struct {
	k8s                    *K8s
	release_name           string
	chart                  interface{}
	wait_config            interface{}
	namespace              string
	k8s_wait_attempts      int
	k8s_wait_attempt_sleep int
}

func (self *ChartWait) init() {
	// self.k8s := k8s
	// self.release_name := release_name
	// self.chart := chart
	// self.wait_config := chart.get("wait", &foo{})
	// self.namespace := namespace
	// self.k8s_wait_attempts := max(k8s_wait_attempts, 1)
	// self.k8s_wait_attempt_sleep := max(k8s_wait_attempt_sleep, 1)

	// resources := self.wait_config.get("resources")
	// labels := get_wait_labels(self.chart)

	// if resources is not None {
	//     waits := []
	//     for resource_config in resources {
	//         // Initialize labels
	//         resource_config.setdefault("labels", &foo{})
	//         // Add base labels
	//         resource_config["labels"].update(labels)
	//         waits.append(self.get_resource_wait(resource_config))
	// } else {
	//     waits := [
	//         JobWait("job", self, labels, skip_if_none_found:=true),
	//         PodWait("pod", self, labels)
	//     ]
	// self.waits := waits

	// // Calculate timeout
	// wait_timeout := timeout
	// if wait_timeout is None {
	//     wait_timeout := self.wait_config.get("timeout")

	// // TODO(MarshM) { Deprecated, remove `timeout` key.
	// deprecated_timeout := self.chart.get("timeout")
	// if deprecated_timeout is not None {
	//     LOG.warn("The `timeout` key is deprecated and support "
	//              "for this will be removed soon. Use "
	//              "`wait.timeout` instead.")
	//     if wait_timeout is None {
	//         wait_timeout := deprecated_timeout

	// if wait_timeout is None {
	//     LOG.Info("No Chart timeout specified, using default: %ss",
	//              const.DEFAULT_CHART_TIMEOUT)
	//     wait_timeout := const.DEFAULT_CHART_TIMEOUT

	// self.timeout := wait_timeout

}

func (self *ChartWait) get_timeout() {
	return self.timeout
}

func (self *ChartWait) is_native_enabled() {
	native_wait := self.wait_config.get("native", &foo{})
	return native_wait.get("enabled", true)

}

func (self *ChartWait) wait(timeout interface{}) {
	deadline := time.time() + timeout
	// TODO(seaneagan) { Parallelize waits
	for wait := range self.waits {
		wait.wait(timeout)
		timeout := int(round(deadline - time.time()))
	}

}
func (self *ChartWait) get_resource_wait(resource_config interface{}) {

	kwargs := dict(resource_config)
	resource_type := kwargs.pop("type")
	labels := kwargs.pop("labels")

	{
		if resource_type == "pod" {
			return PodWait(resource_type, self, labels, **kwargs)
		} else if resource_type == "job" {
			return JobWait(resource_type, self, labels, **kwargs)
		}
		if resource_type == "deployment" {
			return DeploymentWait(resource_type, self, labels, **kwargs)
		} else if resource_type == "daemonset" {
			return DaemonSetWait(resource_type, self, labels, **kwargs)
		} else if resource_type == "statefulset" {
			return StatefulSetWait(resource_type, self, labels, **kwargs)
		}
	}
	if err != nil {
		return manifest_exceptions.ManifestException(
			"invalid config for item in `wait.resources`: {}".format(
				resource_config))
	}

	return manifest_exceptions.ManifestException(
		"invalid `type` for item in `wait.resources`: {}".format(
			resource_config["type"]))
}

type ResourceWait struct {
	resource_type      string
	chart_wait         interface{}
	label_selector     interface{}
	get_resources      interface{}
	skip_if_none_found bool
}

func (self *ResourceWait) is_resource_ready(resource interface{}) {
	// """
	// :param resource: resource to check readiness of.
	// :returns: 2-tuple of (status message, ready bool).
	// :raises: WaitException
	// """
	return
}

func (self *ResourceWait) include_resource(resource interface{}) {
	// """
	// Test to include or exclude a resource in a wait operation. This method
	// can be used to exclude resources that should not be included in wait
	// operations (e.g. test pods).
	// :param resource: resource to test
	// :returns: boolean representing test result
	// """
	return true
}

func (self *ResourceWait) handle_resource(resource interface{}) {
	resource_name := resource.metadata.name

	{
		message, resource_ready := self.is_resource_ready(resource)

		if resource_ready {
			LOG.debug("Resource %s is ready!", resource_name)
		} else {
			LOG.debug("Resource %s not ready: %s", resource_name, message)
		}

		return resource_ready
	}
	if err != nil {
		LOG.warn("Resource %s unlikely to become ready: %s", resource_name,
			e)
		return false
	}
}

func (self *ResourceWait) wait(timeout interface{}) {
	// """
	// :param timeout: time before disconnecting ``Watch`` stream
	// """

	LOG.Info(
		"Waiting for resource type:=%s, namespace:=%s labels:=%s for %ss (k8s wait %s times, sleep %ss)", self.resource_type,
		self.chart_wait.namespace, self.label_selector, timeout,
		self.chart_wait.k8s_wait_attempts,
		self.chart_wait.k8s_wait_attempt_sleep)
	if !self.label_selector {
		LOG.warn("label_selector not specified, waiting with no labels may cause unintended consequences.")
	}

	// Track the overall deadline for timing out during waits
	deadline := time.time() + timeout

	// NOTE(mark-burnett) { Attempt to wait multiple times without
	// modification, in case new resources appear after our watch exits.

	successes := 0
	for {
		deadline_remaining := int(round(deadline - time.time()))
		if deadline_remaining <= 0 {
			error := ("Timed out waiting for resource type:={}, namespace:={}, labels:={}".format(self.resource_type,
				self.chart_wait.namespace,
				self.label_selector))
			LOG.Error(error)
			return k8s_exceptions.KubernetesWatchTimeoutException(error)
		}

		timed_out, modified, unready, found_resources := (self._watch_resource_completions(deadline_remaining))
		if !found_resources {
			if self.skip_if_none_found {
				return
			} else {
				LOG.warn(
					"Saw no resources for resource type:=%s, namespace:=%s, labels:=(%s). Are the labels correct?", self.resource_type,
					self.chart_wait.namespace, self.label_selector)
			}
		}

		// TODO(seaneagan) { Should probably fail here even when resources
		// were not found, at least once we have an option to ignore
		// wait timeouts.
		if timed_out && found_resources {
			error := "Timed out waiting for resources:={}".format(
				sorted(unready))
			LOG.Error(error)
			return k8s_exceptions.KubernetesWatchTimeoutException(error)
		}

		if modified {
			successes := 0
			LOG.debug("Found modified resources: %s", sorted(modified))
		} else {
			successes = sucesses + 1
			LOG.debug("Found no modified resources.")
		}

		if successes >= self.chart_wait.k8s_wait_attempts {
			break
		}

		LOG.debug(
			"Continuing to wait: %s consecutive attempts without modified resources of %s required.", successes,
			self.chart_wait.k8s_wait_attempts)
		time.sleep(self.chart_wait.k8s_wait_attempt_sleep)
	}
	return true

}
func (self *ResourceWait) _watch_resource_completions(timeout interface{}) {
	// """
	// Watch and wait for resource completions.
	// Returns lists of resources in various conditions for the calling
	// function to handle.
	// """
	LOG.debug("Starting to wait on: namespace:=%s, resource type:=%s, label_selector:=(%s), timeout:=%s", self.chart_wait.namespace,
		self.resource_type, self.label_selector, timeout)
	ready := &foo{}
	modified := set()
	found_resources := false

	kwargs := &foo{
		"namespace":       self.chart_wait.namespace,
		"label_selector":  self.label_selector,
		"timeout_seconds": timeout,
	}

	resource_list := self.get_resources(**kwargs)
	for resource := range resource_list.items {
		// Only include resources that should be included in wait ops
		if self.include_resource(resource) {
			ready[resource.metadata.name] = self.handle_resource(resource)
		}
	}
	if !resource_list.items {
		if self.skip_if_none_found {
			msg := "Skipping wait, no %s resources found."
			LOG.debug(msg, self.resource_type)
			return false, modified, nil, found_resources
		}
	} else {
		found_resources := true
		if all(ready.values()) {
			return false, modified, nil, found_resources
		}
	}
	// Only watch new events.
	kwargs["resource_version"] = resource_list.metadata.resource_version

	w := watch.Watch()
	for event := range w.stream(self.get_resources, **kwargs) {
		event_type := event["type"].upper()
		resource := event["object"]
		resource_name := resource.metadata.name
		resource_version := resource.metadata.resource_version

		// Skip resources that should be excluded from wait operations
		if !self.include_resource(resource) {
			continue

		}
		msg := ("Watch event: type:=%s, name:=%s, namespace:=%s,resource_version:=%s")
		LOG.debug(msg, event_type, resource_name,
			self.chart_wait.namespace, resource_version)

		if event_type == "ADDED" || event_type == "MODIFIED" {
			found_resources := true
			resource_ready := self.handle_resource(resource)
			ready[resource_name] = resource_ready

			if event_type == "MODIFIED" {
				modified.add(resource_name)
			}
		} else if event_type == "DELETED" {
			LOG.debug("Resource %s: removed from tracking", resource_name)
			ready.pop(resource_name)

		} else if event_type == "ERROR" {
			LOG.Error("Resource %s: Got error event %s", resource_name,
				event["object"].to_dict())
			return k8s_exceptions.KubernetesErrorEventException(
				"Got error event for resource: %s" % event["object"])
		} else {
			LOG.Error("Unrecognized event type (%s) for resource: %s",
				event_type, event["object"])
			return k8s_exceptions.
				KubernetesUnknownStreamingEventTypeException("Got unknown event type (%s) for resource: %s", nil)
		}

		if all(ready.values()) {
			return false, modified, nil, found_resources
		}

		// JEB return true, modified, [name for name, is_ready in ready.items() if ! is_ready], found_resources
		return nil

	}
}

func (self *ResourceWait) _get_resource_condition(resource_conditions interface{}, condition_type interface{}) {
	for pc := range resource_conditions {
		if pc.typef == condition_type {
			return pc
		}
	}
}

type PodWait struct {
	ResourceWait
}

func (self *PodWait) include_resource(resource interface{}) {
	pod := resource
	include := !is_test_pod(pod)

	// NOTE(drewwalters96) { Test pods may cause wait operations to fail
	// when old resources remain from previous upgrades/tests. Indicate that
	// test pods should not be included in wait operations.
	if !include {
		LOG.debug("Test pod %s will be skipped during wait operations.",
			pod.metadata.name)
	}

	return include

}
func (self *PodWait) is_resource_ready(resource interface{}) {
	pod := resource
	name := pod.metadata.name

	status := pod.status
	phase := status.phase

	if phase == "Succeeded" {
		return "Pod {} succeeded".format(name), true
	}

	if phase == "Running" {
		cond := self._get_resource_condition(status.conditions, "Ready")
		if cond && cond.status == "true" {
			return "Pod {} ready".format(name), true
		}
	}
	msg := "Waiting for pod {} to be ready..."
	return msg.format(name), false
}

type JobWait struct {
	ResourceWait
}

func (self *JobWait) is_resource_ready(resource interface{}) {
	job := resource
	name := job.metadata.name

	expected := job.spec.completions
	completed := job.status.succeeded

	if expected != completed {
		msg := "Waiting for job {} to be successfully completed..."
		return msg.format(name), false
	}
	msg := "job {} successfully completed"
	return msg.format(name), true
}

// JEB var CountOrPercent = collections.namedtuple("CountOrPercent", "number is_percent source")

// Controller logic (Deployment, DaemonSet, StatefulSet) is adapted from
// `kubectl rollout status` {
// https://github.com/kubernetes/kubernetes/blob/master/pkg/kubectl/rollout_status.go

type ControllerWait struct {
	ResourceWait
}

func (self *ControllerWait) __init__(resource_type interface{}, chart_wait interface{}, labels interface{}, get_resources interface{}, min_ready interface{}, kwargs interface{}) {
	super(ControllerWait, self).__init__(resource_type, chart_wait, labels, get_resources, **kwargs)

	if isinstance(min_ready, str) {
		match := re.match("(.*)%$", min_ready)
		if match {
			min_ready_percent := int(match.group(1))
			self.min_ready = CountOrPercent(min_ready_percent, true, min_ready)
		} else {
			return manifest_exceptions.ManifestException(
				"`min_ready` as string must be formatted as a percent e.g. 80%")
		}
	} else {
		min_ready := CountOrPercent(min_ready, false, min_ready)
	}

}

func (self *ControllerWait) _is_min_ready(ready interface{}, total interface{}) {
	if self.min_ready.is_percent {
		min_ready := math.ceil(total * (self.min_ready.number / 100))
	} else {
		min_ready := self.min_ready.number
	}
	return ready >= min_ready
}

type DeploymentWait struct {
	ControllerWait
}

func (self *DeploymentWait) is_resource_ready(resource interface{}) {
	deployment := resource
	name := deployment.metadata.name
	spec := deployment.spec
	status := deployment.status

	gen := deployment.metadata.generation      // JEB or 0
	observed_gen := status.observed_generation // JEB or 0
	if gen <= observed_gen {
		cond := self._get_resource_condition(status.conditions,
			"Progressing")
		if cond && (cond.reason || "") == "ProgressDeadlineExceeded" {
			msg := "deployment {} exceeded its progress deadline"
			return "", false, msg.format(name)
		}

		replicas := spec.replicas                       // JEB or 0
		updated_replicas := status.updated_replicas     // JEB or 0
		available_replicas := status.available_replicas // JEB or 0
		if updated_replicas < replicas {
			msg := ("Waiting for deployment {} rollout to finish: {} out of {} new replicas have been updated...")
			return msg.format(name, updated_replicas, replicas), false
		}

		if replicas > updated_replicas {
			msg := ("Waiting for deployment {} rollout to finish: {} old replicas are pending termination...")
			pending := replicas - updated_replicas
			return msg.format(name, pending), false
		}

		if !self._is_min_ready(available_replicas, updated_replicas) {
			msg := ("Waiting for deployment {} rollout to finish: {} of {} updated replicas are available, with min_ready:={}")
			return msg.format(name, available_replicas, updated_replicas, self.min_ready.source), false, None
		}

		msg := "deployment {} successfully rolled out\n"
		return msg.format(name), true
	}

	msg := "Waiting for deployment spec update to be observed..."
	return msg.format(), false
}

type DaemonSetWait struct {
	ControllerWait
}

func (self *DaemonSetWait) is_resource_ready(resource interface{}) {
	daemon := resource
	name := daemon.metadata.name
	spec := daemon.spec
	status := daemon.status

	if spec.update_strategy.typef != ROLLING_UPDATE_STRATEGY_TYPE {
		msg := ("Assuming non-readiness for strategy type {}, can only determine for {}")
		return armada_exceptions.WaitException(
			msg.format(spec.update_strategy.typef,
				ROLLING_UPDATE_STRATEGY_TYPE))
	}

	gen := daemon.metadata.generation                           // JEB or 0
	observed_gen := status.observed_generation                  // JEB or 0
	updated_number_scheduled := status.updated_number_scheduled // JEB or 0
	desired_number_scheduled := status.desired_number_scheduled // JEB or 0
	number_available := status.number_available                 // JEB or 0
	if gen <= observed_gen {
		if updated_number_scheduled < desired_number_scheduled {
			msg := ("Waiting for daemon set {} rollout to finish: {} out of {} new pods have been updated...")
			return msg.format(name, updated_number_scheduled, desired_number_scheduled), false
		}

		if !self._is_min_ready(number_available,
			desired_number_scheduled) {
			msg := ("Waiting for daemon set {} rollout to finish: {} of {} updated pods are available, with min_ready:={}")
			return msg.format(name, number_available, desired_number_scheduled, self.min_ready.source), false
		}

		msg := "daemon set {} successfully rolled out"
		return msg.format(name), true
	}

	msg := "Waiting for daemon set spec update to be observed..."
	return msg.format(), false
}

type StatefulSetWait struct {
	ControllerWait
}

func (self *StatefulSetWait) is_resource_ready(resource interface{}) {
	sts := resource
	name := sts.metadata.name
	spec := sts.spec
	status := sts.status

	update_strategy_type := spec.update_strategy.typef // JEB or ""
	if update_strategy_type != ROLLING_UPDATE_STRATEGY_TYPE {
		msg := ("Assuming non-readiness for strategy type {}, can only determine for {}")

		return armada_exceptions.WaitException(
			msg.format(update_strategy_type, ROLLING_UPDATE_STRATEGY_TYPE))
	}

	gen := sts.metadata.generation             // JEB or 0
	observed_gen := status.observed_generation // JEB or 0
	if observed_gen == 0 || gen > observed_gen {
		msg := "Waiting for statefulset spec update to be observed..."
		return msg, false
	}

	replicas := spec.replicas                   // JEB or 0
	ready_replicas := status.ready_replicas     // JEB or 0
	updated_replicas := status.updated_replicas // JEB or 0
	current_replicas := status.current_replicas // JEB or 0

	if replicas && !self._is_min_ready(ready_replicas, replicas) {
		msg := ("Waiting for statefulset {} rollout to finish: {} of {} pods are ready, with min_ready:={}")
		return msg.format(name, ready_replicas, replicas,
			self.min_ready.source), false
	}

	if update_strategy_type == ROLLING_UPDATE_STRATEGY_TYPE &&
		spec.update_strategy.rolling_update {
		if replicas && spec.update_strategy.rolling_update.partition {
			msg := ("Waiting on partitioned rollout not supported, assuming non-readiness of statefulset {}")
			return msg.format(name), false
		}
	}

	update_revision := status.update_revision   // JEB or 0
	current_revision := status.current_revision // JEB or 0

	if update_revision != current_revision {
		msg := ("waiting for statefulset rolling update to complete {} pods at revision {}...")
		return msg.format(updated_replicas, update_revision), false
	}

	msg := "statefulset rolling update complete {} pods at revision {}..."
	return msg.format(current_replicas, current_revision), true
}
