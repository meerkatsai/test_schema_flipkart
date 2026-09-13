"""Real contract validation — the vendored *.schema.json files from contracts/dsl,
registered by $id exactly like the otter service's ajv loader, validated with
jsonschema Draft 2020-12. No hand-rolled shape checks."""
import os, json, glob
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_schemas = {}
for f in glob.glob(os.path.join(HERE, "layers", "*", "*.schema.json")):
    s = json.load(open(f))
    _schemas[s["$id"]] = s

TASK_ROUTER = "https://meerkats.ai/schemas/task-router/v1.json"
CATALOG_PLAN = "https://meerkats.ai/schemas/catalog_resolved_plan/v1.json"
CARD = "https://meerkats.ai/schemas/ad-dashboards/card.schema.json"

# the data→UI contract: card.schema.json (vendored from ad-dashboards-prebuilt)
_card_schema = json.load(open(os.path.join(HERE, "layers", "5-presentation-layer", "card.schema.json")))
_schemas[CARD] = _card_schema

_registry = Registry().with_resources(
    (sid, Resource.from_contents(s)) for sid, s in _schemas.items())

_validators = {sid: Draft202012Validator(s, registry=_registry) for sid, s in _schemas.items()}


def validate(schema_id, instance):
    """returns (ok, [error strings])"""
    v = _validators[schema_id]
    errs = sorted(v.iter_errors(instance), key=lambda e: list(e.path))
    return (not errs), [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message[:160]}" for e in errs[:5]]


def validate_ui_payload(representation, payload):
    """The data→UI gate: a chart payload must validate against
    card.schema.json#/$defs/<representation>Data before it is handed to the
    renderer. Underscore-prefixed keys are harness-side render hints, stripped
    at this boundary — the UI contract has additionalProperties:false."""
    clean = {k: v for k, v in payload.items() if not k.startswith("_")}
    sub = {"$ref": f"{CARD}#/$defs/{representation}Data"}
    v = Draft202012Validator(sub, registry=_registry)
    errs = sorted(v.iter_errors(clean), key=lambda e: list(e.path))
    return (not errs), [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message[:160]}" for e in errs[:5]], clean


def loaded():
    return sorted(_schemas)
