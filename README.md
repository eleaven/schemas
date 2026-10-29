# JSON Schemas

[![OpenAPI workflow](https://img.shields.io/github/actions/workflow/status/eleaven/schemas/openapi.yaml?branch=main&label=openapi)](https://github.com/eleaven/schemas/actions/workflows/openapi.yaml)
[![Last commit](https://img.shields.io/github/last-commit/eleaven/schemas/main)](https://github.com/eleaven/schemas/commits/main)

Improved JSON Schemas, automatically kept up to date with their upstream sources by GitHub Actions.

## Why?

The schemas in this repository start from the upstream version and improve it, for example by:

- fixing mistakes or inconsistencies in the upstream schema;
- adding stricter constraints where the specification allows it;
- splitting definitions into reusable sub-schemas.

The goal is a better experience in IDEs and more reliable validation in CI, while staying compatible with the
upstream specification.

## Schema catalog

| Schema | Upstream | Documentation |
| --- | --- | --- |
| OpenAPI | [OpenAPI Initiative](https://spec.openapis.org/) | [`openapi/README.md`](openapi/README.md) |

## Using the schemas

Every schema in this repository can be referenced by URL, for example in a `$schema` keyword or in your editor
settings. Two sources are available:

| Source | URL pattern |
| --- | --- |
| jsDelivr (recommended) | `https://cdn.jsdelivr.net/gh/eleaven/schemas@main/<path>` |
| GitHub raw | `https://raw.githubusercontent.com/eleaven/schemas/main/<path>` |

For example, the OpenAPI 3.1 schema:

```text
https://cdn.jsdelivr.net/gh/eleaven/schemas@main/openapi/3.1/openapi.json
https://raw.githubusercontent.com/eleaven/schemas/main/openapi/3.1/openapi.json
```

> [!WARNING]
> `raw.githubusercontent.com` serves every file with a `Content-Type: text/plain` header. Some IDEs and tools
> handle this badly and may refuse to load the schema or ignore it. Prefer the jsDelivr URL, which is served
> as `application/json`.

> [!NOTE]
> jsDelivr caches files fetched from a branch, so a fresh update can take a few hours to show up. To get it
> immediately, purge the cache by replacing `cdn` with `purge` in the URL
> (`https://purge.jsdelivr.net/gh/eleaven/schemas@main/<path>`).

### Usage in a YAML file

Any editor using the YAML language server (VS Code, Neovim, Helix, …) picks up a modeline at the top of the file:

```yaml
# yaml-language-server: $schema=https://cdn.jsdelivr.net/gh/eleaven/schemas@main/openapi/3.1/openapi.json
openapi: 3.1.0
```

### Validate from the command line

With [check-jsonschema](https://github.com/python-jsonschema/check-jsonschema):

```bash
check-jsonschema --schemafile https://cdn.jsdelivr.net/gh/eleaven/schemas@main/openapi/3.1/openapi.json openapi.yaml
```

## Automatic updates

Each schema has its own GitHub Actions workflow in [`.github/workflows`](.github/workflows) (for example
[`openapi.yaml`](.github/workflows/openapi.yaml)), which runs every week. On each run, the workflow:

1. downloads the latest upstream schema;
2. applies this repository's improvements on top of it;
3. commits the result to `main` if anything changed.
