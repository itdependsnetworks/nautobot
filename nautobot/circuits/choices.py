from nautobot.core.choices import ChoiceSet

#
# Circuits
#


class CircuitStatusChoices(ChoiceSet):
    STATUS_DEPROVISIONING = "deprovisioning"
    STATUS_ACTIVE = "active"
    STATUS_PLANNED = "planned"
    STATUS_PROVISIONING = "provisioning"
    STATUS_OFFLINE = "offline"
    STATUS_DECOMMISSIONED = "decommissioned"

    CHOICES = (
        (STATUS_PLANNED, "Planned"),
        (STATUS_PROVISIONING, "Provisioning"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_OFFLINE, "Offline"),
        (STATUS_DEPROVISIONING, "Deprovisioning"),
        (STATUS_DECOMMISSIONED, "Decommissioned"),
    )


class CircuitSpeedChoices(ChoiceSet):
    """Common circuit speeds (Kbps), offered as suggestions beside the speed inputs on the circuit forms."""

    # NB-FIELDSETS-REVIEW[js-media] (temporary marker, delete before merge): new. The same list used to be hard-coded
    # in circuits/inc/speed_widget.html, rendered by the `SpeedField` layout item (both removed).
    SPEED_10M = 10_000
    SPEED_100M = 100_000
    SPEED_1G = 1_000_000
    SPEED_10G = 10_000_000
    SPEED_25G = 25_000_000
    SPEED_40G = 40_000_000
    SPEED_100G = 100_000_000
    SPEED_T1 = 1_544
    SPEED_E1 = 2_048

    CHOICES = (
        (SPEED_10M, "10 Mbps"),
        (SPEED_100M, "100 Mbps"),
        (SPEED_1G, "1 Gbps"),
        (SPEED_10G, "10 Gbps"),
        (SPEED_25G, "25 Gbps"),
        (SPEED_40G, "40 Gbps"),
        (SPEED_100G, "100 Gbps"),
        (SPEED_T1, "T1 (1.544 Mbps)"),
        (SPEED_E1, "E1 (2.048 Mbps)"),
    )


#
# CircuitTerminations
#


class CircuitTerminationSideChoices(ChoiceSet):
    SIDE_A = "A"
    SIDE_Z = "Z"

    CHOICES = ((SIDE_A, "A"), (SIDE_Z, "Z"))
