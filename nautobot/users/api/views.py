from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiTypes
from rest_framework import status
from rest_framework.authentication import BasicAuthentication
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
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
    PolicyParameter,
    PolicyRule,
    Token,
)

from . import serializers

#
# Users and groups
#


class UserViewSet(ModelViewSet):
    queryset = RestrictedQuerySet(model=get_user_model()).order_by("username")
    serializer_class = serializers.UserSerializer
    filterset_class = filters.UserFilterSet


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


class PermissionPolicyViewSet(ModelViewSet):
    # PLACEHOLDER: will be replaced in C12 (Policy assignment model and stack): annotate assignment_count.
    queryset = PermissionPolicy.objects.all()
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


class PolicyParameterViewSet(ModelViewSet):
    queryset = PolicyParameter.objects.select_related("policy", "target_content_type")
    serializer_class = serializers.PolicyParameterSerializer
    filterset_class = filters.PolicyParameterFilterSet


class PolicyRuleViewSet(ModelViewSet):
    queryset = PolicyRule.objects.select_related("policy", "content_type")
    serializer_class = serializers.PolicyRuleSerializer
    filterset_class = filters.PolicyRuleFilterSet


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
