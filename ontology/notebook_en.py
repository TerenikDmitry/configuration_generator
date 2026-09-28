"""marimo notebook for the reliability-model ontology of UAV groups (English version).

    marimo edit ontology/notebook_en.py     # notebook
    marimo run  ontology/notebook_en.py     # web app

English counterpart of ontology/notebook.py; opens ontology/projects/ontology_UAV_models_en.json
by default and exports to ontology/exports/. Cells follow TZ_marimo_ontology.md §5: loading,
facets, constraints, engine run, instance audit, gap matrix, mission search, export. All
computation lives in ontology/engine.py.
"""

import marimo

__generated_with = "0.17.6"
app = marimo.App(width="medium")


@app.cell
def _():
    import json
    import sys
    from pathlib import Path

    import marimo as mo
    import pandas as pd

    HERE = (
        Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd() / "ontology"
    )
    REPO_ROOT = HERE.parent
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    PROJECTS = HERE / "projects"
    EXPORTS = HERE / "exports"

    from ontology.engine import Ontology, OntologyEngine
    return EXPORTS, HERE, Ontology, OntologyEngine, PROJECTS, json, mo, pd


@app.cell
def _(mo):
    mo.md("""
    # Ontology of reliability and availability models for UAV groups

    The next layer on top of the method for building strategy classifiers: facets are split into
    the **object layer O** (properties of the system) and the **methodological layer M** (the
    researcher's decisions). The Cartesian product is built over layer O only; layer M is not
    enumerated but narrowed by O → M rules to a **residual domain**.

    A gap is a cell of the space that is both **admissible** under the constraints and
    **unpopulated** by any instance.
    """)
    return


@app.cell
def _(PROJECTS, mo):
    _files = sorted(p.name for p in PROJECTS.glob("*.json"))
    _default = "ontology_UAV_models_en.json"
    file_dropdown = mo.ui.dropdown(
        options=_files,
        value=_default if _default in _files else (_files[0] if _files else None),
        label="## 1. Project file",
    )
    file_dropdown
    return (file_dropdown,)


@app.cell
def _(Ontology, OntologyEngine, PROJECTS, file_dropdown, mo):
    ontology = Ontology.load(str(PROJECTS / file_dropdown.value))
    engine = OntologyEngine(ontology)

    _meta = ontology.meta
    _lines = ["### %s" % _meta.get("title", file_dropdown.value)]
    for _key in ("version", "date", "base_format"):
        if _meta.get(_key):
            _lines.append("- **%s:** %s" % (_key, _meta[_key]))
    if _meta.get("extensions"):
        _lines.append("- **format extensions:**")
        _lines += ["    - %s" % _item for _item in _meta["extensions"]]
    _notes = _meta.get("notes") or []
    if isinstance(_notes, str):
        _notes = [_notes]
    if _notes:
        _lines.append("- **notes:**")
        _lines += ["    - %s" % _item for _item in _notes]
    for _name, _body in (_meta.get("derived_quantities") or {}).items():
        _lines.append("- **%s** — %s: %s" % (_name, _body.get("name", ""), _body.get("description", "")))
        _lines += ["    - %s" % _rule for _rule in _body.get("rules", [])]
    if not ontology.instances:
        _lines.append(
            "\n> This file has no `instances` block. "
            "The audit, search and export cells will be empty."
        )
    mo.md("\n".join(_lines))
    return engine, ontology


@app.cell
def _(mo, ontology, pd):
    facets_df = pd.DataFrame(
        [
            {
                "id": _f.id,
                "name": _f.name,
                "domain": " | ".join(_f.domain),
                "layer": _f.layer,
                "group": _f.group or "",
                "facet type": _f.facet_type or "",
                "weight": _f.weight,
            }
            for _f in ontology.facets()
        ]
    )
    mo.vstack(
        [
            mo.md("## 2. Facets"),
            mo.md(
                "Layer O — %d facets, layer M — %d. The weight is used only in the weighted "
                "distance `d_w`; layer M facets have weight 0 and do not enter the distance."
                % (len(ontology.object_facets), len(ontology.methodological_facets))
            ),
            mo.ui.table(facets_df, selection=None, page_size=15),
        ]
    )
    return


@app.cell
def _():
    def format_condition(condition):
        feature = condition.get("feature", "?")
        if "values" in condition:
            return "%s ∈ {%s}" % (feature, ", ".join(condition["values"]))
        return "%s = %s" % (feature, condition.get("value"))

    def format_action(action):
        feature = action.get("feature")
        mode = action.get("mode")
        if mode == "annotate":
            return "annotation: “%s”" % action.get("annotation", "")
        if "blocked_values" in action:
            return "%s ≠ {%s}" % (feature, ", ".join(action["blocked_values"]))
        return "%s: %s" % (feature, mode)
    return format_action, format_condition


@app.cell
def _(format_action, format_condition, mo, ontology, pd):
    constraints_df = pd.DataFrame(
        [
            {
                "id": _c.id,
                "kind": _c.kind or "",
                "rule_type": _c.rule_type,
                "conditions": " and ".join(format_condition(_x) for _x in _c.conditions),
                "actions": " ; ".join(format_action(_x) for _x in _c.actions),
                "description": _c.description,
            }
            for _c in ontology.constraints
        ]
    )
    mo.vstack(
        [
            mo.md("## 3. Constraints"),
            mo.md(
                "Rules are applied **in array order**: a blocked configuration is attributed to "
                "the id of the **first** rule that cut it off. They must not be sorted — the "
                "order sets the diagnostic priority."
            ),
            mo.ui.table(
                constraints_df.sort_values("kind", kind="stable") if "kind" in constraints_df
                else constraints_df,
                selection=None,
                page_size=15,
            ),
        ]
    )
    return


@app.cell
def _(engine, mo, ontology):
    _space = engine.generate_object_space()
    _space_summary = engine.space_summary()
    _valid, _blocked = engine.valid_object_configurations()
    _contradictory = engine.contradictory_configurations()
    _by_rule = engine.blocked_by_constraint()

    _summary = "\n".join(
        [
            "| metric | value |",
            "|---|---|",
            "| total O-configurations | **%d** |" % len(_space),
            "| valid | **%d** |" % len(_valid),
            "| blocked | **%d** |" % len(_blocked),
            "| contradictory (empty M domain) | **%d** |" % len(_contradictory),
            "| occupied (a built model exists) | **%d** |" % _space_summary["occupied"],
            "| gaps, total | **%d** |" % _space_summary["gap"],
            "| &nbsp;&nbsp;· entered in the register (status `gap`) | **%d** |"
            % _space_summary["gap_registered"],
            "| &nbsp;&nbsp;· not entered in the register | **%d** |"
            % _space_summary["gap_unregistered"],
        ]
    )

    _bars = []
    _peak = max(_by_rule.values()) if _by_rule else 1
    for _constraint in ontology.constraints:
        _count = _by_rule.get(_constraint.id, 0)
        if not _count:
            continue
        _width = 100.0 * _count / _peak
        _bars.append(
            "<tr>"
            "<td style='padding:2px 10px 2px 0;white-space:nowrap;font-family:monospace'>%s</td>"
            "<td style='width:100%%'><div style='background:rgba(99,102,241,.55);"
            "height:14px;border-radius:3px;width:%.1f%%'></div></td>"
            "<td style='padding:2px 0 2px 10px;text-align:right;font-variant-numeric:tabular-nums'>"
            "%d</td></tr>" % (_constraint.id, _width, _count)
        )
    _chart = mo.Html(
        "<table style='width:100%%;border-collapse:collapse'>%s</table>" % "".join(_bars)
        if _bars
        else "<em>no rule blocked anything</em>"
    )

    if _contradictory:
        _contra = mo.md(
            "**Contradictory configurations (%d).** An empty residual domain is a defect of the "
            "rule set, not a property of the system:\n\n%s"
            % (
                len(_contradictory),
                "\n".join(
                    "- `%s` → domain **%s** emptied by rules %s"
                    % (engine.format_configuration(_e.coords), _e.facet_id,
                       ", ".join(_e.emptying_constraints))
                    for _e in _contradictory[:20]
                ),
            )
        )
    else:
        _contra = mo.md(
            "**No contradictory configurations.** This is exactly the case the reconciling "
            "rule guards against: it cuts the combination off at the object layer before the "
            "metric's domain becomes empty."
        )

    mo.vstack(
        [
            mo.md("## 4. Engine run"),
            mo.md(_summary),
            mo.md("**How many configurations each rule blocked** (by first cause):"),
            _chart,
            _contra,
        ]
    )
    return


@app.cell
def _(engine, mo, pd):
    _rows = []
    for _entry in engine.audit_instances():
        _problems = []
        if _entry.unknown_facets:
            _problems.append("unknown facets: %s" % ", ".join(_entry.unknown_facets))
        if _entry.missing_facets:
            _problems.append("missing coordinates: %s" % ", ".join(_entry.missing_facets))
        if _entry.out_of_domain:
            _problems.append(
                "out of domain: %s"
                % ", ".join("%s=%s" % (_f, _v) for _f, _v in _entry.out_of_domain)
            )
        if not _entry.is_valid:
            _problems.append("blocked by rule %s" % _entry.blocking_constraint)
        for _facet_id, _ok in _entry.declared_in_residual.items():
            if not _ok:
                _problems.append("declared %s outside the residual domain" % _facet_id)
        _rows.append(
            {
                "id": _entry.instance_id,
                "model": _entry.model,
                "status": _entry.status,
                "coordinates in domains": "yes" if not (
                    _entry.unknown_facets or _entry.missing_facets or _entry.out_of_domain
                ) else "no",
                "vector valid": "yes" if _entry.is_valid else "no",
                "residual M1": ", ".join(_entry.residual.get("M1", [])),
                "residual M2": ", ".join(_entry.residual.get("M2", [])),
                "summary": "OK" if _entry.ok else "; ".join(_problems),
            }
        )

    audit_df = pd.DataFrame(_rows)
    mo.vstack(
        [
            mo.md("## 5. Instance audit"),
            mo.md(
                "Automation of the manual check: coordinates lie inside the domains, the vector "
                "passes all rules, and the declared metric stays in the residual domain of layer M."
            ),
            mo.ui.table(audit_df, selection=None, page_size=15)
            if not audit_df.empty
            else mo.md("_the file has no instances_"),
            mo.md(
                "**All %d instances passed the check.**" % len(_rows)
                if _rows and all(_r["summary"] == "OK" for _r in _rows)
                else "**There are findings — see the “summary” column.** Do not edit the JSON "
                     "on your own."
            )
            if _rows
            else mo.md(""),
        ]
    )
    return


@app.cell
def _(mo, ontology):
    _axis_options = {"%s — %s" % (_f.id, _f.name): _f.id for _f in ontology.object_facets}
    _labels = list(_axis_options)
    _by_id = {_v: _k for _k, _v in _axis_options.items()}

    axis_x = mo.ui.dropdown(
        options=_axis_options,
        value=_by_id.get("O2", _labels[0]),
        label="X axis",
    )
    axis_y = mo.ui.dropdown(
        options=_axis_options,
        value=_by_id.get("O4", _labels[min(1, len(_labels) - 1)]),
        label="Y axis",
    )

    _source = ontology.instances_by_id.get("i7") or (
        ontology.instances[0] if ontology.instances else None
    )
    fixed_filters = mo.ui.dictionary(
        {
            _f.id: mo.ui.dropdown(
                options=list(_f.domain),
                value=(
                    _source.coords.get(_f.id)
                    if _source and _source.coords.get(_f.id) in _f.domain
                    else _f.domain[0]
                ),
                label="%s — %s" % (_f.id, _f.name),
            )
            for _f in ontology.object_facets
        }
    )

    mo.vstack(
        [
            mo.md("## 6. Gap matrix"),
            mo.md(
                "The axes are two layer O facets; the remaining coordinates are fixed by the "
                "filters (by default — the slice around `i7`). A cell is a **gap** if and only if "
                "it is admissible under the constraints and unpopulated by an instance."
            ),
            mo.hstack([axis_x, axis_y], justify="start", gap=2),
            mo.md("**Fixed coordinates** (the selected axes are ignored):"),
            fixed_filters.hstack(justify="start", gap=1, wrap=True),
        ]
    )
    return axis_x, axis_y, fixed_filters


@app.cell
def _(axis_x, axis_y, engine, fixed_filters, mo, ontology):
    if axis_x.value == axis_y.value:
        gap_matrix = None
        gap_view = mo.md("> **The axes must be different facets.**")
    else:
        gap_matrix = engine.gap_matrix(
            axis_x.value,
            axis_y.value,
            {_k: _v for _k, _v in fixed_filters.value.items()
             if _k not in (axis_x.value, axis_y.value)},
        )

        _palette = {
            "occupied": ("rgba(34,197,94,.22)", "occupied"),
            "gap_registered": ("rgba(249,115,22,.22)", "registered gap"),
            "gap": ("rgba(234,179,8,.22)", "gap"),
            "blocked": ("rgba(148,163,184,.18)", "forbidden"),
        }
        _cell_style = (
            "border:1px solid rgba(128,128,128,.35);padding:6px 8px;"
            "font-size:.85em;vertical-align:top;background:%s"
        )
        _head_style = (
            "border:1px solid rgba(128,128,128,.35);padding:6px 8px;font-size:.85em;"
            "font-weight:600;text-align:left"
        )

        _header = "".join("<th style='%s'>%s</th>" % (_head_style, _x)
                          for _x in gap_matrix.x_values)
        _body = []
        for _y in gap_matrix.y_values:
            _cells = []
            for _x in gap_matrix.x_values:
                _cell = gap_matrix.cell(_x, _y)
                _colour, _label = _palette[_cell.state]
                if _cell.state in ("occupied", "gap_registered"):
                    _detail = "<br>".join(
                        "<code>%s</code> — %s" % (_i.id, _i.status) for _i in _cell.instances
                    )
                elif _cell.state == "blocked":
                    _detail = "rule <code>%s</code>" % _cell.constraint_id
                else:
                    _detail = "&mdash;"
                _cells.append(
                    "<td style='%s'><strong>%s</strong><br>%s</td>"
                    % (_cell_style % _colour, _label, _detail)
                )
            _body.append(
                "<tr><th style='%s'>%s</th>%s</tr>" % (_head_style, _y, "".join(_cells))
            )

        _counts = gap_matrix.counts()
        _legend = " &nbsp;·&nbsp; ".join(
            "<span style='background:%s;padding:2px 8px;border-radius:3px'>%s: %d</span>"
            % (_palette[_state][0], _palette[_state][1], _counts[_state])
            for _state in ("occupied", "gap_registered", "gap", "blocked")
        )
        gap_view = mo.vstack(
            [
                mo.md(
                    "**%s** (Y) × **%s** (X)"
                    % (ontology.facet(axis_y.value).name, ontology.facet(axis_x.value).name)
                ),
                mo.Html(
                    "<div style='overflow-x:auto'><table style='border-collapse:collapse'>"
                    "<tr><th style='%s'></th>%s</tr>%s</table></div>"
                    % (_head_style, _header, "".join(_body))
                ),
                mo.Html("<div style='margin-top:6px'>%s</div>" % _legend),
            ]
        )
    gap_view
    return


@app.cell
def _(mo, ontology):
    _source = ontology.instances_by_id.get("i7") or (
        ontology.instances[0] if ontology.instances else None
    )
    mission_inputs = mo.ui.dictionary(
        {
            _f.id: mo.ui.dropdown(
                options=list(_f.domain),
                value=(
                    _source.coords.get(_f.id)
                    if _source and _source.coords.get(_f.id) in _f.domain
                    else _f.domain[0]
                ),
                label="%s — %s" % (_f.id, _f.name),
            )
            for _f in ontology.object_facets
        }
    )
    search_button = mo.ui.run_button(label="Run search (Algorithm 1)")

    mo.vstack(
        [
            mo.md("## 7. Search by mission conditions"),
            mo.md(
                "Input — a vector of layer O coordinates. Output — either an existing suitable "
                "instance, or a new instance with status `gap` together with a draft technical "
                "specification."
            ),
            mission_inputs.hstack(justify="start", gap=1, wrap=True),
            search_button,
        ]
    )
    return mission_inputs, search_button


@app.cell
def _(engine, mission_inputs, mo, pd, search_button):
    mo.stop(not search_button.value, mo.md("_Press the button to run the search._"))

    search_result = engine.search(dict(mission_inputs.value))
    _blocks = [mo.md("### Result: `%s`" % search_result.outcome)]

    if search_result.outcome == "blocked":
        _blocks.append(
            mo.md(
                "The vector is **inadmissible**: blocked by rule `%s`.\n\n"
                "Nearest admissible vectors (one coordinate changed) — %d:"
                % (search_result.blocking_constraint, len(search_result.nearest_admissible))
            )
        )
        _blocks.append(
            mo.ui.table(
                pd.DataFrame([dict(_c) for _c in search_result.nearest_admissible]),
                selection=None,
                page_size=10,
            )
            if search_result.nearest_admissible
            else mo.md("_none — the vector cannot be reached by changing one coordinate_")
        )
    elif search_result.outcome == "contradictory":
        _blocks.append(
            mo.md(
                "**Contradiction in the rule set.** Empty residual domain:\n\n%s"
                % "\n".join(
                    "- **%s** emptied by rules %s"
                    % (_e.facet_id, ", ".join(_e.emptying_constraints))
                    for _e in search_result.contradictions
                )
            )
        )
    else:
        _blocks.append(
            mo.md(
                "**Residual domains of layer M:** %s"
                % "; ".join(
                    "`%s` = {%s}" % (_k, ", ".join(_v))
                    for _k, _v in search_result.residual.items()
                )
            )
        )
        if search_result.annotations:
            _blocks.append(
                mo.md("**Annotations:** %s" % "; ".join(search_result.annotations))
            )

        _blocks.append(mo.md("**Neighbours** (distance over layer O only):"))
        _blocks.append(
            mo.ui.table(
                pd.DataFrame(
                    [
                        {
                            "id": _n.instance.id,
                            "model": _n.instance.model,
                            "status": _n.instance.status,
                            "d": _n.distance,
                            "d_w": _n.weighted_distance,
                        }
                        for _n in search_result.neighbours
                    ]
                ),
                selection=None,
                page_size=10,
            )
            if search_result.neighbours
            else mo.md("_the file has no instances_")
        )

        if search_result.outcome == "existing":
            _blocks.append(
                mo.md(
                    "d_w = 0 and status “%s” → **a suitable model already exists**: `%s` %s"
                    % (
                        search_result.matched.status,
                        search_result.matched.id,
                        search_result.matched.model,
                    )
                )
            )
        elif search_result.outcome == "joins_gap":
            _blocks.append(
                mo.md(
                    "d_w = 0 and status `gap` → the request **joins an existing gap** "
                    "`%s` %s" % (search_result.matched.id, search_result.matched.model)
                )
            )
        else:
            _blocks.append(
                mo.md(
                    "d_w > 0 → **a new instance is created** `%s` with status `gap`.\n\n"
                    "#### Draft technical specification\n\n"
                    "The coordinates that diverge from the nearest neighbour `%s` are the "
                    "estimate of the cost of the extra work:"
                    % (search_result.new_instance["id"], search_result.nearest.id)
                )
            )
            _blocks.append(
                mo.ui.table(
                    pd.DataFrame(
                        [
                            {
                                "facet": "%s — %s" % (_d.facet_id, _d.facet_name),
                                "facet type": _d.facet_type or "",
                                "weight": _d.weight,
                                "neighbour has": _d.from_value,
                                "required": _d.to_value,
                            }
                            for _d in search_result.divergences
                        ]
                    ),
                    selection=None,
                    page_size=10,
                )
            )
            _blocks.append(
                mo.md(
                    "**Verification plan — candidates** (carried over from relations already "
                    "written in the file; the engine does not derive new ones, see the TODO in "
                    "§4.6 of the spec):"
                )
            )
            _blocks.append(
                mo.ui.table(
                    pd.DataFrame(list(search_result.verification_candidates)),
                    selection=None,
                    page_size=10,
                )
                if search_result.verification_candidates
                else mo.md("_none_")
            )

        _blocks.append(
            mo.md(
                "#### Adjacent gaps (ranked by d_w)\n\n"
                "d_w = 1 along a parametric facet inherits the graph structure; d_w ≥ 2 requires "
                "rebuilding the state space. The mirror along O1 is not a gap but a precondition "
                "for comparing strategies."
            )
        )
        _blocks.append(
            mo.ui.table(
                pd.DataFrame(
                    [
                        {
                            "configuration": engine.format_configuration(_g.coords),
                            "d": _g.distance,
                            "d_w": _g.weighted_distance,
                            "divergences": ", ".join(
                                "%s: %s → %s" % (_d.facet_id, _d.from_value, _d.to_value)
                                for _d in _g.divergences
                            ),
                            "comment": _g.rank_note,
                        }
                        for _g in search_result.adjacent_gaps
                    ]
                ),
                selection=None,
                page_size=10,
            )
            if search_result.adjacent_gaps
            else mo.md("_none_")
        )

    mo.vstack(_blocks)
    return


@app.cell
def _(mo):
    export_button = mo.ui.run_button(label="Save the gap list to exports/")
    mo.vstack([mo.md("## 8. Export"), export_button])
    return (export_button,)


@app.cell
def _(EXPORTS, HERE, engine, export_button, file_dropdown, json, mo, ontology, pd):
    mo.stop(not export_button.value, mo.md("_Press the button to save the files._"))

    _gaps = engine.all_gaps()
    _ids = [_f.id for _f in ontology.object_facets]
    _records = [
        dict([(_i, _c[_i]) for _i in _ids]
             + [("configuration", engine.format_configuration(_c))]
             + [("residual_%s" % _k, ", ".join(_v))
                for _k, _v in engine.allowed_methodological_values(_c).items()])
        for _c in _gaps
    ]

    _export_dir = EXPORTS
    _export_dir.mkdir(exist_ok=True)
    _stem = file_dropdown.value.rsplit(".", 1)[0]
    _csv_path = _export_dir / ("%s_gaps.csv" % _stem)
    _json_path = _export_dir / ("%s_gaps.json" % _stem)

    pd.DataFrame(_records).to_csv(_csv_path, index=False, encoding="utf-8-sig")
    with open(_json_path, "w", encoding="utf-8") as _handle:
        json.dump(
            {
                "source": file_dropdown.value,
                "count": len(_records),
                "facets": _ids,
                "gaps": _records,
            },
            _handle,
            ensure_ascii=False,
            indent=4,
        )

    mo.md(
        "Saved **%d** gaps:\n\n- `%s`\n- `%s`"
        % (len(_records), _csv_path.relative_to(HERE.parent), _json_path.relative_to(HERE.parent))
    )
    return


if __name__ == "__main__":
    app.run()