module github.com/keleustes/armada-operator

go 1.12

require (
	github.com/DATA-DOG/go-sqlmock v1.3.3 // indirect
	github.com/MakeNowJust/heredoc v0.0.0-20171113091838-e9091a26100e // indirect
	github.com/Masterminds/goutils v1.1.0 // indirect
	github.com/Masterminds/semver v1.4.2 // indirect
	github.com/Masterminds/sprig v0.0.0-20190301161902-9f8fceff796f // indirect
	github.com/chai2010/gettext-go v0.0.0-20170215093142-bf70f2a70fb1 // indirect
	github.com/docker/spdystream v0.0.0-20181023171402-6480d4af844c // indirect
	github.com/emirpasic/gods v1.12.0 // indirect
	github.com/gobuffalo/packr v1.30.1 // indirect
	github.com/gobwas/glob v0.2.3 // indirect
	github.com/golang/groupcache v0.0.0-20190129154638-5b532d6fd5ef // indirect
	github.com/google/btree v1.0.0 // indirect
	github.com/gregjones/httpcache v0.0.0-20190212212710-3befbb6ad0cc // indirect
	github.com/huandu/xstrings v1.2.0 // indirect
	github.com/jmoiron/sqlx v1.2.0 // indirect
	github.com/keleustes/armada-crd v0.3.0
	github.com/lib/pq v1.1.1 // indirect
	github.com/mattbaird/jsonpatch v0.0.0-20171005235357-81af80346b1a
	github.com/onsi/gomega v1.7.0
	github.com/rubenv/sql-migrate v0.0.0-20190618074426-f4d34eae5a5c // indirect
	github.com/technosophos/moniker v0.0.0-20180509230615-a5dbd03a2245 // indirect
	github.com/xanzy/ssh-agent v0.2.1 // indirect
	github.com/ziutek/mymysql v1.5.4 // indirect
	golang.org/x/crypto v0.0.0-20190829043050-9756ffdc2472
	golang.org/x/net v0.0.0-20190827160401-ba9fcec4b297
	gopkg.in/gorp.v1 v1.7.2 // indirect
	gopkg.in/square/go-jose.v2 v2.3.0 // indirect
	gopkg.in/src-d/go-billy.v4 v4.3.0 // indirect
	gopkg.in/src-d/go-git.v4 v4.11.0
	gopkg.in/yaml.v2 v2.2.2
	k8s.io/api v0.0.0
	k8s.io/apimachinery v0.0.0
	k8s.io/cli-runtime v0.0.0
	k8s.io/client-go v11.0.1-0.20190409021438-1a26190bd76a+incompatible
	k8s.io/helm v2.14.3+incompatible
	k8s.io/kubernetes v1.16.0 // indirect
	sigs.k8s.io/controller-runtime v0.2.2
	sigs.k8s.io/yaml v1.1.0
	vbom.ml/util v0.0.0-20180919145318-efcd4e0f9787 // indirect
)

replace (
	k8s.io/api => k8s.io/api v0.0.0-20190918155943-95b840bb6a1f
	k8s.io/apiextensions-apiserver => k8s.io/apiextensions-apiserver v0.0.0-20190918161926-8f644eb6e783
	k8s.io/apimachinery => k8s.io/apimachinery v0.0.0-20190913080033-27d36303b655
	k8s.io/apiserver => k8s.io/apiserver v0.0.0-20190918160949-bfa5e2e684ad
	k8s.io/cli-runtime => k8s.io/cli-runtime v0.0.0-20190918162238-f783a3654da8
	k8s.io/client-go => k8s.io/client-go v0.0.0-20190918160344-1fbdaa4c8d90
	k8s.io/cloud-provider => k8s.io/cloud-provider v0.0.0-20190918163234-a9c1f33e9fb9
	k8s.io/cluster-bootstrap => k8s.io/cluster-bootstrap v0.0.0-20190918163108-da9fdfce26bb
	k8s.io/code-generator => k8s.io/code-generator v0.0.0-20190912054826-cd179ad6a269
	k8s.io/component-base => k8s.io/component-base v0.0.0-20190918160511-547f6c5d7090
	k8s.io/cri-api => k8s.io/cri-api v0.0.0-20190828162817-608eb1dad4ac
	k8s.io/csi-translation-lib => k8s.io/csi-translation-lib v0.0.0-20190918163402-db86a8c7bb21

	k8s.io/helm => github.com/keleustes/helm v2.10.0-rc.2.0.20190925055845-e5261361168d+incompatible
	k8s.io/kube-aggregator => k8s.io/kube-aggregator v0.0.0-20190918161219-8c8f079fddc3
	k8s.io/kube-controller-manager => k8s.io/kube-controller-manager v0.0.0-20190918162944-7a93a0ddadd8
	k8s.io/kube-proxy => k8s.io/kube-proxy v0.0.0-20190918162534-de037b596c1e
	k8s.io/kube-scheduler => k8s.io/kube-scheduler v0.0.0-20190918162820-3b5c1246eb18
	k8s.io/kubectl => k8s.io/kubectl v0.0.0-20190918164019-21692a0861df
	k8s.io/kubelet => k8s.io/kubelet v0.0.0-20190918162654-250a1838aa2c
	k8s.io/legacy-cloud-providers => k8s.io/legacy-cloud-providers v0.0.0-20190918163543-cfa506e53441
	k8s.io/metrics => k8s.io/metrics v0.0.0-20190918162108-227c654b2546
	k8s.io/sample-apiserver => k8s.io/sample-apiserver v0.0.0-20190918161442-d4c9c65c82af
	sigs.k8s.io/controller-runtime v0.2.2 => github.com/keleustes/controller-runtime v0.2.0-beta.1.0.20190925063420-587bc6ca5913
)
