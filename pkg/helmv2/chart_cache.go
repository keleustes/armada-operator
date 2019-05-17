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
	cpb "k8s.io/helm/pkg/proto/hapi/chart"
	"sync"
)

type ChartCache struct {
	charts map[string]*cpb.Chart
	mu     sync.RWMutex
}

var chartcache *ChartCache
var oncechartcache sync.Once

// Init the ChartCache
func GetChartInstance() *ChartCache {
	oncechartcache.Do(func() {
		chartcache = &ChartCache{
			charts: make(map[string]*cpb.Chart),
		}
	})
	return chartcache
}

// Add chart to ChartCache
func (c *ChartCache) Set(k string, x *cpb.Chart) {
	c.mu.Lock()
	c.charts[k] = x
	c.mu.Unlock()
}

// Remove chart from ChartCache
func (c *ChartCache) Get(k string) (*cpb.Chart, bool) {
	c.mu.RLock()
	item, found := c.charts[k]
	if !found {
		c.mu.RUnlock()
		return nil, false
	}
	c.mu.RUnlock()
	return item, true
}

type DirCache struct {
	dirs map[string]string
	mu   sync.RWMutex
}

var dircache *DirCache
var oncedircache sync.Once

// Init the DirCache
func GetDirInstance() *DirCache {
	oncedircache.Do(func() {
		dircache = &DirCache{
			dirs: make(map[string]string),
		}
	})
	return dircache
}

// Add chart to DirCache
func (c *DirCache) Set(k string, x string) {
	c.mu.Lock()
	c.dirs[k] = x
	c.mu.Unlock()
}

// Remove chart from DirCache
func (c *DirCache) Get(k string) (string, bool) {
	c.mu.RLock()
	item, found := c.dirs[k]
	if !found {
		c.mu.RUnlock()
		return "", false
	}
	c.mu.RUnlock()
	return item, true
}
