"""Ontology engine: the layered extension of the classifier method.

Reads the same ``features`` / ``constraints`` JSON shape as ``models.classifier`` and adds:

* per-facet layer coding (``layer``, ``facet_type``, ``weight``, ``id``);
* ``rule_type: "note"`` — annotation rules that never block a configuration;
* ``conditions[].values`` — set-membership conditions next to the plain ``value`` form;
* ``actions[].blocked_values`` — the complement of the ``allowed_values`` form used by [P2];
* an ``instances`` block — concrete models placed at points of the configuration space.

The Cartesian product is built over the object layer (O) only.
The methodological layer (M) is never enumerated:
for each valid O-vector the cross-layer rules leave a *residual domain* per M-facet.
See TZ_marimo_ontology.md §3.2 for why.

``models/classifier.py`` is deliberately untouched: its regression baselines
(144/42/96, 432/90/324, 9/3/6) must stay reproducible.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from itertools import product
from typing import Any, Dict, List, Optional, Tuple

OBJECT_LAYER = "O"
METHODOLOGICAL_LAYER = "M"

STRUCTURAL = "структурний"
PARAMETRIC = "параметричний"

RULE_DOMAIN = "domain"
RULE_CONDITIONAL = "conditional"
RULE_NOTE = "note"

MODE_BLOCK = "block"
MODE_NULL = "null"
MODE_ANNOTATE = "annotate"

MIRROR_RELATION = "дзеркало-по"
SPECIALISATION_RELATIONS = ("є-спецвипадком", "верифікується-звуженням")

STATUS_GAP = "gap"
REALISED_STATUSES = ("опубліковано", "у рукописі")


# --------------------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Facet:
    """One coordinate of the configuration space."""

    id: str
    name: str
    domain: Tuple[str, ...]
    layer: str
    description: str = ""
    type: str = "enum"
    group: Optional[str] = None
    facet_type: Optional[str] = None
    weight: int = 0
    note: Optional[str] = None

    @property
    def is_structural(self) -> bool:
        return self.facet_type == STRUCTURAL

    @property
    def is_parametric(self) -> bool:
        return self.facet_type == PARAMETRIC


@dataclass(frozen=True)
class Constraint:
    """One rule. ``raw`` keeps the original dict so nothing is lost on round-trip."""

    id: str
    rule_type: str
    description: str = ""
    kind: Optional[str] = None
    conditions: Tuple[Dict[str, Any], ...] = ()
    actions: Tuple[Dict[str, Any], ...] = ()
    feature: Optional[str] = None            # rule_type == "domain"
    allowed_values: Tuple[str, ...] = ()     # rule_type == "domain"
    raw: Dict[str, Any] = field(default_factory=dict, repr=False, compare=False)


@dataclass(frozen=True)
class Instance:
    """A concrete model placed at one point of the space."""

    id: str
    coords: Dict[str, str]
    model: str = ""
    description: str = ""
    status: str = ""
    refs: Tuple[str, ...] = ()
    role: str = ""
    origin: str = ""
    relations: Tuple[Dict[str, Any], ...] = ()

    @property
    def is_gap(self) -> bool:
        return self.status == STATUS_GAP

    @property
    def is_realised(self) -> bool:
        return self.status in REALISED_STATUSES


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    blocking_constraint: Optional[str] = None
    annotations: Tuple[str, ...] = ()
    nulled: Dict[str, str] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.is_valid


@dataclass(frozen=True)
class BlockedEntry:
    coords: Dict[str, str]
    constraint_id: str


@dataclass(frozen=True)
class ContradictoryEntry:
    """A valid O-vector whose residual domain of some M-facet is empty."""

    coords: Dict[str, str]
    facet_id: str
    emptying_constraints: Tuple[str, ...]


@dataclass(frozen=True)
class InstanceAuditEntry:
    instance_id: str
    model: str
    status: str
    unknown_facets: Tuple[str, ...]
    missing_facets: Tuple[str, ...]
    out_of_domain: Tuple[Tuple[str, str], ...]
    is_valid: bool
    blocking_constraint: Optional[str]
    annotations: Tuple[str, ...]
    residual: Dict[str, List[str]]
    declared_in_residual: Dict[str, bool]

    @property
    def ok(self) -> bool:
        return (
            not self.unknown_facets
            and not self.missing_facets
            and not self.out_of_domain
            and self.is_valid
            and all(self.declared_in_residual.values())
        )


@dataclass(frozen=True)
class GapCell:
    coords: Dict[str, str]
    state: str                                   # "occupied" | "gap" | "blocked"
    instances: Tuple[Instance, ...] = ()
    constraint_id: Optional[str] = None


@dataclass(frozen=True)
class GapMatrix:
    axis_x: str
    axis_y: str
    x_values: Tuple[str, ...]
    y_values: Tuple[str, ...]
    fixed: Dict[str, str]
    cells: Dict[Tuple[str, str], GapCell]        # (x_value, y_value) -> cell

    def cell(self, x_value: str, y_value: str) -> GapCell:
        return self.cells[(x_value, y_value)]

    def counts(self) -> Dict[str, int]:
        result = {"occupied": 0, "gap": 0, "blocked": 0}
        for cell in self.cells.values():
            result[cell.state] += 1
        return result


@dataclass(frozen=True)
class NeighbourEntry:
    instance: Instance
    distance: int
    weighted_distance: int


@dataclass(frozen=True)
class DivergenceEntry:
    facet_id: str
    facet_name: str
    facet_type: Optional[str]
    weight: int
    from_value: str
    to_value: str


@dataclass(frozen=True)
class AdjacentGap:
    """An unpopulated valid cell next to the searched vector (Algorithm 1, step 7)."""

    coords: Dict[str, str]
    distance: int
    weighted_distance: int
    divergences: Tuple[DivergenceEntry, ...]
    is_mirror: bool = False
    mirror_facet: Optional[str] = None

    @property
    def rank_note(self) -> str:
        if self.is_mirror:
            return "передумова порівняння стратегій (дзеркало по %s)" % self.mirror_facet
        if self.weighted_distance <= 1:
            return "успадковує структуру графа: закривається перепризначенням міток"
        return "вимагає перебудови простору станів"


@dataclass(frozen=True)
class SearchResult:
    """Outcome of Algorithm 1."""

    outcome: str                                 # blocked | contradictory | existing | joins_gap | new_gap
    coords: Dict[str, str]
    blocking_constraint: Optional[str] = None
    nearest_admissible: Tuple[Dict[str, str], ...] = ()
    contradictions: Tuple[ContradictoryEntry, ...] = ()
    residual: Dict[str, List[str]] = field(default_factory=dict)
    annotations: Tuple[str, ...] = ()
    neighbours: Tuple[NeighbourEntry, ...] = ()
    nearest: Optional[Instance] = None
    matched: Optional[Instance] = None
    divergences: Tuple[DivergenceEntry, ...] = ()
    verification_candidates: Tuple[Dict[str, Any], ...] = ()
    adjacent_gaps: Tuple[AdjacentGap, ...] = ()
    new_instance: Optional[Dict[str, Any]] = None


# --------------------------------------------------------------------------------------
# Ontology file
# --------------------------------------------------------------------------------------

class Ontology:
    """A loaded ontology file: meta, facets, constraints, instances.

    Order is load-bearing (TZ §1.3): ``features`` fixes the coordinate order of every string
    rendering, ``constraints`` fixes which rule is blamed for a block. Nothing is sorted here.
    """

    def __init__(self, data: Dict[str, Any], path: Optional[str] = None) -> None:
        self.path = path
        self.raw = data
        self.meta: Dict[str, Any] = data.get("meta", {})

        self._facets: List[Facet] = [self._build_facet(item) for item in data.get("features", [])]
        self._facets_by_id: Dict[str, Facet] = {}
        for facet in self._facets:
            if facet.id in self._facets_by_id:
                raise ValueError("Duplicate facet id: %s" % facet.id)
            self._facets_by_id[facet.id] = facet

        self.constraints: List[Constraint] = [
            self._build_constraint(item) for item in data.get("constraints", [])
        ]
        self.instances: List[Instance] = [
            self._build_instance(item) for item in data.get("instances", [])
        ]
        self.instances_by_id: Dict[str, Instance] = {i.id: i for i in self.instances}

    # -- loading ------------------------------------------------------------------------

    @classmethod
    def load(cls, path: str) -> "Ontology":
        with open(path, "r", encoding="utf-8") as handle:
            return cls(json.load(handle), path=path)

    @staticmethod
    def _build_facet(item: Dict[str, Any]) -> Facet:
        facet_id = item.get("id") or item.get("name")
        if not facet_id:
            raise ValueError("Feature without id and name: %r" % (item,))
        return Facet(
            id=facet_id,
            name=item.get("name", facet_id),
            domain=tuple(item.get("domain", ())),
            layer=item.get("layer", OBJECT_LAYER),
            description=item.get("description", ""),
            type=item.get("type", "enum"),
            group=item.get("group"),
            facet_type=item.get("facet_type"),
            weight=item.get("weight", 0),
            note=item.get("note"),
        )

    @staticmethod
    def _build_constraint(item: Dict[str, Any]) -> Constraint:
        rule_type = item.get("rule_type")
        if rule_type not in (RULE_DOMAIN, RULE_CONDITIONAL, RULE_NOTE):
            raise ValueError("Unknown rule_type %r in constraint %r" % (rule_type, item.get("id")))
        return Constraint(
            id=item.get("id", ""),
            rule_type=rule_type,
            description=item.get("description", ""),
            kind=item.get("kind"),
            conditions=tuple(item.get("conditions", ())),
            actions=tuple(item.get("actions", ())),
            feature=item.get("feature"),
            allowed_values=tuple(item.get("allowed_values", ())),
            raw=item,
        )

    @staticmethod
    def _build_instance(item: Dict[str, Any]) -> Instance:
        return Instance(
            id=item.get("id", ""),
            coords=dict(item.get("coords", {})),
            model=item.get("model", ""),
            description=item.get("description", ""),
            status=item.get("status", ""),
            refs=tuple(item.get("refs", ())),
            role=item.get("role", ""),
            origin=item.get("origin", ""),
            relations=tuple(item.get("relations", ())),
        )

    # -- access -------------------------------------------------------------------------

    def facets(self, layer: Optional[str] = None) -> List[Facet]:
        if layer is None:
            return list(self._facets)
        return [f for f in self._facets if f.layer == layer]

    def facet(self, facet_id: str) -> Facet:
        try:
            return self._facets_by_id[facet_id]
        except KeyError:
            raise KeyError("Unknown facet id: %s" % facet_id)

    def has_facet(self, facet_id: str) -> bool:
        return facet_id in self._facets_by_id

    @property
    def object_facets(self) -> List[Facet]:
        return self.facets(OBJECT_LAYER)

    @property
    def methodological_facets(self) -> List[Facet]:
        return self.facets(METHODOLOGICAL_LAYER)

    @property
    def structural_facets(self) -> List[Facet]:
        return [f for f in self.object_facets if f.is_structural]

    def mirror_pairs(self) -> Dict[str, List[Tuple[str, str]]]:
        """Genuine mirror pairs, read from ``дзеркало-по`` relations rather than hard-coded.

        TZ §4 step 7: the mirror is a datum of the ontology file (i1↔i2, i3↔i4, i5↔i6 along
        O1), not a property the engine may invent for an arbitrary facet.
        """
        pairs: Dict[str, List[Tuple[str, str]]] = {}
        seen = set()
        for instance in self.instances:
            for relation in instance.relations:
                if relation.get("type") != MIRROR_RELATION:
                    continue
                facet_id = relation.get("facet")
                target = self.instances_by_id.get(relation.get("target", ""))
                if not facet_id or target is None:
                    continue
                left = instance.coords.get(facet_id)
                right = target.coords.get(facet_id)
                if left is None or right is None or left == right:
                    continue
                key = (facet_id, frozenset((left, right)))
                if key in seen:
                    continue
                seen.add(key)
                pairs.setdefault(facet_id, []).append((left, right))
        return pairs

    def mirror_value(self, facet_id: str, value: str) -> Optional[str]:
        for left, right in self.mirror_pairs().get(facet_id, ()):
            if value == left:
                return right
            if value == right:
                return left
        return None


# --------------------------------------------------------------------------------------
# Engine
# --------------------------------------------------------------------------------------

class OntologyEngine:
    """Generation, validation, gap analysis and Algorithm 1 over an :class:`Ontology`."""

    def __init__(self, ontology: Ontology) -> None:
        self.ontology = ontology
        self.statistics: Dict[str, int] = {"iterations": 0}
        self._space: Optional[List[Dict[str, str]]] = None
        self._valid: Optional[List[Dict[str, str]]] = None
        self._blocked: Optional[List[BlockedEntry]] = None
        self._contradictory: Optional[List[ContradictoryEntry]] = None

    # -- rule primitives ----------------------------------------------------------------

    def _condition_holds(self, condition: Dict[str, Any], coords: Dict[str, str]) -> bool:
        """``{"feature": X, "value": v}`` or the set form ``{"feature": X, "values": [...]}``."""
        self.statistics["iterations"] += 1
        current = coords.get(condition.get("feature"))
        if "values" in condition:
            return current in condition["values"]
        return current == condition.get("value")

    @staticmethod
    def _action_permits(action: Dict[str, Any], value: str) -> bool:
        """``allowed_values`` keeps the [P2] semantics; ``blocked_values`` is the complement."""
        if "allowed_values" in action:
            return value in action["allowed_values"]
        if "blocked_values" in action:
            return value not in action["blocked_values"]
        return True

    @staticmethod
    def _narrow(domain: List[str], action: Dict[str, Any]) -> List[str]:
        if "allowed_values" in action:
            return [v for v in domain if v in action["allowed_values"]]
        if "blocked_values" in action:
            return [v for v in domain if v not in action["blocked_values"]]
        return list(domain)

    def _rule_applies(self, constraint: Constraint, coords: Dict[str, str]) -> bool:
        return all(self._condition_holds(c, coords) for c in constraint.conditions)

    # -- generation ---------------------------------------------------------------------

    def generate_object_space(self) -> List[Dict[str, str]]:
        """Full Cartesian product of the object-layer domains. No filtering."""
        if self._space is None:
            facets = self.ontology.object_facets
            ids = [f.id for f in facets]
            self._space = [
                dict(zip(ids, combination))
                for combination in product(*[f.domain for f in facets])
            ]
        return self._space

    def validate(self, coords: Dict[str, str]) -> ValidationResult:
        """Run one vector through every rule, in array order, short-circuiting on the first block.

        Only object-layer actions can invalidate a vector; actions aimed at the M layer narrow
        residual domains instead (see :meth:`allowed_methodological_values`).

        Annotations and ``null`` overrides are accumulated separately and never written back
        into ``coords`` — the same separation as ``null_overrides`` in ``classifier.py``
        (commit f42021a), so a rule's effect cannot depend on where it sits relative to them.
        """
        annotations: List[str] = []
        nulled: Dict[str, str] = {}

        for constraint in self.ontology.constraints:
            if constraint.rule_type == RULE_DOMAIN:
                self.statistics["iterations"] += 1
                feature = constraint.feature
                if feature is None or self._layer_of(feature) != OBJECT_LAYER:
                    continue
                if coords.get(feature) not in constraint.allowed_values:
                    return ValidationResult(False, constraint.id, tuple(annotations), nulled)
                continue

            if not self._rule_applies(constraint, coords):
                continue

            if constraint.rule_type == RULE_NOTE:
                for action in constraint.actions:
                    if action.get("mode", MODE_ANNOTATE) == MODE_ANNOTATE:
                        annotations.append(action.get("annotation", constraint.description))
                continue

            for action in constraint.actions:
                feature = action.get("feature")
                mode = action.get("mode")
                if mode == MODE_ANNOTATE:
                    annotations.append(action.get("annotation", constraint.description))
                    continue
                if feature is None or self._layer_of(feature) != OBJECT_LAYER:
                    continue                      # cross-layer action: handled as M narrowing
                if mode == MODE_NULL:
                    nulled[feature] = "None"      # kept for old classifier files; unused here
                    continue
                if mode == MODE_BLOCK and not self._action_permits(action, coords.get(feature)):
                    return ValidationResult(False, constraint.id, tuple(annotations), nulled)

        return ValidationResult(True, None, tuple(annotations), nulled)

    def _layer_of(self, facet_id: str) -> Optional[str]:
        if not self.ontology.has_facet(facet_id):
            return None
        return self.ontology.facet(facet_id).layer

    def valid_object_configurations(self) -> Tuple[List[Dict[str, str]], List[BlockedEntry]]:
        """``(valid O-vectors, blocked ones tagged with the first constraint that failed them)``.

        No deduplication (TZ §1.4): the gap matrix counts cells of the space, and merging two
        distinct coordinate vectors into one row would make it wrong.
        """
        if self._valid is None or self._blocked is None:
            self.statistics["iterations"] = 0
            valid: List[Dict[str, str]] = []
            blocked: List[BlockedEntry] = []
            for coords in self.generate_object_space():
                result = self.validate(coords)
                if result.is_valid:
                    valid.append(coords)
                else:
                    blocked.append(BlockedEntry(coords, result.blocking_constraint))
            self._valid, self._blocked = valid, blocked
        return self._valid, self._blocked

    def blocked_by_constraint(self) -> Dict[str, int]:
        """How many configurations each rule is blamed for (first cause, so order matters)."""
        _, blocked = self.valid_object_configurations()
        counts: Dict[str, int] = {c.id: 0 for c in self.ontology.constraints}
        for entry in blocked:
            counts[entry.constraint_id] = counts.get(entry.constraint_id, 0) + 1
        return {cid: n for cid, n in counts.items() if n}

    # -- methodological layer -----------------------------------------------------------

    def allowed_methodological_values(self, coords: Dict[str, str]) -> Dict[str, List[str]]:
        """Residual domain of every M-facet for a given O-vector.

        The M layer is never enumerated (TZ §3.2): it is a filter and a provenance record, not
        a dimension of the model space.
        """
        return {facet_id: values for facet_id, (values, _) in self._residual_detail(coords).items()}

    def _residual_detail(
        self, coords: Dict[str, str]
    ) -> Dict[str, Tuple[List[str], List[str]]]:
        """``{facet_id: (residual domain, ids of rules that narrowed it)}``."""
        residual: Dict[str, Tuple[List[str], List[str]]] = {
            facet.id: (list(facet.domain), [])
            for facet in self.ontology.methodological_facets
        }

        for constraint in self.ontology.constraints:
            if constraint.rule_type == RULE_DOMAIN:
                feature = constraint.feature
                if feature in residual:
                    values, blamed = residual[feature]
                    kept = [v for v in values if v in constraint.allowed_values]
                    if kept != values:
                        blamed.append(constraint.id)
                    residual[feature] = (kept, blamed)
                continue

            if constraint.rule_type == RULE_NOTE:
                continue
            if not self._rule_applies(constraint, coords):
                continue

            for action in constraint.actions:
                feature = action.get("feature")
                if feature not in residual or action.get("mode") != MODE_BLOCK:
                    continue
                values, blamed = residual[feature]
                kept = self._narrow(values, action)
                if kept != values:
                    blamed.append(constraint.id)
                residual[feature] = (kept, blamed)

        return residual

    def contradictions(self, coords: Dict[str, str]) -> List[ContradictoryEntry]:
        """Rules that leave some M-facet with an empty domain — a defect of the rule set."""
        entries = []
        for facet_id, (values, blamed) in self._residual_detail(coords).items():
            if not values:
                entries.append(ContradictoryEntry(dict(coords), facet_id, tuple(blamed)))
        return entries

    def contradictory_configurations(self) -> List[ContradictoryEntry]:
        """Valid O-vectors whose residual M domain is empty. Expected to be empty (rule c12)."""
        if self._contradictory is None:
            valid, _ = self.valid_object_configurations()
            found: List[ContradictoryEntry] = []
            for coords in valid:
                found.extend(self.contradictions(coords))
            self._contradictory = found
        return self._contradictory

    # -- instances ----------------------------------------------------------------------

    def audit_instances(self) -> List[InstanceAuditEntry]:
        """Check every instance: coordinates inside domains, vector valid, declared M available."""
        entries: List[InstanceAuditEntry] = []
        for instance in self.ontology.instances:
            unknown = tuple(f for f in instance.coords if not self.ontology.has_facet(f))
            missing = tuple(
                f.id for f in self.ontology.facets() if f.id not in instance.coords
            )
            out_of_domain = tuple(
                (facet_id, value)
                for facet_id, value in instance.coords.items()
                if self.ontology.has_facet(facet_id)
                and value not in self.ontology.facet(facet_id).domain
            )
            result = self.validate(instance.coords)
            residual = self.allowed_methodological_values(instance.coords)
            declared = {
                facet_id: instance.coords.get(facet_id) in values
                for facet_id, values in residual.items()
            }
            entries.append(
                InstanceAuditEntry(
                    instance_id=instance.id,
                    model=instance.model,
                    status=instance.status,
                    unknown_facets=unknown,
                    missing_facets=missing,
                    out_of_domain=out_of_domain,
                    is_valid=result.is_valid,
                    blocking_constraint=result.blocking_constraint,
                    annotations=result.annotations,
                    residual=residual,
                    declared_in_residual=declared,
                )
            )
        return entries

    def object_key(self, coords: Dict[str, str]) -> Tuple[str, ...]:
        """Hashable projection of a vector onto the object layer."""
        return tuple(coords.get(f.id) for f in self.ontology.object_facets)

    def instances_at(self, coords: Dict[str, str]) -> List[Instance]:
        key = self.object_key(coords)
        return [i for i in self.ontology.instances if self.object_key(i.coords) == key]

    def format_configuration(self, coords: Dict[str, str]) -> str:
        """Display form only. Never used as an identity — see TZ §1.4."""
        return "/".join(str(coords.get(f.id)) for f in self.ontology.object_facets)

    # -- distances ----------------------------------------------------------------------

    def distance(self, a: Dict[str, str], b: Dict[str, str], weighted: bool = False) -> int:
        """Hamming distance over the object layer; weighted by ``facet.weight`` if asked.

        Both forms ignore the M layer (its facets carry ``weight = 0`` and are not iterated).
        """
        total = 0
        for facet in self.ontology.object_facets:
            if a.get(facet.id) != b.get(facet.id):
                total += facet.weight if weighted else 1
        return total

    def divergences(self, a: Dict[str, str], b: Dict[str, str]) -> List[DivergenceEntry]:
        """Coordinates where ``b`` differs from ``a``, annotated with facet type and weight."""
        entries = []
        for facet in self.ontology.object_facets:
            if a.get(facet.id) != b.get(facet.id):
                entries.append(
                    DivergenceEntry(
                        facet_id=facet.id,
                        facet_name=facet.name,
                        facet_type=facet.facet_type,
                        weight=facet.weight,
                        from_value=a.get(facet.id),
                        to_value=b.get(facet.id),
                    )
                )
        return entries

    # -- gap analysis -------------------------------------------------------------------

    def gap_matrix(self, axis_x: str, axis_y: str, fixed: Dict[str, str]) -> GapMatrix:
        """Project the space onto two axes with the remaining facets pinned by ``fixed``.

        A cell is a gap if and only if it is admissible under the constraints and unpopulated —
        this is the definition of a gap, drawn directly.
        """
        if axis_x == axis_y:
            raise ValueError("Gap matrix axes must differ: %s" % axis_x)
        x_facet, y_facet = self.ontology.facet(axis_x), self.ontology.facet(axis_y)
        for facet in (x_facet, y_facet):
            if facet.layer != OBJECT_LAYER:
                raise ValueError("Gap matrix axes must belong to the object layer: %s" % facet.id)

        base = {f.id: fixed.get(f.id) for f in self.ontology.object_facets}
        missing = [k for k, v in base.items() if v is None and k not in (axis_x, axis_y)]
        if missing:
            raise ValueError("No fixed value for facets: %s" % ", ".join(missing))

        cells: Dict[Tuple[str, str], GapCell] = {}
        for x_value in x_facet.domain:
            for y_value in y_facet.domain:
                coords = dict(base)
                coords[axis_x] = x_value
                coords[axis_y] = y_value
                result = self.validate(coords)
                if not result.is_valid:
                    cell = GapCell(coords, "blocked", (), result.blocking_constraint)
                else:
                    here = tuple(self.instances_at(coords))
                    cell = GapCell(coords, "occupied" if here else "gap", here, None)
                cells[(x_value, y_value)] = cell

        return GapMatrix(
            axis_x=axis_x,
            axis_y=axis_y,
            x_values=tuple(x_facet.domain),
            y_values=tuple(y_facet.domain),
            fixed={k: v for k, v in base.items() if k not in (axis_x, axis_y)},
            cells=cells,
        )

    def all_gaps(self) -> List[Dict[str, str]]:
        """Every valid, unpopulated cell of the whole space — the export payload."""
        valid, _ = self.valid_object_configurations()
        occupied = {self.object_key(i.coords) for i in self.ontology.instances}
        return [c for c in valid if self.object_key(c) not in occupied]

    def symmetry_violations(self, facet_id: Optional[str] = None) -> List[Dict[str, str]]:
        """Valid vectors whose mirror partner (TZ §6.5) is not itself valid.

        A violation means some rule is implicitly tied to one branch of the mirrored facet.
        """
        pairs = self.ontology.mirror_pairs()
        if facet_id is not None:
            pairs = {facet_id: pairs.get(facet_id, [])}
        valid, _ = self.valid_object_configurations()
        valid_keys = {self.object_key(c) for c in valid}

        violations: List[Dict[str, str]] = []
        for mirrored_facet, value_pairs in pairs.items():
            for left, right in value_pairs:
                for source, target in ((left, right), (right, left)):
                    for coords in valid:
                        if coords.get(mirrored_facet) != source:
                            continue
                        mirrored = dict(coords)
                        mirrored[mirrored_facet] = target
                        if self.object_key(mirrored) not in valid_keys:
                            violations.append(coords)
        return violations

    # -- Algorithm 1 --------------------------------------------------------------------

    def nearest_admissible(self, coords: Dict[str, str]) -> List[Dict[str, str]]:
        """Valid vectors one coordinate away from a blocked one (Algorithm 1, step 1)."""
        found: List[Dict[str, str]] = []
        for facet in self.ontology.object_facets:
            for value in facet.domain:
                if value == coords.get(facet.id):
                    continue
                candidate = dict(coords)
                candidate[facet.id] = value
                if self.validate(candidate).is_valid:
                    found.append(candidate)
        return found

    def verification_candidates(self, nearest: Instance) -> List[Dict[str, Any]]:
        """Specialisation relations carried over from the nearest neighbour (step 6).

        TODO — open question, do not resolve unilaterally (TZ §4 step 6).
        «є-спецвипадком» cannot be derived from coordinates: facet domains carry no order
        relation, so nothing in the data says that "1" is a special case of ">1", and
        "необмежені (m≥D_max)" is neither a narrowing nor a generalisation of
        "обмежені (1<m<D_max)" in the set-inclusion sense. Still to be decided: whether the
        relation has a formal meaning in coordinate terms at all, whether a specialisation
        order should be declared explicitly in the JSON, and whether the step is automatable.
        Until then this only carries over relations already written in the file, and the
        result is a list of candidates rather than a conclusion.
        """
        candidates: List[Dict[str, Any]] = []
        for relation in nearest.relations:
            if relation.get("type") in SPECIALISATION_RELATIONS:
                candidates.append(
                    {
                        "source": nearest.id,
                        "type": relation.get("type"),
                        "target": relation.get("target"),
                        "умови_звуження": relation.get("умови_звуження", ""),
                        "origin": "успадковано від %s" % nearest.id,
                    }
                )
        for instance in self.ontology.instances:
            for relation in instance.relations:
                if (
                    relation.get("type") in SPECIALISATION_RELATIONS
                    and relation.get("target") == nearest.id
                ):
                    candidates.append(
                        {
                            "source": instance.id,
                            "type": relation.get("type"),
                            "target": nearest.id,
                            "умови_звуження": relation.get("умови_звуження", ""),
                            "origin": "оголошує %s своїм узагальненням" % nearest.id,
                        }
                    )
        return candidates

    def adjacent_gaps(self, coords: Dict[str, str], limit: Optional[int] = None) -> List[AdjacentGap]:
        """Unpopulated valid cells ranked by weighted distance to ``coords`` (step 7).

        d_w = 1 means a parametric divergence: the state graph is inherited and the gap closes
        by relabelling. d_w >= 2 means the state space has to be rebuilt. A cell that is the
        genuine mirror of ``coords`` (per the ``дзеркало-по`` relations of the file) is flagged:
        for a comparative study it is a precondition rather than a gap.
        """
        mirror_pairs = self.ontology.mirror_pairs()
        ranked: List[AdjacentGap] = []
        for gap in self.all_gaps():
            if self.object_key(gap) == self.object_key(coords):
                continue
            divergences = self.divergences(coords, gap)
            mirror_facet = None
            if len(divergences) == 1:
                only = divergences[0]
                for left, right in mirror_pairs.get(only.facet_id, ()):
                    if {only.from_value, only.to_value} == {left, right}:
                        mirror_facet = only.facet_id
                        break
            ranked.append(
                AdjacentGap(
                    coords=gap,
                    distance=self.distance(coords, gap),
                    weighted_distance=self.distance(coords, gap, weighted=True),
                    divergences=tuple(divergences),
                    is_mirror=mirror_facet is not None,
                    mirror_facet=mirror_facet,
                )
            )
        ranked.sort(key=lambda g: (g.weighted_distance, g.distance, self.format_configuration(g.coords)))
        return ranked if limit is None else ranked[:limit]

    def search(self, coords: Dict[str, str], gap_limit: Optional[int] = 10) -> SearchResult:
        """Algorithm 1: from mission conditions to either an existing model or a new gap."""
        coords = {f.id: coords.get(f.id) for f in self.ontology.object_facets}

        # 1. admissibility
        result = self.validate(coords)
        if not result.is_valid:
            return SearchResult(
                outcome="blocked",
                coords=coords,
                blocking_constraint=result.blocking_constraint,
                nearest_admissible=tuple(self.nearest_admissible(coords)),
                annotations=result.annotations,
            )

        # 2. methodological narrowing
        residual = self.allowed_methodological_values(coords)
        contradictions = self.contradictions(coords)
        if contradictions:
            return SearchResult(
                outcome="contradictory",
                coords=coords,
                contradictions=tuple(contradictions),
                residual=residual,
                annotations=result.annotations,
            )

        # 3. distances
        neighbours = [
            NeighbourEntry(
                instance=instance,
                distance=self.distance(coords, instance.coords),
                weighted_distance=self.distance(coords, instance.coords, weighted=True),
            )
            for instance in self.ontology.instances
        ]
        neighbours.sort(key=lambda n: (n.weighted_distance, n.distance, n.instance.id))
        nearest = neighbours[0].instance if neighbours else None

        common = dict(
            coords=coords,
            residual=residual,
            annotations=result.annotations,
            neighbours=tuple(neighbours),
            nearest=nearest,
            adjacent_gaps=tuple(self.adjacent_gaps(coords, gap_limit)),
        )

        # 4. three outcomes
        if neighbours and neighbours[0].weighted_distance == 0:
            matched = neighbours[0].instance
            outcome = "joins_gap" if matched.is_gap else "existing"
            return SearchResult(outcome=outcome, matched=matched, **common)

        # 5-7. new gap: spec draft, verification candidates, ranked adjacent gaps
        divergences = tuple(self.divergences(nearest.coords, coords)) if nearest else ()
        candidates = self.verification_candidates(nearest) if nearest else []
        if nearest is None:
            origin = "пошук за умовами місії"
        else:
            origin = "пошук; найближчий сусід %s (d_w = %d)" % (
                nearest.id,
                neighbours[0].weighted_distance,
            )
        new_instance = {
            "id": self._next_instance_id(),
            "model": "",
            "description": "Породжено пошуком за умовами місії",
            "coords": dict(coords),
            "status": STATUS_GAP,
            "refs": [],
            "role": "",
            "origin": origin,
            "relations": [
                {
                    "type": "верифікується-звуженням",
                    "target": c["target"] if c["source"] == nearest.id else c["source"],
                    "умови_звуження": c["умови_звуження"],
                }
                for c in candidates
            ],
        }
        return SearchResult(
            outcome="new_gap",
            divergences=divergences,
            verification_candidates=tuple(candidates),
            new_instance=new_instance,
            **common
        )

    def _next_instance_id(self) -> str:
        numbers = []
        for instance in self.ontology.instances:
            if instance.id.startswith("i") and instance.id[1:].isdigit():
                numbers.append(int(instance.id[1:]))
        return "i%d" % (max(numbers) + 1 if numbers else 1)
