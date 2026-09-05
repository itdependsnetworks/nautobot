from nautobot.core.choices import ChoiceSet


class PolicyParameterKindChoices(ChoiceSet):
    """The kind of value a `PolicyParameter` accepts."""

    KIND_OBJECT = "object"
    KIND_STRING = "string"

    CHOICES = (
        (KIND_OBJECT, "Object reference"),
        (KIND_STRING, "String"),
    )
