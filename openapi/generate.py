#!/usr/bin/env python3
"""Fetch the upstream OpenAPI JSON Schemas and adapt them for editors and validators.

For each OpenAPI version, the latest dated schemas published on https://spec.openapis.org are downloaded and
written to ``<version>/``:

- ``openapi.json``: an OpenAPI document (upstream ``schema``);
- ``openapi-base.json``: same, with Schema Object validation (upstream ``schema-base``, 3.1 and later);
- ``openapi-resource.json``: a Components Object that also accepts named Path Items in ``paths``;
- ``openapi-resource-base.json``: same, with Schema Object validation (3.1 and later).

Every file is self-contained and has no ``$dynamicRef``, so it works in tools that resolve neither references to
other files nor dynamic references (such as JetBrains IDEs).

Set ``GITHUB_TOKEN`` to avoid the GitHub API rate limit used to find the latest versions.
"""

import copy
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

VERSIONS = ("3.0", "3.1", "3.2")

SPEC_URL = "https://spec.openapis.org/oas/{version}/{kind}/{date}"
GITHUB_API_URL = "https://api.github.com/repos/OAI/spec.openapis.org/contents/oas/{version}/{kind}"

RESOURCE_DESCRIPTION = (
    "Not part of the OpenAPI Specification: a Components Object that also accepts named Path Items in `paths`, "
    "to describe a resource in a single file."
)
BASE_DESCRIPTION = " Schema Objects are validated with the OpenAPI dialect."


def fetch(url: str, headers: dict[str, str] | None = None):
    request = urllib.request.Request(url, headers={"User-Agent": "eleaven-schemas", **(headers or {})})
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def latest_url(version: str, kind: str) -> str | None:
    headers = {"Accept": "application/vnd.github+json"}
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    try:
        entries = fetch(GITHUB_API_URL.format(version=version, kind=kind), headers)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise
    dates = [entry["name"] for entry in entries if re.fullmatch(r"\d{4}-\d{2}-\d{2}", entry["name"])]
    return SPEC_URL.format(version=version, kind=kind, date=max(dates)) if dates else None


def transform(node, fn):
    """Apply ``fn(dict)`` bottom-up to every dict of ``node``."""
    if isinstance(node, list):
        return [transform(item, fn) for item in node]
    if not isinstance(node, dict):
        return node
    return fn({key: transform(value, fn) for key, value in node.items()})


def resource(schema: dict) -> dict:
    """Return the Components Object of ``schema``, with an extra ``paths`` map of named Path Items."""
    keyword = "definitions" if "definitions" in schema else "$defs"
    defs = schema[keyword]

    def definition(ref: str) -> dict:
        return defs[ref.removeprefix(f"#/{keyword}/")]

    components = copy.deepcopy(definition(schema["properties"]["components"]["$ref"]))
    paths = definition(schema["properties"]["paths"]["$ref"])
    path_item = next(item for pattern, item in paths["patternProperties"].items() if re.match(pattern, "/"))
    # Path Item names follow the same rule as the names of the other components.
    if keyword == "definitions":
        name_pattern = next(iter(components["properties"]["schemas"]["patternProperties"]))
        named_paths = {"type": "object", "patternProperties": {name_pattern: path_item}, "additionalProperties": False}
    else:
        property_names = next(iter(components["patternProperties"].values()))["propertyNames"]
        named_paths = {"type": "object", "additionalProperties": path_item, "propertyNames": property_names}

    components.pop("$comment", None)
    components["properties"] = {"paths": named_paths} | components["properties"]
    return {"$schema": schema["$schema"], "description": RESOURCE_DESCRIPTION} | components | {keyword: defs}


def anchors(defs: dict) -> dict[str, str]:
    return {definition["$dynamicAnchor"]: name for name, definition in defs.items() if "$dynamicAnchor" in definition}


def with_base(doc: dict, base: dict) -> dict:
    """Validate the Schema Objects of ``doc`` with the OpenAPI dialect, like upstream ``schema-base``.

    Upstream overrides a ``$dynamicAnchor`` from another file; here the anchored definition is replaced.
    """
    doc = copy.deepcopy(doc)
    defs = doc["$defs"]
    base_defs = copy.deepcopy(base["$defs"])
    ((anchor, meta_name),) = anchors(base_defs).items()
    meta = base_defs.pop(meta_name)
    if conflicts := defs.keys() & base_defs.keys():
        raise ValueError(f"schema-base definitions already exist: {sorted(conflicts)}")
    defs[anchors(defs)[anchor]] = meta
    defs |= base_defs
    return doc


def static_refs(doc: dict) -> dict:
    """Replace every ``$dynamicRef`` with a plain ``$ref``: they are equivalent in a self-contained file."""
    names = anchors(doc.get("$defs", {}))

    def static(node: dict) -> dict:
        node = {key: value for key, value in node.items() if key != "$dynamicAnchor"}
        if "$dynamicRef" in node:
            target = f"#/$defs/{names[node['$dynamicRef'].removeprefix('#')]}"
            node = {"$ref" if key == "$dynamicRef" else key: value for key, value in node.items()}
            node["$ref"] = target
        return node

    return transform(doc, static)


def generate(schema: dict, base: dict | None) -> dict[str, dict]:
    upstream_id = schema.get("$id") or schema.get("id")
    openapi = {key: value for key, value in schema.items() if key not in ("$id", "id")}
    files = {"openapi.json": openapi, "openapi-resource.json": resource(openapi)}
    if base is not None:
        if base["$ref"] != upstream_id:
            raise ValueError(f"{base['$id']} references {base['$ref']}, expected {upstream_id}")
        if unknown := base.keys() - {"$id", "$schema", "description", "$ref", "properties", "$defs"}:
            raise ValueError(f"Unexpected schema-base keywords: {sorted(unknown)}")
        openapi_base = with_base(openapi, base)
        openapi_base["description"] = base["description"]
        for name, prop in base["properties"].items():
            openapi_base["properties"][name] = openapi_base["properties"].get(name, {}) | prop
        resource_base = with_base(files["openapi-resource.json"], base)
        resource_base["description"] += BASE_DESCRIPTION
        files |= {"openapi-base.json": openapi_base, "openapi-resource-base.json": resource_base}
    return {filename: static_refs(doc) for filename, doc in files.items()}


def update(version: str, output: Path):
    schema_url = latest_url(version, "schema")
    base_url = latest_url(version, "schema-base")
    print(f"OpenAPI {version}: {schema_url}" + (f", {base_url}" if base_url else ""))

    files = generate(fetch(schema_url), fetch(base_url) if base_url else None)

    output.mkdir(exist_ok=True)
    for stale in output.glob("*.json"):
        stale.unlink()
    for filename, doc in sorted(files.items()):
        (output / filename).write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    print(f"  {len(files)} files written to {output}")


def main():
    for version in VERSIONS:
        update(version, Path(__file__).resolve().parent / version)


if __name__ == "__main__":
    main()
