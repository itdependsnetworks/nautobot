import inspect
import json
import random
import string
from typing import ClassVar, Iterable, Optional

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Count, JSONField, Q, QuerySet
from django.db.models.fields import BooleanField, CharField, TextField
from django.db.models.fields.related import ManyToManyField
from django.db.models.fields.reverse_related import ManyToManyRel, ManyToOneRel
from django.test import tag
import django_filters
from django_filters import FilterSet
from django_filters.utils import get_model_field

from nautobot.core.constants import (
    CHARFIELD_MAX_LENGTH,
    FILTER_CHAR_BASED_LOOKUP_MAP,
    FILTER_NEGATION_LOOKUP_MAP,
    FILTER_NUMERIC_BASED_LOOKUP_MAP,
)
from nautobot.core.filters import (
    ContentTypeChoiceFilter,
    ContentTypeFilter,
    ContentTypeMultipleChoiceFilter,
    field_path_traverses_to_many,
    MappedPredicatesFilterMixin,
    NaturalKeyOrPKMultipleChoiceFilter,
    RelatedMembershipBooleanFilter,
    SearchFilter,
)
from nautobot.core.models.generics import PrimaryModel
from nautobot.core.testing import views
from nautobot.extras.choices import DynamicGroupTypeChoices
from nautobot.extras.models import Contact, ContactAssociation, DynamicGroup, Role, Status, Tag, Team
from nautobot.tenancy import models

# Suffixes of the `<filter>__<lookup>` filters that `BaseFilterSet` generates automatically from a base filter.
# Testing the base filter is considered to cover its generated lookups, as they share all of their logic.
_GENERATED_LOOKUP_SUFFIXES = frozenset(
    {
        *FILTER_CHAR_BASED_LOOKUP_MAP,
        *FILTER_NUMERIC_BASED_LOOKUP_MAP,
        *FILTER_NEGATION_LOOKUP_MAP,
        "isnull",
    }
)

# Filters that are present on (nearly) every FilterSet and that `test_filters_generic` adds to `generic_filter_tests`
# automatically when the FilterSet has them, so no test case needs to list them itself.
_AUTOMATIC_GENERIC_FILTER_TESTS = (
    ["created"],  # BaseModel field, auto-generated MultiValueDateTimeFilter
    ["last_updated"],  # BaseModel field, auto-generated MultiValueDateTimeFilter
    # Added by BaseFilterSet.get_filters() for contact-associable models:
    ["contacts", "associated_contacts__contact__name"],
    ["contacts", "associated_contacts__contact__id"],
    ["teams", "associated_contacts__team__name"],
    ["teams", "associated_contacts__team__id"],
)

# Prefixes of filters that are generated at runtime from database content rather than declared in code. They are
# tested centrally by the tests for the code that generates them, so `test_filters_coverage` doesn't require a test.
_FRAMEWORK_PROVIDED_FILTER_PREFIXES = (
    "cf_",  # CustomFieldModelFilterSetMixin, one filter per CustomField
    "cr_",  # RelationshipModelFilterSetMixin, one filter per Relationship side
)

# Filters that `FilterTestCase` tests itself, via a test method whose name doesn't follow the `test_<filter_name>`
# convention. `test_filters_coverage` treats them as covered whenever the test case has the named method.
_FRAMEWORK_TESTED_FILTERS = {
    "tags": "test_tags_filter",
    "q": "test_q_filter_valid",
    "dynamic_groups": "test_dynamic_groups_filter",
}


@tag("unit")
class FilterTestCases:
    class BaseFilterTestCase(views.TestCase):
        """Base class for testing of FilterSets."""

        queryset: ClassVar[Optional[QuerySet]] = None  # TODO: declared as Optional only to avoid a breaking change

        def get_filterset_test_values(self, field_name, queryset=None, *, raw=False):
            """Returns a list of distinct values from the requested queryset field to use in filterset tests.

            Returns a list for use in testing multiple choice filters. The size of the returned list is random
            but will contain at minimum 2 unique values. The list of values will match at least 2 instances when
            passed to the queryset's filter(field_name__in=[]) method but will fail to match at least one instance.

            Args:
                field_name (str): The name of the field to retrieve test values from.
                queryset (QuerySet): The queryset to retrieve test values. Defaults to `self.queryset`.
                raw (bool): Return the values as stored (e.g. a `dict` for a JSONField) instead of as strings.

            Returns:
                (list): A list of unique values derived from the queryset.

            Raises:
                ValueError: Raised if unable to find a combination of 2 or more unique values
                    to filter the queryset to a subset of the total instances.
            """
            test_values = []
            if queryset is None:
                queryset = self.queryset
            qs_count = queryset.count()
            values_with_count = queryset.values(field_name).annotate(count=Count(field_name)).order_by("count")
            for value in values_with_count:
                # randomly break out of loop after 2 values have been selected
                if len(test_values) > 1 and random.choice([True, False]):  # noqa: S311  # suspicious-non-cryptographic-random-usage
                    break
                if value[field_name] and value["count"] < qs_count:
                    qs_count -= value["count"]
                    test_values.append(value[field_name] if raw else str(value[field_name]))

            if len(test_values) < 2:
                raise ValueError(
                    f"Cannot find enough valid test data for {queryset.model._meta.object_name} field {field_name}. "
                    "At least 3 unique values are required to test multivalue filters."
                )
            return test_values

    class FilterTestCase(BaseFilterTestCase):
        """Add common tests for all FilterSets."""

        filterset: ClassVar[Optional[type[FilterSet]]] = None  # TODO: declared Optional only to avoid breaking change

        # filter predicate fields that should be excluded from q test case
        exclude_q_filter_predicates = []

        # list of filters to be tested by `test_filters_generic`
        # list of iterables with filter name and optional field name
        # example:
        #   generic_filter_tests = [
        #       ["filter1"],
        #       ["filter2", "field2__name"],
        #   ]
        generic_filter_tests: ClassVar[Iterable] = ()

        # Filters that are known to have no test yet. `test_filters_coverage` fails on any filter that is neither
        # tested nor listed here, and also fails if an entry here is stale (no such filter, or the filter has since
        # gained a test), so this list can only ever shrink truthfully. Treat it as a to-do list, not a permanent
        # exemption. Prefer any of the alternatives listed in `test_filters_coverage` over adding an entry here.
        untested_filters: ClassVar[Iterable[str]] = ()

        def setUp(self):
            for attr in ["queryset", "filterset", "generic_filter_tests"]:
                if not hasattr(self, attr):
                    raise NotImplementedError(f'{self} is missing a value for required attribute "{attr}"')
            super().setUp()

        def get_q_filter(self):
            """Helper method to return q filter."""
            self.assertIsNotNone(self.filterset)
            return self.filterset.declared_filters["q"].filter_predicates

        def test_no_distinct_on_empty_filter_params(self):
            """Verify that an empty filterset doesn't cause a `SELECT DISTINCT`."""
            self.assertIsNotNone(self.filterset)
            filterset = self.filterset({}, self.queryset)  # pylint: disable=not-callable  # see assertion above
            self.assertTrue(filterset.is_valid())
            self.assertNotIn(
                "SELECT DISTINCT",
                str(filterset.qs.query),
                "Filter set with empty parameter added `DISTINCT` to select query. This needs to be avoided because it incurs heavy performance penalties.",
            )

        _DISTINCT_REMEDIATION = (
            "To fix each of them:\n"
            "  1. If the filter is declared using a `django_filters` class, switch to the Nautobot class of the "
            "same name from `nautobot.apps.filters`, which derives `distinct` from the field path automatically "
            "so that you don't need to declare it at all. This requires a minimum Nautobot version of 3.2.4: "
            "`MultipleChoiceFilter` and `BooleanFilter` were *added* to `nautobot.apps.filters` in 3.2.4, so "
            "importing them from an earlier version raises `ImportError`, while `ModelMultipleChoiceFilter` and "
            "the `MultiValue<type>Filter` classes already existed but only gained the derivation in 3.2.4.\n"
            "  2. If your App supports Nautobot versions earlier than 3.2.4, or the filter's `field_name` is "
            "not a real model field path (as with `RelationshipFilter`), declare `distinct={distinct_value}` "
            "explicitly on the filter instead, with a comment explaining why.\n"
            "Note that `distinct` has no effect on a filter that declares a `method`; such a filter is "
            "responsible for calling `.distinct()` itself where needed, and is not checked by this test."
        )

        def test_filters_distinct(self):
            """Verify that each filter applies `.distinct()` if and only if it traverses a to-many relation.

            A filter that traverses a to-many relation (a many-to-many field, a reverse foreign key, or a generic
            relation) must apply `.distinct()`, as the underlying SQL join can otherwise return the same object
            more than once. Any other filter applying `.distinct()` incurs database overhead for no benefit.

            Nautobot's filter classes derive this automatically, so a failure here usually means either that the
            filter uses a `django_filters` class rather than the Nautobot equivalent of the same name, or that its
            `field_name` doesn't describe the relation that the filter actually traverses.
            """

            if not self.__class__.__module__.startswith("nautobot."):
                # TODO: Enable this once we have fixed any issues with apps that would fail this test.
                # For now, we want to be able to run this test in core without it being a problem to apps.
                self.skipTest("Skipping: currently only runs in nautobot core test suite.")

            self.assertIsNotNone(self.filterset)
            filterset = self.filterset({}, self.queryset)  # pylint: disable=not-callable  # see assertion above
            model = self.queryset.model
            should_be_distinct = []
            should_not_be_distinct = []

            for filter_name, filter_field in filterset.filters.items():
                # `distinct` has no effect on a filter with a `method`, as django-filter replaces its `filter()`
                if filter_field.method:
                    continue
                if isinstance(filter_field, MappedPredicatesFilterMixin):
                    # A `q`-style filter ORs all of its predicates into one `.filter()` call, so it needs
                    # `.distinct()` if any one of those predicates traverses a to-many relation.
                    paths = list(filter_field.filter_predicates)
                    label = f"{filter_name} (filter_predicates={paths})"
                elif isinstance(filter_field, (django_filters.MultipleChoiceFilter, django_filters.BooleanFilter)):
                    paths = [filter_field.field_name]
                    label = f"{filter_name} (field_name={filter_field.field_name!r})"
                else:
                    continue
                results = [field_path_traverses_to_many(model, path) for path in paths]
                if any(result is None for result in results):
                    # Not a resolvable model field path, so there's nothing to derive an expectation from
                    continue
                traverses_to_many = any(results)
                # `RelatedMembershipBooleanFilter` repurposes `exclude` as a lookup value rather than as an
                # instruction to negate, so it doesn't get the "`.exclude()` is a subquery" exemption.
                negates = filter_field.exclude and getattr(filter_field, "exclude_uses_subquery", True)
                if traverses_to_many and not negates and not filter_field.distinct:
                    should_be_distinct.append(label)
                elif not traverses_to_many and filter_field.distinct:
                    should_not_be_distinct.append(label)

            self.assertEqual(
                should_be_distinct,
                [],
                f"The above {self.filterset.__name__} filters traverse a to-many relation (a many-to-many field, "
                "a reverse foreign key, or a generic relation) but do not apply `.distinct()`, so they can return "
                "the same object more than once.\n" + self._DISTINCT_REMEDIATION.format(distinct_value="True"),
            )
            self.assertEqual(
                should_not_be_distinct,
                [],
                f"The above {self.filterset.__name__} filters apply `.distinct()` without traversing a to-many "
                "relation. `.distinct()` cannot change the result in that case, and is a significant database "
                "cost at scale.\n" + self._DISTINCT_REMEDIATION.format(distinct_value="False"),
            )

        @staticmethod
        def _is_generated_lookup_filter(filter_name, filter_names):
            """Whether `filter_name` is a `<filter>__<lookup>` variant that `BaseFilterSet` generated from a base filter."""
            if "__" not in filter_name:
                return False
            base_name, lookup = filter_name.rsplit("__", 1)
            return lookup in _GENERATED_LOOKUP_SUFFIXES and base_name in filter_names

        def _get_app_extension_filter_names(self):
            """Names of filters added to the FilterSet under test by an installed App's `FilterExtension`."""
            model_label = self.queryset.model._meta.label_lower
            names = set()
            for app_config in apps.get_app_configs():
                features = getattr(app_config, "features", None) or {}
                for entry in features.get("filter_extensions", {}).get("filterset_fields", []):
                    # Entries are recorded by NautobotAppConfig.ready() as "<app_label>.<model> -> <filter_name>"
                    model, _, filter_name = entry.partition(" -> ")
                    if model.lower() == model_label:
                        names.add(filter_name)
            return names

        def _get_filter_coverage(self):
            """Compute which filters on `self.filterset` are and aren't exercised by this test case.

            Returns:
                (dict): With keys:
                    `filter_names` (set): every filter on the FilterSet.
                    `requiring_coverage` (set): the filters this test case is responsible for testing.
                    `covered` (set): the filters that have a test.
            """
            self.assertIsNotNone(self.filterset)
            filterset = self.filterset()  # pylint: disable=not-callable  # see assertion above
            filter_names = set(filterset.filters)
            extension_names = self._get_app_extension_filter_names()
            requiring_coverage = {
                name
                for name in filter_names
                if not self._is_generated_lookup_filter(name, filter_names)
                and not name.startswith(_FRAMEWORK_PROVIDED_FILTER_PREFIXES)
                and name not in extension_names
            }

            covered = {test[0] for test in self.generic_filter_tests}
            covered |= {test[0] for test in self._get_automatic_generic_filter_tests()}
            # `test_boolean_filters_generic` exercises every boolean filter it knows how to test
            covered |= {
                name for name in requiring_coverage if self._generic_boolean_filter_kind(filterset.filters[name])
            }

            # A method named `test_<filter_name>` exercises that filter
            test_method_names = {
                method_name
                for method_name, _ in inspect.getmembers(type(self), predicate=inspect.isfunction)
                if method_name.startswith("test_")
            }
            covered |= {method_name[len("test_") :] for method_name in test_method_names}
            covered |= {
                name for name, method_name in _FRAMEWORK_TESTED_FILTERS.items() if method_name in test_method_names
            }
            if isinstance(self, FilterTestCases.TenancyFilterTestCaseMixin):
                # Its `test_tenant` exercises both `tenant` and `tenant_id`; `test_tenant_group` is covered by name
                covered.add("tenant_id")

            return {
                "filter_names": filter_names,
                "requiring_coverage": requiring_coverage,
                "covered": covered,
            }

        def test_filters_coverage(self):
            """Verify that every filter on the FilterSet has a test, or is explicitly acknowledged in `untested_filters`.

            Line coverage can't tell that a filter was never exercised, as a filter's logic mostly lives in
            django-filter and in Nautobot's shared filter classes. This test instead checks that every filter the
            FilterSet declares is named by at least one test. A filter counts as tested if any of these is true:

            - It is the first item of an entry in `generic_filter_tests`.
            - It is a `RelatedMembershipBooleanFilter` without a custom `method`, which
              `test_boolean_filters_generic` exercises automatically.
            - This test case has a test method named `test_<filter_name>`. This is the convention for every custom
              filter test, so that what each test covers can be read from its name.

            The filters that `FilterTestCase` tests itself never need a test in a subclass: `id`, `created`,
            `last_updated`, `contacts`, `teams` (via `test_filters_generic`), `tags`, `q` and `dynamic_groups`.
            Not checked at all, as they are generated at runtime and tested centrally: custom field (`cf_*`) and
            relationship (`cr_*`) filters, filters added by an App's `FilterExtension`, and the `<filter>__<lookup>`
            variants that `BaseFilterSet` generates from each base filter.

            Any other filter without a test must be listed in `untested_filters`. That list is checked for staleness
            too: an entry that doesn't name a filter, or names a filter that now has a test, fails this test.
            """
            if not self.__class__.__module__.startswith("nautobot."):
                # TODO: Enable this once we have fixed any issues with apps that would fail this test.
                # For now, we want to be able to run this test in core without it being a problem to apps.
                self.skipTest("Skipping: currently only runs in nautobot core test suite.")

            coverage = self._get_filter_coverage()
            untested = set(self.untested_filters)

            with self.subTest("Every filter is exercised by a test"):
                missing = sorted(coverage["requiring_coverage"] - coverage["covered"] - untested)
                self.assertEqual(
                    missing,
                    [],
                    f"The above {self.filterset.__name__} filters are not exercised by any test in "
                    f"{type(self).__name__}. To fix each of them, do one of the following:\n"
                    "  1. Add a `generic_filter_tests` entry for the filter, if it's a multiple-choice filter whose "
                    "results match a `queryset.filter(<field>__in=...)` call.\n"
                    "  2. Write a test method named `test_<filter_name>`, or rename the existing test that "
                    "exercises the filter to follow that convention.\n"
                    "  3. As a last resort, add the filter name to `untested_filters` on this test case to record "
                    "that it still needs a test.",
                )

            with self.subTest("`untested_filters` names only filters that exist and are untested"):
                not_a_filter = sorted(untested - coverage["requiring_coverage"])
                self.assertEqual(
                    not_a_filter,
                    [],
                    f"The above `untested_filters` entries on {type(self).__name__} don't name a filter on "
                    f"{self.filterset.__name__} that requires a test (see `test_filters_coverage`); remove them.",
                )
                now_covered = sorted(untested & coverage["covered"])
                self.assertEqual(
                    now_covered,
                    [],
                    f"The above `untested_filters` entries on {type(self).__name__} now have a test; remove them.",
                )

        def test_id(self):
            """Verify that the filterset supports filtering by id with only lookup `__n`."""
            self.assertIsNotNone(self.filterset)

            with self.subTest("Assert `id`"):
                params = {"id": list(self.queryset.values_list("pk", flat=True)[:2])}
                expected_queryset = self.queryset.filter(id__in=params["id"])
                filterset = self.filterset(params, self.queryset)  # pylint: disable=not-callable  # see assertion above
                self.assertTrue(filterset.is_valid())
                self.assertQuerySetEqualAndNotEmpty(filterset.qs.order_by("id"), expected_queryset.order_by("id"))

            with self.subTest("Assert negate lookup"):
                params = {"id__n": list(self.queryset.values_list("pk", flat=True)[:2])}
                expected_queryset = self.queryset.exclude(id__in=params["id__n"])
                filterset = self.filterset(params, self.queryset)  # pylint: disable=not-callable  # see assertion above
                self.assertTrue(filterset.is_valid())
                self.assertQuerySetEqualAndNotEmpty(filterset.qs.order_by("id"), expected_queryset.order_by("id"))

            with self.subTest("Assert invalid lookup"):
                params = {"id__in": list(self.queryset.values_list("pk", flat=True)[:2])}
                filterset = self.filterset(params, self.queryset)  # pylint: disable=not-callable  # see assertion above
                self.assertFalse(filterset.is_valid())
                self.assertIn("Unknown filter field", filterset.errors.as_text())

        def test_invalid_filter(self):
            """Verify that the filterset reports as invalid when initialized with an unsupported filter parameter."""
            params = {"ice_cream_flavor": ["chocolate"]}
            self.assertIsNotNone(self.filterset)
            self.assertFalse(self.filterset(params, self.queryset).is_valid())  # pylint: disable=not-callable

        def _get_automatic_generic_filter_tests(self):
            """Entries from `_AUTOMATIC_GENERIC_FILTER_TESTS` that apply to `self.filterset` and aren't already listed.

            An entry only applies if the FilterSet has the filter and the model has the field it filters on. (Some
            FilterSets for `BaseModel`-only through models declare `created`/`last_updated` filters via
            `CreatedUpdatedModelFilterSetMixin` although their model lacks those fields; such filters can't be tested.)
            """
            declared = {test[0] for test in self.generic_filter_tests}
            model = self.queryset.model
            applicable = []
            for test in _AUTOMATIC_GENERIC_FILTER_TESTS:
                if test[0] not in self.filterset.base_filters or test[0] in declared:
                    continue
                if test[0] in ("contacts", "teams") and not getattr(model, "is_contact_associable_model", False):
                    # Contact and Team themselves declare `contacts`/`teams` filters with different semantics
                    continue
                try:
                    model._meta.get_field(test[-1].split("__", 1)[0])
                except FieldDoesNotExist:
                    continue
                applicable.append(test)
            return applicable

        def test_filters_generic(self):
            """Test all multiple choice filters declared in `self.generic_filter_tests`.

            The `created` and `last_updated` filters that every model has, and the `contacts` and `teams` filters of
            contact-associable models, are tested automatically without needing to be listed.

            This test uses `get_filterset_test_values()` to retrieve a valid set of test data and asserts
            that the filterset filter output matches the corresponding queryset filter.
            The majority of Nautobot filters use conjoined=False, so the extra logic to support conjoined=True has not
            been implemented here. TagFilter and similar "AND" filters are not supported.

            Examples:
                Multiple tests can be performed for the same filter by adding multiple entries in
                `generic_filter_tests` with explicit field names.
                For example, to test a NaturalKeyOrPKMultipleChoiceFilter, use:
                    generic_filter_tests = (
                        ["filter_name", "field_name__name"],
                        ["filter_name", "field_name__id"],
                    )

                If a field name is not declared, the filter name will be used for the field name:
                    generic_filter_tests = (
                        ["devices"],
                    )
                This expects a field named `devices` on the model and a filter named `devices` on the filterset.
            """
            if not any(test[0] == "id" for test in self.generic_filter_tests):
                self.generic_filter_tests = (["id"], *self.generic_filter_tests)

            self.generic_filter_tests = (*self.generic_filter_tests, *self._get_automatic_generic_filter_tests())

            if getattr(self.queryset.model, "is_contact_associable_model", False):
                # Make sure we have at least 3 contacts and 3 teams in the database
                if Contact.objects.count() < 3:
                    Contact.objects.create(name="Generic Filter Test Contact 1")
                    Contact.objects.create(name="Generic Filter Test Contact 2")
                    Contact.objects.create(name="Generic Filter Test Contact 3")

                if Team.objects.count() < 3:
                    Team.objects.create(name="Generic Filter Test Team 1")
                    Team.objects.create(name="Generic Filter Test Team 2")
                    Team.objects.create(name="Generic Filter Test Team 3")

                # Make sure we have some valid contact-associations:
                if not Role.objects.get_for_model(ContactAssociation).exists():
                    contact_role, _ = Role.objects.get_or_create(name="Administration")
                    contact_role.content_types.add(ContentType.objects.get_for_model(ContactAssociation))

                if not Status.objects.get_for_model(ContactAssociation).exists():
                    contact_status, _ = Status.objects.get_or_create(name="Active")
                    contact_status.content_types.add(ContentType.objects.get_for_model(ContactAssociation))

                for contact, team, instance in zip(Contact.objects.all()[:3], Team.objects.all()[:3], self.queryset):
                    ContactAssociation.objects.create(
                        contact=contact,
                        associated_object=instance,
                        role=Role.objects.get_for_model(ContactAssociation).first(),
                        status=Status.objects.get_for_model(ContactAssociation).first(),
                    )
                    ContactAssociation.objects.create(
                        team=team,
                        associated_object=instance,
                        role=Role.objects.get_for_model(ContactAssociation).last(),
                        status=Status.objects.get_for_model(ContactAssociation).last(),
                    )

            if self.generic_filter_tests:
                self.assertIsNotNone(self.filterset)

            for test in self.generic_filter_tests:
                filter_name = test[0]
                field_name = test[-1]  # default to filter_name if a second list item was not supplied
                with self.subTest(f"{self.filterset.__name__} filter {filter_name} ({field_name})"):
                    self.assertIn(filter_name, self.filterset.base_filters)
                    lookup_expr = self.filterset.base_filters[filter_name].lookup_expr
                    if lookup_expr in ("exact", "in"):
                        test_data = self.get_filterset_test_values(field_name)
                        qs_result = self.queryset.filter(**{f"{field_name}__in": test_data})
                    else:
                        # A filter with another lookup (e.g. the `icontains` that `BaseFilterSet` gives JSONFields)
                        # ORs that lookup across its values, so the expected queryset must do the same.
                        model_field = get_model_field(self.queryset.model, field_name)
                        test_data = [
                            self._lookup_test_value(value, model_field, lookup_expr)
                            for value in self.get_filterset_test_values(field_name, raw=True)
                        ]
                        query = Q()
                        for value in test_data:
                            query |= Q(**{f"{field_name}__{lookup_expr}": value})
                        qs_result = self.queryset.filter(query)
                    params = {filter_name: test_data}
                    filterset = self.filterset(params, self.queryset)  # pylint: disable=not-callable
                    self.assertTrue(filterset.is_valid(), filterset.errors.as_text())
                    self.assertQuerySetEqualAndNotEmpty(filterset.qs, qs_result.distinct(), ordered=False)

        @staticmethod
        def _lookup_test_value(value, model_field, lookup_expr):
            """Turn a stored field value into a parameter suitable for `lookup_expr` on `model_field`.

            For a JSONField under a text lookup such as `icontains`, the database compares against the JSON text,
            in which the Python `repr()` of a `dict` or `list` never appears. Use a fragment that does: a quoted key
            for a mapping, the first element for a list, or the JSON encoding of a scalar.
            """
            if isinstance(model_field, JSONField) and lookup_expr in ("contains", "icontains"):
                if isinstance(value, dict):
                    return json.dumps(next(iter(value)))
                if isinstance(value, list):
                    return json.dumps(value[0])
                if isinstance(value, str):
                    return value
                return json.dumps(value)
            return str(value)

        def test_automagic_filters(self):
            """https://github.com/nautobot/nautobot/issues/6656"""
            self.assertIsNotNone(self.filterset)
            fs = self.filterset()  # pylint: disable=not-callable
            if getattr(self.queryset.model, "is_contact_associable_model", False):
                self.assertIsInstance(fs.filters["contacts"], NaturalKeyOrPKMultipleChoiceFilter)
                self.assertIsInstance(fs.filters["contacts__n"], NaturalKeyOrPKMultipleChoiceFilter)
                self.assertIsInstance(fs.filters["teams"], NaturalKeyOrPKMultipleChoiceFilter)
                self.assertIsInstance(fs.filters["teams__n"], NaturalKeyOrPKMultipleChoiceFilter)

            if getattr(self.queryset.model, "is_dynamic_group_associable_model", False):
                self.assertIsInstance(fs.filters["dynamic_groups"], NaturalKeyOrPKMultipleChoiceFilter)
                self.assertIsInstance(fs.filters["dynamic_groups__n"], NaturalKeyOrPKMultipleChoiceFilter)

        def _generic_boolean_filter_kind(self, filter_object):
            """Classify a filter for `test_boolean_filters_generic`.

            Returns:
                (str | None): `"membership"` for a `RelatedMembershipBooleanFilter`, `"plain"` for any other
                    `BooleanFilter` that does an exact match on a model `BooleanField`, or `None` if the filter has a
                    custom `method` or is otherwise not testable generically.
            """
            if not isinstance(filter_object, django_filters.BooleanFilter) or filter_object.method is not None:
                return None
            if isinstance(filter_object, RelatedMembershipBooleanFilter):
                return "membership"
            if filter_object.lookup_expr != "exact":
                return None
            model_field = get_model_field(self.queryset.model, filter_object.field_name)
            if isinstance(model_field, BooleanField):
                return "plain"
            return None

        def test_boolean_filters_generic(self):
            """Test all boolean filters found in `self.filterset.filters` that don't have a custom `method`.

            For a `RelatedMembershipBooleanFilter`, asserts that `filter=True` matches
            `self.queryset.filter(field__isnull=...)` and that `filter=False` matches
            `self.queryset.exclude(field__isnull=...)`.

            For any other `BooleanFilter` doing an exact match on a model `BooleanField`, asserts that each of
            `filter=True` and `filter=False` matches `self.queryset.filter(field=value)` (or `.exclude()` if the filter
            declares `exclude=True`), and that at least one of the two returns something.
            """
            self.assertIsNotNone(self.filterset)
            for filter_name, filter_object in self.filterset().filters.items():  # pylint: disable=not-callable
                kind = self._generic_boolean_filter_kind(filter_object)
                if kind is None:
                    continue
                field_name = filter_object.field_name
                if kind == "plain":
                    results = []
                    for value in (True, False):
                        with self.subTest(f"{self.filterset.__name__} BooleanFilter {filter_name} ({value})"):
                            filterset_result = self.filterset({filter_name: value}, self.queryset).qs  # pylint: disable=not-callable
                            if filter_object.exclude:
                                qs_result = self.queryset.exclude(**{field_name: value})
                            else:
                                qs_result = self.queryset.filter(**{field_name: value})
                            self.assertQuerySetEqual(filterset_result, qs_result, ordered=False)
                            results.append(qs_result.exists())
                    with self.subTest(f"{self.filterset.__name__} BooleanFilter {filter_name} (has data)"):
                        self.assertTrue(
                            any(results),
                            f"Neither {filter_name}=True nor {filter_name}=False matched anything in the test data",
                        )
                    continue
                with self.subTest(f"{self.filterset.__name__} RelatedMembershipBooleanFilter {filter_name} (True)"):
                    filterset_result = self.filterset({filter_name: True}, self.queryset).qs  # pylint: disable=not-callable
                    qs_result = self.queryset.filter(**{f"{field_name}__isnull": filter_object.exclude}).distinct()
                    self.assertQuerySetEqualAndNotEmpty(filterset_result, qs_result)
                with self.subTest(f"{self.filterset.__name__} RelatedMembershipBooleanFilter {filter_name} (False)"):
                    filterset_result = self.filterset({filter_name: False}, self.queryset).qs  # pylint: disable=not-callable
                    qs_result = self.queryset.exclude(**{f"{field_name}__isnull": filter_object.exclude}).distinct()
                    self.assertQuerySetEqualAndNotEmpty(filterset_result, qs_result)

        def test_dynamic_groups_filter(self):
            """Test the `dynamic_groups` filter that `BaseFilterSet` adds for every dynamic-group-associable model."""
            self.assertIsNotNone(self.filterset)
            if "dynamic_groups" not in self.filterset.base_filters:
                self.skipTest("Not a dynamic-group-associable model")

            model = self.queryset.model
            content_type = ContentType.objects.get_for_model(model)
            # test_id already requires at least 3 instances, so that filtering to 2 of them is a proper subset
            instances = list(self.queryset[:2])
            self.assertEqual(len(instances), 2)
            groups = []
            for instance in instances:
                group = DynamicGroup.objects.create(
                    name=f"Filter test static group {len(groups)} for {model._meta.label_lower}",
                    content_type=content_type,
                    group_type=DynamicGroupTypeChoices.TYPE_STATIC,
                )
                group.add_members([instance])
                groups.append(group)

            params = {"dynamic_groups": [groups[0].name, groups[1].pk]}
            filterset = self.filterset(params, self.queryset)  # pylint: disable=not-callable  # see assertion above
            self.assertTrue(filterset.is_valid(), filterset.errors)
            self.assertQuerySetEqualAndNotEmpty(
                filterset.qs,
                self.queryset.filter(pk__in=[instance.pk for instance in instances]),
                ordered=False,
            )

        def test_tags_filter(self):
            """Test the `tags` filter which should be present on all PrimaryModel filtersets."""
            if not issubclass(self.queryset.model, PrimaryModel):
                self.skipTest("Not a PrimaryModel")

            self.assertIsNotNone(self.filterset)

            # Find an instance with at least two tags (should be common given our factory design)
            for instance in list(self.queryset):
                if len(instance.tags.all()) >= 2:
                    tags = list(instance.tags.all()[:2])
                    break

            # Otherwise, create some tags and apply to an instance for this test
            else:
                model_ct = ContentType.objects.get_for_model(self.queryset.model)
                test_tags_filter_a = Tag.objects.get_or_create(name="test tags filter a")[0]
                test_tags_filter_a.content_types.add(model_ct)
                test_tags_filter_b = Tag.objects.get_or_create(name="test tags filter b")[0]
                test_tags_filter_b.content_types.add(model_ct)
                self.queryset.first().tags.add(test_tags_filter_a, test_tags_filter_b)
                tags = [test_tags_filter_a, test_tags_filter_b]
            params = {"tags": [tags[0].name, tags[1].pk]}
            filterset_result = self.filterset(params, self.queryset).qs  # pylint: disable=not-callable
            # Tags is an AND filter not an OR filter
            qs_result = self.queryset.filter(tags=tags[0]).filter(tags=tags[1]).distinct()
            self.assertQuerySetEqualAndNotEmpty(filterset_result, qs_result)

        def _assert_valid_filter_predicates(self, obj, field_name):
            self.assertTrue(
                hasattr(obj, field_name),
                f"`{field_name}` is an Invalid `q` filter predicate for `{self.filterset.__name__}`",
            )

        def _get_nested_related_obj_and_its_field_name(self, obj, model_field_name):
            """
            Get the nested related object and its field name.

            Args:
                obj: The object to extract the related object from.
                model_field_name: The field name containing the related object.

            Examples:
                >>> _get_nested_related_obj_and_its_field_name(<RelationshipAssociation: One>, "relationship__label")
                (<Relationship: RelationshipExample>, "label")
                >>> _get_nested_related_obj_and_its_field_name(<Device: DeviceOne>, "rack__rack_group__name")
                (<RackGroup: RackGroupExample>, "name")

            Returns:
                Tuple: A tuple containing the related object and its field name.
            """
            rel_obj = obj
            rel_obj_field_name = model_field_name
            while "__" in rel_obj_field_name:
                filter_field_name, rel_obj_field_name = rel_obj_field_name.split("__", 1)
                field = rel_obj._meta.get_field(filter_field_name)
                if isinstance(field, (ManyToOneRel, ManyToManyRel, ManyToManyField)):
                    rel_obj = getattr(rel_obj, filter_field_name).first()
                else:
                    rel_obj = getattr(rel_obj, filter_field_name)
            return rel_obj, rel_obj_field_name

        def _assert_q_filter_predicate_validity(self, obj, obj_field_name, filter_field_name, lookup_method):
            """
            Assert the validity of a `q` filter predicate.

            Args:
                obj: The object to filter.
                obj_field_name: The field name of the object to filter.
                filter_field_name: The field name of the FilterSet q filter predicate to test.
                lookup_method: The method used for the lookup e.g icontains.
            """
            self._assert_valid_filter_predicates(obj, obj_field_name)

            self.assertIsNotNone(self.filterset)

            # Generic test only supports CharField or TextFields, skip all other types
            obj_field = obj._meta.get_field(obj_field_name)
            if not isinstance(obj_field, (CharField, TextField)):
                self.skipTest("Not a CharField or TextField")

            original_value = getattr(obj, obj_field_name)
            # Create random lowercase string to use for icontains lookup
            max_length = obj_field.max_length or CHARFIELD_MAX_LENGTH
            randomized_attr_value = "".join(random.choices(string.ascii_lowercase, k=max_length))  # noqa: S311 # pseudo-random generator
            try:
                setattr(obj, obj_field_name, randomized_attr_value)
                obj.save()

                # if lookup_method is iexact use the full updated attr
                if lookup_method == "iexact":
                    lookup = randomized_attr_value.upper()
                    model_queryset = self.queryset.filter(**{f"{filter_field_name}__iexact": lookup})
                else:
                    lookup = randomized_attr_value[1:].upper()
                    model_queryset = self.queryset.filter(**{f"{filter_field_name}__icontains": lookup})
                params = {"q": lookup}
                filterset_result = self.filterset(params, self.queryset)  # pylint: disable=not-callable

                self.assertTrue(filterset_result.is_valid())
                self.assertQuerySetEqualAndNotEmpty(
                    filterset_result.qs,
                    model_queryset,
                    ordered=False,
                    msg=lookup,
                )
            finally:
                setattr(obj, obj_field_name, original_value)
                obj.save()

        def _get_relevant_filterset_queryset(self, queryset, *filter_params):
            """Gets the relevant queryset based on filter parameters."""

            q_query = Q()
            for param in filter_params:
                q_query &= Q(**{f"{param}__isnull": False})
            queryset = queryset.filter(q_query)

            if not queryset.count():
                raise ValueError(
                    f"Cannot find valid test data for {queryset.model.__name__} with params {filter_params}"
                )
            return queryset

        def test_q_filter_valid(self):
            """Test the `q` filter based on attributes in `filter_predicates`."""
            if not self.filterset.declared_filters.get("q"):
                raise ValueError("`q` filter not implemented")

            if not isinstance(self.filterset.declared_filters.get("q"), SearchFilter):
                # Some FilterSets like IPAddress,Prefix etc might implement a custom `q` filtering
                self.skipTest("`q` filter is not a SearchFilter")

            for filter_field_name, lookup_method in self.get_q_filter().items():
                should_skip_test = (
                    (lookup_method not in ["icontains", "iexact"])  # only testing icontains and iexact filter lookups
                    or (
                        filter_field_name == "id"
                    )  # Ignore `id` because `SearchFilter` always dynamically includes `id: exact` predicate, only testing on user input `filter_predicates`
                    or (filter_field_name in self.exclude_q_filter_predicates)
                )
                if should_skip_test:
                    continue
                with self.subTest(f"Asserting '{filter_field_name}' `q` filter predicates"):
                    queryset = self._get_relevant_filterset_queryset(self.queryset, filter_field_name)
                    obj = queryset.first()
                    obj_field_name = filter_field_name

                    is_nested_filter_name = "__" in filter_field_name

                    if is_nested_filter_name:
                        obj, obj_field_name = self._get_nested_related_obj_and_its_field_name(obj, obj_field_name)
                    self._assert_q_filter_predicate_validity(obj, obj_field_name, filter_field_name, lookup_method)

        def test_content_type_related_fields_uses_content_type_filter(self):
            self.assertIsNotNone(self.filterset)
            fs = self.filterset()  # pylint: disable=not-callable
            for field in self.queryset.model._meta.fields:
                related_model = getattr(field, "related_model", None)
                if not related_model or related_model != ContentType:
                    continue
                with self.subTest(
                    f"Assert {self.filterset.__class__.__name__}.{field.name} implements ContentTypeFilter"
                ):
                    filter_field = fs.filters.get(field.name)
                    if not filter_field:
                        # This field is not part of the Filterset.
                        continue
                    self.assertIsInstance(
                        filter_field,
                        (
                            ContentTypeFilter,
                            ContentTypeMultipleChoiceFilter,
                            ContentTypeChoiceFilter,
                        ),
                    )

    class TenancyFilterTestCaseMixin(views.TestCase):
        """Add test cases for tenant and tenant-group filters."""

        tenancy_related_name = ""

        def test_tenant(self):
            tenants = list(models.Tenant.objects.filter(**{f"{self.tenancy_related_name}__isnull": False}))[:2]
            params = {"tenant_id": [tenants[0].pk, tenants[1].pk]}
            self.assertQuerySetEqual(
                self.filterset(params, self.queryset).qs, self.queryset.filter(tenant__in=tenants), ordered=False
            )
            params = {"tenant": [tenants[0].name, tenants[1].name]}
            self.assertQuerySetEqual(
                self.filterset(params, self.queryset).qs, self.queryset.filter(tenant__in=tenants), ordered=False
            )

        def test_tenant_group(self):
            tenant_groups = list(
                models.TenantGroup.objects.filter(
                    tenants__isnull=False, **{f"tenants__{self.tenancy_related_name}__isnull": False}
                ).distinct()
            )[:2]
            tenant_groups_including_children = []
            for tenant_group in tenant_groups:
                tenant_groups_including_children += tenant_group.descendants(include_self=True)

            params = {"tenant_group": [tenant_groups[0].pk, tenant_groups[1].pk]}
            self.assertQuerySetEqual(
                self.filterset(params, self.queryset).qs,
                self.queryset.filter(tenant__tenant_group__in=tenant_groups_including_children),
                ordered=False,
            )

            params = {"tenant_group": [tenant_groups[0].name, tenant_groups[1].name]}
            self.assertQuerySetEqual(
                self.filterset(params, self.queryset).qs,
                self.queryset.filter(tenant__tenant_group__in=tenant_groups_including_children),
                ordered=False,
            )
