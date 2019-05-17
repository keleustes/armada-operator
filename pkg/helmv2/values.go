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

// +build v2

package helmv2

import (
	"fmt"
	yaml "github.com/ghodss/yaml"
	cpb "k8s.io/helm/pkg/proto/hapi/chart"
)

// merge content of Config object
func mergeConfig(configs []*cpb.Config) (*cpb.Config, error) {
	finalMap := map[string]interface{}{}

	for _, config := range configs {
		currentMap := map[string]interface{}{}

		if err := yaml.Unmarshal([]byte(config.Raw), &currentMap); err != nil {
			return nil, fmt.Errorf("failed to merge config: %s", err)
		}
		// Merge with the previous map
		finalMap = mergeValues(finalMap, currentMap)
	}

	finalRaw, err := yaml.Marshal(finalMap)
	if err != nil {
		return nil, fmt.Errorf("failed to merge config: %s", err)
	}
	finalConfig := &cpb.Config{Raw: string(finalRaw)}
	return finalConfig, nil
}

// Merges source and destination map, preferring values from the source map
func mergeValues(dest map[string]interface{}, src map[string]interface{}) map[string]interface{} {
	for k, v := range src {
		// If the key doesn't exist already, then just set the key to that value
		if _, exists := dest[k]; !exists {
			dest[k] = v
			continue
		}
		nextMap, ok := v.(map[string]interface{})
		// If it isn't another map, overwrite the value
		if !ok {
			dest[k] = v
			continue
		}
		// Edge case: If the key exists in the destination, but isn't a map
		destMap, isMap := dest[k].(map[string]interface{})
		// If the source map has a map for this key, prefer it
		if !isMap {
			dest[k] = v
			continue
		}
		// If we got to this point, it is a map in both, so merge them
		dest[k] = mergeValues(destMap, nextMap)
	}
	return dest
}

// normalizeConfig
func normalizeConfig(config *cpb.Config) (*cpb.Config, error) {
	currentMap := map[string]interface{}{}
	if err := yaml.Unmarshal([]byte(config.Raw), &currentMap); err != nil {
		return nil, fmt.Errorf("failed to normalize config: %s", err)
	}

	// Merge with the previous map
	finalMap := removeNil(currentMap)
	finalRaw, err := yaml.Marshal(finalMap)
	if err != nil {
		return nil, fmt.Errorf("failed to normalize config: %s", err)
	}
	finalConfig := &cpb.Config{Raw: string(finalRaw)}
	return finalConfig, nil
}

// Remove null values
func removeNil(src map[string]interface{}) map[string]interface{} {
	dest := make(map[string]interface{})
	for k, v := range src {
		if v == nil {
			continue
		}

		nextMap, ok := v.(map[string]interface{})
		// If it isn't another map, overwrite the value
		if !ok {
			dest[k] = v
			continue
		}

		dest[k] = removeNil(nextMap)
	}
	return dest
}
