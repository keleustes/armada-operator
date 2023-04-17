
# Image URL to use all building/pushing image targets
COMPONENT        ?= armada-operator
VERSION          ?= 1.27.1
DHUBREPO         ?= keleustes/${COMPONENT}-dev
DOCKER_NAMESPACE ?= keleustes
IMG              ?= ${DHUBREPO}:v${VERSION}

all: docker-build

setup:
	echo $(GOPATH)
# ifndef GOPATH
#	$(error GOPATH not defined, please define GOPATH. Run "go help gopath" to learn more about GOPATH)
#endif

.PHONY: clean
clean:
	rm -fr vendor
	rm -fr cover.out
	rm -fr build/_output
	rm -fr config/crds

.PHONY: install-tools
install-tools:
	cd /tmp && GO111MODULE=on go get sigs.k8s.io/kind@v0.5.0
	cd /tmp && GO111MODULE=on go get github.com/instrumenta/kubeval@0.13.0

# clusterexist=$(shell kind get clusters | grep armada  | wc -l)
# ifeq ($(clusterexist), 1)
#   testcluster=$(shell kind get kubeconfig-path --name="armada")
#   SETKUBECONFIG=KUBECONFIG=$(testcluster)
# else
#   SETKUBECONFIG=
# endif

.PHONY: which-cluster
which-cluster:
	echo $(SETKUBECONFIG)

.PHONY: create-testcluster
create-testcluster:
	kind create cluster --name armada

.PHONY: delete-testcluster
delete-testcluster:
	kind delete cluster --name armada


# Run tests
unittest: setup fmt vet
	echo "sudo systemctl stop kubelet"
	echo -e 'docker stop $$(docker ps -qa)'
	echo -e 'export PATH=$${PATH}:/usr/local/kubebuilder/bin'
	mkdir -p config/crds
	cp chart/templates/*v1alpha1* config/crds/
	GO111MODULE=on go test ./pkg/... ./cmd/... -coverprofile cover.out

# Run go fmt against code
fmt: setup
	GO111MODULE=on go fmt ./pkg/... ./cmd/...

# Run go vet against code
vet: fmt
	GO111MODULE=on go vet -composites=false ./pkg/... ./cmd/...

# Generate code. Moved to armada-crd
# generate: setup
#         # git clone sigs.k8s.io/controller-tools
#         # go install ./cmd/...
# 	GO111MODULE=on controller-gen crd paths=./pkg/apis/armada/... crd:trivialVersions=true output:crd:dir=./chart/templates/ output:none
# 	GO111MODULE=on controller-gen object paths=./pkg/apis/armada/... output:object:dir=./pkg/apis/armada/v1alpha1 output:none
#	cp ../armada-crd/kubectl/*.yaml chart/templates/

# Build the docker image
docker-build: fmt docker-build-vx

docker-build-vx:
	GO111MODULE=on GOOS=linux GOARCH=amd64 CGO_ENABLED=0 go build -o build/_output/bin/armada-operator -gcflags all=-trimpath=${GOPATH} -asmflags all=-trimpath=${GOPATH} ./cmd/...
	docker build . -f build/Dockerfile -t ${IMG}
	docker tag ${IMG} ${DHUBREPO}:latest

# Push the docker image
docker-push: docker-push-vx

docker-push-vx:
	docker push ${IMG}

# Run against the configured Kubernetes cluster in ~/.kube/config
install: install-v2

purge: setup
	kubectl delete act --all
	kubectl delete acg --all
	kubectl delete amf --all
	helm delete --purge armada-operator

installlabels:
	kubectl label nodes --all control-plane=enabled --overwrite
	kubectl label nodes --all openstack-control-plane=enabled --overwrite
	kubectl label nodes --all ucp-control-plane=enabled --overwrite

install-v2: docker-build-v2 installlabels
	helm install --name armada-operator chart --set images.tags.operator=${IMG_V2}

install-v3: docker-build-v3 installlabels
	helm install --name armada-operator chart --set images.tags.operator=${IMG_V3}

# Deploy and purge procedure which do not rely on helm itself
install-kubectl: setup installlabels
	kubectl apply -f ./chart/templates/armada.airshipit.org_armadachartgroups.yaml
	kubectl apply -f ./chart/templates/armada.airshipit.org_armadacharts.yaml
	kubectl apply -f ./chart/templates/armada.airshipit.org_armadamanifests.yaml
	kubectl apply -f ./chart/templates/role_binding.yaml
	kubectl apply -f ./chart/templates/role.yaml
	kubectl apply -f ./chart/templates/service_account.yaml
	kubectl apply -f ./chart/templates/argo_armada_role.yaml
	kubectl apply -f ./deploy/operator.yaml

purge-kubectl: setup
	kubectl delete -f ./deploy/operator.yaml --ignore-not-found=true
	kubectl delete -f ./chart/templates/role_binding.yaml --ignore-not-found=true
	kubectl delete -f ./chart/templates/role.yaml --ignore-not-found=true
	kubectl delete -f ./chart/templates/service_account.yaml --ignore-not-found=true
	kubectl delete -f ./chart/templates/argo_armada_role.yaml --ignore-not-found=true
	kubectl delete -f ./chart/templates/armada.airshipit.org_armadachartgroups.yaml --ignore-not-found=true
	kubectl delete -f ./chart/templates/armada.airshipit.org_armadacharts.yaml --ignore-not-found=true
	kubectl delete -f ./chart/templates/armada.airshipit.org_armadamanifests.yaml --ignore-not-found=true

getcrds:
	kubectl get armadacharts.armada.airshipit.org
	kubectl get armadachartgroups.armada.airshipit.org
	kubectl get armadamanifests.armada.airshipit.org
	kubectl get workflows.argoproj.io

deploy-patch:
	kubectl patch act blog-1 --type merge -p $'spec:\n  target_state: deployed'

.PHONY: kubeval-simple
kubeval-simple:
	@for f in $(shell ls ./examples/armada/* ./examples/gittest/* ./examples/sequenced/* ./examples/stepbystep/* ./examples/tartest/*); do \
		kubeval $${f} --schema-location file://$${HOME}/src/github.com/keleustes/armada-crd/kubeval --strict; \
	done || true

.PHONY: kubeval-argo
kubeval-argo:
	@for f in $(shell ls ./examples/argo/* | grep -v group); do \
		kubeval $${f} --schema-location file://$${HOME}/src/github.com/keleustes/armada-crd/kubeval --strict; \
	done || true

.PHONY: kubeval-keystone
kubeval-keystone:
	@for f in $(shell ls ./examples/keystone/git/* ./examples/keystone/local/* ./examples/keystone/sequenced/*); do \
		kubeval $${f} --schema-location file://$${HOME}/src/github.com/keleustes/armada-crd/kubeval --strict; \
	done || true
	@for f in $(shell ls ./examples/keystone/argo/* | grep -v workflow); do \
		kubeval $${f} --schema-location file://$${HOME}/src/github.com/keleustes/armada-crd/kubeval --strict; \
	done || true

.PHONY: kubeval-checks
kubeval-checks: kubeval-simple kubeval-argo kubeval-keystone
