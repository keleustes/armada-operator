module github.com/keleustes/armada-operator

go 1.12

require (
	github.com/Azure/go-ansiterm v0.0.0-20170929234023-d6e3b3328b78
	github.com/BurntSushi/toml v0.3.1
	github.com/MakeNowJust/heredoc v0.0.0-20171113091838-e9091a26100e
	github.com/Masterminds/goutils v1.1.0
	github.com/Masterminds/semver v1.4.2
	github.com/Masterminds/sprig v0.0.0-20190301161902-9f8fceff796f
	github.com/PuerkitoBio/purell v1.1.1
	github.com/PuerkitoBio/urlesc v0.0.0-20170810143723-de5bf2ad4578
	github.com/appscode/jsonpatch v0.0.0-20190108182946-7c0e3b262f30
	github.com/beorn7/perks v0.0.0-20180321164747-3a771d992973
	github.com/chai2010/gettext-go v0.0.0-20170215093142-bf70f2a70fb1
	github.com/coreos/prometheus-operator v0.26.0
	github.com/cyphar/filepath-securejoin v0.2.2
	github.com/davecgh/go-spew v1.1.1
	github.com/docker/distribution v0.0.0-20170726174610-edc3ab29cdff
	github.com/docker/docker v0.0.0-20180612054059-a9fbbdc8dd87
	github.com/docker/spdystream v0.0.0-20181023171402-6480d4af844c
	github.com/emicklei/go-restful v2.9.0+incompatible
	github.com/emirpasic/gods v1.12.0
	github.com/evanphx/json-patch v4.1.0+incompatible
	github.com/exponent-io/jsonpath v0.0.0-20151013193312-d6023ce2651d
	github.com/ghodss/yaml v1.0.0
	github.com/go-logr/logr v0.1.0
	github.com/go-logr/zapr v0.1.0
	github.com/go-openapi/jsonpointer v0.18.0
	github.com/go-openapi/jsonreference v0.18.0
	github.com/go-openapi/spec v0.19.0
	github.com/go-openapi/swag v0.18.0
	github.com/gobuffalo/envy v1.6.15
	github.com/gobwas/glob v0.2.3
	github.com/gogo/protobuf v1.2.1
	github.com/golang/glog v0.0.0-20160126235308-23def4e6c14b
	github.com/golang/groupcache v0.0.0-20190129154638-5b532d6fd5ef
	github.com/golang/protobuf v1.2.0
	github.com/google/btree v1.0.0
	github.com/google/gofuzz v0.0.0-20170612174753-24818f796faf
	github.com/google/uuid v1.1.0
	github.com/googleapis/gnostic v0.2.0
	github.com/gregjones/httpcache v0.0.0-20190212212710-3befbb6ad0cc
	github.com/grpc-ecosystem/go-grpc-prometheus v1.2.0
	github.com/hashicorp/golang-lru v0.5.0
	github.com/hpcloud/tail v1.0.0
	github.com/huandu/xstrings v1.2.0
	github.com/imdario/mergo v0.3.7
	github.com/inconshreveable/mousetrap v1.0.0
	github.com/jbenet/go-context v0.0.0-20150711004518-d14ea06fba99
	github.com/joho/godotenv v1.3.0
	github.com/json-iterator/go v1.1.5
	github.com/kevinburke/ssh_config v0.0.0-20180830205328-81db2a75821e
	github.com/konsorten/go-windows-terminal-sequences v1.0.2
	github.com/mailru/easyjson v0.0.0-20190221075403-6243d8e04c3f
	github.com/markbates/inflect v1.0.4
	github.com/mattbaird/jsonpatch v0.0.0-20171005235357-81af80346b1a
	github.com/matttproud/golang_protobuf_extensions v1.0.1
	github.com/mitchellh/go-homedir v1.1.0
	github.com/mitchellh/go-wordwrap v1.0.0
	github.com/modern-go/concurrent v0.0.0-20180306012644-bacd9c7ef1dd
	github.com/modern-go/reflect2 v0.0.0-20180701023420-4b7aa43c6742
	github.com/onsi/ginkgo v1.7.0
	github.com/onsi/gomega v1.4.3
	github.com/opencontainers/go-digest v1.0.0-rc1
	github.com/operator-framework/operator-sdk v0.0.0-20190221194702-a882a84f8520
	github.com/pborman/uuid v0.0.0-20180906182336-adf5a7427709
	github.com/pelletier/go-buffruneio v0.2.0
	github.com/petar/GoLLRB v0.0.0-20130427215148-53be0d36a84c
	github.com/peterbourgon/diskv v2.0.1+incompatible
	github.com/pkg/errors v0.8.1
	github.com/prometheus/client_golang v0.9.2
	github.com/prometheus/client_model v0.0.0-20190129233127-fd36f4220a90
	github.com/prometheus/common v0.2.0
	github.com/prometheus/procfs v0.0.0-20190219184716-e4d4a2206da0
	github.com/rogpeppe/go-internal v1.2.2
	github.com/russross/blackfriday v0.0.0-20151117072312-300106c228d5
	github.com/sergi/go-diff v1.0.0
	github.com/shurcooL/sanitized_anchor_name v1.0.0
	github.com/sirupsen/logrus v1.4.0
	github.com/spf13/afero v1.2.1
	github.com/spf13/cobra v0.0.3
	github.com/spf13/pflag v1.0.3
	github.com/src-d/gcfg v1.4.0
	github.com/technosophos/moniker v0.0.0-20180509230615-a5dbd03a2245
	github.com/xanzy/ssh-agent v0.2.1
	go.uber.org/atomic v1.3.2
	go.uber.org/multierr v1.1.0
	go.uber.org/zap v1.9.1
	golang.org/x/crypto v0.0.0-20190219172222-a4c6cb3142f2
	golang.org/x/net v0.0.0-20190213061140-3a22650c66bd
	golang.org/x/oauth2 v0.0.0-20190220154721-9b3c75971fc9
	golang.org/x/sync v0.0.0-20190227155943-e225da77a7e6
	golang.org/x/sys v0.0.0-20190221075227-b4e8571b14e0
	golang.org/x/text v0.3.0
	golang.org/x/time v0.0.0-20181108054448-85acf8d2951c
	golang.org/x/tools v0.0.0-20190226205152-f727befe758c
	google.golang.org/appengine v1.4.0
	google.golang.org/genproto v0.0.0-20190307195333-5fe7a883aa19
	google.golang.org/grpc v1.19.0
	gopkg.in/fsnotify.v1 v1.4.7
	gopkg.in/inf.v0 v0.9.1
	gopkg.in/square/go-jose.v2 v2.3.0
	gopkg.in/src-d/go-billy.v4 v4.3.0
	gopkg.in/src-d/go-git.v4 v4.11.0
	gopkg.in/tomb.v1 v1.0.0-20141024135613-dd632973f1e7
	gopkg.in/warnings.v0 v0.1.2
	gopkg.in/yaml.v2 v2.2.2
	k8s.io/api v0.0.0-20190222213804-5cb15d344471
	k8s.io/apiextensions-apiserver v0.0.0-20190228180357-d002e88f6236
	k8s.io/apimachinery v0.0.0-20190221213512-86fb29eff628
	k8s.io/apiserver v0.0.0-20190228174905-79427f02047f
	k8s.io/cli-runtime v0.0.0-20190228180923-a9e421a79326
	k8s.io/client-go v0.0.0-20190228174230-b40b2a5939e4
	k8s.io/code-generator v0.0.0-20180823001027-3dcf91f64f63
	k8s.io/gengo v0.0.0-20190128074634-0689ccc1d7d6
	k8s.io/helm v2.13.0+incompatible
	k8s.io/klog v0.2.0
	k8s.io/kube-openapi v0.0.0-20180711000925-0cf8f7e6ed1d
	k8s.io/kubernetes v1.13.4
	k8s.io/utils v0.0.0-20190308190857-21c4ce38f2a7
	sigs.k8s.io/controller-runtime v0.1.10
	sigs.k8s.io/controller-tools v0.1.9
	sigs.k8s.io/testing_frameworks v0.1.1
	sigs.k8s.io/yaml v1.1.0
	vbom.ml/util v0.0.0-20180919145318-efcd4e0f9787
)
