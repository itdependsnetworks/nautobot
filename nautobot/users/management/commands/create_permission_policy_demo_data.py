"""
Create demonstration users, groups, policies and assignments that exercise permission policies.

Development and demo environments only: every demo user is created with the password "nautobot".
"""

import importlib

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction

from nautobot.users.models import PermissionPolicy

DEMO_PASSWORD = "nautobot"  # noqa: S105  # deliberately well-known: demo data for development environments
DEMO_PREFIX = "demo-"

REGIONS = {"amer": "AMER", "emea": "EMEA", "apac": "APAC"}
CRUD = ["view", "add", "change", "delete"]

#: username -> (group name, one-line description shown in the summary)
DEMO_USERS = {
    "ntc-operator": ("network-to-code", "Full access to Network to Code's devices, racks, prefixes, IPs and VMs"),
    "it-amer": ("it-amer", "Full access to devices, racks and power in the AMER region"),
    "it-emea": ("it-emea", "Full access to devices, racks and power in the EMEA region"),
    "it-apac": ("it-apac", "Full access to devices, racks and power in the APAC region"),
    "telco-owner": ("telco", "Full access to circuits, providers, provider networks and terminations"),
    "job-runner": ("job-runners", "May view and run the export and import jobs, and see their own results"),
}


def content_type(app_label, model):
    return ContentType.objects.get(app_label=app_label, model=model)


class Command(BaseCommand):
    help = (
        "Create demo users (password 'nautobot'), groups, permission policies and policy assignments illustrating "
        "the built-in and custom policy patterns. Idempotent. Development environments only."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush", action="store_true", help="Remove the demo users, groups, policies and assignments."
        )

    def handle(self, *args, **options):
        if options["flush"]:
            self.flush()
            return
        with transaction.atomic():
            self.ensure_builtin_policies()
            groups = {name: Group.objects.get_or_create(name=name)[0] for _, (name, _) in DEMO_USERS.items()}
            self.create_users(groups)
            self.create_regional_it(groups)
            self.create_telco_owner(groups["telco"])
            self.create_job_runner(groups["job-runners"])
            # PLACEHOLDER: will be replaced in C11 (Policy assignment model and stack): the demo assignments.
        self.print_summary()

    # ----- helpers ------------------------------------------------------------------------------------------

    def ensure_builtin_policies(self):
        """The built-in policies are seeded by migration; recreate them if an administrator removed them."""
        if PermissionPolicy.objects.filter(name__startswith="nautobot-default-").count() < 4:
            from django.apps import apps

            seed = importlib.import_module("nautobot.users.migrations.0015_permission_policy_seed_data")
            seed.create_builtin_policies(apps, None)

    def create_users(self, groups):
        User = get_user_model()
        for username, (group_name, _) in DEMO_USERS.items():
            user, created = User.objects.get_or_create(username=username, defaults={"is_active": True})
            if created or not user.check_password(DEMO_PASSWORD):
                user.set_password(DEMO_PASSWORD)
                user.is_active = True
                user.save()
            user.groups.add(groups[group_name])
            self.stdout.write(f"{'Created' if created else 'Updated'} user {username}")

    def policy(self, name, description):
        policy, created = PermissionPolicy.objects.get_or_create(name=name, defaults={"description": description})
        if not created:
            policy.description = description
            policy.save()
        return policy

    # ----- patterns -----------------------------------------------------------------------------------------

    def create_regional_it(self, groups):
        """Pattern 2: a custom policy with a single tree-node parameter (`in_tree`), assigned once per region."""
        self.policy(
            f"{DEMO_PREFIX}regional-it-operator",
            "Full access to devices, interfaces, racks, rack groups and power panels anywhere within a region; "
            "read access to the region and its child locations.",
        )
        # PLACEHOLDER: will be replaced in C08 (Policy rule model and stack): the region-scoped rules.

    def create_telco_owner(self, group):
        """Pattern 3: an unparameterized custom policy spanning several object types."""
        self.policy(
            f"{DEMO_PREFIX}telco-owner",
            "Full access to everything circuit related, plus read access to locations.",
        )
        # PLACEHOLDER: will be replaced in C08 (Policy rule model and stack): the circuit rules.

    def create_job_runner(self, group):
        """Pattern 4: a multi-valued object parameter selecting which jobs may be run."""
        self.policy(
            f"{DEMO_PREFIX}job-runner",
            "Run a selected set of jobs and see one's own job results and logs.",
        )
        # PLACEHOLDER: will be replaced in C08 (Policy rule model and stack): the job rules.

    # ----- flush and summary --------------------------------------------------------------------------------

    def flush(self):
        User = get_user_model()
        with transaction.atomic():
            policies = PermissionPolicy.objects.filter(name__startswith=DEMO_PREFIX).delete()[0]
            users = User.objects.filter(username__in=DEMO_USERS).delete()[0]
            groups = Group.objects.filter(name__in={group for group, _ in DEMO_USERS.values()}).delete()[0]
        self.stdout.write(
            # PLACEHOLDER: will be replaced in C11 (Policy assignment model and stack): assignments and fixtures.
            f"Removed {policies} policies, {users} users and {groups} groups."
        )

    def print_summary(self):
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Demo users (password: {DEMO_PASSWORD}):"))
        for username, (group, description) in DEMO_USERS.items():
            self.stdout.write(f"  {username:<14} group {group:<18} {description}")
        self.stdout.write("")
        self.stdout.write(
            "Review any user's grants at Profile > Access, or GET /api/users/users/<id>/effective-access/."
        )
        self.stdout.write("Remove everything with: nautobot-server create_permission_policy_demo_data --flush")
