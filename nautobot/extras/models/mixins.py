"""
Class-modifying mixins that need to be standalone to avoid circular imports.
"""

import logging

from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.urls import NoReverseMatch, reverse

from nautobot.core.utils.deprecation import method_deprecated_in_favor_of
from nautobot.core.utils.filtering import build_filter_dict_from_filterset
from nautobot.core.utils.lookup import get_filterset_for_model, get_route_for_model, get_user_from_instance
from nautobot.extras.choices import ApprovalWorkflowStateChoices, ObjectChangeActionChoices

logger = logging.getLogger(__name__)


def unknown_filter_parameters(filterset, filter_data):
    """
    Return the sorted parameter names in `filter_data` that `filterset` does not define.

    A FilterSet form only binds the parameters it knows about, so `form.is_valid()` returns True for a
    filter naming something that does not exist: the parameter is silently dropped and the filter
    matches far more than the author intended. Anywhere a stored filter is validated, the parameter
    names have to be checked separately from the values.
    """
    return sorted(set(filter_data or {}) - set(filterset.filters))


class ApprovableModelMixin(models.Model):
    """Abstract mixin for enabling Approval Flow functionality to a given model class."""

    class Meta:
        abstract = True

    is_approval_workflow_model = True

    # Reverse relation so that deleting a ApprovableModelMixin automatically deletes any approval workflows related to it.

    associated_approval_workflows = GenericRelation(
        "extras.ApprovalWorkflow",
        content_type_field="object_under_review_content_type",
        object_id_field="object_under_review_object_id",
        related_query_name="associated_approval_workflows_%(app_label)s_%(class)s",  # e.g. 'associated_object_approval_workflows_dcim_device'
    )

    def get_approval_workflow_url(self):
        """Return the approval workflow URL for this object."""
        route = get_route_for_model(self, "approvalworkflow")

        # Iterate the pk-like fields and try to get a URL, or return None.
        fields = ["pk", "slug"]
        for field in fields:
            if not hasattr(self, field):
                continue

            try:
                return reverse(route, kwargs={field: getattr(self, field)})
            except NoReverseMatch:
                continue

        return None

    def begin_approval_workflow(self):
        """Find and start the appropriate approval workflow for this object."""
        from nautobot.extras.models.approvals import (
            ApprovalWorkflow,
            ApprovalWorkflowDefinition,
            ApprovalWorkflowStage,
            ApprovalWorkflowStageDefinition,
        )  # because of circular import

        # First check if there's already a pending workflow instance
        if self.associated_approval_workflows.filter(current_state=ApprovalWorkflowStateChoices.PENDING).exists():
            return self.associated_approval_workflows.filter(current_state=ApprovalWorkflowStateChoices.PENDING).first()

        # Check if there's a relevant workflow definition
        workflow_definition = ApprovalWorkflowDefinition.objects.find_for_model(self)
        if not workflow_definition:
            return None

        approval_workflow = ApprovalWorkflow.objects.create(
            approval_workflow_definition=workflow_definition,
            object_under_review_content_type=ContentType.objects.get_for_model(self),
            object_under_review_object_id=self.pk,
            current_state=ApprovalWorkflowStateChoices.PENDING,
            user=get_user_from_instance(self),
        )

        # Create workflow stages if the definition has any
        approval_workflow_stage_definitions = ApprovalWorkflowStageDefinition.objects.filter(
            approval_workflow_definition=workflow_definition
        )

        ApprovalWorkflowStage.objects.bulk_create(
            [
                ApprovalWorkflowStage(
                    approval_workflow=approval_workflow,
                    approval_workflow_stage_definition=definition,
                    state=ApprovalWorkflowStateChoices.PENDING,
                )
                for definition in approval_workflow_stage_definitions
            ]
        )

        self.on_workflow_initiated(approval_workflow)

        return approval_workflow

    def on_workflow_initiated(self, approval_workflow):
        """Called when an approval workflow is initiated."""
        raise NotImplementedError("Subclasses must implement `on_workflow_initiated`.")

    def on_workflow_approved(self, approval_workflow):
        """Called when an approval workflow is approved."""
        raise NotImplementedError("Subclasses must implement `on_workflow_approved`.")

    def on_workflow_denied(self, approval_workflow):
        """Called when an approval workflow is denied."""
        raise NotImplementedError("Subclasses must implement `on_workflow_denied`.")

    def on_workflow_canceled(self, approval_workflow):
        """Called when an approval workflow is canceled."""
        raise NotImplementedError("Subclasses must implement `on_workflow_canceled`.")

    def has_approval_workflow_definition(self) -> bool:
        from nautobot.extras.models.approvals import ApprovalWorkflowDefinition

        return ApprovalWorkflowDefinition.objects.find_for_model(self) is not None


class ContactMixin(models.Model):
    """Abstract mixin for enabling Contact/Team association to a given model class."""

    class Meta:
        abstract = True

    is_contact_associable_model = True

    # Reverse relation so that deleting a ContactMixin automatically deletes any ContactAssociations related to it.
    associated_contacts = GenericRelation(
        "extras.ContactAssociation",
        content_type_field="associated_object_type",
        object_id_field="associated_object_id",
        related_query_name="associated_contacts_%(app_label)s_%(class)s",  # e.g. 'associated_contacts_dcim_device'
    )


class DynamicGroupMixin:
    """
    DEPRECATED - use DynamicGroupsModelMixin instead if you need to mark a model as supporting Dynamic Groups.

    This is necessary because DynamicGroupMixin was incorrectly not implemented as a subclass of models.Model,
    and so it cannot properly implement Model behaviors like the `static_group_association_set` ReverseRelation.
    However, adding this inheritance to DynamicGroupMixin itself would negatively impact existing migrations.
    So unfortunately our best option is to deprecate this class and gradually convert core and app models alike
    to the new DynamicGroupsModelMixin in its place.

    Adds `dynamic_groups` property to a model to facilitate reversing (cached) DynamicGroup membership.

    If up-to-the-minute accuracy is necessary for your use case, it's up to you to call the
    `DynamicGroup.update_cached_members()` API on any relevant DynamicGroups before accessing this property.

    Other related properties added by this mixin should be considered obsolete.
    """

    is_dynamic_group_associable_model = True

    @property
    def dynamic_groups(self):
        """
        Return a queryset of (cached) `DynamicGroup` objects this instance is a member of.
        """
        from nautobot.extras.models.groups import DynamicGroup

        return DynamicGroup.objects.get_for_object(self)

    @property
    @method_deprecated_in_favor_of(dynamic_groups.fget)
    def dynamic_groups_cached(self):
        """Deprecated - use `self.dynamic_groups` instead."""
        return self.dynamic_groups

    @property
    @method_deprecated_in_favor_of(dynamic_groups.fget)
    def dynamic_groups_list(self):
        """Deprecated - use `list(self.dynamic_groups)` instead."""
        return list(self.dynamic_groups)

    @property
    @method_deprecated_in_favor_of(dynamic_groups.fget)
    def dynamic_groups_list_cached(self):
        """Deprecated - use `list(self.dynamic_groups)` instead."""
        return self.dynamic_groups_list

    # TODO may be able to remove this entirely???
    def get_dynamic_groups_url(self):
        """Return the dynamic groups URL for a given instance."""
        route = get_route_for_model(self, "dynamicgroups")

        # Iterate the pk-like fields and try to get a URL, or return None.
        fields = ["pk", "slug"]
        for field in fields:
            if not hasattr(self, field):
                continue

            try:
                return reverse(route, kwargs={field: getattr(self, field)})
            except NoReverseMatch:
                continue

        return None


class DynamicGroupsModelMixin(DynamicGroupMixin, models.Model):
    """
    Add this to models to make them fully support Dynamic Groups.
    """

    class Meta:
        abstract = True

    # Reverse relation so that deleting a DynamicGroupMixin automatically deletes any related StaticGroupAssociations
    static_group_association_set = GenericRelation(  # not "static_group_associations" as that'd collide on DynamicGroup
        "extras.StaticGroupAssociation",
        content_type_field="associated_object_type",
        object_id_field="associated_object_id",
        related_query_name="static_group_association_set_%(app_label)s_%(class)s",
    )


class NotesMixin:
    """
    Adds a `notes` property that returns a queryset of `Notes` membership.
    """

    @property
    def notes(self):
        """Return a `Notes` queryset for this instance."""
        from nautobot.extras.models.models import Note

        if not hasattr(self, "_notes_queryset"):
            queryset = Note.objects.get_for_object(self)
            self._notes_queryset = queryset

        return self._notes_queryset

    def get_notes_url(self, api=False):
        """Return the notes URL for a given instance."""
        route = get_route_for_model(self, "notes", api=api)

        # Iterate the pk-like fields and try to get a URL, or return None.
        fields = ["pk", "slug"]
        for field in fields:
            if not hasattr(self, field):
                continue

            try:
                return reverse(route, kwargs={field: getattr(self, field)})
            except NoReverseMatch:
                continue

        return None


class SavedViewMixin(models.Model):
    """Abstract mixin for enabling Saved View functionality to a given model class."""

    class Meta:
        abstract = True

    is_saved_view_model = True


class DataComplianceModelMixin:
    """
    Adds a `get_data_compliance_url` that can be applied to instances.
    """

    is_data_compliance_model = True

    def get_data_compliance_url(self, api=False):
        """Return the data compliance URL for a given instance."""
        # If is_data_compliance_model overridden should allow to opt out
        if not self.is_data_compliance_model:
            return None
        route = get_route_for_model(self, "data-compliance", api=api)

        # Iterate the pk-like fields and try to get a URL, or return None.
        fields = ["pk", "slug"]
        for field in fields:
            if not hasattr(self, field):
                continue

            try:
                return reverse(route, kwargs={field: getattr(self, field)})
            except NoReverseMatch:
                continue

        return None


class ConditionalTriggerMixin(models.Model):
    """
    Adds a scope and a list of conditions to an action that fires on object changes.

    A Webhook or Job Hook already says *which object types* and *which kinds of change* it watches, via
    `content_types` and the `type_create` / `type_update` / `type_delete` flags. This mixin adds the two
    questions those cannot answer: *which objects* (the scope, a stored set of FilterSet parameters) and
    *which changes* (the conditions, an ordered list that must all pass).

    Both are empty by default, and an action with both empty behaves exactly as it did before this
    existed, which is what makes the feature additive instead of a change to every installation.

    The two live here rather than on a separate model because an action and its trigger logic are the
    same thing to the person configuring them: one page, one object, one set of object types.
    """

    scope_filter = models.JSONField(
        encoder=DjangoJSONEncoder,
        editable=False,
        default=dict,
        blank=True,
        help_text="A JSON-encoded dictionary of filter parameters limiting which objects this fires for. "
        "An empty dictionary means every object of the selected type(s).",
    )
    conditions = models.JSONField(
        encoder=DjangoJSONEncoder,
        default=list,
        blank=True,
        help_text="An ordered list of condition rows, all of which must pass. An empty list means every "
        "in-scope change passes.",
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """Normalise the stored conditions, then save.

        Dropping blank rows is a change to the data, so it belongs here rather than in `clean()`. Doing it
        on every save means a bare `save()` stores the same thing `validated_save()` would.
        """
        if self.conditions in (None, ""):
            self.conditions = []
        if isinstance(self.conditions, list):
            self.conditions = [row for row in self.conditions if row not in (None, "", {}, [])]
        super().save(*args, **kwargs)

    #
    # Scope
    #

    @property
    def has_conditional_trigger(self):
        """Whether this action needs any evaluation beyond its object types and event flags."""
        return bool(self.scope_filter) or bool(self.conditions)

    @property
    def scope_filter_model_class(self):
        """The model class the scope filter form is built from, taken from the first assigned content type."""
        content_types = self.content_types.all()
        if not content_types:
            return None
        return content_types[0].model_class()

    @property
    def scope_filter_prefixed(self):
        """The stored scope filter with a `scope-` prefix on each key, for rendering the filter sub-form."""
        if self.scope_filter:
            return {f"scope-{name}": value for name, value in self.scope_filter.items()}
        return {}

    def watches_action(self, action):
        """Whether this action's event flags include `action`, an `ObjectChangeActionChoices` value."""
        return bool(
            getattr(
                self,
                {
                    ObjectChangeActionChoices.ACTION_CREATE: "type_create",
                    ObjectChangeActionChoices.ACTION_UPDATE: "type_update",
                    ObjectChangeActionChoices.ACTION_DELETE: "type_delete",
                }.get(action, ""),
                False,
            )
        )

    def set_scope_filter(self, form_data):
        """
        Store the filter parameters from a filter form's cleaned data.

        Args:
            form_data (dict): Dictionary of filter parameters, generally a filter form's cleaned data.
        """
        model_class = self.scope_filter_model_class
        if model_class is None:
            self.scope_filter = {}
            return
        filterset_class = get_filterset_for_model(model_class)
        if filterset_class is None:
            self.scope_filter = {}
            return
        self.scope_filter = build_filter_dict_from_filterset(filterset_class, form_data)

    def get_in_scope_queryset(self, queryset, job_logger=logger):
        """
        Return a filtered version of `queryset` containing only the objects in scope.

        If `scope_filter` is empty, `queryset` is returned unchanged, because an unscoped action
        watches everything of its object types.

        If the filter cannot be applied (the model has no filterset, or the stored filter names
        something that filterset does not support) nothing is in scope and the problem is logged as an error. The
        action is inert for that model until someone fixes the filter.

        Fail closed, because a scope filter exists to narrow: widening it to every object would deliver
        webhooks, and run job hooks, against objects the author deliberately excluded, and a delivery cannot
        be recalled. An inert action is the recoverable failure. `CustomField.get_in_scope_queryset` fails
        the other way on purpose: treating everything as in-scope there means provisioning a field on
        more objects than needed, which is a correctable state instead of an action taken in the world.
        """
        if not self.scope_filter:
            return queryset

        model = queryset.model
        filterset_class = get_filterset_for_model(model)
        if not filterset_class:
            job_logger.error(
                "%s `%s` has a scope filter but no filterset exists for %s, so its scope cannot be "
                "evaluated; it will not fire for %s until the filter is removed.",
                self._meta.verbose_name,
                self,
                model._meta.label,
                model._meta.label,
            )
            return queryset.none()

        filterset = filterset_class(data=self.scope_filter, queryset=queryset)

        unknown = unknown_filter_parameters(filterset, self.scope_filter)
        if unknown:
            job_logger.error(
                "%s `%s` scope filter names parameter(s) %s that %s does not support, so its scope cannot "
                "be evaluated; it will not fire for %s until the filter is corrected.",
                self._meta.verbose_name,
                self,
                ", ".join(unknown),
                model._meta.label,
                model._meta.label,
            )
            return queryset.none()

        if not filterset.form.is_valid():
            job_logger.error(
                "%s `%s` has an invalid scope filter for %s (%s), so its scope cannot be evaluated; it "
                "will not fire for %s until the filter is corrected.",
                self._meta.verbose_name,
                self,
                model._meta.label,
                filterset.form.errors.as_text(),
                model._meta.label,
            )
            return queryset.none()

        return filterset.qs

    def matches_scope(self, instance, job_logger=logger):
        """
        Return whether `instance` is in scope.

        This runs inside a change-logging signal receiver, once per scoped action per changed object, so it
        is deliberately the cheapest query the ORM can issue: the scope filter applied to a queryset already
        constrained to a single primary key.
        """
        if not self.scope_filter:
            return True
        model = instance._meta.concrete_model
        queryset = model.objects.filter(pk=instance.pk)
        return self.get_in_scope_queryset(queryset, job_logger=job_logger).exists()

    @staticmethod
    def check_scope_filter(scope_filter, content_types):
        """
        Return an error message if `scope_filter` is not usable for every content type, or None if it is.

        Validated against every selected content type, not just the first. An action watching two models
        stores one filter for both, so a parameter only one of them supports would silently fail to scope
        the other, which reads as "it fired for something out of scope".

        A static method because the content types have to be passed in: they are many-to-many, so on a
        create neither `clean()` nor a serializer's `validate()` can read them off the instance.

        Args:
            scope_filter (dict): The filter parameters to check.
            content_types (iterable): The ContentTypes the action watches.

        Returns:
            (str): The problem, or None if there is none.
        """
        if not scope_filter:
            return None
        problems = []
        for content_type in content_types:
            model_class = content_type.model_class()
            if model_class is None:
                continue
            filterset_class = get_filterset_for_model(model_class)
            if filterset_class is None:
                problems.append(f"{model_class._meta.label} has no filterset, so it cannot be scoped.")
                continue
            filterset = filterset_class(data=scope_filter, queryset=model_class.objects.none())
            unknown = unknown_filter_parameters(filterset, scope_filter)
            if unknown:
                problems.append(f"{model_class._meta.label} has no filter parameter(s): {', '.join(unknown)}.")
                continue
            if not filterset.form.is_valid():
                problems.append(filterset.form.errors.as_text())
        # Every selected type is reported, so an action watching three models that all reject the filter
        # is fixed in one pass instead of one save per model.
        return " ".join(problems) if problems else None

    #
    # Validation
    #

    def clean_conditional_trigger(self):
        """Validate the scope filter and conditions. Call this from the model's own `clean()`."""
        self._clean_scope_filter()
        self._clean_conditions()

    def _clean_scope_filter(self):
        """Reject a scope filter the model's filterset cannot understand, rather than finding out at event time."""
        if not self.scope_filter:
            return
        if not isinstance(self.scope_filter, dict):
            raise ValidationError({"scope_filter": "Scope filter must be a dictionary of filter parameters."})
        if not self.present_in_database:
            # content_types is a M2M and is not populated until after the first save, so there is no model to
            # validate against yet. The form and serializer validate the filter at that point instead.
            return
        error = self.check_scope_filter(self.scope_filter, self.content_types.all())
        if error:
            raise ValidationError({"scope_filter": error})

    def _clean_conditions(self):
        """Reject condition rows that could not run: unknown preset, bad params, or an expression that won't compile.

        Validates without normalising. Blank rows are skipped here and stripped in `save()`, so `clean()`
        stays free of side effects and a caller that inspects `self.conditions` after validation sees what
        it passed in.
        """
        from nautobot.extras.choices import ConditionTypeChoices
        from nautobot.extras.conditions.engine import compile_condition, ConditionError
        from nautobot.extras.conditions.presets import get_condition_preset

        conditions = [] if self.conditions in (None, "") else self.conditions
        if not isinstance(conditions, list):
            raise ValidationError({"conditions": "Conditions must be a list of condition rows."})

        # Every bad row is reported, so a user with three malformed rows fixes them in one pass rather
        # than one save per row.
        problems = []

        for index, row in enumerate(conditions):
            label = f"Condition {index + 1}"

            # A blank row is what an untouched row on the form means and what an empty cell in a CSV
            # import means. In both cases the intent is "no condition here", not "a condition I got wrong".
            if row in (None, "", {}, []):
                continue

            if not isinstance(row, dict):
                problems.append(f"{label}: each condition must be a dictionary.")
                continue

            if "negate" in row and not isinstance(row["negate"], bool):
                problems.append(f"{label}: `negate` must be true or false.")
                continue

            row_type = row.get("type")
            if row_type == ConditionTypeChoices.TYPE_PRESET:
                preset = get_condition_preset(row.get("preset"))
                if preset is None:
                    problems.append(f"{label}: unknown preset `{row.get('preset')}`.")
                    continue
                try:
                    preset.clean_params(row.get("params"))
                except ValidationError as exc:
                    problems.append(f"{label}: {' '.join(exc.messages)}")
            elif row_type == ConditionTypeChoices.TYPE_EXPRESSION:
                source = row.get("source")
                if not isinstance(source, str) or not source.strip():
                    problems.append(f"{label}: an expression row requires a `source`.")
                    continue
                try:
                    compile_condition(source)
                except ConditionError as exc:
                    problems.append(f"{label}: {exc}")
            else:
                problems.append(
                    f"{label}: unknown condition type `{row_type}`. "
                    f"Expected `{ConditionTypeChoices.TYPE_PRESET}` or "
                    f"`{ConditionTypeChoices.TYPE_EXPRESSION}`."
                )

        if problems:
            raise ValidationError({"conditions": problems})
