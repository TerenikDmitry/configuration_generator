"""Ontology of reliability models for UAV groups: layered O/M facets, instances, gap matrix, search.

Independent of the ``classifier`` package: neither imports the other, and the engine reads only
the ontology format (``ontology/projects/``) — classifier files are rejected on load.

    marimo edit ontology/notebook.py        # Ukrainian notebook
    marimo edit ontology/notebook_en.py     # English notebook
    python ontology/tests/check_ontology.py # acceptance checks (spec: ontology/TZ_marimo_ontology.md)
"""