package v1alpha1

//JEB: Inspired from ETCD backup and adapt to Armada/Airship

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

const (
	// Offsite related consts
	BackupStorageTypeOffsite         BackupStorageType = "Offsite"
	OffsiteSecretCredentialsFileName                   = "credentials"
	OffsiteSecretConfigFileName                        = "config"

	// Ceph related consts
	BackupStorageTypeCeph BackupStorageType = "Ceph"
	CephAccessToken                         = "access-token"
	CephCredentialsJson                     = "credentials.json"
)

type BackupStorageType string

// ArmadaBackupSpec defines the desired state of ArmadaBackup
type ArmadaBackupSpec struct {
	// ArmadaEndpoints specifies the endpoints of an armada cluster.
	// When multiple endpoints are given, the backup operator retrieves
	// the backup from the endpoint that has the most up-to-date state.
	// The given endpoints must belong to the same armada cluster.
	ArmadaEndpoints []string `json:"armadaEndpoints,omitempty"`
	// StorageType is the armada backup storage type.
	// We need this field because CRD doesn't support validation against invalid fields
	// and we cannot verify invalid backup storage source.
	StorageType BackupStorageType `json:"storageType"`
	// BackupPolicy configures the backup process.
	BackupPolicy *BackupPolicy `json:"backupPolicy,omitempty"`
	// BackupSource is the backup storage source.
	BackupSource `json:",inline"`
	// ClientTLSSecret is the secret containing the armada TLS client certs and
	// must contain the following data items:
	// data:
	//    "armada-client.crt": <pem-encoded-cert>
	//    "armada-client.key": <pem-encoded-key>
	//    "armada-client-ca.crt": <pem-encoded-ca-cert>
	ClientTLSSecret string `json:"clientTLSSecret,omitempty"`

	// Reference to impacted ArmadaCharts
	Charts []string `json:"charts,omitempty"`
	// Target state of the Helm Custom Resources
	TargetState HelmResourceState `json:"targetState,omitempty"`
}

// BackupSource contains the supported backup sources.
type BackupSource struct {
	// Offsite defines the Offsite backup source spec.
	Offsite *OffsiteBackupSource `json:"offsite,omitempty"`
	// Ceph defines the Ceph backup source spec.
	Ceph *CephBackupSource `json:"ceph,omitempty"`
}

// OffsiteBackupSource provides the spec how to store backups on Offsite.
type OffsiteBackupSource struct {
	// Path is the full offsite path where the backup is saved.
	// The format of the path must be: "<offsite-bucket-name>/<path-to-backup-file>"
	// e.g: "mybucket/armada.backup"
	Path string `json:"path"`

	// The name of the secret object that stores the Offsite credential and config files.
	// The file name of the credential MUST be 'credentials'.
	// The file name of the config MUST be 'config'.
	// The profile to use in both files will be 'default'.
	//
	// OffsiteSecret overwrites the default armada operator wide Offsite credential and config.
	OffsiteSecret string `json:"offsiteSecret"`

	// Endpoint if blank points to offsite. If specified, can point to offsite compatible object
	// stores.
	Endpoint string `json:"endpoint,omitempty"`

	// ForcePathStyle forces to use path style over the default subdomain style.
	// This is useful when you have an offsite compatible endpoint that doesn't support
	// subdomain buckets.
	ForcePathStyle bool `json:"forcePathStyle"`
}

// CephBackupSource provides the spec how to store backups on Ceph.
type CephBackupSource struct {
	// Path is the full Ceph path where the backup is saved.
	// The format of the path must be: "<ceph-bucket-name>/<path-to-backup-file>"
	// e.g: "mycephbucket/armada.backup"
	Path string `json:"path"`

	// The name of the secret object that stores the Google storage credential
	// containing at most ONE of the following:
	// An access token with file name of 'access-token'.
	// JSON credentials with file name of 'credentials.json'.
	//
	// If omitted, client will use the default application credentials.
	CephSecret string `json:"cephSecret,omitempty"`
}

// BackupPolicy defines backup policy.
type BackupPolicy struct {
	// TimeoutInSecond is the maximal allowed time in second of the entire backup process.
	TimeoutInSecond int64 `json:"timeoutInSecond,omitempty"`
}

// ArmadaBackupStatus defines the observed state of ArmadaBackup
type ArmadaBackupStatus struct {
	ArmadaStatus `json:",inline"`
}

// +k8s:deepcopy-gen:interfaces=k8s.io/apimachinery/pkg/runtime.Object

// ArmadaBackup is the Schema for the armadabackups API
// +k8s:openapi-gen=true
// +kubebuilder:subresource:status
// +kubebuilder:resource:path=armadabackups,shortName=abck
// +kubebuilder:printcolumn:name="State",type="string",JSONPath=".status.actual_state",description="State"
// +kubebuilder:printcolumn:name="Target State",type="string",JSONPath=".spec.target_state",description="Target State"
// +kubebuilder:printcolumn:name="Satisfied",type="boolean",JSONPath=".status.satisfied",description="Satisfied"
type ArmadaBackup struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   ArmadaBackupSpec   `json:"spec,omitempty"`
	Status ArmadaBackupStatus `json:"status,omitempty"`
}

// +k8s:deepcopy-gen:interfaces=k8s.io/apimachinery/pkg/runtime.Object

// ArmadaBackupList contains a list of ArmadaBackup
type ArmadaBackupList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []ArmadaBackup `json:"items"`
}

func init() {
	SchemeBuilder.Register(&ArmadaBackup{}, &ArmadaBackupList{})
}
