// Copyright 2018 The Operator-SDK Authors
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

// +build v3

package helmv3

import (
	"os"

	"sigs.k8s.io/controller-runtime/pkg/manager"

	av1 "github.com/keleustes/armada-operator/pkg/apis/armada/v1alpha1"
	helmif "github.com/keleustes/armada-operator/pkg/services"

	"k8s.io/helm/helm/pkg/kube"
	"k8s.io/helm/helm/pkg/storage"
	"k8s.io/helm/helm/pkg/storage/driver"
)

type managerFactory struct {
	storageBackend *storage.Storage
	helmKubeClient *kube.Client
}

// NewManagerFactory returns a new Helm manager factory capable of installing and uninstalling releases.
func NewManagerFactory(mgr manager.Manager) helmif.HelmManagerFactory {
	// Create Tiller's storage backend and kubernetes client
	storageBackend := storage.Init(driver.NewMemory())
	helmKubeClient, err := NewFromManager(mgr)
	if err != nil {
		log.Error(err, "Failed to create new Tiller client.", storageBackend, helmKubeClient)
		os.Exit(1)
	}

	return &managerFactory{storageBackend, helmKubeClient}
}

func (f managerFactory) NewArmadaChartManager(r *av1.ArmadaChart) helmif.HelmManager {
	return &chartmanager{
		storageBackend: f.storageBackend,
		helmKubeClient: f.helmKubeClient,
		chartLocation:  r.Spec.Source,

		renderer:    nil,
		releaseName: r.Spec.Release,
		namespace:   r.GetNamespace(),

		spec:   r.Spec,
		status: &r.Status,
	}
}
