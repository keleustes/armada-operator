// Copyright 2018 The Operator-SDK Authors
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

	av1 "github.com/keleustes/armada-crd/pkg/apis/armada/v1alpha1"
	helmmgr "github.com/keleustes/armada-operator/pkg/helm"
	services "github.com/keleustes/armada-operator/pkg/services"

	corev1 "k8s.io/api/core/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"

	"sigs.k8s.io/controller-runtime/pkg/controller"
	crthandler "sigs.k8s.io/controller-runtime/pkg/handler"
	"sigs.k8s.io/controller-runtime/pkg/manager"
	"sigs.k8s.io/controller-runtime/pkg/reconcile"
	logf "sigs.k8s.io/controller-runtime/pkg/log"
	"sigs.k8s.io/controller-runtime/pkg/source"
)

var actlog = logf.Log.WithName("act-controller")

// AddArmadaChartController creates a new ArmadaChart Controller and adds it to
// the Manager. The Manager will set fields on the Controller and Start it when
// the Manager is Started.
func AddArmadaChartController(mgr manager.Manager) error {
	return add(mgr, newReconciler(mgr))
}

// newReconciler returns a new reconcile.Reconciler
func newReconciler(mgr manager.Manager) reconcile.Reconciler {
	r := &ChartReconciler{
		BaseReconciler: BaseReconciler{
			client:   mgr.GetClient(),
			scheme:   mgr.GetScheme(),
			recorder: mgr.GetEventRecorderFor("act-recorder"),
		},
		managerFactory: helmmgr.NewManagerFactory(mgr),
	}

	return r
}

// add adds a new Controller to mgr with r as the reconcile.Reconciler
func add(mgr manager.Manager, r reconcile.Reconciler) error {

	// Create a new controller
	c, err := controller.New("act-controller", mgr, controller.Options{Reconciler: r})
	if err != nil {
		return err
	}

	// Watch for changes to primary resource ArmadaChart
	// EnqueueRequestForObject enqueues a Request containing the Name and Namespace of the object
	// that is the source of the Event. (e.g. the created / deleted / updated objects Name and Namespace).
	err = c.Watch(&source.Kind{Type: &av1.ArmadaChart{}}, &crthandler.EnqueueRequestForObject{})
	if err != nil {
		return err
	}

	// Watch for changes to secondary resource (described in the helm chart) and requeue the owner ArmadaChart
	// EnqueueRequestForOwner enqueues Requests for the Owners of an object. E.g. the object
	// that created the object that was the source of the Event
	if racr, isChartReconciler := r.(*ChartReconciler); isChartReconciler {
		// The enqueueRequestForOwner is not actually done here since we don't know yet the
		// content of the release. The tools wait for the helm chart to be parse. The chart_manager
		// then add the "OwnerReference" to the content of the yaml files. It then invokes the EnqueueRequestForOwner
		owner := av1.NewArmadaChartVersionKind("", "")
		dependentPredicate := racr.BuildDependentPredicate()
		racr.depResourceWatchUpdater = services.BuildDependentResourceWatchUpdater(mgr, owner, c, *dependentPredicate)
	} else if rrf, isReconcileFunc := r.(*reconcile.Func); isReconcileFunc {
		// Unit test issue
		log.Info("UnitTests", "ReconfileFunc", rrf)
	}

	return nil
}

var _ reconcile.Reconciler = &ChartReconciler{}

// ChartReconciler reconciles custom resources as Helm releases.
type ChartReconciler struct {
	BaseReconciler
	managerFactory services.HelmManagerFactory
}

const (
	finalizerArmadaChart = "uninstall-helm-release"
)

// Reconcile reads that state of the cluster for an ArmadaChart object and
// makes changes based on the state read and what is in the ArmadaChart.Spec
//
// Note: The Controller will requeue the Request to be processed again if the
// returned error is non-nil or Result.Requeue is true, otherwise upon
// completion it will remove the work from the queue.
func (r *ChartReconciler) Reconcile(request reconcile.Request) (reconcile.Result, error) {
	reclog := actlog.WithValues("namespace", request.Namespace, "act", request.Name)
	reclog.Info("Received a request")

	instance := &av1.ArmadaChart{}
	instance.SetNamespace(request.Namespace)
	instance.SetName(request.Name)

	err := r.client.Get(context.TODO(), request.NamespacedName, instance)

	if apierrors.IsNotFound(err) {
		// We are working asynchronously. By the time we receive the event,
		// the object is already gone
		return reconcile.Result{}, nil
	}

	if err != nil {
		reclog.Error(err, "Failed to lookup ArmadaChart")
		return reconcile.Result{}, err
	}

	instance.Init()
	mgr := r.managerFactory.NewArmadaChartManager(instance)
	reclog = reclog.WithValues("release", mgr.ReleaseName())

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
		if shouldRequeue, err = r.deleteArmadaChart(mgr, instance); shouldRequeue {
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
	case !mgr.IsInstalled():
		if shouldRequeue, err = r.installArmadaChart(mgr, instance); shouldRequeue {
			return reconcile.Result{RequeueAfter: r.reconcilePeriod}, err
		}
		return reconcile.Result{}, err
	case mgr.IsUpdateRequired():
		if shouldRequeue, err = r.updateArmadaChart(mgr, instance); shouldRequeue {
			return reconcile.Result{RequeueAfter: r.reconcilePeriod}, err
		}
		return reconcile.Result{}, err
	}

	forcedRequeue, err := r.reconcileArmadaChart(mgr, instance)
	if err != nil {
		// Let's don't force a requeue.
		return reconcile.Result{}, err
	}
	if forcedRequeue {
		// We have been waked up out of order ?
		return reconcile.Result{RequeueAfter: r.reconcilePeriod}, nil
	}

	reclog.Info("Reconciled ArmadaChart")
	if err = r.updateResourceStatus(instance); err != nil {
		return reconcile.Result{Requeue: true}, err
	}
	return reconcile.Result{}, nil
}

// logAndRecordFailure adds a failure event to the recorder
func (r ChartReconciler) logAndRecordFailure(instance *av1.ArmadaChart, hrc *av1.HelmResourceCondition, err error) {
	reclog := actlog.WithValues("namespace", instance.Namespace, "act", instance.Name)
	reclog.Error(err, fmt.Sprintf("%s. ErrorCondition", hrc.Type.String()))
	r.recorder.Event(instance, corev1.EventTypeWarning, hrc.Type.String(), hrc.Reason.String())
}

// logAndRecordSuccess adds a success event to the recorder
func (r ChartReconciler) logAndRecordSuccess(instance *av1.ArmadaChart, hrc *av1.HelmResourceCondition) {
	reclog := actlog.WithValues("namespace", instance.Namespace, "act", instance.Name)
	reclog.Info(fmt.Sprintf("%s. SuccessCondition", hrc.Type.String()))
	r.recorder.Event(instance, corev1.EventTypeNormal, hrc.Type.String(), hrc.Reason.String())
}

// updateResource updates the Resource object in the cluster
func (r ChartReconciler) updateResource(instance *av1.ArmadaChart) error {
	return r.client.Update(context.TODO(), instance)
}

// updateResourceStatus updates the the Status field of the Resource object in the cluster
func (r ChartReconciler) updateResourceStatus(instance *av1.ArmadaChart) error {
	reclog := actlog.WithValues("namespace", instance.Namespace, "act", instance.Name)

	helper := av1.HelmResourceConditionListHelper{Items: instance.Status.Conditions}
	instance.Status.Conditions = helper.InitIfEmpty()

	// JEB: Be sure to have update status subresources in the CRD.yaml
	// JEB: Look for kubebuilder subresources in the _types.go
	err := r.client.Status().Update(context.TODO(), instance)
	if err != nil {
		reclog.Error(err, "Failure to update status. Ignoring")
		err = nil
	}

	return err
}

// ensureSynced checks that the HelmManager is in sync with the cluster
func (r ChartReconciler) ensureSynced(mgr services.HelmManager, instance *av1.ArmadaChart) error {
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
func (r ChartReconciler) updateFinalizers(instance *av1.ArmadaChart) (bool, error) {
	pendingFinalizers := instance.GetFinalizers()
	if !instance.IsDeleted() && !r.contains(pendingFinalizers, finalizerArmadaChart) {
		finalizers := append(pendingFinalizers, finalizerArmadaChart)
		instance.SetFinalizers(finalizers)
		err := r.updateResource(instance)

		return true, err
	}
	return false, nil
}

// watchDependentResources updates all resources which are dependent on this one
func (r ChartReconciler) watchDependentResources(resource *services.HelmRelease) error {
	if r.depResourceWatchUpdater != nil {
		if err := r.depResourceWatchUpdater(resource.GetDependentResources()); err != nil {
			return err
		}
	}
	return nil
}

// deleteArmadaChart deletes an instance of an ArmadaChart. It returns true if the reconciler should be re-enqueueed
func (r ChartReconciler) deleteArmadaChart(mgr services.HelmManager, instance *av1.ArmadaChart) (bool, error) {
	reclog := actlog.WithValues("namespace", instance.Namespace, "act", instance.Name)
	reclog.Info("Deleting")

	pendingFinalizers := instance.GetFinalizers()
	if !r.contains(pendingFinalizers, finalizerArmadaChart) {
		reclog.Info("ArmadaChart is terminated, skipping reconciliation")
		return false, nil
	}

	uninstalledResource, err := mgr.UninstallRelease(context.TODO())
	if err != nil && err != services.ErrNotFound {
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

	if err == services.ErrNotFound {
		reclog.Info("Release already uninstalled, Removing finalizer")
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
		if pendingFinalizer != finalizerArmadaChart {
			finalizers = append(finalizers, pendingFinalizer)
		}
	}
	instance.SetFinalizers(finalizers)
	err = r.updateResource(instance)

	return true, err
}

// installArmadaChart attempts to install instance. It returns true if the reconciler should be re-enqueueed
func (r ChartReconciler) installArmadaChart(mgr services.HelmManager, instance *av1.ArmadaChart) (bool, error) {
	reclog := actlog.WithValues("namespace", instance.Namespace, "act", instance.Name)
	reclog.Info("Installing")

	installedResource, err := mgr.InstallRelease(context.TODO())
	if err != nil {
		instance.Status.RemoveCondition(av1.ConditionRunning)

		hrc := av1.HelmResourceCondition{
			Type:    av1.ConditionFailed,
			Status:  av1.ConditionStatusTrue,
			Reason:  av1.ReasonInstallError,
			Message: err.Error(),
		}
		instance.Status.SetCondition(hrc, instance.Spec.TargetState)
		r.logAndRecordFailure(instance, &hrc, err)

		_ = r.updateResourceStatus(instance)
		return false, err
	}
	instance.Status.RemoveCondition(av1.ConditionFailed)

	if err := r.watchDependentResources(installedResource); err != nil {
		reclog.Error(err, "Failed to update watch on dependent resources")
		return false, err
	}

	hrc := av1.HelmResourceCondition{
		Type:            av1.ConditionRunning,
		Status:          av1.ConditionStatusTrue,
		Reason:          av1.ReasonInstallSuccessful,
		Message:         installedResource.GetNotes(),
		ResourceName:    installedResource.GetName(),
		ResourceVersion: installedResource.GetVersion(),
	}
	instance.Status.SetCondition(hrc, instance.Spec.TargetState)
	r.logAndRecordSuccess(instance, &hrc)

	err = r.updateResourceStatus(instance)
	return true, err
}

// updateArmadaChart attempts to update instance. It returns true if the reconciler should be re-enqueueed
func (r ChartReconciler) updateArmadaChart(mgr services.HelmManager, instance *av1.ArmadaChart) (bool, error) {
	reclog := actlog.WithValues("namespace", instance.Namespace, "act", instance.Name)
	reclog.Info("Updating")

	_, updatedResource, err := mgr.UpdateRelease(context.TODO())
	if err != nil {
		instance.Status.RemoveCondition(av1.ConditionRunning)

		hrc := av1.HelmResourceCondition{
			Type:         av1.ConditionFailed,
			Status:       av1.ConditionStatusTrue,
			Reason:       av1.ReasonUpdateError,
			Message:      err.Error(),
			ResourceName: updatedResource.GetName(),
		}
		instance.Status.SetCondition(hrc, instance.Spec.TargetState)
		r.logAndRecordFailure(instance, &hrc, err)

		_ = r.updateResourceStatus(instance)
		return false, err
	}
	instance.Status.RemoveCondition(av1.ConditionFailed)

	if err := r.watchDependentResources(updatedResource); err != nil {
		reclog.Error(err, "Failed to update watch on dependent resources")
		return false, err
	}

	hrc := av1.HelmResourceCondition{
		Type:            av1.ConditionRunning,
		Status:          av1.ConditionStatusTrue,
		Reason:          av1.ReasonUpdateSuccessful,
		Message:         updatedResource.GetNotes(),
		ResourceName:    updatedResource.GetName(),
		ResourceVersion: updatedResource.GetVersion(),
	}
	instance.Status.SetCondition(hrc, instance.Spec.TargetState)
	r.logAndRecordSuccess(instance, &hrc)

	err = r.updateResourceStatus(instance)
	return true, err
}

// reconcileArmadaChart reconciles the release with the cluster
func (r ChartReconciler) reconcileArmadaChart(mgr services.HelmManager, instance *av1.ArmadaChart) (bool, error) {
	reclog := actlog.WithValues("namespace", instance.Namespace, "act", instance.Name)
	reclog.Info("Reconciling ArmadaChart and HelmRelease")

	reconciledResource, err := mgr.ReconcileRelease(context.TODO())
	if err != nil {
		instance.Status.RemoveCondition(av1.ConditionRunning)

		hrc := av1.HelmResourceCondition{
			Type:         av1.ConditionIrreconcilable,
			Status:       av1.ConditionStatusTrue,
			Reason:       av1.ReasonReconcileError,
			Message:      err.Error(),
			ResourceName: reconciledResource.GetName(),
		}
		instance.Status.SetCondition(hrc, instance.Spec.TargetState)
		r.logAndRecordFailure(instance, &hrc, err)

		_ = r.updateResourceStatus(instance)
		return false, err
	}
	instance.Status.RemoveCondition(av1.ConditionIrreconcilable)

	if err := r.watchDependentResources(reconciledResource); err != nil {
		reclog.Error(err, "Failed to update watch on dependent resources")
		return false, err
	}

	if reconciledResource.IsFailedOrError() {
		// We reconcile. Everything is ready. The flow is now ok
		instance.Status.RemoveCondition(av1.ConditionRunning)

		hrc := av1.HelmResourceCondition{
			Type:         av1.ConditionError,
			Status:       av1.ConditionStatusTrue,
			Reason:       av1.ReasonUnderlyingResourcesError,
			Message:      "",
			ResourceName: reconciledResource.GetName(),
		}
		instance.Status.SetCondition(hrc, instance.Spec.TargetState)
		r.logAndRecordSuccess(instance, &hrc)

		err = r.updateResourceStatus(instance)
		return false, err
	}

	if reconciledResource.IsReady() {
		// We reconcile. Everything is ready. The flow is now ok
		instance.Status.RemoveCondition(av1.ConditionRunning)

		hrc := av1.HelmResourceCondition{
			Type:         av1.ConditionDeployed,
			Status:       av1.ConditionStatusTrue,
			Reason:       av1.ReasonUnderlyingResourcesReady,
			Message:      "",
			ResourceName: reconciledResource.GetName(),
		}
		instance.Status.SetCondition(hrc, instance.Spec.TargetState)
		r.logAndRecordSuccess(instance, &hrc)

		err = r.updateResourceStatus(instance)
		return false, err
	}

	return false, nil
}
