
# Image URL to use all building/pushing image targets
COMPONENT        ?= armada-operator
VERSION_V2       ?= 2.14.1
VERSION_V3       ?= 3.0.0
DHUBREPO         ?= keleustes/${COMPONENT}-dev
DOCKER_NAMESPACE ?= keleustes
IMG_V2           ?= ${DHUBREPO}:v${VERSION_V2}
IMG_V3           ?= ${DHUBREPO}:v${VERSION_V3}

all: docker-build

setup:
ifndef GOPATH
	$(error GOPATH not defined, please define GOPATH. Run "go help gopath" to learn more about GOPATH)
endif

clean:
	rm -fr vendor
	rm -fr cover.out
	rm -fr build/_output
	rm -fr config/crds

# Run tests
unittest: setup fmt vet-v3
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
vet-v2: fmt
	GO111MODULE=on go vet -composites=false -tags=v2 ./pkg/... ./cmd/...

vet-v3: fmt
	GO111MODULE=on go vet -composites=false -tags=v3 ./pkg/... ./cmd/...

# Generate code
generate: setup
        # git clone sigs.k8s.io/controller-tools
        # go install ./cmd/...
	GO111MODULE=on controller-gen crd paths=./pkg/apis/armada/... crd:trivialVersions=true output:crd:dir=./chart/templates/ output:none
	GO111MODULE=on controller-gen object paths=./pkg/apis/armada/... output:object:dir=./pkg/apis/armada/v1alpha1 output:none

# Build the docker image
docker-build: fmt docker-build-v3

docker-build-v2:
	GO111MODULE=on GOOS=linux GOARCH=amd64 CGO_ENABLED=0 go build -o build/_output/bin/armada-operator -gcflags all=-trimpath=${GOPATH} -asmflags all=-trimpath=${GOPATH} -tags=v2 ./cmd/...
	docker build . -f build/Dockerfile -t ${IMG_V2}
	docker tag ${IMG_V2} ${DHUBREPO}:latest

docker-build-v3: 
	GO111MODULE=on GOOS=linux GOARCH=amd64 CGO_ENABLED=0 go build -o build/_output/bin/armada-operator -gcflags all=-trimpath=${GOPATH} -asmflags all=-trimpath=${GOPATH} -tags=v3 ./cmd/...
	docker build . -f build/Dockerfile -t ${IMG_V3}
	docker tag ${IMG_V3} ${DHUBREPO}:latest


# Push the docker image
docker-push: docker-push-v3

docker-push-v2:
	docker push ${IMG_V2}

docker-push-v3:
	docker push ${IMG_V3}

# Run against the configured Kubernetes cluster in ~/.kube/config
install: install-v3

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
