# OpenAPI schemas

JSON Schemas for [OpenAPI](https://spec.openapis.org/) documents and resource files, adapted from the upstream
schemas.

| Version | Folder | JSON Schema dialect | Upstream |
| --- | --- | --- | --- |
| 3.0 | [`3.0`](3.0) | Draft 4 | [`oas/3.0/schema`](https://github.com/OAI/spec.openapis.org/tree/main/oas/3.0/schema/) |
| 3.1 | [`3.1`](3.1) | Draft 2020-12 | [`oas/3.1/schema`](https://github.com/OAI/spec.openapis.org/tree/main/oas/3.1/schema/), [`oas/3.1/schema-base`](https://github.com/OAI/spec.openapis.org/tree/main/oas/3.1/schema-base/) |
| 3.2 | [`3.2`](3.2) | Draft 2020-12 | [`oas/3.2/schema`](https://github.com/OAI/spec.openapis.org/tree/main/oas/3.2/schema/), [`oas/3.2/schema-base`](https://github.com/OAI/spec.openapis.org/tree/main/oas/3.2/schema-base/) |

The files are generated from the latest upstream schemas by [`generate.py`](generate.py). Don't edit them by hand.

## Files

### Whole document

| File | Validates |
| --- | --- |
| `openapi.json` | A complete OpenAPI document. In 3.1 and 3.2, Schema Objects are only checked to be objects or booleans. |
| `openapi-base.json` | 3.1 and 3.2 only. Same as `openapi.json`, and Schema Objects are also validated against the OpenAPI JSON Schema dialect. |

`openapi-base.json` is stricter, but it references the dialect and meta-schemas hosted on spec.openapis.org, so
the validator needs network access. In 3.0, `openapi.json` already validates Schema Objects.

### Resource files

| File | Validates |
| --- | --- |
| `openapi-resource.json` | A file grouping everything about one resource: a Components Object (`schemas`, `parameters`, `responses`…) with an extra `paths` map of named Path Items. |
| `openapi-resource-base.json` | 3.1 and 3.2 only. Same as `openapi-resource.json`, and Schema Objects are also validated against the OpenAPI JSON Schema dialect. |

This format isn't part of the OpenAPI Specification: it's meant for documents split into one file per resource,
whose parts are referenced from the main document (see [Resource files](#resource-files-1) below).

## Usage

The examples use jsDelivr and OpenAPI 3.1; see the [root README](../README.md#using-the-schemas) for the other
URLs. Replace `3.1` with `3.0` or `3.2` for other versions.

### Whole document

```yaml
# yaml-language-server: $schema=https://cdn.jsdelivr.net/gh/eleaven/schemas@main/openapi/3.1/openapi-base.json
openapi: 3.1.1
info:
  title: Example API
  version: 1.0.0
paths: {}
```

```bash
check-jsonschema --schemafile https://cdn.jsdelivr.net/gh/eleaven/schemas@main/openapi/3.1/openapi-base.json openapi.yaml
```

### Resource files

A resource file defines path items and components side by side:

```yaml
# yaml-language-server: $schema=https://cdn.jsdelivr.net/gh/eleaven/schemas@main/openapi/3.1/openapi-resource-base.json
paths:
  byId:
    get:
      summary: Get a product
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: string
      responses:
        "200":
          description: The product
          content:
            application/json:
              schema:
                $ref: "#/schemas/Product"
schemas:
  Product:
    type: object
    properties:
      id:
        type: string
        format: uuid
```

The main document then references its parts:

```yaml
paths:
  /products/{id}:
    $ref: "./products.yaml#/paths/byId"
```

## License

The generated schemas are derived from the [OpenAPI Initiative schemas](https://github.com/OAI/spec.openapis.org),
licensed under the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0). They are modified by
[`generate.py`](generate.py): resource schemas are added, `schema-base` is merged into its schema, and dynamic references
are replaced with static ones. The rest of this folder is under the repository's [MIT License](../LICENSE).
