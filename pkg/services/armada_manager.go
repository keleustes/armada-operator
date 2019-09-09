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

package services

import (
	"context"
	av1 "github.com/keleustes/armada-crd/pkg/apis/armada/v1alpha1"
)

// ArmdaChartGroupManager manages a Armada Chart Group. It can install, update, reconcile,
// and uninstall a list of Armada Charts` .
type ArmadaChartGroupManager interface {
	ResourceName() string
	IsInstalled() bool
	IsUpdateRequired() bool
	Sync(context.Context) error
	InstallResource(context.Context) (*av1.ArmadaCharts, error)
	UpdateResource(context.Context) (*av1.ArmadaCharts, *av1.ArmadaCharts, error)
	ReconcileResource(context.Context) (*av1.ArmadaCharts, error)
	UninstallResource(context.Context) (*av1.ArmadaCharts, error)
}

// ArmdaManifestManager manages a Armada Chart Group. It can install, update, reconcile,
// and uninstall a list of Armada Charts` .
type ArmadaManifestManager interface {
	ResourceName() string
	IsInstalled() bool
	IsUpdateRequired() bool
	Sync(context.Context) error
	InstallResource(context.Context) (*av1.ArmadaChartGroups, error)
	UpdateResource(context.Context) (*av1.ArmadaChartGroups, *av1.ArmadaChartGroups, error)
	ReconcileResource(context.Context) (*av1.ArmadaChartGroups, error)
	UninstallResource(context.Context) (*av1.ArmadaChartGroups, error)
}
