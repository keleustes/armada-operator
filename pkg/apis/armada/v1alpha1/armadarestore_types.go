package v1alpha1

//JEB: Inspired from ETCD backup and adapt to Armada/Airship

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

// ArmadaRestoreSpec defines the desired state of ArmadaRestore
type ArmadaRestoreSpec struct {
	// BackupStorageType is the type of the backup storage which is used as RestoreSource.
	BackupStorageType BackupStorageType `json:"backupStorageType"`
	// RestoreSource tells the where to get the backup and restore from.
	RestoreSource `json:",inline"`

	// Reference to impacted ArmadaCharts
	Charts []string `json:"charts,omitempty"`
	// Target state of the Helm Custom Resources
	TargetState HelmResourceState `json:"targetState,omitempty"`
}

// ArmadaRestoreStatus defines the observed state of ArmadaRestore
type ArmadaRestoreStatus struct {
	ArmadaStatus `json:",inline"`
}

type RestoreSource struct {
	// Offsite tells where on Offsite the backup is saved and how to fetch the backup.
	Offsite *OffsiteRestoreSource `json:"offsite,omitempty"`

	// Ceph tells where on Ceph the backup is saved and how to fetch the backup.
	Ceph *CephRestoreSource `json:"ceph,omitempty"`
}

type OffsiteRestoreSource struct {
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
	Endpoint string `json:"endpoint"`

	// ForcePathStyle forces to use path style over the default subdomain style.
	// This is useful when you have an offsite compatible endpoint that doesn't support
	// subdomain buckets.
	ForcePathStyle bool `json:"forcePathStyle"`
}

type CephRestoreSource struct {
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

// +k8s:deepcopy-gen:interfaces=k8s.io/apimachinery/pkg/runtime.Object

// ArmadaRestore is the Schema for the armadarestores API
// +k8s:openapi-gen=true
// +kubebuilder:subresource:status
// +kubebuilder:resource:path=armadarestores,shortName=arst
// +kubebuilder:printcolumn:name="State",type="string",JSONPath=".status.actual_state",description="State"
// +kubebuilder:printcolumn:name="Target State",type="string",JSONPath=".spec.target_state",description="Target State"
// +kubebuilder:printcolumn:name="Satisfied",type="boolean",JSONPath=".status.satisfied",description="Satisfied"
type ArmadaRestore struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   ArmadaRestoreSpec   `json:"spec,omitempty"`
	Status ArmadaRestoreStatus `json:"status,omitempty"`
}

// +k8s:deepcopy-gen:interfaces=k8s.io/apimachinery/pkg/runtime.Object

// ArmadaRestoreList contains a list of ArmadaRestore
type ArmadaRestoreList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []ArmadaRestore `json:"items"`
}

func init() {
	SchemeBuilder.Register(&ArmadaRestore{}, &ArmadaRestoreList{})
}
