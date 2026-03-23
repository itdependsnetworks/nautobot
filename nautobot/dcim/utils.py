from copy import deepcopy
import functools
import uuid

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.utils.html import format_html, format_html_join
from netutils.lib_mapper import NAME_TO_ALL_LIB_MAPPER, NAME_TO_LIB_MAPPER_REVERSE

from nautobot.core.choices import ColorChoices
from nautobot.core.templatetags.helpers import hyperlinked_object
from nautobot.core.utils.config import get_settings_or_config
from nautobot.dcim.choices import InterfaceModeChoices


def compile_path_node(ct_id, object_id):
    return f"{ct_id}:{object_id}"


def decompile_path_node(representation):
    ct_id, object_id = representation.split(":")
    # The value is stored as a string, but the lookup later uses UUID objects as keys so we convert it now.
    # Note that the content type ID is still an integer because we have no control over that model.
    return int(ct_id), uuid.UUID(object_id)


def object_to_path_node(obj):
    """
    Return a representation of an object suitable for inclusion in a CablePath path. Node representation is in the
    form <ContentType ID>:<Object ID>.
    """
    ct = ContentType.objects.get_for_model(obj)
    return compile_path_node(ct.pk, obj.pk)


def path_node_to_object(representation):
    """
    Given the string representation of a path node, return the corresponding instance.
    """
    ct_id, object_id = decompile_path_node(representation)
    ct = ContentType.objects.get_for_id(ct_id)
    return ct.model_class().objects.get(pk=object_id)


def cable_status_color_css(record):
    """
    Given a record such as an Interface, return the CSS needed to apply appropriate coloring to it.
    """
    if not record.cable:
        return ""
    else:
        CABLE_STATUS_TO_CSS_CLASS = {
            ColorChoices.COLOR_GREEN: "table-success",
            ColorChoices.COLOR_AMBER: "table-warning",
            ColorChoices.COLOR_CYAN: "table-info",
        }
        status_color = record.cable.get_status_color().strip("#")
        return CABLE_STATUS_TO_CSS_CLASS.get(status_color, "")


def get_network_driver_mapping_tool_names():
    """
    Return a list of all available network driver tool names derived from the netutils library and the optional NETWORK_DRIVERS setting.

    Tool names are "ansible", "hier_config", "napalm", "netmiko", etc...
    """
    network_driver_names = set(NAME_TO_LIB_MAPPER_REVERSE.keys())
    network_driver_names.update(get_settings_or_config("NETWORK_DRIVERS", fallback={}).keys())
    return sorted(network_driver_names)


def get_all_network_driver_mappings():
    """
    Return a dict of all available network driver mappings derived from the netutils library and the optional NETWORK_DRIVERS setting.

    Example output:
        {
            "cisco_ios": {
                "ansible": "cisco.ios.ios",
                "napalm": "ios",
            },
            "cisco_nxos": {
                "ansible": "cisco.nxos.nxos",
                "napalm": "nxos",
            },
            etc...
        }
    """
    network_driver_mappings = deepcopy(NAME_TO_ALL_LIB_MAPPER)

    # add mappings from optional NETWORK_DRIVERS setting
    network_drivers_config = get_settings_or_config("NETWORK_DRIVERS", fallback={})
    for tool_name, mappings in network_drivers_config.items():
        for normalized_name, mapped_name in mappings.items():
            network_driver_mappings.setdefault(normalized_name, {})
            network_driver_mappings[normalized_name][tool_name] = mapped_name

    return network_driver_mappings


def validate_interface_tagged_vlans(instance, model, pk_set):
    """
    Validate that the VLANs being added to the 'tagged_vlans' field of an Interface instance are all from the same location
    as the parent device or are global and that the mode of the Interface is set to `InterfaceModeChoices.MODE_TAGGED`.

    Args:
        instance (Interface): The instance of the Interface model that the VLANs are being added to.
        model (Model): The model of the related VLAN objects.
        pk_set (set): The primary keys of the VLAN objects being added to the 'tagged_vlans' field.
    """

    if instance.mode != InterfaceModeChoices.MODE_TAGGED:
        raise ValidationError(
            {"tagged_vlans": f"Mode must be set to {InterfaceModeChoices.MODE_TAGGED} when specifying tagged_vlans"}
        )

    # Filter the model objects based on the primary keys passed in kwargs and exclude the ones that have
    # a location that is not the parent's location, or parent's location's ancestors, or None
    location = getattr(instance.parent, "location", None)
    if location:
        location_ids = location.ancestors(include_self=True).values_list("id", flat=True)
    else:
        location_ids = []
    tagged_vlans = (
        model.objects.filter(pk__in=pk_set).exclude(locations__isnull=True).exclude(locations__in=location_ids)
    )

    if tagged_vlans.count():
        raise ValidationError(
            {
                "tagged_vlans": (
                    f"Tagged VLAN with names {list(tagged_vlans.values_list('name', flat=True))} must all belong to the "
                    "same location as the interface's parent device, "
                    "one of the parent locations of the interface's parent device's location, or it must be global."
                )
            }
        )


def convert_watts_to_va(watts, power_factor):
    """
    Convert watts to VA using power factor.
    """
    if not watts:
        return 0
    return int(watts / power_factor)


def render_software_version_and_image_files(instance, software_version, context):
    display = hyperlinked_object(software_version)
    overridden_software_image_files = instance.software_image_files.all()
    if software_version is not None:
        display += format_html(
            '<ul class="software-image-hierarchy">{}</ul>',
            format_html_join(
                "\n",
                "<li>{}{}</li>",
                [
                    [
                        hyperlinked_object(img, "image_file_name"),
                        " (overridden)" if overridden_software_image_files.exists() else "",
                    ]
                    for img in software_version.software_image_files.restrict(context["request"].user, "view")
                ],
            ),
        )
    if overridden_software_image_files.exists():
        display += format_html(
            "<br><strong>Software Image Files Overridden:</strong>\n<ul>{}</ul>",
            format_html_join(
                "\n", "<li>{}</li>", [[hyperlinked_object(img)] for img in overridden_software_image_files.all()]
            ),
        )
    return display


# Cable disconnect utilities


def disconnect_termination(termination):
    """Disconnect a single termination from its cable without deleting the cable.

    Clears the CableTerminationEndpoint row, clears mixin caches on both the termination
    and its peer, and cleans up CablePaths. Returns the cable if successful, None otherwise.
    """
    from django.contrib.contenttypes.models import ContentType

    from nautobot.dcim.models import CablePath, CableTerminationEndpoint

    if not termination or not termination.cable_id:
        return None

    cable = termination.cable

    # Clear the peer's caches
    peer = termination._cable_peer
    if peer is not None:
        peer.cable = None
        peer._cable_peer = None
        if getattr(peer, "_path_id", None):
            path_id = peer._path_id
            peer._path = None
            peer.save()
            CablePath.objects.filter(pk=path_id).delete()
        else:
            peer.save()

    # Clear _path FK before deleting CablePath to avoid FK constraint violation
    if getattr(termination, "_path_id", None):
        path_id = termination._path_id
        termination._path = None
        termination.save()
        CablePath.objects.filter(pk=path_id).delete()

    # Remove the CableTerminationEndpoint row
    CableTerminationEndpoint.objects.filter(
        termination_type=ContentType.objects.get_for_model(termination),
        termination_id=termination.pk,
    ).delete()

    # Clear the mixin cache on this termination
    termination.cable = None
    termination._cable_peer = None
    termination.save()

    return cable


# Breakout cable lane utilities


@functools.lru_cache(maxsize=1)
def _get_cable_termination_concrete_models():
    """Lazily import and cache the concrete CableTermination subclass models."""
    from nautobot.circuits.models import CircuitTermination
    from nautobot.dcim.models import (
        ConsolePort,
        ConsoleServerPort,
        FrontPort,
        Interface,
        PowerFeed,
        PowerOutlet,
        PowerPort,
        RearPort,
    )

    return [
        Interface,
        ConsolePort,
        ConsoleServerPort,
        PowerPort,
        PowerOutlet,
        FrontPort,
        RearPort,
        PowerFeed,
        CircuitTermination,
    ]


def get_all_lane_terminations(cable):
    """
    Return all CableTermination rows for the given cable from the concrete CableTermination table.

    Returns a QuerySet of CableTermination model instances.
    """
    from nautobot.dcim.models.cables import CableTerminationEndpoint as CableTerminationModel

    return CableTerminationModel.objects.filter(cable=cable).order_by("cable_end", "connector", "position")


def get_opposite_lane_termination(cable, side, connector, position):
    """
    Given a cable and one side's (connector, position), return the termination object on the opposite side
    by looking up the cable's breakout template mapping.

    Returns the termination object or None if the opposite lane is unconnected.
    """
    from nautobot.dcim.models.cables import CableTerminationEndpoint as CableTerminationModel

    if not cable.breakout_template_id:
        return None

    mapping = cable.breakout_template.mapping
    side_key = "a" if side == "A" else "b"
    opp_key = "b" if side == "A" else "a"
    opp_side = "B" if side == "A" else "A"

    for entry in mapping:
        if entry[f"{side_key}_connector"] == connector and entry[f"{side_key}_position"] == position:
            opp_connector = entry[f"{opp_key}_connector"]
            opp_position = entry[f"{opp_key}_position"]
            # Try exact connector+position match first
            endpoint = CableTerminationModel.objects.filter(
                cable=cable,
                cable_end=opp_side,
                connector=opp_connector,
                position=opp_position,
            ).first()
            if endpoint:
                return endpoint.termination
            # Fall back to connector-only match (trunk port representing all positions)
            endpoint = CableTerminationModel.objects.filter(
                cable=cable,
                cable_end=opp_side,
                connector=opp_connector,
            ).first()
            return endpoint.termination if endpoint else None
    return None
