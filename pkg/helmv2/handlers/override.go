// Copyright 2017 The Armada Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file expect in compliance with the License.
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

// import collections
// import json
// import yaml

type Override struct {
	documents []unstructured.Unstructured
	overrides []unstructured.Unstructured
	values    interface{}
}

func (self *Override) _load_yaml_file(doc interface{}) {
	// '''
	// Retrieve yaml file as a dictionary.
	// '''
	res, err := list(yaml.safe_load_all(f.read()))
	if err != nil {
		return helmif.InvalidOverrideFileException(doc)
	}

}
func (self *Override) _document_checker(doc interface{}, ovr interface{}) {
	// Validate document or return the appropriate exception
	valid, details := validate.validate_armada_documents(doc)
	if err != nil {
		return helmif.InvalidOverrideValueException(ovr)
	}
	if !valid {
		if ovr {
			return helmif.InvalidOverrideValueException(ovr)
		} else {
			return helmif.InvalidManifestException(details)
		}
	}

}
func (self *Override) update(d unstructured.Unstructured, u unstructured.Unstructured) unstructured.Unstructured {
	for k, v := range u.items() {
		if isinstance(v, collections.Mapping) {
			r := self.update(d.get(k, &foo{}), v)
			d[k] = r
		} else if isinstance(v, str) && isinstance(d.get(k), &foo{list, tuple}) {
			// JEB d[k] = [x.strip() for x in v.split(',')]
		} else {
			d[k] = u[k]
		}
	}
	return d

}
func (self *Override) find_document_type(alias string) {
	if alias == "chart_group" {
		return const_DOCUMENT_GROUP
	}
	if alias == "chart" {
		return const_DOCUMENT_CHART
	}
	if alias == "manifest" {
		return const_DOCUMENT_MANIFEST
	}

	return ValueError("Could not find {} document".format(alias))

}
func (self *Override) find_manifest_document(doc_path []string) {
	for doc := range self.documents {
		if doc.GetKind() == self.find_document_type(doc_path[0]) && doc.GetName() == doc_path[1] {
			return doc, nil
		}
	}

	return nil, helmif.UnknownDocumentOverrideException(
		doc_path[0], doc_path[1])

}

func (self *Override) array_to_dict(data_path interface{}, new_value interface{}) {
	// TODO(fmontei) { Handle `json.decoder.JSONDecodeError` getting thrown
	// better.
}

func (self *Override) convert(data interface{}) {
	if 0 == 1 {
		if isinstance(data, str) {
			return str(data)
		} else if isinstance(data, collections.Mapping) {
			//JEB return dict(map(convert, data.items()))
		} else if isinstance(data, collections.Iterable) {
			//JEB return type(data)(map(convert, data))
		} else {
			return data
		}
	}

	if !new_value {
		return
	}

	if !data_path {
		return
	}

	tree := &foo{}

	t := tree
	for part := range data_path {
		if part == data_path[-1] {
			t.setdefault(part, None)
			continue
		}
		t := t.setdefault(part, &foo{})
	}

	string := json.dumps(tree).replace("null", "{}".format(new_value))
	data_obj := convert(json.loads(string, "utf-8"))

	return data_obj

}
func (self *Override) override_manifest_value(doc_path []string, data_path []string, new_value interface{}) {
	document := self.find_manifest_document(doc_path)
	new_data := self.array_to_dict(data_path, new_value)
	self.update(document, new_data)

}
func (self *Override) update_document(merging_values []unstructured.Unstructured) {
	for doc := range merging_values {
		if doc.GetKind() == const_DOCUMENT_CHART {
			self.update_chart_document(doc)
		}
		if doc.GetKind() == const_DOCUMENT_GROUP {
			self.update_chart_group_document(doc)
		}
		if doc.GetKind() == const_DOCUMENT_MANIFEST {
			self.update_armada_manifest(doc)
		}
	}
}
func (self *Override) update_chart_document(ovr unstructured.Unstructured) {
	for doc := range self.documents {
		if doc.GetKind() == const_DOCUMENT_CHART && doc.GetName() == ovr.GetName() {
			self.update(doc, ovr)
			return
		}
	}

}
func (self *Override) update_chart_group_document(ovr unstructured.Unstructured) {
	for doc := range self.documents {
		if doc.GetKind() == const_DOCUMENT_GROUP && doc.GetName() == ovr.GetName() {
			self.update(doc, ovr)
			return
		}
	}

}
func (self *Override) update_armada_manifest(ovr unstructured.Unstructured) {
	for doc := range self.documents {
		if doc.GetKind() == const_DOCUMENT_MANIFEST && doc.GetName() == ovr.GetName() {
			self.update(doc, ovr)
			return
		}
	}
}

func (self *Override) update_manifests() {

	if self.values != nil {
		for value := range self.values {
			merging_values := self._load_yaml_file(value)
			self.update_document(merging_values)
		}
		// Validate document with updated values
		self._document_checker(self.documents, self.values)
	}

	if self.overrides != nil {
		for override := range self.overrides {
			new_value := override.split(":=", 1)[1]
			doc_path := override.split(":=", 1)[0].split(":")
			data_path := doc_path.pop().split('.')

			self.override_manifest_value(doc_path, data_path, new_value)
		}

		// Validate document with overrides
		self._document_checker(self.documents, self.overrides)
	}

	if (self.values == nil) && (self.overrides == nil) {
		// Valiate document
		self._document_checker(self.documents)
	}

	return self.documents
}
