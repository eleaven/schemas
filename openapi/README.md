# OpenAPI schemas

JSON Schemas for [OpenAPI](https://spec.openapis.org/) documents, split into one file per object so each part
of a document can be validated on its own.

| Version | Folder | JSON Schema dialect | Upstream |
| --- | --- | --- | --- |
| 3.0 | [`3.0`](3.0) | Draft 4 | [`oas/3.0/schema`](https://github.com/OAI/spec.openapis.org/tree/main/oas/3.0/schema/) |
| 3.1 | [`3.1`](3.1) | Draft 2020-12 | [`oas/3.1/schema`](https://github.com/OAI/spec.openapis.org/tree/main/oas/3.1/schema/), [`oas/3.1/schema-base`](https://github.com/OAI/spec.openapis.org/tree/main/oas/3.1/schema-base/) |
| 3.2 | [`3.2`](3.2) | Draft 2020-12 | [`oas/3.2/schema`](https://github.com/OAI/spec.openapis.org/tree/main/oas/3.2/schema/), [`oas/3.2/schema-base`](https://github.com/OAI/spec.openapis.org/tree/main/oas/3.2/schema-base/) |

The files are generated from the latest upstream schemas by [`update.py`](update.py). Don't edit them by hand.

## Files

### Whole document

| File | Validates |
| --- | --- |
| `openapi.json` | A complete OpenAPI document. In 3.1 and 3.2, Schema Objects are only checked to be objects or booleans. |
| `openapi-base.json` | 3.1 and 3.2 only. Same as `openapi.json`, and Schema Objects are also validated against the OpenAPI JSON Schema dialect. |

`openapi-base.json` is stricter, but it references the dialect and meta-schemas hosted on spec.openapis.org, so
the validator needs network access. In 3.0, `openapi.json` already validates Schema Objects.

### Sub-schemas

Every other file validates a single part of a document and is named `openapi-<name>.json`:

- **Objects**: one file per OpenAPI object, such as `openapi-info.json`, `openapi-path-item.json`,
  `openapi-operation.json`, `openapi-parameter.json`, `openapi-response.json` or `openapi-schema.json`.
- **Objects or references**: `openapi-<object>-or-reference.json` accepts either the object or a Reference
  Object (`$ref`), such as `openapi-parameter-or-reference.json`.
- **Collections**: arrays and maps of objects, as found in the document:

  | File | Content | Used by |
  | --- | --- | --- |
  | `openapi-paths.json` | Paths Object | `paths` |
  | `openapi-responses.json` | Responses Object | `responses` in an operation |
  | `openapi-parameters.json` | Array of parameters or references | `parameters` |
  | `openapi-servers.json` | Array of servers | `servers` |
  | `openapi-security.json` | Array of security requirements | `security` |
  | `openapi-tags.json` | Array of tags | `tags` at the root |
  | `openapi-webhooks.json` | Map of path items (3.1+) | `webhooks` |
  | `openapi-content.json` | Map of media types | `content` |
  | `openapi-headers.json` | Map of headers or references | `headers` |
  | `openapi-links.json` | Map of links or references | `links` |
  | `openapi-examples.json` | Map of examples or references | `examples` |
  | `openapi-callbacks.json` | Map of callbacks or references | `callbacks` |
  | `openapi-encodings.json` | Map of encodings | `encoding` in a media type |
  | `openapi-server-variables.json` | Map of server variables | `variables` in a server |

The file names use kebab-case in every version, including 3.0 whose upstream names are in PascalCase
(`PathItem` becomes `openapi-path-item.json`). Two upstream definitions are renamed to free their name for a
collection: the Callback Object is `openapi-callback.json` (upstream `callbacks`), and the mixin that forbids
`example` and `examples` together is `openapi-example-xor-examples.json` (upstream `examples`).

> [!NOTE]
> In 3.1 and 3.2, a sub-schema used on its own doesn't validate the Schema Objects it contains: only
> `openapi-base.json` does.

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

### Split documents

When a document is split into several files, point each file to the sub-schema matching its content. For example,
a Path Item referenced from `paths` with `$ref: ./paths/users.yaml`:

```yaml
# yaml-language-server: $schema=https://cdn.jsdelivr.net/gh/eleaven/schemas@main/openapi/3.1/openapi-path-item.json
get:
  summary: List users
  responses:
    "200":
      description: The users
```

```bash
check-jsonschema --schemafile https://cdn.jsdelivr.net/gh/eleaven/schemas@main/openapi/3.1/openapi-path-item.json paths/users.yaml
```

### In your own schemas

Sub-schemas can be referenced from another JSON Schema of the same dialect, for example to describe a
configuration file that embeds OpenAPI servers:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "servers": {
      "$ref": "https://cdn.jsdelivr.net/gh/eleaven/schemas@main/openapi/3.1/openapi-servers.json"
    }
  }
}
```
