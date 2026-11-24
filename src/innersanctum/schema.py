"""Read OKF index declarations and validate authored concept fields."""

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import PurePosixPath
import json
import re
import tomllib

from markdown_it import MarkdownIt
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
from ruamel.yaml.nodes import MappingNode, ScalarNode
from ruamel.yaml.tokens import AliasToken, AnchorToken, DirectiveToken, TagToken


LIMIT = 1024 * 1024
MANAGED = frozenset({"id", "generated", "verified", "owner", "scope"})
ID = re.compile(r"bho:[0-9]{7}")
DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
TYPES = {"any", "bool", "bho", "date", "datetime", "dict", "enum", "integer", "list", "scalar", "string"}
MD = MarkdownIt("commonmark")


class Refused(Exception):
    """A safe, actionable command error."""


def read_text(raw):
    if len(raw) > LIMIT:
        raise Refused("A Markdown or TOML input exceeds 1 MiB.")
    try:
        return raw.decode("utf-8")
    except UnicodeError:
        raise Refused("An input is not UTF-8.") from None


def path_parts(value):
    if (type(value) is not str or not value or "\\" in value or
            any(not c.isprintable() for c in value)):
        raise Refused("Expected a visible bundle-relative path.")
    parts = value.split("/")
    if any(not part or part.startswith(".") for part in parts):
        raise Refused("Expected a visible bundle-relative path.")
    return parts


def yaml_reader(text, *, allow_opaque_tags=False):
    yaml = YAML(typ="safe", pure=True)
    yaml.allow_duplicate_keys = False
    yaml.max_depth = 32
    unsupported = (AliasToken, AnchorToken, DirectiveToken)
    if not allow_opaque_tags:
        unsupported += (TagToken,)
    for count, token in enumerate(yaml.scan(text), 1):
        if count > 40_000 or isinstance(token, unsupported):
            features = "directives, anchors or aliases" if allow_opaque_tags else "tags, directives, anchors or aliases"
            raise Refused(f"YAML exceeds the supported profile (no {features}).")
    return yaml


def mapping(text):
    try:
        data = yaml_reader(text).load(text)
    except (YAMLError, ValueError, TypeError, RecursionError, OverflowError):
        raise Refused("Invalid YAML mapping or duplicate key.") from None
    if type(data) is not dict or any(type(key) is not str for key in data):
        raise Refused("Expected a YAML mapping with string keys.")
    return data


def split_document(text, *, required=True):
    lines = text.split("\n")
    if lines[0] not in {"---", "---\r"}:
        if not required:
            return None, text, 0
        raise Refused("Concept input needs YAML frontmatter.")
    for i in range(1, len(lines)):
        if lines[i] in {"---", "---\r"}:
            return "\n".join(lines[1:i]) + "\n", "\n".join(lines[i + 1:]), i + 1
    raise Refused("YAML frontmatter is not closed.")


def document(text, *, required=True):
    frontmatter, body, offset = split_document(text, required=required)
    return mapping(frontmatter) if frontmatter is not None else {}, body, offset


def existing_identity(text):
    """Read an existing ID without constructing tagged legacy field values."""
    frontmatter, _, _ = split_document(text, required=False)
    if frontmatter is None:
        return None
    try:
        node = yaml_reader(frontmatter, allow_opaque_tags=True).compose(frontmatter)
    except (YAMLError, ValueError, TypeError, RecursionError, OverflowError):
        raise Refused("An existing concept has invalid YAML.") from None
    prefix = "tag:yaml.org,2002:"
    string = prefix + "str"
    if not isinstance(node, MappingNode) or node.tag != prefix + "map":
        raise Refused("An existing concept needs ordinary mapping frontmatter.")
    seen = set()
    identity = None
    for key, value in node.value:
        if (not isinstance(key, ScalarNode) or key.tag != string or key.value == "<<"
                or key.value in seen):
            raise Refused("An existing concept has ambiguous frontmatter keys.")
        seen.add(key.value)
        if key.value == "id":
            if not isinstance(value, ScalarNode) or value.tag != string or not value.value.strip():
                raise Refused("An existing concept has an invalid ID.")
            identity = value.value
    return identity


def declarations(text):
    _, body, _ = document(text, required=False)
    for token in MD.parse(body):
        if token.level or token.type != "fence" or token.info.strip().lower() not in {"yaml", "yml"}:
            continue
        data = mapping(token.content)
        if "okf_schema" not in data:
            continue
        if set(data) != {"okf_schema"} or type(data["okf_schema"]) is not dict:
            raise Refused("Malformed okf_schema declaration.")
        schema = data["okf_schema"]
        kind = schema.get("type")
        if type(kind) is not str or not kind.strip() or not kind.isprintable():
            raise Refused("A declaration needs a nonblank type.")
        yield kind, schema


def date_value(value):
    if type(value) is date:
        return True
    if type(value) is not str or not DATE.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def datetime_value(value):
    if type(value) is str:
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
                            r"(?:\.[0-9]+)?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])", value):
            return False
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return False
    return type(value) is datetime and value.utcoffset() is not None


def names(value):
    return (type(value) is list and all(type(k) is str and k.strip() and k.isprintable() for k in value)
            and len(value) == len(set(value)))


def same(left, right):
    if type(left) is not type(right):
        return False
    if type(left) is list:
        return len(left) == len(right) and all(same(a, b) for a, b in zip(left, right))
    if type(left) is dict:
        return left.keys() == right.keys() and all(same(left[key], right[key]) for key in left)
    return left == right


def rules(fields):
    if type(fields) is not dict or not names(list(fields)):
        raise Refused("Schema fields must be a mapping with unique names.")
    for name, rule in fields.items():
        rule_shape(rule, name)


def rule_shape(rule, name):
    if type(rule) is str:
        rule = {"type": rule}
    if type(rule) is not dict or "type" not in rule and "const" not in rule:
        raise Refused(f"Unsupported schema rule for {name}.")
    kind = rule.get("type", "any")
    if type(kind) is not str or kind not in TYPES:
        raise Refused(f"Unsupported schema field type for {name}.")
    extra = {"enum": {"values"}, "list": {"items", "bare_scalar"}, "dict": {"required", "fields"},
             "bho": {"allow_list"}}.get(kind, set())
    if set(rule) - ({"type", "const"} | extra):
        raise Refused(f"Unsupported schema rule for {name}.")
    if kind == "enum" and (type(rule.get("values")) is not list or not rule["values"]):
        raise Refused(f"An enum needs values: {name}.")
    for flag in ("allow_list", "bare_scalar"):
        if flag in rule and type(rule[flag]) is not bool:
            raise Refused(f"Invalid schema flag for {name}.")
    if "items" in rule:
        rule_shape(rule["items"], name)
    if kind == "dict":
        if not names(rule.get("required", [])):
            raise Refused(f"Invalid nested required fields for {name}.")
        rules(rule.get("fields", {}))


def matches(value, rule):
    if type(rule) is str:
        rule = {"type": rule}
    if "const" in rule and not same(value, rule["const"]):
        return False
    kind = rule.get("type", "any")
    if kind == "any":
        return True
    if kind in {"string", "integer", "bool"}:
        return type(value) is {"string": str, "integer": int, "bool": bool}[kind]
    if kind == "scalar":
        return type(value) in {str, int, float, bool, date, datetime}
    if kind == "bho":
        if type(value) is list and rule.get("allow_list"):
            return all(type(item) is str and ID.fullmatch(item) for item in value)
        return type(value) is str and bool(ID.fullmatch(value))
    if kind == "date":
        return date_value(value) or datetime_value(value)
    if kind == "datetime":
        return datetime_value(value)
    if kind == "enum":
        return any(same(value, allowed) for allowed in rule["values"])
    if kind == "list":
        item_rule = rule.get("items", "string")
        if type(value) is list:
            return all(matches(item, item_rule) for item in value)
        return bool(rule.get("bare_scalar") and matches(value, item_rule))
    return (type(value) is dict and all(type(key) is str for key in value)
            and not field_errors(value, rule.get("required", []), rule.get("fields", {})))


def field_errors(data, required, fields):
    return ([f"missing {key}" for key in required if data.get(key) is None]
            + [f"invalid {key}" for key, rule in fields.items() if key in data and not matches(data[key], rule)])


@dataclass(frozen=True)
class Route:
    kind: str
    directory: str
    required: tuple
    fields: dict
    variants: tuple
    forbidden: frozenset

    @property
    def index(self):
        return "index.md" if self.directory == "/" else f"{self.directory}/index.md"

    def target(self, identity):
        return str(PurePosixPath(self.index).with_name(f"{identity[4:]}.md"))

    def validate(self, data):
        problems = field_errors(data, self.required, self.fields)
        problems.extend(f"forbidden {key}" for key in sorted(self.forbidden.intersection(data)))
        title = data.get("title")
        if type(title) is not str or not title.strip() or not title.isprintable():
            problems.append("title must be a nonblank, single-line string")
        if problems:
            raise Refused("Concept does not match its schema: " + "; ".join(problems) + ".")

    def template(self):
        lines = ["---", f"type: {json.dumps(self.kind)}", "# InnerSanctum supplies id and generated."]
        for name in dict.fromkeys(("title", *self.required, *self.fields, *self.variants)):
            if name in MANAGED or name == "type" or name in self.forbidden:
                continue
            label = json.dumps(name, ensure_ascii=False)
            rule = self.fields.get(name)
            detail = f"; rule: {json.dumps(rule, default=str)}" if rule is not None else ""
            if name in self.required or name == "title":
                lines.extend((f"# Required{detail}", f"{label}: null"))
            else:
                lines.append(f"# {label}: null  # Optional{detail}")
        return "\n".join([*lines, "---", "", ""])


def resolve_route(kind, route_text, indexes):
    try:
        table = tomllib.loads(route_text)
    except tomllib.TOMLDecodeError:
        raise Refused("Invalid TOML creation routes.") from None
    if set(table) != {"types"} or type(table["types"]) is not dict:
        raise Refused("Invalid creation routing table.")
    if kind not in table["types"]:
        raise Refused("This type has no explicit creation route.")
    route = table["types"][kind]
    if type(route) is not dict or set(route) != {"schema", "directory"}:
        raise Refused("A creation route needs a declaring index and destination directory.")
    declaring, directory = route["schema"], route["directory"]
    if path_parts(declaring)[-1] != "index.md":
        raise Refused("Creation route must name an index.md declaration.")
    if directory != "/":
        path_parts(directory)
    found = [(path, schema) for path, text in indexes.items() for name, schema in declarations(text)
             if name == kind]
    if len(found) != 1 or found[0][0] != declaring:
        raise Refused("The routed type must have one matching declaration in the specified index.")
    schema = found[0][1]
    if set(schema) - {"type", "directory", "required", "fields", "variants", "legacy", "never"}:
        raise Refused("Unsupported type declaration keys.")
    if "directory" in schema:
        scope = schema["directory"]
        if scope != "/":
            path_parts(scope)
        if directory != scope and (scope == "/" or not directory.startswith(scope + "/")):
            raise Refused("The creation destination is outside the schema's directory scope.")
    required, variants, legacy = (schema.get(key, []) for key in ("required", "variants", "legacy"))
    forbidden, fields = schema.get("never", {}), schema.get("fields", {})
    if (not all(names(value) for value in (required, variants, legacy))
            or type(forbidden) is not dict or not names(list(forbidden))):
        raise Refused("Unsupported schema field lists.")
    rules(fields)
    result = Route(kind, directory, tuple(required), fields, tuple(variants), frozenset(forbidden))
    if result.index not in indexes:
        raise Refused("The destination must already have an index.md.")
    return result
