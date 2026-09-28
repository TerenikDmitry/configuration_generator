"""Strategy classifier ([P2], DOI 10.26906/SUNZ.2025.2.195-202): FCE over feature domains, FCE* by constraints.

Independent of the ``ontology`` package: neither imports the other, and each reads only its own
``projects/`` directory.

    python -m classifier.app                                                   # PyQt5 GUI
    python -m classifier.create_configurations classifier/projects/project_swarm_of_UAV.json
"""