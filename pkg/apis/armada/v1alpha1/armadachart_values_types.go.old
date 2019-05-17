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

import ()

type AVPod struct {
}

type AVStorageclass struct {
}

type AVNetworking struct {
}

type AVLivenessprobe struct {
}

type AVImages struct {
	// tags contains tbd
	Tags map[string]string `json:"tags,omitempty"`
	// pull_policy contains tbd
	PullPolicy string `json:"pull_policy,omitempty"`
}

type AVData struct {
}

type AVJobs struct {
}

type AVStorage struct {
}

type AVAnchor struct {
}

type AVApiserver struct {
}

type AVMonitoring struct {
}

type AVKubeService struct {
}

type AVCephMgrModulesConfig struct {
}

type AVSecrets struct {
	// anchor contains tbd
	Anchor *AVSecretAnchor `json:"anchor,omitempty"`
	// etcd contains tbd
	Etcd *AVSecretEtcd `json:"etcd,omitempty"`
	// keyrings contains tbd
	Keyrings *AVSecretKeyrings `json:"keyrings,omitempty"`
	// maas_region contains tbd
	MaasRegion *AVSecretMaasRegion `json:"maas_region,omitempty"`
	// service_account contains tbd
	ServiceAccount *AVSecretServiceAccount `json:"service_account,omitempty"`
	// tls contains tbd
	Tls *AVTls `json:"tls,omitempty"`
}

type AVService struct {
}

type AVBootstrap struct {
	// enabled contains tbd
	Enabled bool `json:"enabled,omitempty"`
	// script contains tbd
	Script string `json:"script,omitempty"`
	// ip contains tbd
	Ip string `json:"ip,omitempty"`
}

type AVConf struct {
}

type AVNetwork struct {
}

type AVDevelopment struct {
}

type AVBootstrapping struct {
}

type AVEndpoints struct {
	// alerts contains tbd
	Alerts *AVEndpointType1 `json:"alerts,omitempty"`
	// armada contains tbd
	Armada *AVEndpointType1 `json:"armada,omitempty"`
	// ceph_object_store contains tbd
	CephObjectStore *AVEndpointType1 `json:"ceph_object_store,omitempty"`
	// cloudformation contains tbd
	Cloudformation *AVEndpointType1 `json:"cloudformation,omitempty"`
	// cloudwatch contains tbd
	Cloudwatch *AVEndpointType1 `json:"cloudwatch,omitempty"`
	// compute_metadata contains tbd
	ComputeMetadata *AVEndpointType1 `json:"compute_metadata,omitempty"`
	// compute_novnc_proxy contains tbd
	ComputeNovncProxy *AVEndpointType1 `json:"compute_novnc_proxy,omitempty"`
	// compute contains tbd
	Compute *AVEndpointType1 `json:"compute,omitempty"`
	// compute_spice_proxy contains tbd
	ComputeSpiceProxy *AVEndpointType1 `json:"compute_spice_proxy,omitempty"`
	// dashboard contains tbd
	Dashboard *AVEndpointType1 `json:"dashboard,omitempty"`
	// deckhand contains tbd
	Deckhand *AVEndpointType1 `json:"deckhand,omitempty"`
	// elasticsearch contains tbd
	Elasticsearch *AVEndpointType1 `json:"elasticsearch,omitempty"`
	// fluentd contains tbd
	Fluentd *AVEndpointType1 `json:"fluentd,omitempty"`
	// grafana contains tbd
	Grafana *AVEndpointType1 `json:"grafana,omitempty"`
	// identity contains tbd
	Identity *AVEndpointType1 `json:"identity,omitempty"`
	// image contains tbd
	Image *AVEndpointType1 `json:"image,omitempty"`
	// image_registry contains tbd
	ImageRegistry *AVEndpointType1 `json:"image_registry,omitempty"`
	// key_manager contains tbd
	KeyManager *AVEndpointType1 `json:"key_manager,omitempty"`
	// kibana contains tbd
	Kibana *AVEndpointType1 `json:"kibana,omitempty"`
	// kube_controller_manager contains tbd
	KubeControllerManager *AVEndpointType1 `json:"kube_controller_manager,omitempty"`
	// kubernetesprovisioner contains tbd
	Kubernetesprovisioner *AVEndpointType1 `json:"kubernetesprovisioner,omitempty"`
	// kube_scheduler contains tbd
	KubeScheduler *AVEndpointType1 `json:"kube_scheduler,omitempty"`
	// kube_state_metrics contains tbd
	KubeStateMetrics *AVEndpointType1 `json:"kube_state_metrics,omitempty"`
	// ldap contains tbd
	Ldap *AVEndpointType1 `json:"ldap,omitempty"`
	// maas_region_ui contains tbd
	MaasRegionUi *AVEndpointType1 `json:"maas_region_ui,omitempty"`
	// monitoring contains tbd
	Monitoring *AVEndpointType1 `json:"monitoring,omitempty"`
	// nagios contains tbd
	Nagios *AVEndpointType1 `json:"nagios,omitempty"`
	// network contains tbd
	Network *AVEndpointType1 `json:"network,omitempty"`
	// node_metrics contains tbd
	NodeMetrics *AVEndpointType1 `json:"node_metrics,omitempty"`
	// object_store contains tbd
	ObjectStore *AVEndpointType1 `json:"object_store,omitempty"`
	// orchestration contains tbd
	Orchestration *AVEndpointType1 `json:"orchestration,omitempty"`
	// physicalprovisioner contains tbd
	Physicalprovisioner *AVEndpointType1 `json:"physicalprovisioner,omitempty"`
	// placement contains tbd
	Placement *AVEndpointType1 `json:"placement,omitempty"`
	// process_exporter_metrics contains tbd
	ProcessExporterMetrics *AVEndpointType1 `json:"process_exporter_metrics,omitempty"`
	// prometheus_elasticsearch_exporter contains tbd
	PrometheusElasticsearchExporter *AVEndpointType1 `json:"prometheus_elasticsearch_exporter,omitempty"`
	// prometheus_fluentd_exporter contains tbd
	PrometheusFluentdExporter *AVEndpointType1 `json:"prometheus_fluentd_exporter,omitempty"`
	// prometheus_mysql_exporter contains tbd
	PrometheusMysqlExporter *AVEndpointType1 `json:"prometheus_mysql_exporter,omitempty"`
	// prometheus_openstack_exporter contains tbd
	PrometheusOpenstackExporter *AVEndpointType1 `json:"prometheus_openstack_exporter,omitempty"`
	// prometheus_rabbitmq_exporter contains tbd
	PrometheusRabbitmqExporter *AVEndpointType1 `json:"prometheus_rabbitmq_exporter,omitempty"`
	// shipyard contains tbd
	Shipyard *AVEndpointType1 `json:"shipyard,omitempty"`
	// volume contains tbd
	Volume *AVEndpointType1 `json:"volume,omitempty"`
	// volumev2 contains tbd
	Volumev2 *AVEndpointType1 `json:"volumev2,omitempty"`
	// volumev3 contains tbd
	Volumev3 *AVEndpointType1 `json:"volumev3,omitempty"`

	// maas_db contains tbd
	MaasDb *AVEndpointType2 `json:"maas_db,omitempty"`
	// oslo_db_api contains tbd
	OsloDbApi *AVEndpointType2 `json:"oslo_db_api,omitempty"`
	// oslo_db_cell0 contains tbd
	OsloDbCell0 *AVEndpointType2 `json:"oslo_db_cell0,omitempty"`
	// oslo_db contains tbd
	OsloDb *AVEndpointType2 `json:"oslo_db,omitempty"`
	// oslo_db_session contains tbd
	OsloDbSession *AVEndpointType2 `json:"oslo_db_session,omitempty"`
	// oslo_messaging contains tbd
	OsloMessaging *AVEndpointType2 `json:"oslo_messaging,omitempty"`
	// postgresql_airflow_celery_db contains tbd
	PostgresqlAirflowCeleryDb *AVEndpointType2 `json:"postgresql_airflow_celery_db,omitempty"`
	// postgresql_airflow_db contains tbd
	PostgresqlAirflowDb *AVEndpointType2 `json:"postgresql_airflow_db,omitempty"`
	// postgresql contains tbd
	Postgresql *AVEndpointType2 `json:"postgresql,omitempty"`
	// postgresql_shipyard_db contains tbd
	PostgresqlShipyardDb *AVEndpointType2 `json:"postgresql_shipyard_db,omitempty"`
}

type AVEndpointType1 struct {
	// auth contains tbd
	Auth *map[string]AVEndpointAuth `json:"auth,omitempty"`
	// host_fqdn_override contains tbd
	HostFqdnOverride *AVDefaultPublic `json:"host_fqdn_override,omitempty"`
	// hosts contains tbd
	Hosts *AVDefaultPublic `json:"hosts,omitempty"`
	// name contains tbd
	Name string `json:"name,omitempty"`
	// namespace contains tbd
	Namespace string `json:"namespace,omitempty"`
	// path contains tbd
	Path *AVDefaultPublic `json:"path,omitempty"`
	// port contains tbd
	Port *map[string]AVEndpointPort `json:"port,omitempty"`
	// scheme contains tbd
	Scheme *AVDefaultPublic `json:"scheme,omitempty"`
	// type contains tbd
	Type string `json:"type,omitempty"`
}

type AVEndpointType2 struct {
	// auth contains tbd
	Auth *map[string]AVEndpointAuth `json:"auth,omitempty"`
	// host_fqdn_override contains tbd
	HostFqdnOverride *AVDefaultPublic `json:"host_fqdn_override,omitempty"`
	// hosts contains tbd
	Hosts *AVDefaultPublic `json:"hosts,omitempty"`
	// name contains tbd
	Name string `json:"name,omitempty"`
	// namespace contains tbd
	Namespace string `json:"namespace,omitempty"`
	// path contains tbd
	Path string `json:"path,omitempty"`
	// port contains tbd
	Port *map[string]AVEndpointPort `json:"port,omitempty"`
	// scheme contains tbd
	Scheme string `json:"scheme,omitempty"`
	// type contains tbd
	Type string `json:"type,omitempty"`
}

type AVEndpointAuth struct {
	// access_key contains tbd
	AccessKey string `json:"access_key,omitempty"`
	// bind contains tbd
	Bind string `json:"bind,omitempty"`
	// bind_dn contains tbd
	BindDn string `json:"bind_dn,omitempty"`
	// database contains tbd
	Database string `json:"database,omitempty"`
	// domain_name contains tbd
	DomainName string `json:"domain_name,omitempty"`
	// email contains tbd
	Email string `json:"email,omitempty"`
	// password contains tbd
	Password string `json:"password,omitempty"`
	// project_domain_name contains tbd
	ProjectDomainName string `json:"project_domain_name,omitempty"`
	// project_name contains tbd
	ProjectName string `json:"project_name,omitempty"`
	// region_name contains tbd
	RegionName string `json:"region_name,omitempty"`
	// role contains tbd
	Role *string `json:"role,omitempty"`
	// secret_key contains tbd
	SecretKey string `json:"secret_key,omitempty"`
	// tls contains tbd
	Tls *AVTls `json:"tls,omitempty"`
	// tmpurlkey contains tbd
	Tmpurlkey string `json:"tmpurlkey,omitempty"`
	// user_domain_name contains tbd
	UserDomainName string `json:"user_domain_name,omitempty"`
	// username contains tbd
	Username string `json:"username,omitempty"`
}

type AVEndpointPort struct {
	// default contains tbd
	Default int `json:"default,omitempty"`
	// internal contains tbd
	Internal int `json:"internal,omitempty"`
	// nodeport contains tbd
	Nodeport int `json:"nodeport,omitempty"`
	// public contains tbd
	Public int `json:"public,omitempty"`
}

type AVTls struct {
	// ca contains tbd
	Ca string `json:"ca,omitempty"`
	// crt contains tbd
	Crt string `json:"crt,omitempty"`
	// key contains tbd
	Key string `json:"key,omitempty"`
	// client contains tbd
	Client *AVTlsCa `json:"client,omitempty"`
	// peer contains tbd
	Peer *AVTlsCa `json:"peer,omitempty"`
}

type AVTlsCa struct {
	// ca contains tbd
	Ca string `json:"ca,omitempty"`
}

type AVDefaultPublic struct {
	// default contains tbd
	Default string `json:"default,omitempty"`
	// discovery contains tbd
	Discovery string `json:"discovery,omitempty"`
	// public contains tbd
	Public string `json:"public,omitempty"`
}

type AVSecretAnchor struct {
	// tls contains tbd
	Tls *AVTls `json:"tls,omitempty"`
}

type AVSecretMaasRegion struct {
	// value contains tbd
	Value string `json:"value,omitempty"`
}

type AVSecretKeyrings struct {
	// admin contains tbd
	Admin string `json:"admin,omitempty"`
}

type AVSecretServiceAccount struct {
	// private_key contains tbd
	PrivateKey string `json:"private_key,omitempty"`
	// public contains tbd
	PublicKey string `json:"public_key,omitempty"`
}

type AVSecretEtcd struct {
	// tls contains tbd
	Tls *AVTls `json:"tls,omitempty"`
}
