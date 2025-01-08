import json
import sys
from typing import Dict

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QLabel,
    QLineEdit,
    QDialog,
    QDialogButtonBox,
    QMenuBar,
    QFileDialog,
    QHBoxLayout,
    QFrame,
    QStackedWidget,
)
from PyQt5.QtCore import Qt, QMimeData, pyqtSignal
from PyQt5.QtGui import QDrag


class AddGroupDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Add Group")

        self.layout = QVBoxLayout()

        self.label = QLabel("Enter a group name:")
        self.layout.addWidget(self.label)

        self.group_name_input = QLineEdit()
        self.layout.addWidget(self.group_name_input)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

        self.setLayout(self.layout)

    def get_group_name(self):
        return self.group_name_input.text()


class AddFeatureDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Add a feature")

        self.layout = QVBoxLayout()
        self.label = QLabel("Enter a feature name:")
        self.layout.addWidget(self.label)

        self.feature_name_input = QLineEdit()
        self.layout.addWidget(self.feature_name_input)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

        self.setLayout(self.layout)

    def get_feature_name(self):
        return self.feature_name_input.text()


class DraggableLabel(QLabel):
    dropped = pyqtSignal(object, object)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dragStartPosition = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragStartPos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            distance = (event.pos() - self.dragStartPos).manhattanLength()
            if distance >= QApplication.startDragDistance():
                drag = QDrag(self)
                mime_data = QMimeData()
                mime_data.setText(self.text())
                drag.setMimeData(mime_data)
                drag.exec_(Qt.MoveAction)
        super().mouseMoveEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        event.setDropAction(Qt.MoveAction)
        event.acceptProposedAction()
        # Generating a signal
        self.dropped.emit(event.source(), self)


class MainWindow(QMainWindow):

    colors = [
        "#FCE4EC",  # рожевий пастельний
        "#FFF3E0",  # персиковий пастельний
        "#FFF9C4",  # жовтий пастельний
        "#E8F5E9",  # зелений пастельний
        "#E3F2FD",  # блакитний пастельний
        "#EDE7F6",  # лавандовий пастельний
        "#FFEBEE",  # кораловий пастельний
        "#F3E5F5",  # ліловий пастельний
        "#E1F5FE"  # м'ятно-блакитний пастельний
    ]

    def _get_color(self, index):
        return self.colors[index % len(self.colors)]

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Classifier")
        self.setGeometry(200, 200, 400, 600)

        # Main Data
        self.groups = {}
        self.filters = []

        # Menu
        self.menu_bar = QMenuBar()
        self.setMenuBar(self.menu_bar)

        file_menu = self.menu_bar.addMenu("Project")
        project_view_action = file_menu.addAction("Project View")
        project_view_action.triggered.connect(self.project_view)

        save_action = file_menu.addAction("Save Project")
        save_action.triggered.connect(self.save_project)

        load_action = file_menu.addAction("Load Project")
        load_action.triggered.connect(self.load_project)

        clear_action = file_menu.addAction("Clear Project")
        clear_action.triggered.connect(self.clear_project)

        classifier_menu = self.menu_bar.addMenu("Classifier")
        classifier_view_action = classifier_menu.addAction("Classifier View")
        classifier_view_action.triggered.connect(self.classifier_view)

        load_classifier_action = classifier_menu.addAction("Load Classifier")
        load_classifier_action.triggered.connect(self.load_classifier)

        # Central widget stack
        self.central_widget = QStackedWidget()
        self.setCentralWidget(self.central_widget)

        self.project_layout = QVBoxLayout()
        self.project_widget = QWidget()
        self.project_widget.setLayout(self.project_layout)
        self.project_widget_id = 0

        self.classifier_layout = QVBoxLayout()
        self.classifier_widget = QWidget()
        self.classifier_widget.setLayout(self.classifier_layout)
        self.classifier_widget_id = 1

        self.central_widget.addWidget(self.project_widget)
        self.central_widget.addWidget(self.classifier_widget)

        # "Add Group" button to project_layout
        self.add_group_button = QPushButton("Add Group +")
        self.add_group_button.setStyleSheet("padding: 10px;")
        self.add_group_button.clicked.connect(self.show_add_group_dialog)
        self.project_layout.addWidget(self.add_group_button)

        # Placeholder to classifier_layout
        classifier_label = QLabel(f"Load classifier...")
        self.classifier_layout.addWidget(classifier_label)

        self.switch_to_layout(self.project_widget_id)

    def switch_to_layout(self, index):
        self.central_widget.setCurrentIndex(index)

    def show_add_group_dialog(self):
        dialog = AddGroupDialog()
        if dialog.exec():  # If OK is pressed
            group_priority = len(self.groups.keys()) + 1
            group_name = dialog.get_group_name()
            if group_name:
                group = {
                    "group_name": group_name,
                    "features": {}
                }
                self.groups[group_priority] = group
                self.add_group_block(group_priority, group)

    def add_group_block(self, group_priority: int, group: Dict):
        group_layout = QVBoxLayout()

        group_header = QHBoxLayout()
        group_label = DraggableLabel(f"Group ({group_priority}): {group['group_name']}")
        group_label.setProperty("labelType", "group")
        group_label.setProperty("groupIndex", group_priority)
        group_label.setFrameStyle(QFrame.Panel | QFrame.Raised)
        group_label.setLineWidth(2)
        group_label.setAcceptDrops(True)
        group_label.dropped.connect(self.handleDrop)

        add_feature_button = QPushButton("Add a feature +")
        add_feature_button.clicked.connect(lambda: self.show_add_feature_dialog(group))

        group_header.addWidget(group_label)
        group_header.addWidget(add_feature_button)
        group_layout.addLayout(group_header)

        if not group["features"]:
            feature_label = QLabel(f"Add new feature...")
            group_layout.addWidget(feature_label)

        for feature_priority, feature in group["features"].items():
            label_text = f"Feature ({feature_priority}): {feature['name']}"
            for option in feature["options"]:
                label_text += f"\n({option['code']}) {option['name']}"
            feature_label = DraggableLabel(label_text)
            feature_label.setProperty("labelType", "feature")
            feature_label.setProperty("groupIndex", group_priority)
            feature_label.setProperty("featureIndex", feature_priority)
            feature_label.setFrameStyle(QFrame.Panel | QFrame.Raised)
            feature_label.setLineWidth(2)
            feature_label.setAcceptDrops(True)
            feature_label.dropped.connect(self.handleDrop)
            group_layout.addWidget(feature_label)

        container = QWidget()
        group_color = self._get_color(self.project_layout.count())
        container.setStyleSheet(f"background: {group_color};")
        container.setLayout(group_layout)
        self.project_layout.insertWidget(self.project_layout.count() - 1, container)

    def show_add_feature_dialog(self, group: Dict):
        dialog = AddFeatureDialog()
        if dialog.exec():
            feature_priority = len(group["features"]) + 1
            feature_name = dialog.get_feature_name()
            if feature_name:
                feature = {
                    "name": feature_name,
                    "options": []
                }
                group["features"][feature_priority] = feature
                self.refresh_groups()

    def save_project(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Project", "./projects/", "JSON Files (*.json)", options=options)
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as project_file:
                json.dump(
                    {
                        "groups": self.groups,
                        "filters": {}
                    },
                    project_file,
                    ensure_ascii=False,
                    indent=4
                )

    def load_project(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(self, "load Project", "./projects/", "JSON Files (*.json)", options=options)
        if file_path:
            with open(file_path, 'r', encoding='utf-8') as project_file:
                project_configs = json.load(project_file)
                self.groups = project_configs["groups"]
                self.filters = project_configs["filters"]
                self.refresh_groups()

    def clear_project(self):
        self.groups = {}
        self.refresh_groups()

    def project_view(self):
        self.switch_to_layout(self.project_widget_id)

    def classifier_view(self):
        self.switch_to_layout(self.classifier_widget_id)

    def load_classifier(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(self, "load Project", "./projects/", "JSON Files (*.json)", options=options)
        if file_path:
            with open(file_path, 'r', encoding='utf-8') as project_file:
                project_configs = json.load(project_file)
                self.groups = project_configs["groups"]
                self.filters = project_configs["filters"]
                self.refresh_classifier()

    def handleDrop(self, source_label, target_label):
        source_type = source_label.property("labelType")  # 'group' or 'feature'
        source_group_idx = source_label.property("groupIndex")
        source_feature_idx = source_label.property("featureIndex")  # can be None if it is a 'group'

        target_type = target_label.property("labelType")  # 'group' or 'feature'
        target_group_idx = target_label.property("groupIndex")
        target_feature_idx = target_label.property("featureIndex")

        if source_type == "group" and target_type == "group":
            # swap group priority
            source_group = json.loads(json.dumps(self.groups[source_group_idx]))
            target_group = json.loads(json.dumps(self.groups[target_group_idx]))
            self.groups[source_group_idx] = target_group
            self.groups[target_group_idx] = source_group

        elif source_type == "feature" and target_type == "feature" and source_group_idx == target_group_idx:
            # swap feature priority
            group = self.groups[source_group_idx]
            source_feature = json.loads(json.dumps(group["features"][source_feature_idx]))
            target_feature = json.loads(json.dumps(group["features"][target_feature_idx]))

            group["features"][source_feature_idx] = target_feature
            group["features"][target_feature_idx] = source_feature

        self.refresh_groups()

    def refresh_groups(self):
        while self.project_layout.count() > 1:
            project_widget = self.project_layout.takeAt(0).widget()
            if project_widget:
                project_widget.deleteLater()

        for group_priority, group in self.groups.items():
            self.add_group_block(group_priority, group)

    def refresh_classifier(self):
        while self.classifier_layout.count() > 1:
            classifier_widget = self.classifier_layout.takeAt(0).widget()
            if classifier_widget:
                classifier_widget.deleteLater()

        for group_priority, group in self.groups.items():
            self.add_group_block(group_priority, group)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    main_window = MainWindow()
    main_window.show()

    sys.exit(app.exec())
