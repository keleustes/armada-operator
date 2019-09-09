// Copyright 2017 AT&T Intellectual Property.  All other rights reserved.
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

// from deepdiff import DeepDiff
// import yaml

type ReleaseDiff struct {
	// """
	// A utility for discovering diffs in helm release inputs, for example to
	// determine whether an upgrade is needed and what specific changes will be
	// applied.

	// Release inputs which are relevant are the override values given, and
	// the chart content including {

	// * default values (values.yaml),
	// * templates and their content
	// * files and their content
	// * the above for each chart on which the chart depends transitively.

	// This excludes Chart.yaml content as that is rarely used by the chart
	// via ``{{ .Chart }}``, and even when it is does not usually necessitate
	// an upgrade.

	// :param old_chart: The deployed chart.
	// :type  old_chart: Chart
	// :param old_values: The deployed chart override values.
	// :type  old_values: dict
	// :param new_chart: The chart to deploy.
	// :type  new_chart: Chart
	// :param new_values: The chart override values to deploy.
	// :type  new_values: dict
	// """
	old_chart  interface{}
	old_values interface{}
	new_chart  interface{}
	new_values interface{}
}

func (self *ReleaseDiff) get_diff() {
	// """
	// Get the diff.

	// :return: Mapping of difference types to sets of those differences.
	// :rtype: dict
	// """

	old_input := self.make_release_input(self.old_chart, self.old_values,
		"previously deployed")
	new_input := self.make_release_input(self.new_chart, self.new_values,
		"currently being deployed")

	return DeepDiff(old_input, new_input, "tree")

}
func (self *ReleaseDiff) make_release_input(chart interface{}, values interface{}, desc interface{}) {
	return &foo{"chart": self.make_chart_dict(chart, desc), "values": values}

}
func (self *ReleaseDiff) make_chart_dict(chart interface{}, desc interface{}) {
	default_values := yaml.safe_load(chart.values.raw)
	if err != nil {
		chart_desc := "{} ({})".format(chart.metadata.name, desc)
		return armada_exceptions.InvalidValuesYamlException(chart_desc)
	}
	files := &foo{f.type_url: f.value} //JEB for f in chart.files}
	templates := &foo{t.name: t.data}  //JEB for t in chart.templates}
	dependencies := &foo{
		"d.metadata.name": self.make_chart_dict(d, "{}({} dependency)".format(desc, d.metadata.name)),
		// JEB for d in chart.dependencies
	}

	return &foo{
		// TODO(seaneagan) { Are there use cases to include other
		// `chart.metadata` (Chart.yaml) fields? If so, could include option
		// under `upgrade` key in armada chart schema for this. Or perhaps
		// can even add `upgrade.always` there to handle dynamic things
		// used in charts like dates, environment variables, etc.
		"name":         chart.metadata.name,
		"values":       default_values,
		"files":        files,
		"templates":    templates,
		"dependencies": dependencies,
	}
}
