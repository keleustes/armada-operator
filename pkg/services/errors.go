// Copyright 2018 The Operator-SDK Authors
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//   http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package services

import (
	"errors"
)

var (
	// ErrNotFound indicates the release was not found.
	ErrNotFound = errors.New("release not found")

	// Base class for API exceptions and error handling.
	ApiException = errors.New("An unknown API error occurred.")

	// Exception that occurs during chart cleanup.
	ApiBaseException = errors.New("There was an error listing the Helm chart releases.")

	// Exception that occurs during chart cleanup.
	ApiJsonException = errors.New("There was an error listing the Helm chart releases.")

	// Exception that occurs when the server returns a 401 Unauthorized error.
	ClientUnauthorizedError = errors.New("There was an error listing the Helm chart releases.")

	// Exception that occurs when the server returns a 403 Forbidden error.
	ClientForbiddenError = errors.New("There was an error listing the Helm chart releases.")

	// Exception that occurs when the server returns a 500 Internal Server error.
	ClientError = errors.New("There was an error listing the Helm chart releases.")

	// Base class for Armada handler exception and error handling.
	ArmadaException = errors.New("An unknown Armada handler error occurred.")

	ArmadaTimeoutException = errors.New("Armada timed out waiting on: %s")

	// Exception that occurs when Armada encounters a release with status other
	// than DEPLOYED that is designated `protected` in the Chart and
	// continue_processing` is False.
	ProtectedReleaseException = errors.New("Armada encountered protected release {} in {} status")

	// Exception that occurs when Armada encounters invalid values.yaml content in
	// a helm chart.
	InvalidValuesYamlException = errors.New("Armada encountered invalid values.yaml in helm chart: %s")

	// Exception that occurs when Armada encounters invalid override yaml in
	// helm chart.
	InvalidOverrideValuesYamlException = errors.New("Armada encountered invalid values.yaml in helm chart: %s")

	// Exception that occurs while deploying charts.
	ChartDeployException = errors.New("Exception deploying charts: %s")

	// Exception that occurs while waiting for resources to become ready.
	WaitException = errors.New("message")

	// Exception that occurs when it is detected that an existing release
	// operation (e.g. install, update, rollback, delete) is likely still pending.
	DeploymentLikelyPendingException = errors.New("Existing deployment likely pending release={}, status={}")

	// Base class for Armada exception and error handling.
	ArmadaBaseException = errors.New("ArmadaBaseException")

	// Base class for the Chartbuilder handler exception and error handling.
	ChartBuilderException = errors.New("An unknown Armada handler error occurred.")

	// Exception that occurs when dependencies cannot be resolved.
	DependencyException = errors.New("Failed to resolve dependencies for chart_name.")

	// Exception that occurs when Helm Chart fails to build.
	HelmChartBuildException = errors.New("Failed to build Helm chart for {chart_name}.")

	// Exception that occurs while trying to read a file in the chart directory.
	FilesLoadException = errors.New("FilesLoadException")

	// Exception that occurs when there is an error loading files contained in .helmignore.
	IgnoredFilesLoadException = errors.New("An error occurred while loading the ignored files in .helmignore")

	// Exception that occurs when metadata loading fails.
	MetadataLoadException = errors.New("Failed to load metadata from chart yaml file")

	// Exception for unknown chart source type.
	UnknownChartSourceException = errors.New("Unknown source type source_type for chart chart_name")

	// Base class for Kubernetes exceptions and error handling.
	KubernetesException = errors.New("An unknown Kubernetes error occurred.")

	// Exception for timing out during a watch on a Kubernetes object
	KubernetesWatchTimeoutException = errors.New("Kubernetes Watch has timed out.")

	// Exception for getting an unknown event type from the Kubernetes API
	KubernetesUnknownStreamingEventTypeException = errors.New("An unknown event type was returned from the streaming API.")

	// Exception for getting an error from the Kubernetes API
	KubernetesErrorEventException = errors.New("An error event was returned from the streaming API.")

	// An exception occurred while attempting to build an Armada manifest. The
	// exception will return with details as to why.
	ManifestException = errors.New("An error occurred while generating the manifest: %(details)s.")

	// An exception occurred while attempting to build the chart for an
	// Armada manifest. The exception will return with details as to why.
	BuildChartException = errors.New("An error occurred while trying to build chart: %(details)s.")

	// An exception occurred while attempting to build the chart group for an
	// Armada manifest. The exception will return with details as to why.
	BuildChartGroupException = errors.New("An error occurred while building chart group: %(details)s.")

	// An exception occurred while attempting to build a chart dependency for an
	// Armada manifest. The exception will return with details as to why.
	ChartDependencyException = errors.New("An error occurred while building a dependency chart")

	// Base class for Override handler exception and error handling.
	OverrideException = errors.New("An unknown Override handler error occurred.")

	// Exception that occurs when an invalid override type is used with the
	// set flag.
	InvalidOverrideTypeException = errors.New("Override type {} is invalid")

	// Exception that occurs when an invalid override file is provided.
	InvalidOverrideFileException = errors.New("{} is not a valid override file")

	// Exception that occurs when an invalid value is used with the set flag.
	InvalidOverrideValueException = errors.New("{} is not a valid override statement.")

	// Exception that occurs when an invalid value is used with the set flag.
	UnknownDocumentOverrideException = errors.New("Unable to find {1} document schema: {0}")

	//Base class for Git exceptions and error handling.
	SourceException = errors.New("An unknown error occurred while accessing a chart source.")

	// Exception when an error occurs cloning a Git repository.
	GitException = errors.New("Git exception occurred location may not be a valid git repository.")

	// Exception that occurs when authentication fails for cloning a repo.
	GitAuthException = errors.New("Failed to authenticate for repo {} with ssh-key at path {}")

	// Exception when an error occurs cloning a Git repository
	// through a proxy.
	GitProxyException = errors.New("Could not resolve proxy [location].")

	// Exception that occurs when an SSH key could not be found.
	GitSSHException = errors.New("Failed to find specified SSH key: {}.")

	// Exception that occurs for an invalid dir.
	SourceCleanupException = errors.New("target_dir is not a valid directory.")

	// Exception that occurs when the tarball cannot be downloaded from the
	// provided URL.
	TarballDownloadException = errors.New("Unable to download from tarball_url")

	// Exception that occurs when extracting the tarball fails.
	TarballExtractException = errors.New("Unable to extract tarball_dir")

	// Exception that occurs when a nonexistant path is accessed.
	InvalidPathException = errors.New("Unable to access path path")

	// Exception for unknown chart source type.
	ChartSourceException = errors.New("Unknown source type source_type for chart chart_name")

	// Base class for Tiller exceptions and error handling.
	TillerException = errors.New("An unknown Tiller error occurred.")

	// Exception for tiller service being unavailable.
	TillerServicesUnavailableException = errors.New("Tiller services unavailable.")

	// Exception that occurs during chart cleanup.
	ChartCleanupException = errors.New("An error occurred during cleanup while removing {}")

	// Exception that occurs when listing charts
	ListChartsException = errors.New("There was an error listing the Helm chart releases.")

	// Exception that occurs when a job deletion
	PostUpdateJobDeleteException = errors.New("Failed to delete k8s job {} in {}")

	// Exception that occurs when a job creation fails.
	PostUpdateJobCreateException = errors.New("Failed to create k8s job {} in {}")

	//
	PreUpdateJobDeleteException = errors.New("Failed to delete k8s job {} in {}")

	// Exception that occurs when a release fails to install, upgrade, delete,
	// or test.
	ReleaseException = errors.New("Failed to {} release: {} - Tiller Message: {}")

	// Exception that occurs when a release test fails.
	TestFailedException = errors.New("Test failed for release: {}")

	// Exception that occurs during a failed gRPC channel creation
	ChannelException = errors.New("Failed to create gRPC channel.")

	// Exception that occurs during a failed Release Testing.
	GetReleaseStatusException = errors.New("Failed to get {} status {} version")

	// Exception that occurs during a failed Release Testing
	GetReleaseContentException = errors.New("Failed to get {} content {} version {}")

	// Exception that occurs during a failed Release Rollback
	RollbackReleaseException = errors.New("Failed to rollback release {} to version {}")

	// Exception that occurs when a tiller pod cannot be found using the labels
	// specified in the Armada config.
	TillerPodNotFoundException = errors.New("Could not find Tiller pod with labels {}")

	// Exception that occurs when no tiller pod is found in a running state.
	TillerPodNotRunningException = errors.New("No Tiller pods found in running state")

	// Exception that occurs during a failed Release Testing
	TillerVersionException = errors.New("Failed to get Tiller Version")

	// Exception that occurs when paging through releases listed by tiller
	// and the total releases changes between pages.
	TillerListReleasesPagingException = errors.New("Failed to page through tiller releases")

	// Base class for linting exceptions and errors.
	ValidateException = errors.New("An unknown linting error occurred.")

	// Exception for invalid manifests.
	InvalidManifestException = errors.New("Armada manifest(s) failed validation")

	// Exception that occurs when an invalid filename is encountered.
	InvalidChartNameException = errors.New("Chart name must be a string.")

	// Exception when invalid chart definition is encountered.
	InvalidChartDefinitionException = errors.New("Invalid chart definition. Chart definition must be array.")

	// Exception that occurs when a release is invalid.
	InvalidReleaseException = errors.New("Release needs to be a string.")

	// Exception that occurs when an Armada object is not declared.
	InvalidArmadaObjectException = errors.New("An Armada object failed internal validation")
)
