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

// JEB: This file has been at first generated from the file presents in
// https://github.com/openstack/airship-armada/tree/master/armada/schemas
// and then through yaml2json tools followed by a call to schema-generate
// This file will be deleted once we figure out what we really want
// to put in our CRDs.

package v1alpha1

import ()

// Labels
type ArmadaLabels struct {
	AdditionalProperties map[string]string `json:"-,omitempty"`
}

// Native
type ArmadaWaitNative struct {
	// Config for the native ``helm (install|upgrade) --wait`` flag. defaults to true
	Enabled bool `json:"enabled,omitempty"`
}

// ResourcesItems
type ArmadaWaitResourcesItems struct {
	// mapping of kubernetes resource labels
	Labels *ArmadaLabels `json:"labels,omitempty"`
	// Only for controller ``type``s. Amount of pods in a controller which must be ready.
	// Can be integer or percent string e.g. ``80%``. Default ``100%``.
	MinReady int `json:"min_ready,omitempty"`
	// k8s resource type, supports: controllers ('deployment', 'daemonset', 'statefulset', 'pod', 'job')
	Type string `json:"type"`
}

// Wait
type ArmadaWait struct {
	// Base mapping of labels to wait on. They are added to any labels in
	// each item in the ``resources`` array.
	Labels *ArmadaLabels `json:"labels,omitempty"`
	// See `Wait Native`_.
	Native *ArmadaWaitNative `json:"native,omitempty"`
	// Array of `Wait Resource`_ to wait on, with ``labels`` added to each
	// item. Defaults to pods and jobs (if any exist) matching ``labels``.
	Resources []*ArmadaWaitResourcesItems `json:"resources,omitempty"`
	// time (in seconds) to wait for chart to deploy
	Timeout int64 `json:"timeout,omitempty"`
}

// HookActionItems
type ArmadaHookActionItems struct {
	Labels *ArmadaLabels `json:"labels,omitempty"`
	Name   string        `json:"name,omitempty"`
	Type   string        `json:"type"`
}

// Delete
type ArmadaDelete struct {
	// time (in seconds) to wait for chart to be deleted
	Timeout int64 `json:"timeout,omitempty"`
}

// Options
type ArmadaUpgradeOptions struct {
	Force        bool `json:"force,omitempty"`
	RecreatePods bool `json:"recreate_pods,omitempty"`
}

// Pre
type ArmadaUpgradePre struct {
	// | pre         | object   | actions performed prior to updating a release                 |
	Create []*ArmadaHookActionItems `json:"create,omitempty"`
	Delete []*ArmadaHookActionItems `json:"delete,omitempty"`
	Update []*ArmadaHookActionItems `json:"update,omitempty"`
}

// Post
type ArmadaUpgradePost struct {
	Create []*ArmadaHookActionItems `json:"create,omitempty"`
}

// Upgrade
type ArmadaUpgrade struct {
	NoHooks bool                  `json:"no_hooks"`
	Options *ArmadaUpgradeOptions `json:"options,omitempty"`
	Post    *ArmadaUpgradePost    `json:"post,omitempty"`
	Pre     *ArmadaUpgradePre     `json:"pre,omitempty"`
}

// Protected
type ArmadaProtectedRelease struct {
	// do not delete FAILED releases when encountered from previous run (provide the
	// 'continue_processing' bool to continue or halt execution (default: halt))
	ContinueProcessing bool `json:"continue_processing,omitempty"`
}

// Source
type ArmadaChartSource struct {
	AuthMethod string `json:"auth_method,omitempty"`
	// ``url`` or ``path`` to the chart's parent directory
	Location    string `json:"location"`
	ProxyServer string `json:"proxy_server,omitempty"`
	// (optional) branch, commit, or reference in the repo (``master`` if not specified)
	Reference string `json:"reference,omitempty"`
	// (optional) relative path to target chart from parent (``.`` if not specified)
	Subpath string `json:"subpath"`
	// source to build the chart: ``git``, ``local``, or ``tar``
	Type string `json:"type"`
}

// Test. JEB that structure could not be converted automatically
type ArmadaTestOptions struct {
	Cleanup bool `json:"cleanup,omitempty"`
}

type ArmadaTest struct {
	Enabled bool               `json:"enabled,omitempty"`
	Timeout int64              `json:"timeout,omitempty"`
	Options *ArmadaTestOptions `json:"options,omitempty"`
}
