"""The JSON/YAML metadata-document wire format shared by import and export.

This is the single source of truth for the self-describing document that the `ExportObjectList` job
writes (via `build_import_document`) and the JSON/YAML import parsers read (via
`ImportDocumentParserMixin`, which consumes these constants). Defining the version and key names here
keeps the writer and reader in lock-step — bump or rename in one place and both ends follow.
"""

IMPORT_DOCUMENT_VERSION = "1"
IMPORT_DOCUMENT_VERSION_KEY = "nautobot_import"
IMPORT_DOCUMENT_MODEL_KEY = "model"
IMPORT_DOCUMENT_MATCH_FIELDS_KEY = "match_fields"
IMPORT_DOCUMENT_RECORDS_KEY = "records"


def build_import_document(model_label, records, match_fields=None):
    """Wrap records in the metadata document understood by the JSON/YAML import parsers.

    Single source of truth for the document wire format, shared by the `ExportObjectList` job (writer)
    and `ImportDocumentParserMixin` (reader), so key names and version stay in lock-step. Key insertion
    order (version, model, match_fields, records) is preserved for readable YAML output.

    Args:
        model_label (str): The `app_label.model` the records belong to.
        records (list): The reshaped record dicts.
        match_fields (list, optional): The fields an importer should match existing records on. Omitted
            from the document when falsy.

    Returns:
        dict: The metadata document.
    """
    document = {
        IMPORT_DOCUMENT_VERSION_KEY: IMPORT_DOCUMENT_VERSION,
        IMPORT_DOCUMENT_MODEL_KEY: model_label,
    }
    if match_fields:
        document[IMPORT_DOCUMENT_MATCH_FIELDS_KEY] = list(match_fields)
    document[IMPORT_DOCUMENT_RECORDS_KEY] = records
    return document
