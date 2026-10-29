#!/usr/bin/env python3
"""Fetch the upstream OpenAPI JSON Schemas and split them into reusable sub-schemas.

For each OpenAPI version, the latest dated schema published on https://spec.openapis.org is
downloaded, and every definition is written to its own file in ``<version>/``:

- ``openapi.json``: the OpenAPI document itself (upstream ``schema``);
- ``openapi-base.json``: same, with Schema Object validation (upstream ``schema-base``);
- ``openapi-resource.json``: a Components Object that also accepts named Path Items in ``paths``,
  and ``openapi-resource-base.json`` with Schema Object validation;
- ``openapi-<name>.json``: one file per object (``openapi-parameter.json``, ``openapi-path-item.json``, …);
- ``openapi-<name>-or-reference.json``: the object or a Reference Object;
- ``openapi-<collection>.json``: arrays and maps of objects (``openapi-parameters.json``, …).

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

ROOT = "openapi"
ROOT_BASE = "openapi-base"
PREFIX = "openapi-"
RESOURCE = "resource"
RESOURCE_BASE = "resource-base"
REFERENCE = "reference"

# Upstream names that clash with the collections below.
RENAMES = {
    "callbacks": "callback",
    "callbacks-or-reference": "callback-or-reference",
    "examples": "example-xor-examples",
}

# Collection name -> (property names it applies to, kind, item schema).
COLLECTIONS = {
    "servers": ({"servers"}, "array", "server"),
    "parameters": ({"parameters"}, "array", "parameter-or-reference"),
    "security": ({"security"}, "array", "security-requirement"),
    "tags": ({"tags"}, "array", "tag"),
    "webhooks": ({"webhooks"}, "map", "path-item"),
    "content": ({"content"}, "map", "media-type"),
    "headers": ({"headers"}, "map", "header-or-reference"),
    "links": ({"links"}, "map", "link-or-reference"),
    "examples": ({"examples"}, "map", "example-or-reference"),
    "callbacks": ({"callbacks"}, "map", "callback-or-reference"),
    "encodings": ({"encoding"}, "map", "encoding"),
    "server-variables": ({"variables"}, "map", "server-variable"),
}

ITEMS_KEYWORD = {"array": "items", "map": "additionalProperties"}
JSON_TYPE = {"array": "array", "map": "object"}

DRAFT_04 = "http://json-schema.org/draft-04/schema#"

RESOURCE_DESCRIPTION = (
    "Not part of the OpenAPI Specification: a Components Object that also accepts named Path Items in `paths`, "
    "to describe a resource in a single file."
)


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


def filename(name: str) -> str:
    return f"{name}.json" if name in (ROOT, ROOT_BASE) else f"{PREFIX}{name}.json"


def kebab(name: str) -> str:
    name = name.replace("OAuth", "Oauth")
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1-\2", name)
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", name)
    return RENAMES.get(name.lower(), name.lower())


def transform(node, fn, prop: str | None = None):
    """Apply ``fn(schema, property_name)`` bottom-up to every dict of ``node``."""
    if isinstance(node, list):
        return [transform(item, fn) for item in node]
    if not isinstance(node, dict):
        return node
    result = {}
    for key, value in node.items():
        if key == "properties" and isinstance(value, dict):
            result[key] = {name: transform(schema, fn, name) for name, schema in value.items()}
        else:
            result[key] = transform(value, fn)
    return fn(result, prop)


class Splitter:
    def __init__(self, schema: dict, base: dict | None):
        self.dialect = schema["$schema"]
        self.draft_04 = self.dialect == DRAFT_04
        defs_keyword = "definitions" if self.draft_04 else "$defs"
        self.defs_prefix = f"#/{defs_keyword}/"
        self.upstream_id = schema.get("$id") or schema.get("id")

        root = copy.deepcopy(schema)
        definitions = root.pop(defs_keyword)
        root.pop("$id", None)
        root.pop("id", None)
        self.names = {name: kebab(name) for name in definitions}
        self.docs = {ROOT: root} | {self.names[name]: copy.deepcopy(d) for name, d in definitions.items()}
        self.anchors = {
            doc["$dynamicAnchor"]: name for name, doc in self.docs.items() if "$dynamicAnchor" in doc
        }
        self.docs = {name: transform(doc, self.rewrite_refs) for name, doc in self.docs.items()}

        self.base = None
        if base is not None:
            if base["$ref"] != self.upstream_id:
                raise ValueError(f"{base['$id']} references {base['$ref']}, expected {self.upstream_id}")
            self.base = copy.deepcopy(base)
            self.base.pop("$id")
            self.base["$ref"] = filename(ROOT)

    def rewrite_refs(self, node: dict, _prop):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith(self.defs_prefix):
            name, _, rest = ref.removeprefix(self.defs_prefix).partition("/")
            node["$ref"] = filename(self.names[name]) + (f"#/{rest}" if rest else "")
        elif ref == "#":
            node["$ref"] = filename(ROOT)
        dynamic_ref = node.get("$dynamicRef")
        if isinstance(dynamic_ref, str) and dynamic_ref.startswith("#"):
            node["$dynamicRef"] = filename(self.anchors[dynamic_ref[1:]]) + dynamic_ref
        return node

    def add_or_references(self):
        """Replace ``oneOf: [X, Reference]`` with ``X-or-reference`` (OpenAPI 3.0 only)."""
        reference_ref = {"$ref": filename(REFERENCE)}
        created = {}

        def replace(node: dict, _prop):
            choices = node.get("oneOf")
            if node.keys() != {"oneOf"} or len(choices) != 2 or reference_ref not in choices:
                return node
            target = next(choice for choice in choices if choice != reference_ref)
            if target.keys() != {"$ref"} or "#" in target["$ref"]:
                return node
            name = target["$ref"].removeprefix(PREFIX).removesuffix(".json") + "-or-reference"
            created[name] = {"oneOf": [target, reference_ref]}
            return {"$ref": filename(name)}

        self.docs = {name: transform(doc, replace) for name, doc in self.docs.items()}
        self.docs |= created

    def add_collections(self):
        occurrences = {}

        def core(node: dict, prop):
            for name, (props, kind, item) in COLLECTIONS.items():
                if (
                    prop in props
                    and name not in self.docs
                    and node.get("type") == JSON_TYPE[kind]
                    and node.get(ITEMS_KEYWORD[kind]) == {"$ref": filename(item)}
                ):
                    return name, {"type": JSON_TYPE[kind], ITEMS_KEYWORD[kind]: {"$ref": filename(item)}}
            return None, None

        def collect(node: dict, prop):
            name, shared = core(node, prop)
            if name:
                extra = {key: value for key, value in node.items() if key not in shared}
                occurrences.setdefault(name, []).append(extra)
            return node

        for doc in self.docs.values():
            transform(doc, collect)

        # Keywords common to every occurrence move into the collection, the others stay in place.
        collections = {}
        for name, extras in occurrences.items():
            _, kind, item = COLLECTIONS[name]
            common = {key: value for key, value in extras[0].items() if all(e.get(key) == value for e in extras)}
            common = {key: value for key, value in common.items() if key not in ("default", "description")}
            collections[name] = {"type": JSON_TYPE[kind], ITEMS_KEYWORD[kind]: {"$ref": filename(item)}} | common

        def replace(node: dict, prop):
            name, shared = core(node, prop)
            if not name:
                return node
            moved = shared.keys() | collections[name].keys()
            extra = {key: value for key, value in node.items() if key not in moved}
            if self.draft_04 and extra:
                # Draft 4 ignores the keywords next to $ref.
                return {"allOf": [{"$ref": filename(name)}]} | extra
            return {"$ref": filename(name)} | extra

        self.docs = {name: transform(doc, replace) for name, doc in self.docs.items()}
        self.docs |= collections

    def add_resource(self):
        """Add a Components Object that also accepts named Path Items in ``paths``."""
        resource = copy.deepcopy(self.docs["components"])
        resource.pop("$comment", None)
        path_item = {"$ref": filename("path-item")}
        if self.draft_04:
            name_pattern = next(iter(resource["properties"]["schemas"]["patternProperties"]))
            paths = {"type": "object", "patternProperties": {name_pattern: path_item}, "additionalProperties": False}
        else:
            property_names = next(iter(resource["patternProperties"].values()))["propertyNames"]
            paths = {"type": "object", "additionalProperties": path_item, "propertyNames": property_names}
        resource["properties"] = {"paths": paths} | resource["properties"]
        self.docs[RESOURCE] = {"description": RESOURCE_DESCRIPTION} | resource

    def files(self) -> dict[str, dict]:
        docs = dict(self.docs)
        if self.base is not None:
            docs[ROOT_BASE] = self.base
            docs[RESOURCE_BASE] = {
                "description": RESOURCE_DESCRIPTION + " Schema Objects are validated with the OpenAPI dialect.",
                "$ref": filename(RESOURCE),
                "$defs": copy.deepcopy(self.base["$defs"]),
            }
        return {filename(name): self.finalize(name, doc) for name, doc in docs.items()}

    def finalize(self, name: str, doc: dict) -> dict:
        own_file = filename(name)

        def localize(node: dict, _prop):
            for keyword in ("$ref", "$dynamicRef"):
                value = node.get(keyword)
                if isinstance(value, str) and value.partition("#")[0] == own_file:
                    node[keyword] = "#" + value.partition("#")[2]
            return node

        doc = transform(doc, localize)
        doc.pop("$schema", None)
        return {"$schema": self.dialect} | doc


def update(version: str, output: Path):
    schema_url = latest_url(version, "schema")
    base_url = latest_url(version, "schema-base")
    print(f"OpenAPI {version}: {schema_url}" + (f", {base_url}" if base_url else ""))

    splitter = Splitter(fetch(schema_url), fetch(base_url) if base_url else None)
    if splitter.draft_04:
        splitter.add_or_references()
    splitter.add_collections()
    splitter.add_resource()
    files = splitter.files()

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
