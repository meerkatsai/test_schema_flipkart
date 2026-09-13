"""Task-trace style span log: every report run emits (a) a human-readable stage log
and (b) a task-trace-v1-shaped JSON. This is the 'show me how the query was formed'
surface — nothing in the pipeline runs unlogged."""
import json, time, uuid, datetime, hashlib


def task_digest(task_env):
    """Content address of a task instance: sha256 over the canonical serialization
    (sorted keys, no whitespace). Identical tasks — across spans, traces, days —
    share one digest; this is the task_instances PRIMARY KEY and the artifact_ref
    digest the trace/audit layers point at."""
    canon = json.dumps(task_env, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canon.encode()).hexdigest()


class Trace:
    STAGES = ["route", "validate_structural", "validate_semantic", "resolve", "plan", "execute", "present"]

    def __init__(self, utterance, channel="report_harness"):
        self.trace_id = str(uuid.uuid4())
        self.received_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.input = {"utterance": utterance, "channel": channel}
        self.spans = []
        self.lines = []
        self._t0 = time.time()

    def span(self, stage, status="ok", detail=None, **attrs):
        s = {
            "span_id": f"s{len(self.spans)+1}",
            "parent_span_id": None,
            "stage": stage,
            "status": status,
            "duration_ms": round((time.time() - self._t0) * 1000, 1),
            "attributes": attrs,
        }
        self.spans.append(s)
        icon = {"ok": "✓", "error": "✗", "skipped": "·"}.get(status, "•")
        head = f"[{s['span_id']:>3}] {icon} {stage:<22}"
        self.lines.append(head + (detail or ""))
        for k, v in attrs.items():
            self.lines.append(f"       · {k}: {json.dumps(v, ensure_ascii=False, default=str)}")
        return s

    def note(self, text):
        self.lines.append(f"       » {text}")

    def finish(self, status, classification, task, output_ref=None, data_as_of=None):
        return {
            "trace_id": self.trace_id,
            "received_at": self.received_at,
            "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "input": self.input,
            "classification": classification,
            "task": task,
            "spans": self.spans,
            "outcome": {"status": status, "data_as_of": data_as_of,
                        **({"output": {"ref": output_ref}} if output_ref else {})},
        }

    def pretty(self):
        return "\n".join(self.lines)
