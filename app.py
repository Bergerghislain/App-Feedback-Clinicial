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
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
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
OUTPUT_CSV_DELIMITER = ";"
COLLECTION_CSV_NAME = "evaluations.csv"


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


def detect_csv_delimiter(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8-sig") as file:
            sample = file.read(4096)
    except Exception:
        return OUTPUT_CSV_DELIMITER

    if not sample.strip():
        return OUTPUT_CSV_DELIMITER

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,")
        return dialect.delimiter if dialect.delimiter in (";", ",") else OUTPUT_CSV_DELIMITER
    except Exception:
        if sample.count(";") >= sample.count(","):
            return ";"
        return ","


def read_csv_rows(path: Path):
    delimiter = detect_csv_delimiter(path)
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file, delimiter=delimiter)
        return (reader.fieldnames or []), list(reader)


def bootstrap_collection_csv(default_path: Path) -> Path:
    default_path.parent.mkdir(parents=True, exist_ok=True)
    if default_path.exists():
        return default_path

    legacy_paths = sorted(default_path.parent.glob("evaluations_*.csv"))
    if not legacy_paths:
        return default_path

    merged_columns: List[str] = []
    merged_rows: List[Dict[str, Any]] = []
    seen_rows = set()

    for legacy_path in legacy_paths:
        try:
            columns, rows = read_csv_rows(legacy_path)
        except Exception:
            continue

        for column in columns:
            if column not in merged_columns:
                merged_columns.append(column)

        for row in rows:
            row_signature = json.dumps(row, ensure_ascii=False, sort_keys=True)
            if row_signature in seen_rows:
                continue
            seen_rows.add(row_signature)
            merged_rows.append(row)

    if not merged_columns:
        return default_path

    normalized_rows = [{column: row.get(column, "") for column in merged_columns} for row in merged_rows]
    with default_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=merged_columns, delimiter=OUTPUT_CSV_DELIMITER)
        writer.writeheader()
        writer.writerows(normalized_rows)

    return default_path


def get_collection_csv_path() -> Path:
    return bootstrap_collection_csv(DEFAULT_RESULTS_DIR / COLLECTION_CSV_NAME)


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
        self.setWindowTitle("Clinical Feedback - Evaluation Clinique")
        self.resize(1280, 820)

        self.questions_path = APP_DIR / "questions.json"
        self.questions = load_questions_from_json(self.questions_path)
        self.reasoning_qcm = [
            {
                "id": "clarte",
                "text": "La reflexion de l'IA est-elle claire ?",
                "options": [("tres_claire", "Tres claire"), ("moyenne", "Moyennement claire"), ("peu_claire", "Peu claire")],
            },
            {
                "id": "coherence",
                "text": "La reflexion est-elle coherent avec les donnees patient ?",
                "options": [("coherente", "Oui"), ("partielle", "Partiellement"), ("non_coherente", "Non")],
            },
            {
                "id": "utilite",
                "text": "La reflexion apporte-t-elle une aide clinique utile ?",
                "options": [("utile", "Utile"), ("limitee", "Utilite limitee"), ("inutile", "Peu utile")],
            },
        ]

        self.data_dir = self._default_data_dir()
        self.results_dir = APP_DIR / "results"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.csv_conclusion_ia_path = self.results_dir / "evaluations_conclusion_ia.csv"
        self.csv_conclusion_rcp_path = self.results_dir / "evaluations_conclusion_rcp.csv"
        self.csv_reasoning_path = self.results_dir / "evaluations_reflexion_ia.csv"

        self.bundles, _, _ = discover_patient_bundles(self.data_dir)
        self.current_index = 0
        self.patient_states: Dict[str, Dict[str, Any]] = {}
        self.completed_count = 0
        self.current_conclusion_mapping: Dict[str, Any] = {}

        self.page1_groups: Dict[str, Dict[str, QButtonGroup]] = {}
        self.page2_qcm_groups: Dict[str, QButtonGroup] = {}
        self.page2_qcm_options: Dict[str, List[Any]] = {}

        self._build_ui()
        self._apply_styles()
        self._load_current_patient()

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

        header = QFrame()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(12, 12, 12, 12)
        header_layout.setSpacing(4)
        self.patient_counter_label = QLabel("Patient 0/0")
        self.progress_label = QLabel("Evaluations finalisees: 0/0")
        self.status_label = QLabel(f"Dossier de donnees detecte: {self.data_dir}")
        header_layout.addWidget(self.patient_counter_label)
        header_layout.addWidget(self.progress_label)
        header_layout.addWidget(self.status_label)
        root_layout.addWidget(header)

        self.stack = QStackedWidget()
        root_layout.addWidget(self.stack, 1)

        # Page 1: evaluation des conclusions (blindees)
        self.page1 = QWidget()
        page1_layout = QVBoxLayout(self.page1)
        page1_layout.setContentsMargins(8, 8, 8, 8)
        page1_layout.setSpacing(10)

        self.page1_title_label = QLabel("Etape 1 - Evaluation des conclusions")
        page1_layout.addWidget(self.page1_title_label)

        description_group = QGroupBox("Description patient (a lire en premier)")
        description_layout = QVBoxLayout(description_group)
        self.description_text = QPlainTextEdit()
        self.description_text.setReadOnly(True)
        self.description_text.setMinimumHeight(120)
        self.description_text.setMaximumHeight(180)
        description_layout.addWidget(self.description_text)
        page1_layout.addWidget(description_group)

        conclusions_group = QGroupBox("Conclusions (affichage neutre)")
        conclusions_layout = QGridLayout(conclusions_group)
        conclusions_layout.addWidget(QLabel("Conclusion 1"), 0, 0)
        conclusions_layout.addWidget(QLabel("Conclusion 2"), 0, 1)
        self.conclusion1_text = QPlainTextEdit()
        self.conclusion2_text = QPlainTextEdit()
        for widget in (self.conclusion1_text, self.conclusion2_text):
            widget.setReadOnly(True)
            widget.setMinimumHeight(90)
            widget.setMaximumHeight(140)
        conclusions_layout.addWidget(self.conclusion1_text, 1, 0)
        conclusions_layout.addWidget(self.conclusion2_text, 1, 1)
        page1_layout.addWidget(conclusions_group)

        questionnaire_group = QGroupBox("Noter chaque conclusion (1 a 5)")
        questionnaire_layout = QGridLayout(questionnaire_group)
        questionnaire_layout.addWidget(QLabel("Question"), 0, 0)
        questionnaire_layout.addWidget(QLabel("Conclusion 1"), 0, 1)
        questionnaire_layout.addWidget(QLabel("Conclusion 2"), 0, 2)

        for row, question in enumerate(self.questions, start=1):
            question_label = QLabel(f"{row}. {question['text']}")
            question_label.setWordWrap(True)
            questionnaire_layout.addWidget(question_label, row, 0)

            self.page1_groups[question["id"]] = {}
            for col, label in enumerate(("c1", "c2"), start=1):
                score_row = QHBoxLayout()
                group = QButtonGroup(self)
                group.setExclusive(True)
                self.page1_groups[question["id"]][label] = group
                for score in range(1, 6):
                    button = QPushButton(str(score))
                    button.setCheckable(True)
                    button.setMaximumWidth(36)
                    group.addButton(button, score)
                    score_row.addWidget(button)
                container = QWidget()
                container.setLayout(score_row)
                questionnaire_layout.addWidget(container, row, col)
        page1_layout.addWidget(questionnaire_group)

        action_row = QHBoxLayout()
        self.page1_locked_label = QLabel("")
        self.page1_locked_label.hide()
        self.page1_next_btn = QPushButton("Go to the next page")
        self.page1_next_btn.clicked.connect(self._on_page1_next)
        action_row.addWidget(self.page1_locked_label, 1)
        action_row.addWidget(self.page1_next_btn)
        page1_layout.addLayout(action_row)
        self.stack.addWidget(self._wrap_in_scroll_area(self.page1))

        # Page 2: evaluation de la reflexion IA
        self.page2 = QWidget()
        page2_layout = QVBoxLayout(self.page2)
        page2_layout.setContentsMargins(8, 8, 8, 8)
        page2_layout.setSpacing(10)

        self.page2_title_label = QLabel("Etape 2 - Evaluation de la reflexion IA (meme patient)")
        page2_layout.addWidget(self.page2_title_label)

        reasoning_group = QGroupBox("Reflexion de l'IA")
        reasoning_layout = QVBoxLayout(reasoning_group)
        self.reasoning_text = QPlainTextEdit()
        self.reasoning_text.setReadOnly(True)
        self.reasoning_text.setMinimumHeight(140)
        self.reasoning_text.setMaximumHeight(210)
        reasoning_layout.addWidget(self.reasoning_text)
        page2_layout.addWidget(reasoning_group)

        qcm_group = QGroupBox("QCM reflexion IA")
        qcm_layout = QVBoxLayout(qcm_group)
        for question in self.reasoning_qcm:
            row = QHBoxLayout()
            label = QLabel(question["text"])
            label.setWordWrap(True)
            row.addWidget(label, 2)

            options_layout = QHBoxLayout()
            group = QButtonGroup(self)
            group.setExclusive(True)
            self.page2_qcm_groups[question["id"]] = group
            self.page2_qcm_options[question["id"]] = question["options"]

            for index, (_, option_label) in enumerate(question["options"]):
                button = QPushButton(option_label)
                button.setCheckable(True)
                group.addButton(button, index)
                options_layout.addWidget(button)
            row.addLayout(options_layout, 3)
            qcm_layout.addLayout(row)
        page2_layout.addWidget(qcm_group)

        comment_group = QGroupBox("Commentaire libre sur la reflexion IA")
        comment_layout = QVBoxLayout(comment_group)
        self.reasoning_comment_edit = QPlainTextEdit()
        self.reasoning_comment_edit.setPlaceholderText("Commentaire clinique libre sur la reflexion IA...")
        self.reasoning_comment_edit.setMinimumHeight(90)
        self.reasoning_comment_edit.setMaximumHeight(140)
        comment_layout.addWidget(self.reasoning_comment_edit)
        page2_layout.addWidget(comment_group)

        nav_row = QHBoxLayout()
        self.page2_previous_btn = QPushButton("Previous page")
        self.page2_previous_btn.clicked.connect(self._on_page2_previous)
        self.page2_next_patient_btn = QPushButton("Go to the next patient")
        self.page2_next_patient_btn.clicked.connect(self._on_page2_next_patient)
        nav_row.addWidget(self.page2_previous_btn)
        nav_row.addStretch(1)
        nav_row.addWidget(self.page2_next_patient_btn)
        page2_layout.addLayout(nav_row)
        self.stack.addWidget(self._wrap_in_scroll_area(self.page2))

    def _wrap_in_scroll_area(self, page_widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page_widget)
        return scroll

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
            QLabel { color: #233142; font-size: 13px; }
            QPlainTextEdit {
                background: #fbfdff;
                border: 1px solid #c9d8ee;
                border-radius: 8px;
                padding: 8px;
            }
            QScrollArea {
                border: none;
                background: transparent;
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

    def _set_status(self, text: str):
        self.status_label.setText(text)

    def _extract_reasoning_text(self, ia_data: Any) -> str:
        if isinstance(ia_data, dict):
            for key in (
                "reasoning",
                "reflexion",
                "reflection",
                "raisonnement",
                "reasoning_text",
                "justification",
                "explication",
                "explanation",
                "analysis",
            ):
                value = ia_data.get(key)
                if value not in (None, "", []):
                    return format_value(value)
        return "Aucune reflexion IA fournie dans le JSON."

    def _assign_conclusion_mapping(self, bundle: PatientBundle) -> Dict[str, Any]:
        rcp_text = extract_evaluation_text(bundle.rcp_data)
        ia_text = extract_evaluation_text(bundle.ia_data)
        parity = sum(ord(character) for character in normalize_pair_key(bundle.key)) % 2
        if parity == 0:
            return {"c1_role": "ia", "c2_role": "rcp", "c1_text": ia_text, "c2_text": rcp_text}
        return {"c1_role": "rcp", "c2_role": "ia", "c1_text": rcp_text, "c2_text": ia_text}

    def _set_page1_editable(self, editable: bool):
        for group_map in self.page1_groups.values():
            for group in group_map.values():
                for button in group.buttons():
                    button.setEnabled(editable)

    def _reset_page1_form(self):
        for group_map in self.page1_groups.values():
            for group in group_map.values():
                group.setExclusive(False)
                for button in group.buttons():
                    button.setChecked(False)
                group.setExclusive(True)

    def _reset_page2_form(self):
        for group in self.page2_qcm_groups.values():
            group.setExclusive(False)
            for button in group.buttons():
                button.setChecked(False)
            group.setExclusive(True)
        self.reasoning_comment_edit.clear()

    def _update_header(self):
        total = len(self.bundles)
        current = self.current_index + 1 if 0 <= self.current_index < total else 0
        self.patient_counter_label.setText(f"Patient {current}/{total}")
        self.progress_label.setText(f"Evaluations finalisees: {self.completed_count}/{total}")

    def _load_current_patient(self):
        if not self.bundles:
            self.patient_counter_label.setText("Patient 0/0")
            self.progress_label.setText("Evaluations finalisees: 0/0")
            self.description_text.setPlainText("Aucun patient charge. Verifiez le dossier data/.")
            self.conclusion1_text.clear()
            self.conclusion2_text.clear()
            self.reasoning_text.clear()
            self.page1_next_btn.setEnabled(False)
            self.page2_next_patient_btn.setEnabled(False)
            self._set_status(f"Aucun patient detecte dans {self.data_dir}")
            return

        self._update_header()
        bundle = self.bundles[self.current_index]
        self.current_conclusion_mapping = self._assign_conclusion_mapping(bundle)

        self.page1_title_label.setText(
            f"Etape 1 - Evaluation des conclusions pour patient {bundle.patient_id}"
        )
        self.page2_title_label.setText(
            f"Etape 2 - Evaluation de la reflexion IA pour patient {bundle.patient_id}"
        )

        self.description_text.setPlainText(format_patient_description(bundle.patient_data))
        self.conclusion1_text.setPlainText(self.current_conclusion_mapping["c1_text"])
        self.conclusion2_text.setPlainText(self.current_conclusion_mapping["c2_text"])
        self.reasoning_text.setPlainText(self._extract_reasoning_text(bundle.ia_data))
        self._reset_page2_form()

        state = self.patient_states.get(bundle.key, {})
        if state.get("stage1_saved"):
            self.page1_locked_label.setText("Evaluation des conclusions deja enregistree. Modification desactivee.")
            self.page1_locked_label.show()
            self._set_page1_editable(False)
        else:
            self.page1_locked_label.hide()
            self._set_page1_editable(True)
            self._reset_page1_form()

        is_last = self.current_index == len(self.bundles) - 1
        self.page2_next_patient_btn.setText("Finish" if is_last else "Go to the next patient")
        self.stack.setCurrentIndex(0)
        self._set_status(f"Patient charge: {bundle.patient_id}")

    def _collect_page1_scores(self):
        scores = {"c1": {}, "c2": {}}
        for question in self.questions:
            question_id = question["id"]
            score_c1 = self.page1_groups[question_id]["c1"].checkedId()
            score_c2 = self.page1_groups[question_id]["c2"].checkedId()
            if score_c1 not in (1, 2, 3, 4, 5) or score_c2 not in (1, 2, 3, 4, 5):
                return None
            scores["c1"][question_id] = score_c1
            scores["c2"][question_id] = score_c2
        return scores

    def _collect_page2_answers(self):
        answers: Dict[str, Dict[str, str]] = {}
        for question in self.reasoning_qcm:
            question_id = question["id"]
            selected_index = self.page2_qcm_groups[question_id].checkedId()
            if selected_index < 0:
                return None
            option_id, option_label = self.page2_qcm_options[question_id][selected_index]
            answers[question_id] = {"option_id": option_id, "option_label": option_label}
        return answers

    def _on_page1_next(self):
        if not self.bundles:
            return

        bundle = self.bundles[self.current_index]
        state = self.patient_states.setdefault(bundle.key, {})
        if state.get("stage1_saved"):
            self.stack.setCurrentIndex(1)
            return

        scores = self._collect_page1_scores()
        if scores is None:
            QMessageBox.warning(self, "Questionnaire incomplet", "Renseignez toutes les notes pour Conclusion 1 et Conclusion 2.")
            return

        timestamp = datetime.now()
        evaluation_id = f"{bundle.patient_id}_{timestamp.strftime('%Y%m%d%H%M%S%f')}"
        common_data = {
            "evaluation_id": evaluation_id,
            "timestamp": timestamp.isoformat(timespec="seconds"),
            "patient_id": bundle.patient_id,
            "batch_key": bundle.key,
            "patient_json_path": str(bundle.patient_path),
            "rcp_json_path": str(bundle.rcp_path),
            "ia_json_path": str(bundle.ia_path),
        }

        rows_to_save = []
        for display_key, display_label in (("c1", "Conclusion 1"), ("c2", "Conclusion 2")):
            role = self.current_conclusion_mapping[f"{display_key}_role"]
            row = {
                **common_data,
                "conclusion_affichee": display_label,
                "source_reelle": role.upper(),
                "conclusion_text": self.current_conclusion_mapping[f"{display_key}_text"],
            }
            for question in self.questions:
                question_id = question["id"]
                row[f"question_{question_id}"] = question["text"]
                row[f"score_{question_id}"] = scores[display_key][question_id]
            rows_to_save.append((role, row))

        try:
            for role, row in rows_to_save:
                target_csv = self.csv_conclusion_ia_path if role == "ia" else self.csv_conclusion_rcp_path
                self.append_row_to_csv(target_csv, row)
        except Exception as error:
            QMessageBox.critical(self, "Erreur export CSV", f"Impossible d'enregistrer les conclusions:\n{error}")
            return

        state["stage1_saved"] = True
        state["evaluation_id"] = evaluation_id
        self.page1_locked_label.setText("Evaluation des conclusions enregistree. Modification desactivee.")
        self.page1_locked_label.show()
        self._set_page1_editable(False)
        self._set_status(f"Conclusions enregistrees pour {bundle.patient_id}.")
        self.stack.setCurrentIndex(1)

    def _on_page2_previous(self):
        self.stack.setCurrentIndex(0)

    def _on_page2_next_patient(self):
        if not self.bundles:
            return

        bundle = self.bundles[self.current_index]
        state = self.patient_states.get(bundle.key, {})
        if not state.get("stage1_saved"):
            QMessageBox.warning(self, "Etape 1 requise", "Enregistrez d'abord l'evaluation des conclusions (page 1).")
            return
        if state.get("stage2_saved"):
            QMessageBox.information(self, "Deja enregistre", "L'evaluation de reflexion IA est deja enregistree pour ce patient.")
            return

        answers = self._collect_page2_answers()
        if answers is None:
            QMessageBox.warning(self, "QCM incomplet", "Merci de repondre a tout le QCM de reflexion IA.")
            return

        row = {
            "evaluation_id": state["evaluation_id"],
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "patient_id": bundle.patient_id,
            "batch_key": bundle.key,
            "patient_json_path": str(bundle.patient_path),
            "ia_json_path": str(bundle.ia_path),
            "commentaire_reflexion": self.reasoning_comment_edit.toPlainText().strip(),
        }
        for question in self.reasoning_qcm:
            question_id = question["id"]
            row[f"qcm_{question_id}_question"] = question["text"]
            row[f"qcm_{question_id}_option_id"] = answers[question_id]["option_id"]
            row[f"qcm_{question_id}_option_label"] = answers[question_id]["option_label"]

        try:
            self.append_row_to_csv(self.csv_reasoning_path, row)
        except Exception as error:
            QMessageBox.critical(self, "Erreur export CSV", f"Impossible d'enregistrer l'evaluation de reflexion IA:\n{error}")
            return

        if not state.get("stage2_saved"):
            state["stage2_saved"] = True
            self.completed_count += 1

        if self.current_index == len(self.bundles) - 1:
            self._update_header()
            QMessageBox.information(
                self,
                "Finish",
                "Evaluation terminee.\n"
                f"- {self.csv_conclusion_ia_path}\n"
                f"- {self.csv_conclusion_rcp_path}\n"
                f"- {self.csv_reasoning_path}",
            )
            self._set_status("Collecte terminee pour tous les patients.")
            return

        self.current_index += 1
        self._load_current_patient()

    def append_row_to_csv(self, output_csv_path: Path, row: Dict[str, Any]) -> Path:
        output_csv_path.parent.mkdir(parents=True, exist_ok=True)
        new_columns = list(row.keys())
        existing_rows: List[Dict[str, Any]] = []
        existing_columns: List[str] = []

        if output_csv_path.exists():
            delimiter = detect_csv_delimiter(output_csv_path)
            with output_csv_path.open("r", newline="", encoding="utf-8-sig") as file:
                reader = csv.DictReader(file, delimiter=delimiter)
                existing_columns = reader.fieldnames or []
                existing_rows = list(reader)

        merged_columns = list(existing_columns)
        for column in new_columns:
            if column not in merged_columns:
                merged_columns.append(column)
        if not merged_columns:
            merged_columns = new_columns

        normalized_rows = [{column: old_row.get(column, "") for column in merged_columns} for old_row in existing_rows]
        normalized_rows.append({column: row.get(column, "") for column in merged_columns})

        with output_csv_path.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=merged_columns, delimiter=OUTPUT_CSV_DELIMITER)
            writer.writeheader()
            writer.writerows(normalized_rows)
        return output_csv_path


def main():
    app = QApplication(sys.argv)
    window = ClinicianFeedbackApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
