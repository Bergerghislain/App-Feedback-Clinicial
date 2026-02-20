import csv
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)


DEFAULT_QUESTIONS = [
    {"id": "q1", "text": "La conclusion IA est-elle cliniquement pertinente pour ce patient ?"},
    {"id": "q2", "text": "Le niveau de detail de l'evaluation IA est-il suffisant ?"},
    {"id": "q3", "text": "L'evaluation IA est-elle globalement coherente avec la conclusion RCP ?"},
    {"id": "q4", "text": "L'evaluation IA aide-t-elle a la prise de decision clinique ?"},
]

PAIR_KEYWORD_STOPWORDS = {
    "patient",
    "patients",
    "pat",
    "rcp",
    "ia",
    "ai",
    "eval",
    "evaluation",
    "evaluations",
    "conclusion",
    "conclusions",
    "result",
    "results",
    "data",
    "datas",
}

PATIENT_HINT_KEYS = {
    "patient_id",
    "id",
    "identifiant",
    "nom",
    "name",
    "age",
    "sexe",
    "sex",
    "genre",
    "diagnostic",
    "antecedents",
    "symptomes",
    "symptoms",
    "traitements",
    "treatments",
    "description",
    "description_patient",
    "clinical_context",
    "contexte_clinique",
}

EVALUATION_TEXT_KEYS = {
    "evaluation_text",
    "conclusion",
    "resume",
    "summary",
    "texte",
    "text",
    "analysis",
}


def get_app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


APP_DIR = get_app_base_dir()
DEFAULT_RESULTS_DIR = APP_DIR / "results"


@dataclass
class PatientBundle:
    key: str
    patient_path: Path
    rcp_path: Path
    ia_path: Path
    patient_data: Any
    rcp_data: Any
    ia_data: Any
    patient_id: str


def get_first_present_value(source: Dict[str, Any], keys: List[str]):
    for key in keys:
        if key in source and source[key] not in (None, "", []):
            return source[key]
    return None


def format_value(value) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


def normalize_pair_key(raw_value: str) -> str:
    simplified = re.sub(r"[^a-z0-9]+", "", raw_value.lower())
    return simplified or raw_value.lower()


def tokenize_name(value: str) -> List[str]:
    return [token for token in re.split(r"[^a-z0-9]+", value.lower()) if token]


def derive_key_from_filename(path: Path) -> str:
    tokens = tokenize_name(path.stem)
    filtered = [token for token in tokens if token not in PAIR_KEYWORD_STOPWORDS]
    base = "_".join(filtered) if filtered else path.stem.lower()
    return normalize_pair_key(base)


def infer_role_from_path(path: Path) -> Optional[str]:
    tokens = tokenize_name(path.stem) + tokenize_name(path.parent.name)
    token_set = set(tokens)
    if "rcp" in token_set:
        return "rcp"
    if "ia" in token_set or "ai" in token_set:
        return "ia"
    if "patient" in token_set or "patients" in token_set or "pat" in token_set:
        return "patient"
    return None


def infer_role_from_payload(payload) -> Optional[str]:
    if isinstance(payload, str):
        return "evaluation"
    if not isinstance(payload, dict):
        return None

    keys = {str(key).lower() for key in payload.keys()}
    if "questions" in keys and len(keys) <= 3:
        return None

    patient_hits = keys.intersection(PATIENT_HINT_KEYS)
    eval_hits = keys.intersection(EVALUATION_TEXT_KEYS)

    source_fields = [
        get_first_present_value(payload, ["source", "type", "origin", "auteur", "author"]),
        get_first_present_value(payload, ["modele", "model", "engine"]),
    ]
    source_text = " ".join(str(value).lower() for value in source_fields if value not in (None, "", []))

    if "rcp" in source_text:
        return "rcp"
    if any(token in source_text for token in ("ia", "ai", "llm", "model", "modele")):
        return "ia"
    if patient_hits and len(patient_hits) >= 2:
        return "patient"

    if eval_hits:
        serialized = json.dumps(payload, ensure_ascii=False).lower()
        if "rcp" in serialized:
            return "rcp"
        if any(token in serialized for token in (" ia", " ai", "llm", "modele", "model")):
            return "ia"
        return "evaluation"

    nested = get_first_present_value(payload, ["patient", "patient_data", "evaluation", "data", "result"])
    if isinstance(nested, dict):
        return infer_role_from_payload(nested)
    return None


def extract_patient_id_from_payload(payload) -> Optional[str]:
    if not isinstance(payload, dict):
        return None

    simple_id = get_first_present_value(payload, ["patient_id", "id", "identifiant"])
    if simple_id is not None and not isinstance(simple_id, (dict, list)):
        return str(simple_id)

    for key in ("patient", "patient_data", "data", "metadata"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            nested_id = get_first_present_value(nested, ["patient_id", "id", "identifiant"])
            if nested_id is not None and not isinstance(nested_id, (dict, list)):
                return str(nested_id)
    return None


def normalize_patient_payload(payload):
    if isinstance(payload, dict):
        nested = get_first_present_value(payload, ["patient", "patient_data", "data"])
        if isinstance(nested, dict):
            return nested
    return payload


def normalize_evaluation_payload(payload):
    if isinstance(payload, dict):
        nested = get_first_present_value(payload, ["evaluation", "evaluation_data", "result", "conclusion_data", "data"])
        if nested is not None:
            return nested
    return payload


def format_patient_description(patient_data) -> str:
    if not isinstance(patient_data, dict):
        return format_value(patient_data)

    known_fields = {
        "Identifiant patient": ["patient_id", "id", "identifiant"],
        "Nom": ["nom", "name"],
        "Age": ["age"],
        "Sexe": ["sexe", "sex", "genre"],
        "Contexte clinique": ["contexte_clinique", "clinical_context", "contexte"],
        "Diagnostic": ["diagnostic"],
        "Antecedents": ["antecedents", "history"],
        "Symptomes": ["symptomes", "symptoms"],
        "Traitements": ["traitements", "treatments"],
        "Description libre": ["description", "description_patient", "summary"],
    }

    lines: List[str] = []
    used_keys = set()

    for label, aliases in known_fields.items():
        value = get_first_present_value(patient_data, aliases)
        if value is not None:
            lines.append(f"{label}: {format_value(value)}")
            for alias in aliases:
                if alias in patient_data:
                    used_keys.add(alias)

    remaining = [f"- {key}: {format_value(value)}" for key, value in patient_data.items() if key not in used_keys]
    if not lines and not remaining:
        return "Aucune information patient exploitable."

    if remaining:
        lines.append("")
        lines.append("Autres informations:")
        lines.extend(remaining)

    return "\n".join(lines)


def extract_evaluation_text(data) -> str:
    if isinstance(data, str):
        return data

    if isinstance(data, dict):
        value = get_first_present_value(
            data,
            ["evaluation_text", "conclusion", "resume", "summary", "texte", "text", "analysis"],
        )
        if value is not None:
            return format_value(value)
        return json.dumps(data, ensure_ascii=False, indent=2)

    return format_value(data)


def load_questions_from_json(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return DEFAULT_QUESTIONS

    try:
        with path.open("r", encoding="utf-8-sig") as file:
            payload = json.load(file)
    except Exception:
        return DEFAULT_QUESTIONS

    question_items = payload.get("questions") if isinstance(payload, dict) else payload
    if not isinstance(question_items, list):
        return DEFAULT_QUESTIONS

    parsed_questions: List[Dict[str, str]] = []
    for index, item in enumerate(question_items, start=1):
        if isinstance(item, str):
            parsed_questions.append({"id": f"q{index}", "text": item})
        elif isinstance(item, dict) and item.get("text"):
            parsed_questions.append({"id": str(item.get("id") or f"q{index}"), "text": str(item["text"])})

    return parsed_questions or DEFAULT_QUESTIONS


def discover_patient_bundles(root: Path):
    entries: Dict[str, Dict[str, Any]] = {}

    for json_file in root.rglob("*.json"):
        try:
            with json_file.open("r", encoding="utf-8-sig") as file:
                payload = json.load(file)
        except Exception:
            continue

        role = infer_role_from_path(json_file) or infer_role_from_payload(payload)
        if role is None:
            continue

        possible_keys = [derive_key_from_filename(json_file)]
        key_from_json = extract_patient_id_from_payload(payload)
        if key_from_json:
            possible_keys.append(normalize_pair_key(key_from_json))

        for pair_key in dict.fromkeys(possible_keys):
            entry = entries.setdefault(
                pair_key,
                {"key": pair_key, "patient": None, "rcp": None, "ia": None, "unknown_eval": []},
            )
            if role in ("patient", "rcp", "ia") and entry[role] is None:
                entry[role] = (json_file, payload)
            elif role == "evaluation":
                entry["unknown_eval"].append((json_file, payload))

    for entry in entries.values():
        deduplicated: Dict[str, Any] = {}
        for eval_path, eval_payload in entry["unknown_eval"]:
            deduplicated[str(eval_path)] = (eval_path, eval_payload)
        for eval_path, eval_payload in deduplicated.values():
            if entry["rcp"] is None:
                entry["rcp"] = (eval_path, eval_payload)
            elif entry["ia"] is None:
                entry["ia"] = (eval_path, eval_payload)

    bundles: List[PatientBundle] = []
    seen_triplets = set()
    for entry in entries.values():
        if not (entry["patient"] and entry["rcp"] and entry["ia"]):
            continue

        patient_path, patient_raw = entry["patient"]
        rcp_path, rcp_raw = entry["rcp"]
        ia_path, ia_raw = entry["ia"]
        triplet = (str(patient_path), str(rcp_path), str(ia_path))
        if triplet in seen_triplets:
            continue
        seen_triplets.add(triplet)

        patient_data = normalize_patient_payload(patient_raw)
        rcp_data = normalize_evaluation_payload(rcp_raw)
        ia_data = normalize_evaluation_payload(ia_raw)
        patient_id = (
            extract_patient_id_from_payload(patient_data)
            or extract_patient_id_from_payload(patient_raw)
            or entry["key"]
        )

        bundles.append(
            PatientBundle(
                key=entry["key"],
                patient_path=Path(patient_path),
                rcp_path=Path(rcp_path),
                ia_path=Path(ia_path),
                patient_data=patient_data,
                rcp_data=rcp_data,
                ia_data=ia_data,
                patient_id=str(patient_id),
            )
        )

    bundles.sort(key=lambda item: (item.patient_id.lower(), item.key))
    total_keys = len(entries)
    incomplete = max(0, total_keys - len(bundles))
    return bundles, total_keys, incomplete


class ClinicianFeedbackApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Clinical Feedback - Evaluation IA vs RCP")
        self.resize(1420, 920)

        self.questions_path = APP_DIR / "questions.json"
        self.questions = load_questions_from_json(self.questions_path)
        self.question_groups: Dict[str, QButtonGroup] = {}

        default_csv = DEFAULT_RESULTS_DIR / f"evaluations_{datetime.now():%Y%m%d}.csv"
        self.output_csv_path = default_csv
        self.data_dir = self._default_data_dir()
        self.bundles: List[PatientBundle] = []
        self.current_index = -1
        self.evaluated_keys = set()

        self._build_ui()
        self._apply_styles()
        self.scan_data_directory(show_message=False)

    def _default_data_dir(self) -> Path:
        if (APP_DIR / "data").exists():
            return APP_DIR / "data"
        if (APP_DIR / "sample_data").exists():
            return APP_DIR / "sample_data"
        return APP_DIR

    def _build_ui(self):
        central = QWidget()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)
        self.setCentralWidget(central)

        top_card = QFrame()
        top_layout = QGridLayout(top_card)
        top_layout.setContentsMargins(12, 12, 12, 12)
        top_layout.setHorizontalSpacing(8)
        top_layout.setVerticalSpacing(8)

        top_layout.addWidget(QLabel("Dossier donnees JSON"), 0, 0)
        self.data_dir_input = QLineEdit(str(self.data_dir))
        self.data_dir_input.setReadOnly(True)
        top_layout.addWidget(self.data_dir_input, 0, 1)
        self.change_dir_btn = QPushButton("Changer dossier")
        self.change_dir_btn.clicked.connect(self.select_data_directory)
        top_layout.addWidget(self.change_dir_btn, 0, 2)
        self.refresh_btn = QPushButton("Rafraichir liste JSON")
        self.refresh_btn.clicked.connect(lambda: self.scan_data_directory(show_message=True))
        top_layout.addWidget(self.refresh_btn, 0, 3)

        top_layout.addWidget(QLabel("CSV resultats"), 1, 0)
        self.csv_output_input = QLineEdit(str(self.output_csv_path))
        top_layout.addWidget(self.csv_output_input, 1, 1)
        self.pick_csv_btn = QPushButton("Choisir CSV")
        self.pick_csv_btn.clicked.connect(self.pick_output_csv)
        top_layout.addWidget(self.pick_csv_btn, 1, 2)

        self.save_btn = QPushButton("Enregistrer evaluation")
        self.save_btn.clicked.connect(self.save_current_evaluation)
        top_layout.addWidget(self.save_btn, 1, 3)

        self.status_label = QLabel("Pret.")
        top_layout.addWidget(self.status_label, 2, 0, 1, 4)
        root_layout.addWidget(top_card)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(splitter, 1)

        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)
        left_layout.addWidget(QLabel("Patients detectes"))

        self.patient_list = QListWidget()
        self.patient_list.currentRowChanged.connect(self.on_patient_selected)
        left_layout.addWidget(self.patient_list, 1)

        nav_row = QHBoxLayout()
        self.prev_btn = QPushButton("Precedent")
        self.prev_btn.clicked.connect(self.go_previous)
        self.next_btn = QPushButton("Suivant")
        self.next_btn.clicked.connect(self.go_next)
        nav_row.addWidget(self.prev_btn)
        nav_row.addWidget(self.next_btn)
        left_layout.addLayout(nav_row)

        self.progress_label = QLabel("Patients evalues: 0/0")
        left_layout.addWidget(self.progress_label)
        splitter.addWidget(left_panel)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(10)
        right_scroll.setWidget(right_container)
        splitter.addWidget(right_scroll)
        splitter.setStretchFactor(1, 1)

        self.current_patient_label = QLabel("Patient courant: -")
        right_layout.addWidget(self.current_patient_label)

        details_group = QGroupBox("Informations en texte")
        details_layout = QGridLayout(details_group)
        details_layout.setVerticalSpacing(6)
        details_layout.addWidget(QLabel("Description patient"), 0, 0)
        details_layout.addWidget(QLabel("Conclusion RCP"), 0, 1)
        details_layout.addWidget(QLabel("Conclusion IA"), 0, 2)

        self.patient_text = QPlainTextEdit()
        self.rcp_text = QPlainTextEdit()
        self.ia_text = QPlainTextEdit()
        for widget in (self.patient_text, self.rcp_text, self.ia_text):
            widget.setReadOnly(True)
            widget.setMinimumHeight(220)

        details_layout.addWidget(self.patient_text, 1, 0)
        details_layout.addWidget(self.rcp_text, 1, 1)
        details_layout.addWidget(self.ia_text, 1, 2)
        right_layout.addWidget(details_group)

        questionnaire_group = QGroupBox("Questionnaire (notes 1 a 5)")
        questionnaire_layout = QVBoxLayout(questionnaire_group)
        questionnaire_layout.setSpacing(8)
        for index, question in enumerate(self.questions, start=1):
            row = QHBoxLayout()
            text_label = QLabel(f"{index}. {question['text']}")
            text_label.setWordWrap(True)
            row.addWidget(text_label, 2)

            buttons_box = QHBoxLayout()
            group = QButtonGroup(self)
            group.setExclusive(True)
            self.question_groups[question["id"]] = group
            for score in range(1, 6):
                button = QPushButton(str(score))
                button.setCheckable(True)
                button.setMaximumWidth(38)
                group.addButton(button, score)
                buttons_box.addWidget(button)
            row.addLayout(buttons_box, 1)
            questionnaire_layout.addLayout(row)
        right_layout.addWidget(questionnaire_group)

        comment_group = QGroupBox("Commentaire libre (optionnel)")
        comment_layout = QVBoxLayout(comment_group)
        self.comment_edit = QPlainTextEdit()
        self.comment_edit.setPlaceholderText("Commentaire clinique libre...")
        self.comment_edit.setMinimumHeight(120)
        comment_layout.addWidget(self.comment_edit)
        right_layout.addWidget(comment_group)

    def _apply_styles(self):
        self.setStyleSheet(
            """
            QMainWindow { background: #f4f7fb; color: #17212b; }
            QFrame, QGroupBox {
                background: white;
                border: 1px solid #d8e2f0;
                border-radius: 10px;
            }
            QGroupBox {
                margin-top: 10px;
                padding-top: 10px;
                font-weight: 600;
            }
            QLabel { color: #233142; }
            QLineEdit, QPlainTextEdit, QListWidget {
                background: #fbfdff;
                border: 1px solid #c9d8ee;
                border-radius: 8px;
                padding: 6px;
            }
            QPushButton {
                background: #2f80ed;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 12px;
                font-weight: 600;
            }
            QPushButton:hover { background: #2568c4; }
            QPushButton:checked { background: #1f5fb6; }
            """
        )

    def set_status(self, text: str):
        self.status_label.setText(text)

    def select_data_directory(self):
        selected = QFileDialog.getExistingDirectory(self, "Choisir dossier de donnees", str(self.data_dir))
        if not selected:
            return
        self.data_dir = Path(selected)
        self.data_dir_input.setText(str(self.data_dir))
        self.scan_data_directory(show_message=True)

    def pick_output_csv(self):
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Choisir fichier CSV de sortie",
            str(self.output_csv_path),
            "CSV Files (*.csv);;All Files (*)",
        )
        if not selected:
            return
        self.output_csv_path = Path(selected)
        self.csv_output_input.setText(str(self.output_csv_path))
        self.load_evaluated_keys_from_csv()
        self.refresh_patient_list_status()

    def load_evaluated_keys_from_csv(self):
        self.evaluated_keys = set()
        csv_path = Path(self.csv_output_input.text().strip())
        if not csv_path.exists():
            return
        try:
            with csv_path.open("r", newline="", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    batch_key = (row.get("batch_key") or "").strip()
                    patient_id = (row.get("patient_id") or "").strip()
                    if batch_key:
                        self.evaluated_keys.add(normalize_pair_key(batch_key))
                    elif patient_id:
                        self.evaluated_keys.add(normalize_pair_key(patient_id))
        except Exception:
            pass

    def scan_data_directory(self, show_message: bool):
        root = Path(self.data_dir_input.text().strip())
        if not root.exists() or not root.is_dir():
            QMessageBox.warning(self, "Dossier invalide", f"Dossier introuvable: {root}")
            return

        bundles, total_keys, incomplete = discover_patient_bundles(root)
        self.bundles = bundles
        self.current_index = -1
        self.patient_list.clear()
        self.clear_view()
        self.load_evaluated_keys_from_csv()

        for bundle in self.bundles:
            item = QListWidgetItem(self._item_text(bundle))
            item.setData(Qt.ItemDataRole.UserRole, bundle.key)
            self.patient_list.addItem(item)

        if self.bundles:
            target_index = self._first_unevaluated_index()
            self.patient_list.setCurrentRow(target_index)
        self.refresh_patient_list_status()

        self.set_status(
            f"JSON detectes: {len(self.bundles)} patients complets, {incomplete} incomplets ignores (cles: {total_keys})."
        )
        if show_message:
            QMessageBox.information(
                self,
                "Scan termine",
                f"Patients complets detectes: {len(self.bundles)}\nPatients incomplets ignores: {incomplete}",
            )

    def _first_unevaluated_index(self) -> int:
        for index, bundle in enumerate(self.bundles):
            if not self._is_evaluated(bundle):
                return index
        return 0

    def _is_evaluated(self, bundle: PatientBundle) -> bool:
        return normalize_pair_key(bundle.key) in self.evaluated_keys or normalize_pair_key(bundle.patient_id) in self.evaluated_keys

    def _item_text(self, bundle: PatientBundle) -> str:
        status = "Evalue" if self._is_evaluated(bundle) else "A evaluer"
        return f"[{status}] {bundle.patient_id} ({bundle.key})"

    def refresh_patient_list_status(self):
        done = 0
        for index, bundle in enumerate(self.bundles):
            if self._is_evaluated(bundle):
                done += 1
            item = self.patient_list.item(index)
            if item is not None:
                item.setText(self._item_text(bundle))
        total = len(self.bundles)
        self.progress_label.setText(f"Patients evalues: {done}/{total}")

    def on_patient_selected(self, row: int):
        if row < 0 or row >= len(self.bundles):
            self.current_index = -1
            self.clear_view()
            return
        self.current_index = row
        self.load_patient_into_view(self.bundles[row])

    def clear_view(self):
        self.current_patient_label.setText("Patient courant: -")
        self.patient_text.clear()
        self.rcp_text.clear()
        self.ia_text.clear()
        self.reset_form()

    def load_patient_into_view(self, bundle: PatientBundle):
        self.current_patient_label.setText(
            f"Patient courant: {bundle.patient_id} | {self.current_index + 1}/{len(self.bundles)}"
        )
        self.patient_text.setPlainText(format_patient_description(bundle.patient_data))
        self.rcp_text.setPlainText(extract_evaluation_text(bundle.rcp_data))
        self.ia_text.setPlainText(extract_evaluation_text(bundle.ia_data))
        self.reset_form()
        self.set_status(f"Patient charge: {bundle.patient_id}")

    def reset_form(self):
        for group in self.question_groups.values():
            group.setExclusive(False)
            for button in group.buttons():
                button.setChecked(False)
            group.setExclusive(True)
        self.comment_edit.clear()

    def go_previous(self):
        if not self.bundles:
            return
        if self.current_index <= 0:
            self.set_status("Premier patient deja selectionne.")
            return
        self.patient_list.setCurrentRow(self.current_index - 1)

    def go_next(self):
        if not self.bundles:
            return
        if self.current_index >= len(self.bundles) - 1:
            self.set_status("Dernier patient atteint.")
            return
        self.patient_list.setCurrentRow(self.current_index + 1)

    def collect_ratings(self) -> Optional[Dict[str, int]]:
        ratings = {}
        for question in self.questions:
            group = self.question_groups[question["id"]]
            score = group.checkedId()
            if score not in (1, 2, 3, 4, 5):
                return None
            ratings[question["id"]] = score
        return ratings

    def save_current_evaluation(self):
        if self.current_index < 0 or self.current_index >= len(self.bundles):
            QMessageBox.warning(self, "Aucun patient", "Selectionnez un patient a evaluer.")
            return

        ratings = self.collect_ratings()
        if ratings is None:
            QMessageBox.warning(self, "Questionnaire incomplet", "Renseignez toutes les notes de 1 a 5.")
            return

        csv_path = Path(self.csv_output_input.text().strip())
        if not csv_path.name:
            QMessageBox.warning(self, "CSV invalide", "Definissez un chemin CSV valide.")
            return
        csv_path.parent.mkdir(parents=True, exist_ok=True)

        bundle = self.bundles[self.current_index]
        row = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "patient_id": bundle.patient_id,
            "batch_key": bundle.key,
            "patient_json_path": str(bundle.patient_path),
            "rcp_json_path": str(bundle.rcp_path),
            "ia_json_path": str(bundle.ia_path),
            "commentaire": self.comment_edit.toPlainText().strip(),
        }
        for question in self.questions:
            row[f"score_{question['id']}"] = ratings[question["id"]]

        try:
            final_path = self.append_row_to_csv(csv_path, row)
        except Exception as error:
            QMessageBox.critical(self, "Erreur export CSV", str(error))
            return

        self.evaluated_keys.add(normalize_pair_key(bundle.key))
        self.evaluated_keys.add(normalize_pair_key(bundle.patient_id))
        self.refresh_patient_list_status()
        self.set_status(f"Evaluation enregistree dans {final_path}")

        if self.current_index < len(self.bundles) - 1:
            self.patient_list.setCurrentRow(self.current_index + 1)
        else:
            QMessageBox.information(self, "Batch termine", f"Toutes les evaluations sont enregistrees.\nCSV: {final_path}")

    def append_row_to_csv(self, output_csv_path: Path, row: Dict[str, Any]) -> Path:
        target_path = output_csv_path
        expected_columns = list(row.keys())

        if target_path.exists():
            with target_path.open("r", newline="", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                existing_columns = reader.fieldnames or []
            if existing_columns != expected_columns:
                timestamp = datetime.now().strftime("%H%M%S")
                target_path = target_path.with_stem(f"{target_path.stem}_{timestamp}")

        file_exists = target_path.exists()
        with target_path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=expected_columns)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
        return target_path


def main():
    app = QApplication(sys.argv)
    window = ClinicianFeedbackApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
