"""Acceptance checks for the ontology engine (TZ_marimo_ontology.md §6.2-§6.5).

The ontology counterpart of the classifier's regression table: it runs ``ontology.engine`` over an
ontology file, prints the baseline next to the values fixed in the specification and exits with
code 1 if anything diverges. There is no pytest suite; this script is the test.

Usage (from the repository root; the script puts the root on ``sys.path`` itself)::

    python ontology/tests/check_ontology.py                                    # Ukrainian file
    python ontology/tests/check_ontology.py ontology/projects/ontology_UAV_models_en.json

Both files describe the same ontology, so both must pass with the same numbers. Language-specific
domain values used by the point checks are taken from ``POINT_VALUES`` by ``meta.language``.

What is checked (33 checks in total; the count is printed at the end):

* §6.2 — size of the O-space, valid / blocked / contradictory counts, and the per-rule breakdown
  of blocked vectors. The breakdown is first-cause and therefore depends on the order of the
  ``constraints`` array: reordering rules changes these numbers by design.
* §6.3 — point checks: specific vectors built from ``i7`` must be valid or blocked by a named
  rule; the residual domains of M1 and M2 must match.
* §6.4 — every instance passes the audit (coordinates in domains, vector valid, declared
  M-values within the residual domain). A failure here is a finding about the data, not a bug
  to be fixed by editing the JSON (TZ §6.4).
* §6.5 — mirror symmetry along the facets named by the mirror relations of the file.
* state of the space — occupied / gap counts; occupancy is decided by instance status, so a
  registered instance with status ``gap`` is still a gap.

``iterations`` is printed for information only and is not asserted.

The expected values below are the specification's baseline, not a snapshot of whatever the
engine currently prints. Change them only together with §6.2 of ontology/TZ_marimo_ontology.md,
and only when the ontology file itself changes.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ontology.engine import Ontology, OntologyEngine  # noqa: E402

DEFAULT_PATH = str(REPO_ROOT / "ontology" / "projects" / "ontology_UAV_models.json")

EXPECTED_TOTALS = {"all": 12288, "valid": 2080, "blocked": 10208, "contradictory": 0}
EXPECTED_SPACE = {"occupied": 2, "gap": 2078, "gap_registered": 5, "gap_unregistered": 2073}
POINT_VALUES = {
    "uk": {
        "O1_cold": "холодний резерв (mc)",
        "O4_none": "відсутні (m=0)",
        "O4_single": "один канал (m=1)",
        "O4_limited": "обмежені (1<m<D_max)",
        "O6_single": "одиночна",
        "O6_multiple": "множинна (каскадні)",
        "O8_none": "відсутня",
        "O9_infinite": "нескінченний",
        "O3_deterministic": "детермінований",
        "M2_markov": ("аналітичний CTMC", "SAM-ASNA"),
    },
    "en": {
        "O1_cold": "cold reserve (mc)",
        "O4_none": "none (m=0)",
        "O4_single": "single channel (m=1)",
        "O4_limited": "limited (1<m<D_max)",
        "O6_single": "single",
        "O6_multiple": "multiple (cascading)",
        "O8_none": "none",
        "O9_infinite": "infinite",
        "O3_deterministic": "deterministic",
        "M2_markov": ("analytical CTMC", "SAM-ASNA"),
    },
}
EXPECTED_BLOCKED_BY_RULE = {
    "c1": 2816,
    "c2": 1536,
    "c3": 1536,
    "c5": 544,
    "c6": 1792,
    "c7": 1440,
    "c8": 192,
    "c12": 352,
}


def _status(ok):
    return "OK" if ok else "FAIL"


def main(path):
    ontology = Ontology.load(path)
    engine = OntologyEngine(ontology)
    failures = []

    print("Ontology: %s (%s)" % (ontology.meta.get("title", path), path))
    print("Facets: %d object / %d methodological, constraints: %d, instances: %d\n"
          % (len(ontology.object_facets), len(ontology.methodological_facets),
             len(ontology.constraints), len(ontology.instances)))

    # 6.2 - space size and totals
    space = engine.generate_object_space()
    valid, blocked = engine.valid_object_configurations()
    contradictory = engine.contradictory_configurations()
    totals = {
        "all": len(space),
        "valid": len(valid),
        "blocked": len(blocked),
        "contradictory": len(contradictory),
    }

    print("6.2 Baseline")
    for key in ("all", "valid", "blocked", "contradictory"):
        ok = totals[key] == EXPECTED_TOTALS[key]
        failures.append(ok)
        print("  %-14s %6d   expected %6d   %s"
              % (key, totals[key], EXPECTED_TOTALS[key], _status(ok)))

    print("\n  Blocked by constraint (first cause, order-dependent):")
    by_rule = engine.blocked_by_constraint()
    for constraint in ontology.constraints:
        expected = EXPECTED_BLOCKED_BY_RULE.get(constraint.id, 0)
        actual = by_rule.get(constraint.id, 0)
        if expected == 0 and actual == 0:
            continue
        ok = actual == expected
        failures.append(ok)
        print("    %-5s %6d   expected %6d   %s" % (constraint.id, actual, expected, _status(ok)))

    print("\n  Iterations (condition checks, informational): %d" % engine.statistics["iterations"])

    # 6.3 - point checks
    i7 = ontology.instances_by_id["i7"].coords
    base = {f.id: i7[f.id] for f in ontology.object_facets}

    def variant(**overrides):
        coords = dict(base)
        coords.update(overrides)
        return coords

    v = POINT_VALUES[ontology.language]
    point_checks = [
        ("coords of i7", base, True, None),
        ("O4=none, O9=infinite",
         variant(O4=v["O4_none"], O9=v["O9_infinite"]), False, "c12"),
        ("O6=multiple, O2=1, O4=single channel",
         variant(O6=v["O6_multiple"], O2="1", O4=v["O4_single"]), False, "c5"),
        ("O6=single, O2=1, O4=limited",
         variant(O6=v["O6_single"], O2="1", O4=v["O4_limited"]), False, "c8"),
        ("O1=cold, O2=0", variant(O1=v["O1_cold"], O2="0"), False, "c6"),
        ("O1=cold, O8=none", variant(O1=v["O1_cold"], O8=v["O8_none"]), False, "c7"),
        ("O3=deterministic", variant(O3=v["O3_deterministic"]), True, None),
    ]

    print("\n6.3 Point checks")
    for label, coords, expect_valid, expect_rule in point_checks:
        result = engine.validate(coords)
        ok = result.is_valid == expect_valid and result.blocking_constraint == expect_rule
        failures.append(ok)
        verdict = "valid" if result.is_valid else "blocked by %s" % result.blocking_constraint
        print("  %-38s %-22s %s" % (label, verdict, _status(ok)))

    residual_i7 = engine.allowed_methodological_values(base)
    ok = residual_i7["M1"] == ["K_ss"]
    failures.append(ok)
    print("  %-38s M1 = %-17s %s" % ("residual M1 for i7", residual_i7["M1"], _status(ok)))

    residual_det = engine.allowed_methodological_values(variant(O3=v["O3_deterministic"]))
    ok = not (set(v["M2_markov"]) & set(residual_det["M2"]))
    failures.append(ok)
    print("  %-38s M2 = %s   %s"
          % ("residual M2 for O3=deterministic", residual_det["M2"], _status(ok)))

    # 6.4 - instance audit
    print("\n6.4 Instance audit")
    for entry in engine.audit_instances():
        failures.append(entry.ok)
        problems = []
        if entry.unknown_facets:
            problems.append("unknown facets: %s" % ", ".join(entry.unknown_facets))
        if entry.missing_facets:
            problems.append("missing facets: %s" % ", ".join(entry.missing_facets))
        if entry.out_of_domain:
            problems.append("out of domain: %s" % entry.out_of_domain)
        if not entry.is_valid:
            problems.append("blocked by %s" % entry.blocking_constraint)
        for facet_id, declared_ok in entry.declared_in_residual.items():
            if not declared_ok:
                problems.append("%s not in residual domain" % facet_id)
        print("  %-4s %-14s %-12s M1=%-10s %s%s"
              % (entry.instance_id, entry.model, entry.status,
                 ",".join(entry.residual["M1"]), _status(entry.ok),
                 "  " + "; ".join(problems) if problems else ""))

    # 6.5 - symmetry
    violations = engine.symmetry_violations()
    ok = not violations
    failures.append(ok)
    print("\n6.5 Symmetry (mirror pairs from the file: %s)" % engine.ontology.mirror_pairs())
    print("  violations: %d   expected 0   %s" % (len(violations), _status(ok)))

    # state of the space: occupancy is decided by status, a registered gap is still a gap
    summary = engine.space_summary()
    print("\nState of the model space")
    for key in ("occupied", "gap", "gap_registered", "gap_unregistered"):
        ok = summary[key] == EXPECTED_SPACE[key]
        failures.append(ok)
        print("  %-18s %6d   expected %6d   %s"
              % (key, summary[key], EXPECTED_SPACE[key], _status(ok)))

    passed = all(failures)
    print("\n%s (%d checks)" % ("ALL CHECKS PASSED" if passed else "CHECKS FAILED", len(failures)))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH))