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

package v1alpha1

import (
	"testing"
)

func TestComputeActualState(t *testing.T) {
	// NOTE: testStatus is modified by the call to ComputeActualState.
	// It *must* be recreated before each call to assure desired state
	var testStatus *ArmadaStatus
	var testCondition HelmResourceCondition

	testCondition = HelmResourceCondition{Status: ConditionStatusTrue, Type: ConditionInitialized}
	testStatus = &ArmadaStatus{ActualState: StateUnknown}
	testStatus.ComputeActualState(testCondition, StateDeployed)
	compareState(t, testStatus, StateInitialized, false, "")
	testStatus = &ArmadaStatus{ActualState: StateUnknown}
	testStatus.ComputeActualState(testCondition, StateInitialized)
	compareState(t, testStatus, StateInitialized, true, "")

	testCondition = HelmResourceCondition{Status: ConditionStatusTrue, Type: ConditionDeployed}
	testStatus = &ArmadaStatus{ActualState: StateUnknown}
	testStatus.ComputeActualState(testCondition, StateInitialized)
	compareState(t, testStatus, StateDeployed, false, "")
	testStatus = &ArmadaStatus{ActualState: StateUnknown}
	testStatus.ComputeActualState(testCondition, StateDeployed)
	compareState(t, testStatus, StateDeployed, true, "")

	testCondition = HelmResourceCondition{Status: ConditionStatusTrue, Type: ConditionIrreconcilable}
	testStatus = &ArmadaStatus{ActualState: StateUnknown}
	testStatus.ComputeActualState(testCondition, StateDeployed)
	compareState(t, testStatus, StateFailed, false, testStatus.Reason)

	testCondition = HelmResourceCondition{Status: ConditionStatusTrue, Type: "TEST TYPE"}
	testStatus = &ArmadaStatus{ActualState: StateUnknown}
	testStatus.ComputeActualState(testCondition, StateInitialized)
	compareState(t, testStatus, testStatus.ActualState, false, "")
	testStatus = &ArmadaStatus{ActualState: StateInitialized}
	testStatus.ComputeActualState(testCondition, StateInitialized)
	compareState(t, testStatus, testStatus.ActualState, true, "")

	testCondition = HelmResourceCondition{Status: ConditionStatusFalse, Type: ConditionDeployed}
	testStatus = &ArmadaStatus{ActualState: StateUnknown}
	testStatus.ComputeActualState(testCondition, StateUnknown)
	compareState(t, testStatus, StateUninstalled, false, "")
	testStatus = &ArmadaStatus{ActualState: StateUnknown}
	testStatus.ComputeActualState(testCondition, StateUninstalled)
	compareState(t, testStatus, StateUninstalled, true, "")

	testCondition = HelmResourceCondition{Status: ConditionStatusFalse, Type: "TEST TYPE"}
	testStatus = &ArmadaStatus{ActualState: StateUninstalled}
	testStatus.ComputeActualState(testCondition, StateDeployed)
	compareState(t, testStatus, testStatus.ActualState, false, "")
	testStatus.ComputeActualState(testCondition, StateUninstalled)
	compareState(t, testStatus, testStatus.ActualState, true, "")

}

// compareState is a convenience function to check all the results of ComputeActualState
func compareState(t *testing.T, s *ArmadaStatus, expectedState HelmResourceState, expectedSatisfied bool, expectedReason string) {
	if s.ActualState != expectedState {
		t.Errorf("Expected 's.ActualState' to be %s, got %s", expectedState, s.ActualState)
	}
	if s.Satisfied != expectedSatisfied {
		t.Errorf("Expected 's.Satisfied' to be %t, got %t", expectedSatisfied, s.Satisfied)
	}
	if s.Reason != expectedReason {
		t.Errorf("Expected 's.Reason' to be %s, got %s", expectedReason, s.Reason)
	}
}
