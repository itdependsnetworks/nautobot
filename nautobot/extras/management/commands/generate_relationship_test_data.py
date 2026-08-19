"""
Generate relationship benchmark data in a real database, for query-plan analysis and hand-timed page loads.

Delegates to `nautobot.extras.tests.relationship_fixtures.build_relationship_benchmark_fixture()` so that this
command and the automated benchmarks generate byte-identical data shapes; the same pattern is used by
`generate_load_balancer_models_test_data`.

Unlike `generate_test_data`, this command has no `--database` option and always writes to the default database.
Relationship generation touches the ContentType cache, `validated_save()` signals, and the Redis-backed
relationship definition cache, none of which are database-scoped, so a `--database` option here would be
plumbing that no test exercises.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from nautobot.dcim.models import Location, LocationType
from nautobot.extras.models import Relationship
from nautobot.extras.tests.relationship_fixtures import (
    build_relationship_benchmark_fixture,
    PEER_MODEL_LABELS,
    peer_models,
    RELATIONSHIP_BENCH_SCENARIOS,
)

EXPLAIN_TEMPLATE = """
-- Source-side association lookup (the query the object-centric loader issues)
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM extras_relationshipassociation
  WHERE source_type_id = {location_ct_id} AND source_id = '{location_id}';

-- Destination-side association lookup
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM extras_relationshipassociation
  WHERE destination_type_id = {location_ct_id} AND destination_id = '{location_id}';

-- Source-side lookup narrowed to specific relationships, which is what the composite indexes add coverage for
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM extras_relationshipassociation
  WHERE source_type_id = {location_ct_id} AND source_id = '{location_id}'
    AND relationship_id IN ({relationship_ids});
"""


class Command(BaseCommand):
    help = (
        "Populate the database with Relationship definitions and associations in one of the named benchmark shapes, "
        "so that query plans and page loads can be measured against realistic volumes. Intended for development "
        "databases only."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--scenario",
            choices=sorted(RELATIONSHIP_BENCH_SCENARIOS),
            default="S1",
            help="Named data shape to generate. See nautobot.extras.tests.relationship_fixtures. Default: S1.",
        )
        parser.add_argument(
            "--definitions",
            type=int,
            help="Override the scenario's number of relationship definitions.",
        )
        parser.add_argument(
            "--associations",
            type=int,
            help="Override the scenario's number of associations per primary object.",
        )
        parser.add_argument(
            "--peer-content-types",
            type=int,
            help=f"Override the scenario's number of distinct peer content types (2 to {len(PEER_MODEL_LABELS)}).",
        )
        parser.add_argument(
            "--objects",
            type=int,
            help="Override the scenario's number of primary objects.",
        )
        parser.add_argument(
            "--no-coverage",
            action="store_false",
            dest="coverage",
            default=None,
            help=(
                "Generate only homogeneous many-to-many definitions instead of the full behavior-coverage set. "
                "Use for scaling sweeps, where varying definition *kind* alongside definition count would "
                "confound the measurement."
            ),
        )
        parser.add_argument(
            "--seed",
            default="relbench",
            help="Name prefix for all generated records, making runs reproducible and removable. Default: relbench.",
        )
        parser.add_argument(
            "--flush",
            action="store_true",
            help=(
                "Delete previously generated records carrying this --seed prefix before generating. This removes "
                "only records this command created; it never flushes the database as a whole."
            ),
        )
        parser.add_argument(
            "--print-explain",
            action="store_true",
            help="After generating, print EXPLAIN (ANALYZE, BUFFERS) statements for the association lookups.",
        )

    def handle(self, *args, **options):
        seed = options["seed"]

        if options["flush"]:
            self._flush(seed)

        try:
            with transaction.atomic():
                fixture = build_relationship_benchmark_fixture(
                    scenario=options["scenario"],
                    definition_count=options["definitions"],
                    association_count=options["associations"],
                    peer_content_type_count=options["peer_content_types"],
                    object_count=options["objects"],
                    coverage=options["coverage"],
                    seed=seed,
                )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        summary = fixture.summary()
        self.stdout.write(self.style.SUCCESS(f"Generated relationship benchmark data (seed={seed!r}):"))
        for key, value in summary.items():
            self.stdout.write(f"  {key}: {value}")
        self.stdout.write(f"  primary object: {fixture.primary_object.name} ({fixture.primary_object.pk})")

        if options["print_explain"]:
            self._print_explain(fixture)

    def _flush(self, seed):
        """Remove records generated by a previous run of this command with the same seed."""
        deleted = {}

        definitions = Relationship.objects.filter(label__startswith=f"{seed} ")
        # Deleting the definitions cascades to their associations.
        deleted["relationships"] = definitions.count()
        definitions.delete()

        locations = Location.objects.filter(name__startswith=f"{seed} Bench Location ")
        deleted["locations"] = locations.count()
        locations.delete()

        location_types = LocationType.objects.filter(name=f"{seed} Bench Location Type")
        deleted["location_types"] = location_types.count()
        location_types.delete()

        for model in peer_models():
            peers = model.objects.filter(name__startswith=f"{seed} Bench {model._meta.model_name} ")
            deleted[model._meta.model_name] = peers.count()
            peers.delete()

        self.stdout.write(self.style.WARNING(f"Flushed prior benchmark data for seed {seed!r}: {deleted}"))

    def _print_explain(self, fixture):
        """Print ready-to-run EXPLAIN statements for the two side-specific association lookups."""
        from django.contrib.contenttypes.models import ContentType

        relationship_ids = ", ".join(f"'{definition.pk}'" for definition in fixture.definitions[:10])
        self.stdout.write(
            EXPLAIN_TEMPLATE.format(
                location_ct_id=ContentType.objects.get_for_model(Location).pk,
                location_id=fixture.primary_object.pk,
                relationship_ids=relationship_ids,
            )
        )
