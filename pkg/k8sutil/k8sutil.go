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

package k8sutil

import (
	"context"
	"fmt"
	"io/ioutil"
	"os"
	"strings"

	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/runtime/schema"
	discovery "k8s.io/client-go/discovery"
	crclient "sigs.k8s.io/controller-runtime/pkg/client"
	logf "sigs.k8s.io/controller-runtime/pkg/log"
)

var log = logf.Log.WithName("k8sutil")

// GetWatchNamespace returns the namespace the operator should be watching for changes
func GetWatchNamespace() (string, error) {
	ns, found := os.LookupEnv(WatchNamespaceEnvVar)
	if !found {
		return "", fmt.Errorf("%s must be set", WatchNamespaceEnvVar)
	}
	return ns, nil
}

// errNoNS indicates that a namespace could not be found for the current
// environment
var ErrNoNamespace = fmt.Errorf("namespace not found for current environment")

// GetOperatorNamespace returns the namespace the operator should be running in.
func GetOperatorNamespace() (string, error) {
	nsBytes, err := ioutil.ReadFile("/var/run/secrets/kubernetes.io/serviceaccount/namespace")
	if err != nil {
		if os.IsNotExist(err) {
			return "", ErrNoNamespace
		}
		return "", err
	}
	ns := strings.TrimSpace(string(nsBytes))
	log.V(1).Info("Found namespace", "Namespace", ns)
	return ns, nil
}

// GetOperatorName return the operator name
func GetOperatorName() (string, error) {
	operatorName, found := os.LookupEnv(OperatorNameEnvVar)
	if !found {
		return "", fmt.Errorf("%s must be set", OperatorNameEnvVar)
	}
	if len(operatorName) == 0 {
		return "", fmt.Errorf("%s must not be empty", OperatorNameEnvVar)
	}
	return operatorName, nil
}

// ResourceExists returns true if the given resource kind exists
// in the given api groupversion
func ResourceExists(dc discovery.DiscoveryInterface, apiGroupVersion, kind string) (bool, error) {
	apiLists, err := dc.ServerPreferredResources()
	if err != nil {
		return false, err
	}
	for _, apiList := range apiLists {
		if apiList.GroupVersion == apiGroupVersion {
			for _, r := range apiList.APIResources {
				if r.Kind == kind {
					return true, nil
				}
			}
		}
	}
	return false, nil
}

// GetPod returns a Pod object that corresponds to the pod in which the code
// is currently running.
// It expects the environment variable POD_NAME to be set by the downwards API.
func GetPod(ctx context.Context, client crclient.Client, ns string) (*corev1.Pod, error) {
	podName := os.Getenv(PodNameEnvVar)
	if podName == "" {
		return nil, fmt.Errorf("required env %s not set, please configure downward API", PodNameEnvVar)
	}

	log.V(1).Info("Found podname", "Pod.Name", podName)

	pod := &corev1.Pod{}
	key := crclient.ObjectKey{Namespace: ns, Name: podName}
	err := client.Get(ctx, key, pod)
	if err != nil {
		log.Error(err, "Failed to get Pod", "Pod.Namespace", ns, "Pod.Name", podName)
		return nil, err
	}

	// .Get() clears the APIVersion and Kind,
	// so we need to set them before returning the object.
	pod.TypeMeta.APIVersion = "v1"
	pod.TypeMeta.Kind = "Pod"

	log.V(1).Info("Found Pod", "Pod.Namespace", ns, "Pod.Name", pod.Name)

	return pod, nil
}

// GetGVKsFromAddToScheme takes in the runtime scheme and filters out all generic apimachinery meta types.
// It returns just the GVK specific to this scheme.
func GetGVKsFromAddToScheme(addToSchemeFunc func(*runtime.Scheme) error) ([]schema.GroupVersionKind, error) {
	s := runtime.NewScheme()
	err := addToSchemeFunc(s)
	if err != nil {
		return nil, err
	}
	schemeAllKnownTypes := s.AllKnownTypes()
	ownGVKs := []schema.GroupVersionKind{}
	for gvk, _ := range schemeAllKnownTypes {
		if !isKubeMetaKind(gvk.Kind) {
			ownGVKs = append(ownGVKs, gvk)
		}
	}

	return ownGVKs, nil
}

func isKubeMetaKind(kind string) bool {
	if strings.HasSuffix(kind, "List") ||
		kind == "GetOptions" ||
		kind == "DeleteOptions" ||
		kind == "ExportOptions" ||
		kind == "APIVersions" ||
		kind == "APIGroupList" ||
		kind == "APIResourceList" ||
		kind == "UpdateOptions" ||
		kind == "CreateOptions" ||
		kind == "Status" ||
		kind == "WatchEvent" ||
		kind == "ListOptions" ||
		kind == "APIGroup" {
		return true
	}

	return false
}
