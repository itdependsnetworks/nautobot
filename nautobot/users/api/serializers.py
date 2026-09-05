from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist, ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from nautobot.core.api import (
    BaseModelSerializer,
    ChoiceField,
    ContentTypeField,
    ValidatedModelSerializer,
)
from nautobot.users.choices import PolicyParameterKindChoices
from nautobot.users.models import (
    ObjectPermission,
    PERMISSION_OBJECT_TYPE_LIMIT_CHOICES,
    PermissionPolicy,
    PolicyParameter,
    PolicyRule,
    Token,
)


class UserSerializer(ValidatedModelSerializer):
    class Meta:
        model = get_user_model()
        exclude = ["user_permissions"]
        extra_kwargs = {"password": {"write_only": True, "required": False, "allow_null": True}}

    def validate(self, attrs):
        """Handle omission of a password by setting it to the unusable None value."""
        mock_password = False
        if "password" not in attrs and not self.partial:
            attrs["password"] = make_password(None)
            mock_password = True
        validated_data = super().validate(attrs)
        if mock_password:
            validated_data["password"] = None
        elif "password" in validated_data:
            validate_password(validated_data["password"], user=self.instance)
        return validated_data

    def create(self, validated_data):
        """
        Extract the password from validated data and set it separately to ensure proper hash generation.
        """
        password = validated_data.pop("password")
        user = super().create(validated_data)
        user.set_password(password)
        user.save()

        return user

    def update(self, instance, validated_data):
        """
        Extract the password from validated data and set it separately to ensure proper hash generation.
        """
        update_password = False
        password = None
        if "password" in validated_data:
            update_password = True
            password = validated_data.pop("password")
        elif not self.partial:
            update_password = True
        super().update(instance, validated_data)
        if update_password:
            instance.set_password(password)
            instance.save()
        return instance


class GroupSerializer(ValidatedModelSerializer):
    id = serializers.IntegerField(read_only=True)
    url = serializers.HyperlinkedIdentityField(view_name="users-api:group-detail")
    user_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Group
        exclude = ["permissions"]


class TokenSerializer(ValidatedModelSerializer):
    key = serializers.CharField(min_length=40, max_length=40, allow_blank=True, required=False)

    class Meta:
        model = Token
        exclude = ["user"]

    def to_internal_value(self, data):
        data = super().to_internal_value(data)
        if "key" not in data and not self.instance:
            data["key"] = Token.generate_key()
        data["user"] = self.context["request"].user
        return data


class ObjectPermissionSerializer(ValidatedModelSerializer):
    object_types = ContentTypeField(queryset=ContentType.objects.all(), many=True)
    actions = serializers.ListField(
        child=serializers.CharField(max_length=30),
        help_text="The list of actions granted by this permission",
    )

    class Meta:
        model = ObjectPermission
        fields = "__all__"


#
# Permission policies
#


class PolicyParameterSerializer(ValidatedModelSerializer):
    """A `PolicyParameter` on its own endpoint; `policy` is writable and the model's `clean()` runs on save."""

    target_content_type = ContentTypeField(queryset=ContentType.objects.all(), required=False, allow_null=True)
    kind = ChoiceField(choices=PolicyParameterKindChoices)

    class Meta:
        model = PolicyParameter
        fields = "__all__"


class PolicyParameterChildSerializer(BaseModelSerializer):
    """
    A `PolicyParameter` nested in `PermissionPolicySerializer`, which owns the policy: it sets `policy`, matches
    children by name (never by id, so a writable id would only receive a fresh default on PUT), and runs
    `full_clean()` itself once the parent is known.
    """

    id = serializers.UUIDField(read_only=True)
    target_content_type = ContentTypeField(queryset=ContentType.objects.all(), required=False, allow_null=True)
    kind = ChoiceField(choices=PolicyParameterKindChoices)

    class Meta:
        model = PolicyParameter
        fields = "__all__"
        read_only_fields = ["policy"]
        validators = []  # the (policy, name) unique_together is enforced by the parent serializer


class PolicyRuleSerializer(ValidatedModelSerializer):
    """A `PolicyRule` on its own endpoint; `policy` is writable and the model's `clean()` runs on save."""

    content_type = ContentTypeField(queryset=ContentType.objects.filter(PERMISSION_OBJECT_TYPE_LIMIT_CHOICES))
    actions = serializers.ListField(
        child=serializers.CharField(max_length=30),
        help_text="The list of actions granted on this object type",
    )
    constraint_template = serializers.JSONField(required=False)
    path_map = serializers.JSONField(required=False)

    class Meta:
        model = PolicyRule
        fields = "__all__"

    def validate(self, attrs):
        # PLACEHOLDER: will be replaced in C10 (Policy rule validation and rendering): generate an omitted
        # `constraint_template` from `path_map`.
        return super().validate(attrs)


class PolicyRuleChildSerializer(BaseModelSerializer):
    """A `PolicyRule` nested in `PermissionPolicySerializer`; see `PolicyParameterChildSerializer`."""

    id = serializers.UUIDField(read_only=True)
    content_type = ContentTypeField(queryset=ContentType.objects.filter(PERMISSION_OBJECT_TYPE_LIMIT_CHOICES))
    actions = serializers.ListField(
        child=serializers.CharField(max_length=30),
        help_text="The list of actions granted on this object type",
    )
    constraint_template = serializers.JSONField(required=False)
    path_map = serializers.JSONField(required=False)

    class Meta:
        model = PolicyRule
        fields = "__all__"
        read_only_fields = ["policy"]
        validators = []  # the (policy, content_type) unique_together is enforced by the parent serializer

    def validate(self, attrs):
        # PLACEHOLDER: will be replaced in C10 (Policy rule validation and rendering): generate an omitted
        # `constraint_template` from `path_map`.
        return super().validate(attrs)


class PermissionPolicySerializer(ValidatedModelSerializer):
    """
    A `PermissionPolicy` with its parameters and rules as writable nested lists.

    Children are saved in one transaction with the policy and validated against the final state, because the
    consistency rules (every parameter accounted for in every rule) span all of them. Children are matched by
    natural key (`name` for parameters, `content_type` for rules); children absent from a supplied list are
    deleted. Omit `parameters` or `rules` entirely on PATCH to leave them unchanged.
    """

    parameters = PolicyParameterChildSerializer(many=True, required=False)
    rules = PolicyRuleChildSerializer(many=True, required=False)

    class Meta:
        model = PermissionPolicy
        fields = "__all__"
        # Nested lists are treated like M2M fields: shown by default here, hidden with `?exclude_m2m=true`.
        default_m2m_fields = ("parameters", "rules")

    def validate(self, attrs):
        nested = {key: attrs.pop(key) for key in ("parameters", "rules") if key in attrs}
        attrs = super().validate(attrs)
        attrs.update(nested)
        return attrs

    def create(self, validated_data):
        parameters = validated_data.pop("parameters", None)
        rules = validated_data.pop("rules", None)
        with transaction.atomic():
            instance = super().create(validated_data)
            self._sync_children(instance, parameters, rules)
        return instance

    def update(self, instance, validated_data):
        parameters = validated_data.pop("parameters", None)
        rules = validated_data.pop("rules", None)
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            self._sync_children(instance, parameters, rules)
        return instance

    @staticmethod
    def _sync(policy, related_manager, items, key, errors, error_key):
        existing = {getattr(child, key): child for child in related_manager.all()}
        keep = set()
        seen = set()
        for index, item in enumerate(items):
            item_key = item.get(key)
            if item_key in seen:
                errors.setdefault(error_key, {})[index] = {key: [f"Duplicate entry for {key} '{item_key}'."]}
                continue
            seen.add(item_key)
            child = existing.get(item_key)
            changed = child is None
            if child is None:
                child = related_manager.model(policy=policy)
            for attribute, value in item.items():
                try:
                    current = getattr(child, attribute)
                except ObjectDoesNotExist:  # unset FK on a new child
                    current = None
                if current != value:
                    setattr(child, attribute, value)
                    changed = True
            try:
                child.full_clean()
            except DjangoValidationError as exc:
                errors.setdefault(error_key, {})[index] = exc.message_dict
                continue
            if changed:
                child.save()
            keep.add(getattr(child, key))
        for child_key, child in existing.items():
            if child_key not in keep:
                child.delete()

    def _sync_children(self, policy, parameters, rules):
        errors = {}
        if parameters is not None:
            self._sync(policy, policy.parameters, parameters, "name", errors, "parameters")
            if errors:
                raise ValidationError(errors)
        # Rule validation reads `policy.parameters`; drop any prefetched cache so it sees what was just saved.
        policy.refresh_from_db()
        if rules is not None:
            self._sync(policy, policy.rules, rules, "content_type", errors, "rules")
            if errors:
                raise ValidationError(errors)
        # PLACEHOLDER: will be replaced in C11 (Policy definition validation): validate the policy as a whole.


class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()

    def validate(self, attrs):
        user = authenticate(
            self.context["request"],
            username=attrs["username"],
            password=attrs["password"],
        )
        if not user:
            raise ValidationError("Invalid login credentials.")
        return {"user": user}
