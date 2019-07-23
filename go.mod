module github.com/keleustes/armada-operator

go 1.12

require (
	github.com/DATA-DOG/go-sqlmock v1.3.3 // indirect
	github.com/Masterminds/goutils v1.1.0 // indirect
	github.com/Masterminds/semver v1.4.2 // indirect
	github.com/Masterminds/sprig v2.20.0+incompatible // indirect
	github.com/ghodss/yaml v0.0.0-20180820084758-c7ce16629ff4
	github.com/gobuffalo/packr v1.30.1 // indirect
	github.com/gobwas/glob v0.2.3 // indirect
	github.com/gogo/protobuf v1.2.1 // indirect
	github.com/golang/groupcache v0.0.0-20190129154638-5b532d6fd5ef // indirect
	github.com/google/uuid v1.1.0 // indirect
	github.com/huandu/xstrings v1.2.0 // indirect
	github.com/imdario/mergo v0.3.7 // indirect
	github.com/jmoiron/sqlx v1.2.0 // indirect
	github.com/lib/pq v1.2.0 // indirect
	github.com/mattbaird/jsonpatch v0.0.0-20171005235357-81af80346b1a
	github.com/onsi/ginkgo v1.7.0 // indirect
	github.com/onsi/gomega v1.4.3
	github.com/prometheus/client_model v0.0.0-20190129233127-fd36f4220a90 // indirect
	github.com/prometheus/common v0.2.0 // indirect
	github.com/prometheus/procfs v0.0.0-20190219184716-e4d4a2206da0 // indirect
	github.com/rubenv/sql-migrate v0.0.0-20190717103323-87ce952f7079 // indirect
	github.com/technosophos/moniker v0.0.0-20180509230615-a5dbd03a2245 // indirect
	github.com/xeipuuv/gojsonpointer v0.0.0-20180127040702-4e3ac2762d5f // indirect
	github.com/xeipuuv/gojsonreference v0.0.0-20180127040603-bd5ef7bd5415 // indirect
	github.com/xeipuuv/gojsonschema v1.1.0 // indirect
	github.com/ziutek/mymysql v1.5.4 // indirect
	golang.org/x/crypto v0.0.0-20190621222207-cc06ce4a13d4
	golang.org/x/net v0.0.0-20190502183928-7f726cade0ab
	golang.org/x/time v0.0.0-20181108054448-85acf8d2951c // indirect
	gopkg.in/gorp.v1 v1.7.2 // indirect
	gopkg.in/src-d/go-git.v4 v4.12.0
	gopkg.in/yaml.v2 v2.2.2
	helm.sh/helm v3.0.0-alpha.2+incompatible
	k8s.io/api v0.0.0
	k8s.io/apimachinery v0.0.0
	k8s.io/cli-runtime v0.0.0
	k8s.io/client-go v11.0.1-0.20190409021438-1a26190bd76a+incompatible
	k8s.io/kubernetes v1.15.1 // indirect
	sigs.k8s.io/controller-runtime v0.2.0-beta.3
)

replace k8s.io/api => k8s.io/api v0.0.0-20190718183219-b59d8169aab5

replace k8s.io/apiextensions-apiserver => k8s.io/apiextensions-apiserver v0.0.0-20190718185103-d1ef975d28ce

replace k8s.io/apimachinery => k8s.io/apimachinery v0.0.0-20190612205821-1799e75a0719

replace k8s.io/apiserver => k8s.io/apiserver v0.0.0-20190718184206-a1aa83af71a7

replace k8s.io/cli-runtime => k8s.io/cli-runtime v0.0.0-20190718185405-0ce9869d0015

replace k8s.io/client-go => k8s.io/client-go v0.0.0-20190718183610-8e956561bbf5

replace k8s.io/cloud-provider => k8s.io/cloud-provider v0.0.0-20190718190308-f8e43aa19282

replace k8s.io/cluster-bootstrap => k8s.io/cluster-bootstrap v0.0.0-20190718190146-f7b0473036f9

replace k8s.io/code-generator => k8s.io/code-generator v0.0.0-20190612205613-18da4a14b22b

replace k8s.io/component-base => k8s.io/component-base v0.0.0-20190718183727-0ececfbe9772

replace k8s.io/cri-api => k8s.io/cri-api v0.0.0-20190531030430-6117653b35f1

replace k8s.io/csi-translation-lib => k8s.io/csi-translation-lib v0.0.0-20190718190424-bef8d46b95de

replace k8s.io/kube-aggregator => k8s.io/kube-aggregator v0.0.0-20190718184434-a064d4d1ed7a

replace k8s.io/kube-controller-manager => k8s.io/kube-controller-manager v0.0.0-20190718190030-ea930fedc880

replace k8s.io/kube-proxy => k8s.io/kube-proxy v0.0.0-20190718185641-5233cb7cb41e

replace k8s.io/kube-scheduler => k8s.io/kube-scheduler v0.0.0-20190718185913-d5429d807831

replace k8s.io/kubelet => k8s.io/kubelet v0.0.0-20190718185757-9b45f80d5747

replace k8s.io/legacy-cloud-providers => k8s.io/legacy-cloud-providers v0.0.0-20190718190548-039b99e58dbd

replace k8s.io/metrics => k8s.io/metrics v0.0.0-20190718185242-1e1642704fe6

replace k8s.io/sample-apiserver => k8s.io/sample-apiserver v0.0.0-20190718184639-baafa86838c0
