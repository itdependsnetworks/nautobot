import contextlib

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiTypes
from rest_framework import status
from rest_framework.authentication import BasicAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.viewsets import ViewSet

from nautobot.core.api.serializers import BulkOperationIntegerIDSerializer
from nautobot.core.api.views import ModelViewSet
from nautobot.core.models.querysets import RestrictedQuerySet
from nautobot.core.settings_funcs import is_truthy
from nautobot.core.utils.data import deepmerge
from nautobot.core.utils.orm_paths import find_relation_paths
from nautobot.users import filters
from nautobot.users.models import (
    ObjectPermission,
    PermissionPolicy,
    PolicyAssignment,
    PolicyParameter,
    PolicyRule,
    Token,
)
from nautobot.users.policies import (
    collect_user_grants,
    permission_names_for_rule,
    PolicyRenderError,
    preview_policy,
    render_rule_constraints,
    rule_content_type,
    validate_parameter_values,
)

from . import serializers


def _absolute_url(request, viewname, pk):
    return request.build_absolute_uri(reverse(viewname, kwargs={"pk": pk}))


def _effective_access_payload(user, request):
    """Build the effective-access response for `user`: every grant with the source that produced it."""
    grants = []
    for grant in collect_user_grants(user):
        source = {"type": grant.source_type, "id": str(grant.source.pk), "name": str(grant.source)}
        if grant.source_type == "objectpermission":
            source["url"] = _absolute_url(request, "users-api:objectpermission-detail", grant.source.pk)
        else:
            source["url"] = _absolute_url(request, "users-api:policyassignment-detail", grant.source.pk)
            source["policy"] = {
                "id": str(grant.policy.pk),
                "name": grant.policy.name,
                "url": _absolute_url(request, "users-api:permissionpolicy-detail", grant.policy.pk),
            }
        grants.append({**grant.as_dict(), "source": source})
    return {
        "user": {
            "id": str(user.pk),
            "username": user.username,
            "url": _absolute_url(request, "users-api:user-detail", user.pk),
        },
        "is_superuser": user.is_superuser,
        "grants": grants,
    }


#
# Users and groups
#


class UserViewSet(ModelViewSet):
    queryset = RestrictedQuerySet(model=get_user_model()).order_by("username")
    serializer_class = serializers.UserSerializer
    filterset_class = filters.UserFilterSet

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    @action(detail=True, methods=["get"], url_path="effective-access")
    def effective_access(self, request, pk=None):
        """
        The effective access of one user, from both stored permissions and policy assignments, with sources.

        A user may always read their own access. Reading another user's access requires permission to view
        users, object permissions and policy assignments.
        """
        user = self.get_object()
        if user.pk != request.user.pk and not (
            request.user.has_perm("users.view_objectpermission")
            and request.user.has_perm("users.view_policyassignment")
        ):
            raise PermissionDenied(
                "Viewing another user's effective access requires permission to view object permissions and "
                "policy assignments."
            )
        return Response(_effective_access_payload(user, request))

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    @action(
        detail=False,
        methods=["get"],
        url_path="effective-access",
        url_name="effective-access-self",
        permission_classes=[IsAuthenticated],
    )
    def own_effective_access(self, request):
        """The effective access of the requesting user."""
        return Response(_effective_access_payload(request.user, request))


@extend_schema_view(
    bulk_destroy=extend_schema(request=BulkOperationIntegerIDSerializer(many=True)),
)
class GroupViewSet(ModelViewSet):
    queryset = RestrictedQuerySet(model=Group).annotate(user_count=Count("user")).order_by("name")
    serializer_class = serializers.GroupSerializer
    bulk_operation_serializer_class = BulkOperationIntegerIDSerializer
    filterset_class = filters.GroupFilterSet


#
# REST API tokens
#


class TokenViewSet(ModelViewSet):
    queryset = RestrictedQuerySet(model=Token).select_related("user")  # pylint: disable=not-callable  # no idea why?
    serializer_class = serializers.TokenSerializer
    filterset_class = filters.TokenFilterSet

    @property
    def authentication_classes(self):
        """Inherit default authentication_classes and basic authentication."""
        classes = super().authentication_classes
        return [*classes, BasicAuthentication]

    def get_queryset(self):
        """
        Limit users to their own Tokens.
        """
        queryset = super().get_queryset()
        if not isinstance(self.request.user, AnonymousUser):
            return queryset.filter(user=self.request.user)
        return queryset.none()


#
# ObjectPermissions
#


class ObjectPermissionViewSet(ModelViewSet):
    queryset = ObjectPermission.objects.all()
    serializer_class = serializers.ObjectPermissionSerializer
    filterset_class = filters.ObjectPermissionFilterSet


#
# Permission policies
#


class PermissionPolicyViewPermissions(BasePermission):
    """Allow an action to any authenticated user who may view the permission policy (used for preview)."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated) and request.user.has_perm(
            "users.view_permissionpolicy"
        )

    def has_object_permission(self, request, view, obj):
        return request.user.has_perm("users.view_permissionpolicy", obj)


def _model_from_label(label, parameter):
    """Resolve an `app_label.model` query parameter to a model class, raising ValueError with a usable message."""
    if not label:
        raise ValueError(f"The '{parameter}' query parameter is required, as 'app_label.model'.")
    try:
        app_label, model_name = label.lower().split(".")
        content_type = ContentType.objects.get_by_natural_key(app_label, model_name)
    except (ValueError, ContentType.DoesNotExist):
        raise ValueError(f"'{label}' is not a known content type for '{parameter}'.")
    model = content_type.model_class()
    if model is None:
        raise ValueError(f"'{label}' is not an installed model.")
    return model


def _sample_payload(request, objects):
    sample = []
    for obj in objects:
        entry = {"id": str(obj.pk), "display": str(obj)}
        if hasattr(obj, "get_absolute_url"):
            # A model without a UI route is still previewable; it simply has no link.
            with contextlib.suppress(Exception):
                entry["url"] = request.build_absolute_uri(obj.get_absolute_url())
        sample.append(entry)
    return sample


class PermissionPolicyViewSet(ModelViewSet):
    queryset = PermissionPolicy.objects.annotate(assignment_count=Count("assignments", distinct=True))
    serializer_class = serializers.PermissionPolicySerializer
    filterset_class = filters.PermissionPolicyFilterSet

    def get_queryset(self):
        queryset = super().get_queryset()
        # The nested lists render each child's content type; fetch them with the children unless the lists are
        # excluded from the response altogether (`?exclude_m2m=true`), in which case nothing extra is needed.
        if not is_truthy(self.request.query_params.get("exclude_m2m", False)):
            queryset = queryset.prefetch_related("rules__content_type", "parameters__target_content_type")
        return queryset

    @extend_schema(
        parameters=[
            OpenApiParameter("content_type", str, required=True, description="Source model, as app_label.model"),
            OpenApiParameter("target_content_type", str, required=True, description="Target model, as app_label.model"),
        ],
        responses={200: OpenApiTypes.OBJECT},
    )
    @action(detail=False, methods=["get"], url_path="resolve-path")
    def resolve_path(self, request):
        """
        Propose lookup paths from one model to another across forward single-valued relations, shortest first.

        An empty `candidates` list is a normal response meaning no path exists.
        """
        try:
            source_model = _model_from_label(request.query_params.get("content_type"), "content_type")
            target_model = _model_from_label(request.query_params.get("target_content_type"), "target_content_type")
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        candidates = find_relation_paths(source_model, target_model)
        return Response(
            {
                "content_type": source_model._meta.label_lower,
                "target_content_type": target_model._meta.label_lower,
                "candidates": [candidate.as_dict() for candidate in candidates],
            }
        )

    @extend_schema(request=serializers.PolicyPreviewRequestSerializer, responses={200: OpenApiTypes.OBJECT})
    @action(detail=True, methods=["post"], permission_classes=[PermissionPolicyViewPermissions])
    def preview(self, request, pk=None):
        """
        Render this policy with the supplied parameter values and report, per object type, the match count and a
        sample of matching objects. The sample is limited to objects the requesting user can already view.

        Preview writes nothing, so it deliberately needs only the view permission (and is therefore open to
        read-only tokens). The object is fetched with a view-restricted queryset rather than `get_object()`, whose
        restriction would apply the `add` action to a POST.
        """
        policy = get_object_or_404(PermissionPolicy.objects.restrict(request.user, "view"), pk=pk)
        body = serializers.PolicyPreviewRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            values = validate_parameter_values(policy, body.validated_data["parameter_values"])
        except DjangoValidationError as exc:
            return Response({"parameter_values": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        try:
            rows = preview_policy(policy, values, request.user, sample_size=body.validated_data["limit"])
        except PolicyRenderError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {"results": [{**row.as_dict(), "sample": _sample_payload(request, row.sample)} for row in rows]}
        )


class PolicyParameterViewSet(ModelViewSet):
    queryset = PolicyParameter.objects.select_related("policy", "target_content_type")
    serializer_class = serializers.PolicyParameterSerializer
    filterset_class = filters.PolicyParameterFilterSet


class PolicyRuleViewSet(ModelViewSet):
    queryset = PolicyRule.objects.select_related("policy", "content_type")
    serializer_class = serializers.PolicyRuleSerializer
    filterset_class = filters.PolicyRuleFilterSet


class PolicyAssignmentViewSet(ModelViewSet):
    queryset = PolicyAssignment.objects.select_related("policy")
    serializer_class = serializers.PolicyAssignmentSerializer
    filterset_class = filters.PolicyAssignmentFilterSet

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "constraints":
            queryset = queryset.prefetch_related("policy__rules")
        return queryset

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    @action(detail=True, methods=["get"])
    def constraints(self, request, pk=None):
        """The constraints this assignment grants, per object type, as rendered by permission resolution."""
        assignment = self.get_object()
        rules = []
        for rule in assignment.policy.rules.all():
            try:
                constraints = render_rule_constraints(rule, assignment.parameter_values or {})
            except PolicyRenderError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            content_type = rule_content_type(rule)
            rules.append(
                {
                    "content_type": f"{content_type.app_label}.{content_type.model}",
                    "actions": list(rule.actions),
                    "permissions": permission_names_for_rule(rule),
                    "constraints": constraints,
                }
            )
        return Response(
            {
                "assignment": {
                    "id": str(assignment.pk),
                    "name": assignment.name,
                    "url": _absolute_url(request, "users-api:policyassignment-detail", assignment.pk),
                },
                "policy": {
                    "id": str(assignment.policy.pk),
                    "name": assignment.policy.name,
                    "url": _absolute_url(request, "users-api:permissionpolicy-detail", assignment.policy.pk),
                },
                "rules": rules,
            }
        )


#
# User preferences
#


class UserConfigViewSet(ViewSet):
    """
    An API endpoint via which a user can update his or her own config data (user preferences), but no one else's.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def list(self, request):
        """
        Return the config_data for the currently authenticated User.
        """
        return Response(request.user.config_data)

    @extend_schema(request=OpenApiTypes.OBJECT)
    def patch(self, request):
        """
        Update the config_data for the currently authenticated User.
        """
        # TODO: How can we validate this data?
        user = request.user
        user.config_data = deepmerge(user.config_data, request.data)
        user.save()

        return Response(user.config_data)
