"""Navigation menu items for the users app."""

from nautobot.core.ui.choices import NavigationIconChoices, NavigationWeightChoices
from nautobot.core.ui.nav import NavMenuAddButton, NavMenuGroup, NavMenuItem, NavMenuTab

menu_items = (
    NavMenuTab(
        name="Extensibility",
        icon=NavigationIconChoices.EXTENSIBILITY,
        weight=NavigationWeightChoices.EXTENSIBILITY,
        groups=(
            NavMenuGroup(
                name="Users",
                weight=150,
                items=(
                    NavMenuItem(
                        link="users:permissionpolicy_list",
                        name="Permission Policies",
                        weight=200,
                        permissions=["users.view_permissionpolicy"],
                        buttons=(
                            NavMenuAddButton(
                                link="users:permissionpolicy_add",
                                permissions=["users.add_permissionpolicy"],
                            ),
                        ),
                    ),
                    NavMenuItem(
                        link="users:policyparameter_list",
                        name="Policy Parameters",
                        weight=300,
                        permissions=["users.view_policyparameter"],
                        buttons=(
                            NavMenuAddButton(
                                link="users:policyparameter_add",
                                permissions=["users.add_policyparameter"],
                            ),
                        ),
                    ),
                    NavMenuItem(
                        link="users:policyrule_list",
                        name="Policy Rules",
                        weight=400,
                        permissions=["users.view_policyrule"],
                        buttons=(
                            NavMenuAddButton(
                                link="users:policyrule_add",
                                permissions=["users.add_policyrule"],
                            ),
                        ),
                    ),
                ),
            ),
        ),
    ),
)
