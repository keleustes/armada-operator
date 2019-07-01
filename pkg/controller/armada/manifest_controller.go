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

package armada

import (
	"context"
	"fmt"

	av1 "github.com/keleustes/armada-operator/pkg/apis/armada/v1alpha1"
	armadamgr "github.com/keleustes/armada-operator/pkg/armada"
	armadaif "github.com/keleustes/armada-operator/pkg/services"

	corev1 "k8s.io/api/core/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/types"

	"sigs.k8s.io/controller-runtime/pkg/controller"
	"sigs.k8s.io/controller-runtime/pkg/controller/controllerutil"
	crthandler "sigs.k8s.io/controller-runtime/pkg/handler"
	"sigs.k8s.io/controller-runtime/pkg/manager"
	"sigs.k8s.io/controller-runtime/pkg/reconcile"
	logf "sigs.k8s.io/controller-runtime/pkg/runtime/log"
	"sigs.k8s.io/controller-runtime/pkg/source"
)

var amflog = logf.Log.WithName("amf-controller")

// AddArmadaManifestController creates a new ArmadaManifest Controller and
// adds it to the Manager. The Manager will set fields on the Controller and
// Start it when the Manager is Started.
func AddArmadaManifestController(mgr manager.Manager) error {

	r := &ManifestReconciler{
		BaseReconciler: BaseReconciler{
			client:   mgr.GetClient(),
			scheme:   mgr.GetScheme(),
			recorder: mgr.GetEventRecorderFor("amf-recorder"),
		},
		managerFactory: armadamgr.NewManagerFactory(mgr),
	}

	// Create a new controller
	c, err := controller.New("amf-controller", mgr, controller.Options{Reconciler: r})
	if err != nil {
		return err
	}

	// Watch for changes to primary resource ArmadaManifest
	// EnqueueRequestForObject enqueues a Request containing the Name and Namespace of the object
	// that is the source of the Event. (e.g. the created / deleted / updated objects Name and Namespace).
	err = c.Watch(&source.Kind{Type: &av1.ArmadaManifest{}}, &crthandler.EnqueueRequestForObject{})
	if err != nil {
		return err
	}

	// Watch for changes to ArmadaChartGroup and requeue the owner ArmadaManifest
	// EnqueueRequestForOwner enqueues Requests for the Owners of an object. E.g. the object
	// that created the object that was the source of the Event
	// IsController if set will only look at the first OwnerReference with Controller: true.
	acg := av1.NewArmadaChartGroupVersionKind("", "")
	dependentPredicate := r.BuildDependentPredicate()
	err = c.Watch(&source.Kind{Type: acg},
		&crthandler.EnqueueRequestForOwner{
			IsController: true,
			OwnerType:    &av1.ArmadaManifest{},
		},
		*dependentPredicate)
	if err != nil {
		return err
	}

	// JEB: Will see later if we need to put the ownership between the backup/restore and the Manifest
	// err = c.Watch(&source.Kind{Type: &av1.ArmadaBackup{}}, &crthandler.EnqueueRequestForOwner{OwnerType: owner},
	// 	dependentPredicate)
	// err = c.Watch(&source.Kind{Type: &av1.ArmadaRestore{}}, &crthandler.EnqueueRequestForOwner{OwnerType: owner},
	// 	dependentPredicate)

	return nil
}

var _ reconcile.Reconciler = &ManifestReconciler{}

// ManifestReconciler reconciles a ArmadaManifest object
type ManifestReconciler struct {
	BaseReconciler
	managerFactory armadaif.ArmadaManagerFactory
}

const (
	finalizerArmadaManifest = "uninstall-amf"
)

// Reconcile reads that state of the cluster for a ArmadaManifest object and
// makes changes based on the state read and what is in the ArmadaManifest.Spec
//
// Note: The Controller will requeue the Request to be processed again if the
// returned error is non-nil or Result.Requeue is true, otherwise upon
// completion it will remove the work from the queue.
func (r *ManifestReconciler) Reconcile(request reconcile.Request) (reconcile.Result, error) {
	reclog := amflog.WithValues("namespace", request.Namespace, "amf", request.Name)
	reclog.Info("Reconciling")

	instance := &av1.ArmadaManifest{}
	instance.SetNamespace(request.Namespace)
	instance.SetName(request.Name)

	err := r.client.Get(context.TODO(), request.NamespacedName, instance)
	if apierrors.IsNotFound(err) {
		// We are working asynchronously. By the time we receive the event,
		// the object is already gone
		return reconcile.Result{}, nil
	}
	if err != nil {
		reclog.Error(err, "Failed to lookup ArmadaManifest")
		return reconcile.Result{}, err
	}

	instance.Init()
	mgr := r.managerFactory.NewArmadaManifestManager(instance)
	reclog = reclog.WithValues("amf", mgr.ResourceName())

	var shouldRequeue bool
	if shouldRequeue, err = r.updateFinalizers(instance); shouldRequeue {
		// Need to requeue because finalizer update does not change metadata.generation
		return reconcile.Result{Requeue: true}, err
	}

	if err := r.ensureSynced(mgr, instance); err != nil {
		if !instance.IsDeleted() {
			// TODO(jeb): Changed the behavior to stop only if we are not
			// in a delete phase.
			return reconcile.Result{}, err
		}
	}

	if instance.IsDeleted() {
		if shouldRequeue, err = r.deleteArmadaManifest(mgr, instance); shouldRequeue {
			// Need to requeue because finalizer update does not change metadata.generation
			return reconcile.Result{Requeue: true}, err
		}
		return reconcile.Result{}, err
	}

	if instance.IsTargetStateUninitialized() {
		reclog.Info("TargetState uninitialized; skipping")
		err = r.updateResource(instance)
		if err != nil {
			return reconcile.Result{}, err
		}
		err = r.client.Status().Update(context.TODO(), instance)
		return reconcile.Result{}, err
	}

	hrc := av1.HelmResourceCondition{
		Type:   av1.ConditionInitialized,
		Status: av1.ConditionStatusTrue,
	}
	instance.Status.SetCondition(hrc, instance.Spec.TargetState)

	switch {
	case mgr.IsUpdateRequired():
		if shouldRequeue, err = r.updateArmadaManifest(mgr, instance); shouldRequeue {
			return reconcile.Result{RequeueAfter: r.reconcilePeriod}, err
		}
		return reconcile.Result{}, err
	}

	if err := r.reconcileArmadaManifest(mgr, instance); err != nil {
		return reconcile.Result{}, err
	}

	reclog.Info("Reconciled ArmadaManifest")
	if err = r.updateResourceStatus(instance); err != nil {
		return reconcile.Result{Requeue: true}, err
	}
	return reconcile.Result{}, nil
}

// logAndRecordFailure adds a failure event to the recorder
func (r ManifestReconciler) logAndRecordFailure(instance *av1.ArmadaManifest, hrc *av1.HelmResourceCondition, err error) {
	reclog := amflog.WithValues("namespace", instance.Namespace, "amf", instance.Name)
	reclog.Error(err, fmt.Sprintf("%s. ErrorCondition", hrc.Type.String()))
	r.recorder.Event(instance, corev1.EventTypeWarning, hrc.Type.String(), hrc.Reason.String())
}

// logAndRecordSuccess adds a success event to the recorder
func (r ManifestReconciler) logAndRecordSuccess(instance *av1.ArmadaManifest, hrc *av1.HelmResourceCondition) {
	reclog := amflog.WithValues("namespace", instance.Namespace, "amf", instance.Name)
	reclog.Info(fmt.Sprintf("%s. SuccessCondition", hrc.Type.String()))
	r.recorder.Event(instance, corev1.EventTypeNormal, hrc.Type.String(), hrc.Reason.String())
}

// updateResource updates the Resource object in the cluster
func (r ManifestReconciler) updateResource(o *av1.ArmadaManifest) error {
	return r.client.Update(context.TODO(), o)
}

// updateResourceStatus updates the the Status field of the Resource object in the cluster
func (r ManifestReconciler) updateResourceStatus(instance *av1.ArmadaManifest) error {
	reclog := amflog.WithValues("namespace", instance.Namespace, "amf", instance.Name)

	helper := av1.HelmResourceConditionListHelper{Items: instance.Status.Conditions}
	instance.Status.Conditions = helper.InitIfEmpty()

	// JEB: Be sure to have update status subresources in the CRD.yaml
	// JEB: Look for kubebuilder subresources in the _types.go
	err := r.client.Status().Update(context.TODO(), instance)
	if err != nil {
		reclog.Error(err, "Failure to update ManifestStatus")
	}

	return err
}

// ensureSynced checks that the ArmadaManifestManager is in sync with the cluster
func (r ManifestReconciler) ensureSynced(mgr armadaif.ArmadaManifestManager, instance *av1.ArmadaManifest) error {
	if err := mgr.Sync(context.TODO()); err != nil {
		hrc := av1.HelmResourceCondition{
			Type:    av1.ConditionIrreconcilable,
			Status:  av1.ConditionStatusTrue,
			Reason:  av1.ReasonReconcileError,
			Message: err.Error(),
		}
		instance.Status.SetCondition(hrc, instance.Spec.TargetState)
		r.logAndRecordFailure(instance, &hrc, err)

		_ = r.updateResourceStatus(instance)
		return err
	}
	instance.Status.RemoveCondition(av1.ConditionIrreconcilable)
	return nil
}

// updateFinalizers asserts that the finalizers match what is expected based on
// whether the instance is currently being deleted or not. It returns true if
// the finalizers were changed, false otherwise
func (r ManifestReconciler) updateFinalizers(instance *av1.ArmadaManifest) (bool, error) {
	pendingFinalizers := instance.GetFinalizers()
	if !instance.IsDeleted() && !r.contains(pendingFinalizers, finalizerArmadaManifest) {
		finalizers := append(pendingFinalizers, finalizerArmadaManifest)
		instance.SetFinalizers(finalizers)
		err := r.updateResource(instance)

		return true, err
	}
	return false, nil
}

// watchArmadaChartGroups updates all resources which are dependent on this one
func (r ManifestReconciler) watchArmadaChartGroups(instance *av1.ArmadaManifest, toWatchList *av1.ArmadaChartGroups) error {
	reclog := amflog.WithValues("namespace", instance.Namespace, "amf", instance.Name)
	reclog.Info("Adding Watch")

	errs := make([]error, 0)
	for _, toWatch := range (*toWatchList).List.Items {
		found := toWatch.FromArmadaChartGroup()
		err := r.client.Get(context.TODO(), types.NamespacedName{Name: found.GetName(), Namespace: found.GetNamespace()}, found)
		if err == nil {
			if err1 := controllerutil.SetControllerReference(instance, found, r.scheme); err1 != nil {
				reclog.Error(err1, "Can't get ownership of ArmadaChartGroup", "name", found.GetName())
				errs = append(errs, err1)
				continue
			}
			if err2 := r.client.Update(context.TODO(), found); err2 != nil {
				reclog.Error(err2, "Can't get ownership of ArmadaChartGroup", "name", found.GetName())
				errs = append(errs, err2)
				continue
			}
			reclog.Info("Added ownership of ArmadaChart", "name", found.GetName())
		} else {
			reclog.Error(err, "Can't get ownership of ArmadaChartGroup", "name", found.GetName())
			errs = append(errs, err)
		}
	}

	return nil
}

// deleteArmadaManifest deletes an instance of an ArmadaManifest. It returns true if the reconciler should be re-enqueueed
func (r ManifestReconciler) deleteArmadaManifest(mgr armadaif.ArmadaManifestManager, instance *av1.ArmadaManifest) (bool, error) {
	reclog := amflog.WithValues("namespace", instance.Namespace, "amf", instance.Name)
	reclog.Info("Deleting")

	pendingFinalizers := instance.GetFinalizers()
	if !r.contains(pendingFinalizers, finalizerArmadaManifest) {
		reclog.Info("Manifest is terminated, skipping reconciliation")
		return false, nil
	}

	uninstalledResource, err := mgr.UninstallResource(context.TODO())
	if err != nil && err != armadaif.ErrNotFound {
		hrc := av1.HelmResourceCondition{
			Type:         av1.ConditionFailed,
			Status:       av1.ConditionStatusTrue,
			Reason:       av1.ReasonUninstallError,
			Message:      err.Error(),
			ResourceName: uninstalledResource.GetName(),
		}
		instance.Status.SetCondition(hrc, instance.Spec.TargetState)
		r.logAndRecordFailure(instance, &hrc, err)

		_ = r.updateResourceStatus(instance)
		return false, err
	}
	instance.Status.RemoveCondition(av1.ConditionFailed)

	if err == armadaif.ErrNotFound {
		reclog.Info("ChartGroups are already deleted, removing finalizer")
	} else {
		hrc := av1.HelmResourceCondition{
			Type:   av1.ConditionDeployed,
			Status: av1.ConditionStatusFalse,
			Reason: av1.ReasonUninstallSuccessful,
		}
		instance.Status.SetCondition(hrc, instance.Spec.TargetState)
		r.logAndRecordSuccess(instance, &hrc)
	}
	if err := r.updateResourceStatus(instance); err != nil {
		return false, err
	}

	finalizers := []string{}
	for _, pendingFinalizer := range pendingFinalizers {
		if pendingFinalizer != finalizerArmadaManifest {
			finalizers = append(finalizers, pendingFinalizer)
		}
	}
	instance.SetFinalizers(finalizers)
	err = r.updateResource(instance)

	// Need to requeue because finalizer update does not change metadata.generation
	return true, err
}

// updateArmadaManifest attempts to update instance. It returns true if the reconciler should be re-enqueueed
func (r ManifestReconciler) updateArmadaManifest(mgr armadaif.ArmadaManifestManager, instance *av1.ArmadaManifest) (bool, error) {
	reclog := amflog.WithValues("namespace", instance.Namespace, "amf", instance.Name)
	reclog.Info("Updating")

	_, updatedResource, err := mgr.UpdateResource(context.TODO())

	// TODO(jeb): Behavior is flacky here. err != nil means updatedResource is nil
	// Watch for panic exception if UpdateResource behavior is modified
	if err != nil {
		hrc := av1.HelmResourceCondition{
			Type:         av1.ConditionFailed,
			Status:       av1.ConditionStatusTrue,
			Reason:       av1.ReasonUpdateError,
			Message:      err.Error(),
			ResourceName: "",
		}
		instance.Status.SetCondition(hrc, instance.Spec.TargetState)
		r.logAndRecordFailure(instance, &hrc, err)

		_ = r.updateResourceStatus(instance)
		return false, err
	}
	instance.Status.RemoveCondition(av1.ConditionFailed)

	if err := r.watchArmadaChartGroups(instance, updatedResource); err != nil {
		return false, err
	}

	hrc := av1.HelmResourceCondition{
		Type:         av1.ConditionDeployed,
		Status:       av1.ConditionStatusTrue,
		Reason:       av1.ReasonUpdateSuccessful,
		Message:      "HardcodedMessage",
		ResourceName: updatedResource.GetName(),
	}
	instance.Status.SetCondition(hrc, instance.Spec.TargetState)
	r.logAndRecordSuccess(instance, &hrc)

	err = r.updateResourceStatus(instance)
	return true, err
}

// reconcileArmadaManifest reconciles the release with the cluster
func (r ManifestReconciler) reconcileArmadaManifest(mgr armadaif.ArmadaManifestManager, instance *av1.ArmadaManifest) error {
	reclog := amflog.WithValues("namespace", instance.Namespace, "amf", instance.Name)
	reclog.Info("Reconciling ArmadaManifest and ArmadaChartGroupList")

	expectedResource, err := mgr.ReconcileResource(context.TODO())
	if err != nil {
		hrc := av1.HelmResourceCondition{
			Type:         av1.ConditionIrreconcilable,
			Status:       av1.ConditionStatusTrue,
			Reason:       av1.ReasonReconcileError,
			Message:      err.Error(),
			ResourceName: expectedResource.GetName(),
		}
		instance.Status.SetCondition(hrc, instance.Spec.TargetState)
		r.logAndRecordFailure(instance, &hrc, err)

		_ = r.updateResourceStatus(instance)
		return err
	}
	instance.Status.RemoveCondition(av1.ConditionIrreconcilable)
	err = r.watchArmadaChartGroups(instance, expectedResource)
	return err
}
