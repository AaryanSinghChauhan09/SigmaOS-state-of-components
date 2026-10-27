"""Component health dashboard for SigmaOS-state-of-components
(inspired by state-of-omarchy).

Takes an injected inventory of components (name -> status/version) and
produces pure snapshots, diffs, gap analyses against a required set, and a
weighted health score. Nothing is probed from the real system; facts come in,
a dashboard goes out.
"""
import argparse, json, sys

ENGINE = {
    "name": "sigma-state",
    "summary": "Snapshot, diff, gap and score component health",
    "language": "python",
    "verbs": ["snapshot", "diff", "gaps", "score"],
    "principles": ["Pure Functions", "Deterministic Testing", "Fail-Fast",
                   "Least Astonishment", "KISS"],
}

cli_doc = """\
$ sigma-state snapshot --facts inventory.json --out snap.json
$ sigma-state diff --before old.json --after new.json
$ sigma-state gaps --snapshot snap.json --required required.txt
$ sigma-state score --snapshot snap.json
"""

VALID_STATUS = ("ok", "degraded", "failed", "missing", "unknown")


class StateError(Exception):
    pass


def normalize(facts):
    """Pure: validate + canonicalize an inventory dict.

    Accepts {"components": {...}} or a bare {name: {status, version}} map.
    """
    raw = facts.get("components", facts) if isinstance(facts, dict) else facts
    if not isinstance(raw, dict) or not raw:
        raise StateError("empty or invalid inventory")
    components = {}
    for name in sorted(raw):
        entry = raw[name]
        if isinstance(entry, str):  # shorthand: name -> status
            entry = {"status": entry}
        if not isinstance(entry, dict):
            raise StateError(f"component {name!r}: bad entry {entry!r}")
        status = entry.get("status", "unknown")
        if status not in VALID_STATUS:
            raise StateError(f"component {name!r}: bad status {status!r}; "
                             f"choose from {VALID_STATUS}")
        components[name] = {"status": status,
                            "version": entry.get("version"),
                            "detail": entry.get("detail")}
    return components


def snapshot(facts, timestamp="1970-01-01T00:00:00Z"):
    """Pure: inventory -> timestamped snapshot record."""
    components = normalize(facts)
    counts = {s: 0 for s in VALID_STATUS}
    for c in components.values():
        counts[c["status"]] += 1
    return {"timestamp": timestamp, "component_count": len(components),
            "counts": counts, "components": components}


def diff(before, after):
    """Pure: added/removed/changed components between two snapshots."""
    b = normalize(before)
    a = normalize(after)
    changes = []
    for name in sorted(set(b) | set(a)):
        if name not in b:
            changes.append({"component": name, "kind": "added",
                            "before": None, "after": a[name]})
        elif name not in a:
            changes.append({"component": name, "kind": "removed",
                            "before": b[name], "after": None})
        elif b[name] != a[name]:
            changes.append({"component": name, "kind": "changed",
                            "before": b[name], "after": a[name]})
    return changes


def gaps(snapshot_rec, required):
    """Pure: required components that are absent or not ok."""
    components = snapshot_rec.get("components", snapshot_rec)
    if not required:
        raise StateError("required list is empty")
    missing, broken = [], []
    for name in sorted(set(required)):
        if name not in components:
            missing.append(name)
        elif components[name].get("status") != "ok":
            broken.append({"component": name,
                           "status": components[name].get("status"),
                           "detail": components[name].get("detail")})
    return {"missing": missing, "broken": broken,
            "satisfied": [n for n in sorted(set(required))
                          if n in components
                          and components[n].get("status") == "ok"]}


WEIGHTS = {"ok": 1.0, "degraded": 0.5, "unknown": 0.25, "missing": 0.0,
           "failed": 0.0}


def score(snapshot_rec):
    """Pure: weighted health score 0-100, rounded, deterministic."""
    components = snapshot_rec.get("components", snapshot_rec)
    components = normalize(components)  # accept shorthand or full entries
    if not components:
        raise StateError("no components to score")
    total = sum(WEIGHTS[c.get("status", "unknown")] for c in components.values())
    value = round(100.0 * total / len(components))
    grade = ("A" if value >= 90 else "B" if value >= 75 else
             "C" if value >= 60 else "D" if value >= 40 else "F")
    worst = sorted((c for c in components if components[c].get("status")
                    in ("failed", "missing")),
                   key=str)
    return {"score": value, "grade": grade, "components": len(components),
            "worst": worst}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=ENGINE["name"], description=ENGINE["summary"])
    sub = p.add_subparsers(dest="cmd", required=True)
    sn = sub.add_parser("snapshot", help="validate + timestamp an inventory")
    sn.add_argument("--facts", required=True, help="JSON inventory file")
    sn.add_argument("--timestamp", default="1970-01-01T00:00:00Z")
    sn.add_argument("--out", default=None, help="write snapshot JSON here")
    df = sub.add_parser("diff", help="diff two snapshots")
    df.add_argument("--before", required=True)
    df.add_argument("--after", required=True)
    gp = sub.add_parser("gaps", help="check a snapshot against a required set")
    gp.add_argument("--snapshot", required=True)
    gp.add_argument("--required", required=True,
                    help="file with one component name per line")
    sc = sub.add_parser("score", help="compute the health score")
    sc.add_argument("--snapshot", required=True)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "snapshot":
            with open(args.facts) as fh:
                snap = snapshot(json.load(fh), args.timestamp)
            text = json.dumps(snap, indent=2, sort_keys=True)
            if args.out:
                with open(args.out, "w") as fh:
                    fh.write(text + "\n")
            print(text)
        elif args.cmd == "diff":
            with open(args.before) as fh:
                before = json.load(fh)
            with open(args.after) as fh:
                after = json.load(fh)
            changes = diff(before, after)
            if not changes:
                print("no changes")
            for c in changes:
                print(f"{c['kind']:8} {c['component']}")
        elif args.cmd == "gaps":
            with open(args.snapshot) as fh:
                snap = json.load(fh)
            with open(args.required) as fh:
                required = [l.strip() for l in fh if l.strip()]
            report = gaps(snap, required)
            for name in report["missing"]:
                print(f"MISSING  {name}")
            for item in report["broken"]:
                print(f"BROKEN   {item['component']} ({item['status']})")
            for name in report["satisfied"]:
                print(f"OK       {name}")
            return 1 if (report["missing"] or report["broken"]) else 0
        elif args.cmd == "score":
            with open(args.snapshot) as fh:
                result = score(json.load(fh))
            print(f"score: {result['score']}/100  grade: {result['grade']}  "
                  f"({result['components']} components)")
            if result["worst"]:
                print("worst: " + ", ".join(result["worst"]))
        return 0
    except (StateError, OSError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def self_test() -> None:
    # normalization accepts shorthand and validates statuses
    inv = {"terminal": "ok", "compositor": {"status": "ok", "version": "0.7"},
           "bar": {"status": "degraded", "detail": "missing glyphs"},
           "notify": {"status": "failed", "detail": "socket refused"}}
    components = normalize(inv)
    assert components["terminal"]["status"] == "ok"
    assert components["compositor"]["version"] == "0.7"
    assert list(components) == sorted(components)  # deterministic order
    assert normalize({"components": inv}) == components  # wrapped form too
    try:
        normalize({"x": {"status": "on-fire"}})
    except StateError as e:
        assert "bad status" in str(e)
    else:
        raise AssertionError("bad status not caught")
    try:
        normalize({})
    except StateError:
        pass
    else:
        raise AssertionError("empty inventory not caught")

    snap = snapshot(inv, "2026-10-24T12:00:00Z")
    assert snap["component_count"] == 4
    assert snap["counts"]["ok"] == 2 and snap["counts"]["failed"] == 1
    assert snap["timestamp"] == "2026-10-24T12:00:00Z"

    # diff: added / removed / changed / unchanged
    after_inv = {"terminal": {"status": "ok", "version": "2.0"},  # changed
                 "compositor": {"status": "ok", "version": "0.7"},  # same
                 "bar": "ok",  # changed (recovered)
                 "notify": "failed",  # same (shorthand == full)
                 "wallpaper": "ok"}  # added
    changes = diff(inv, after_inv)
    kinds = {c["component"]: c["kind"] for c in changes}
    # notify changes too: full entry (detail='socket refused') -> shorthand 'failed'
    assert kinds == {"terminal": "changed", "bar": "changed",
                     "notify": "changed", "wallpaper": "added"}, kinds
    term = [c for c in changes if c["component"] == "terminal"][0]
    assert term["before"]["version"] is None and term["after"]["version"] == "2.0"
    notify = [c for c in changes if c["component"] == "notify"][0]
    assert notify["before"]["detail"] == "socket refused"
    assert notify["after"] == {"status": "failed", "version": None, "detail": None}
    assert diff(inv, inv) == []
    # removal detection
    back = diff({"a": "ok", "b": "ok"}, {"a": "ok"})
    assert back == [{"component": "b", "kind": "removed",
                     "before": {"status": "ok", "version": None,
                                "detail": None}, "after": None}]

    # gaps against a required set
    report = gaps(snap, ["terminal", "compositor", "bar", "notify", "vpn"])
    assert report["missing"] == ["vpn"]
    assert [b["component"] for b in report["broken"]] == ["bar", "notify"]
    assert report["satisfied"] == ["compositor", "terminal"]
    ok_report = gaps(snap, ["terminal", "compositor"])
    assert ok_report["missing"] == [] and ok_report["broken"] == []
    try:
        gaps(snap, [])
    except StateError as e:
        assert "empty" in str(e)
    else:
        raise AssertionError("empty required list not caught")

    # scoring: weights, grade thresholds, worst list
    healthy = snapshot({"a": "ok", "b": "ok", "c": "ok", "d": "ok"})
    assert score(healthy) == {"score": 100, "grade": "A", "components": 4,
                              "worst": []}
    mixed = snapshot(inv)  # 2 ok, 1 degraded (0.5), 1 failed (0)
    result = score(mixed)
    assert result["score"] == round(100 * 2.5 / 4) == 62
    assert result["grade"] == "C"
    assert result["worst"] == ["notify"]
    half = score(snapshot({"a": "ok", "b": "degraded"}))
    assert half["score"] == 75 and half["grade"] == "B"
    dead = score({"a": "failed", "b": "failed"})
    assert dead["score"] == 0 and dead["grade"] == "F"
    try:
        score({"components": {}})
    except StateError:
        pass
    else:
        raise AssertionError("empty score not caught")

    # snapshot from an on-disk inventory round-trips through diff
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        path = f"{d}/inv.json"
        with open(path, "w") as fh:
            json.dump(inv, fh)
        with open(path) as fh:
            assert snapshot(json.load(fh))["counts"] == snap["counts"]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
