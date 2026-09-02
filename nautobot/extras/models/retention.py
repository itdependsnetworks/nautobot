"""
The retention policy model.

`RetentionRule` decides what changelog truncation deletes. It is policy rather than retained history, so
it lives beside the archive models rather than among them: nothing here is written by rotation, and the
rule outlives every record it acts on.
"""

from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from nautobot.core.constants import CHARFIELD_MAX_LENGTH
from nautobot.core.models.generics import OrganizationalModel
from nautobot.extras.choices import RetentionRuleModeChoices
from nautobot.extras.constants import CHANGELOG_ARCHIVE_COVERED_MODELS
from nautobot.extras.models.mixins import ScopedFilterMixin
from nautobot.extras.utils import extras_features


@extras_features("custom_links", "custom_validators", "export_templates", "graphql", "webhooks")
class RetentionRule(ScopedFilterMixin, OrganizationalModel):
    """
    A filter-driven rule for what the truncation job deletes from warm storage.

    Rules are evaluated by `ChangelogTruncation`, which resolves `scope_filter` through the covered
    model's FilterSet. An `exclude` rule protects the records it matches, and wins over any `include`
    rule that would otherwise select them.

    The scope is expressed the same way a custom field's is -- `ScopedFilterMixin`, edited with the same
    filter builder -- so a rule selects exactly what the same filter selects in the UI or REST API, and an
    operator can check what a rule will do by running its filter on the change log first.

    This is an `OrganizationalModel` specifically so that edits to it are change-logged. A rule decides
    what gets deleted, so who changed it and when has to be auditable.
    """

    name = models.CharField(max_length=CHARFIELD_MAX_LENGTH, unique=True)
    description = models.CharField(max_length=CHARFIELD_MAX_LENGTH, blank=True, default="")
    enabled = models.BooleanField(default=True)
    content_type = models.ForeignKey(
        to="contenttypes.ContentType",
        # CASCADE: a rule scoped to a content type that no longer exists cannot be evaluated, and
        # leaving it behind would be a rule whose scope is unknowable.
        on_delete=models.CASCADE,
        related_name="retention_rules",
        help_text="The covered model this rule applies to.",
    )
    mode = models.CharField(
        max_length=16,
        choices=RetentionRuleModeChoices,
        default=RetentionRuleModeChoices.MODE_INCLUDE,
        help_text="Whether this rule selects records for deletion or protects them from it.",
    )
    scope_filter = models.JSONField(
        encoder=DjangoJSONEncoder,
        editable=False,
        default=dict,
        help_text="A JSON-encoded dictionary of filter parameters selecting the records this rule applies "
        "to. An empty filter matches every record of the content type.",
    )
    max_age_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Only records older than this many days are affected. Leave empty to apply regardless of age.",
    )
    weight = models.PositiveSmallIntegerField(
        default=100,
        help_text="Evaluation order. Lower weights are evaluated first.",
    )

    documentation_static_path = "docs/user-guide/platform-functionality/change-logging.html"
    natural_key_field_names = ["name"]

    class Meta:
        ordering = ["weight", "name"]
        verbose_name = "retention rule"
        verbose_name_plural = "retention rules"

    def clean(self):
        """
        A rule has to be one truncation can actually act on.

        Two ways it can fail to be, and both used to save cleanly and then do nothing: naming a model
        retention does not cover, and carrying a filter the model's FilterSet rejects. Either way the rule
        sits in the list looking enabled while truncation skips it, and the only evidence is a job log
        nobody is reading. Both are caught here so they land on the form, and so they land on the REST API
        too, which is the path that had no check at all.
        """
        super().clean()
        errors = {}
        if self.content_type_id:
            label = f"{self.content_type.app_label}.{self.content_type.model}"
            if label not in CHANGELOG_ARCHIVE_COVERED_MODELS:
                errors["content_type"] = (
                    f"Changelog retention does not cover {label}, so a rule for it would never apply. "
                    f"Covered models are: {', '.join(CHANGELOG_ARCHIVE_COVERED_MODELS)}."
                )
            else:
                self._validate_scope_filter(errors)
        if errors:
            raise ValidationError(errors)

    def _validate_scope_filter(self, errors):
        """
        Reject a filter the model's own FilterSet does not accept.

        Truncation refuses such a rule at run time rather than widening it, which is the safe behaviour but
        a late one: the rule sits in the list looking enabled and does nothing until someone reads a job
        log. The edit form already rejected it, so before this the REST API was the one way to store a
        filter the UI would not let you save.

        A model with no FilterSet is not the operator's problem and does not block the save; the job logs
        and skips that case. Anything the FilterSet raises other than a rejection is treated the same way,
        since a save is the wrong place to surface it and truncation remains the backstop.
        """
        if not self.scope_filter:
            return
        from nautobot.core.utils.lookup import get_filterset_for_model

        model = self.content_type.model_class()
        if model is None:
            return
        filterset_class = get_filterset_for_model(model)
        if filterset_class is None:
            return
        try:
            filterset = filterset_class(self.scope_filter, model.objects.all())
            valid = filterset.is_valid()
        except Exception:  # a broken FilterSet must not block the save; truncation still refuses
            return
        if not valid:
            # `filterset.errors` renders itself as an HTML `<ul>`, which is right for a form and wrong in a
            # REST response, so the messages are flattened to text.
            detail = "; ".join(
                f"{field}: {' '.join(str(message) for message in messages)}"
                for field, messages in filterset.errors.items()
            )
            errors["scope_filter"] = (
                f"The filter is not valid for {self.content_type.app_label}.{self.content_type.model}, so "
                f"truncation would refuse it. {detail}"
            )

    @property
    def scope_filter_model_class(self):
        """The model this rule's scope filters over: the covered model it is scoped to."""
        return self.content_type.model_class()

    def get_mode_class(self):
        """CSS class for the mode badge, as `ChoiceFieldColumn` renders it."""
        return RetentionRuleModeChoices.CSS_CLASSES.get(self.mode)

    def __str__(self):
        return self.name
