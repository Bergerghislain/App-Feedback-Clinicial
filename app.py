import csv
import json
import re
import shutil
import sys
import tempfile
import zipfile
import os
import base64
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

try:
    import pyzipper
except Exception:
    pyzipper = None


DEFAULT_QUESTIONS = [
    {"id": "q1", "text": "Cette conclusion est-elle cliniquement pertinente pour ce patient ?"},
    {"id": "q2", "text": "Le niveau de detail de cette conclusion est-il suffisant ?"},
    {"id": "q3", "text": "Cette conclusion est-elle coherente avec les donnees du patient ?"},
    {"id": "q4", "text": "Cette conclusion aide-t-elle a la prise de decision clinique ?"},
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
APP_DATA_KEY_FILE = ".data_access.key"
APP_DATA_KEY_FILE_ALTERNATES = [".data_access.key", "data_access.key"]
APP_DATA_KEY_ENV_VAR = "APP_FEEDBACK_DATA_PASSWORD"
APP_DATA_OBFUSCATION_SECRET = b"AppFeedbackClinical"
APP_DATA_KEY_PREFIX = "AFCLINICAL"


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


def _xor_bytes(data: bytes, key: bytes) -> bytes:
    return bytes(data[index] ^ key[index % len(key)] for index in range(len(data)))


def decode_app_data_password(token: str) -> Optional[str]:
    cleaned = token.strip()
    if not cleaned:
        return None
    try:
        decoded = base64.urlsafe_b64decode(cleaned.encode("utf-8"))
        plaintext = _xor_bytes(decoded, APP_DATA_OBFUSCATION_SECRET).decode("utf-8")
    except Exception:
        return None
    if not plaintext.startswith(f"{APP_DATA_KEY_PREFIX}:"):
        return None
    return plaintext.split(":", 1)[1]


def blind_question_text(text: str) -> str:
    replacements = [
        (r"(?i)\bla\s+conclusion\s+ia\b", "la conclusion évaluee"),
        (r"(?i)\ble\s+niveau\s+de\s+detail\s+de\s+la\s+conclusion\s+ia\b", "le niveau de detail de cette conclusion"),
        (r"(?i)\bla\s+conclusion\s+rcp\b", "l'autre conclusion"),
        (r"(?i)\bl['’]evaluation\s+ia\b", "l'évaluation de cette conclusion"),
        (r"(?i)\bevaluation\s+ia\b", "évaluation de cette conclusion"),
        (r"(?i)\bconclusion\s+ia\b", "conclusion évaluee"),
        (r"(?i)\bconclusion\s+rcp\b", "autre conclusion"),
        (r"(?i)\bRCP\b", "autre conclusion"),
        (r"(?i)\bIA\b", "cette conclusion"),
        (r"(?i)du modele", "de cette conclusion"),
        (r"(?i)du modèle", "de cette conclusion"),
    ]
    output = text
    for pattern, replacement in replacements:
        output = re.sub(pattern, replacement, output)
    output = re.sub(r"\bla\s+cette\b", "cette", output, flags=re.IGNORECASE)
    output = re.sub(r"\bla\s+la\b", "la", output, flags=re.IGNORECASE)
    output = re.sub(r"\s{2,}", " ", output)
    if text and text[0].isupper() and output:
        output = output[0].upper() + output[1:]
    return output.strip()


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
        self.setWindowTitle("Clinical Feedback - Évaluation clinique")
        self.resize(1280, 820)

        self.questions_path = APP_DIR / "questions.json"
        self.questions = load_questions_from_json(self.questions_path)
        self.reasoning_qcm = [
            {
                "id": "clarte",
                "text": "La réflexion de l'IA est-elle claire ?",
                "options": [("tres_claire", "Tres claire"), ("moyenne", "Moyennement claire"), ("peu_claire", "Peu claire")],
            },
            {
                "id": "coherence",
                "text": "La réflexion est-elle cohérente avec les données patient ?",
                "options": [("coherente", "Oui"), ("partielle", "Partiellement"), ("non_coherente", "Non")],
            },
            {
                "id": "utilite",
                "text": "La réflexion apporte-t-elle une aide clinique utile ?",
                "options": [("utile", "Utile"), ("limitee", "Utilite limitee"), ("inutile", "Peu utile")],
            },
        ]

        self._temp_data_root: Optional[Path] = None
        self._data_origin_label = "dossier local"
        self.data_dir = self._resolve_data_dir()
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
        self.progress_draft_path = self.results_dir / "progress_draft.json"
        self._pending_draft: Optional[Dict[str, Any]] = None

        self._build_ui()
        self._apply_styles()
        self._load_existing_progress()
        self._restore_draft_progress_if_any()
        self._load_current_patient()

    def _default_data_dir(self) -> Path:
        for base_dir in self._candidate_base_dirs():
            if (base_dir / "data").exists():
                return base_dir / "data"
            if (base_dir / "sample_data").exists():
                return base_dir / "sample_data"
        return APP_DIR

    def _candidate_base_dirs(self) -> List[Path]:
        candidates = [APP_DIR]
        parent_dir = APP_DIR.parent
        if parent_dir != APP_DIR:
            candidates.append(parent_dir)
        # Evite les doublons tout en gardant l'ordre.
        seen = set()
        ordered = []
        for candidate in candidates:
            normalized = str(candidate.resolve())
            if normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(candidate)
        return ordered

    def _resolve_data_dir(self) -> Path:
        for base_dir in self._candidate_base_dirs():
            data_zip_path = base_dir / "data.zip"
            if not data_zip_path.exists():
                continue

            password = self._load_data_zip_password(base_dir)
            if not password:
                fallback = self._default_data_dir()
                self._data_origin_label = str(fallback)
                QMessageBox.warning(
                    self,
                    "Configuration securite manquante",
                    f"Le fichier de cle ({' ou '.join(APP_DATA_KEY_FILE_ALTERNATES)}) est requis a cote de data.zip.",
                )
                return fallback

            extracted = self._extract_data_zip_silent(data_zip_path, password)
            if extracted is not None:
                self._data_origin_label = f"data.zip (dechiffre automatique): {data_zip_path}"
                return extracted

            fallback = self._default_data_dir()
            self._data_origin_label = str(fallback)
            if fallback == APP_DIR:
                QMessageBox.warning(
                    self,
                    "Donnees non accessibles",
                    "Aucun dossier data lisible n'est disponible.",
                )
            return fallback

        fallback = self._default_data_dir()
        self._data_origin_label = str(fallback)
        return fallback

    def _load_data_zip_password(self, base_dir: Path) -> Optional[str]:
        password_from_env = os.getenv(APP_DATA_KEY_ENV_VAR, "").strip()
        if password_from_env:
            return password_from_env

        candidate_files = []
        for key_filename in APP_DATA_KEY_FILE_ALTERNATES:
            candidate_files.append(base_dir / key_filename)
        for key_filename in APP_DATA_KEY_FILE_ALTERNATES:
            candidate_files.append(APP_DIR / key_filename)
        key_file = next((path for path in candidate_files if path.exists()), None)
        if key_file is None:
            return None

        try:
            token = key_file.read_text(encoding="utf-8-sig")
        except Exception:
            return None
        return decode_app_data_password(token)

    def _extract_data_zip_silent(self, zip_path: Path, password: str) -> Optional[Path]:
        temp_root = Path(tempfile.mkdtemp(prefix="app_feedback_data_"))
        try:
            self._extract_zip_content(zip_path, temp_root, password)
            self._extract_nested_payload_if_present(temp_root)
            extracted_data_dir = self._locate_data_directory(temp_root)
            if extracted_data_dir is None:
                raise ValueError("Aucun JSON detecte apres extraction de data.zip.")
        except Exception as error:
            shutil.rmtree(temp_root, ignore_errors=True)
            QMessageBox.warning(self, "Acces data.zip impossible", f"Impossible d'ouvrir data.zip : {error}")
            return None

        self._temp_data_root = temp_root
        return extracted_data_dir

    def _extract_nested_payload_if_present(self, extracted_root: Path):
        payload_file = extracted_root / "payload.bin"
        if not payload_file.exists():
            return
        with zipfile.ZipFile(payload_file, "r") as inner_zip:
            inner_zip.extractall(extracted_root)
        payload_file.unlink(missing_ok=True)

    def _extract_zip_content(self, zip_path: Path, target_dir: Path, password: str):
        encoded_pwd = password.encode("utf-8")
        if pyzipper is not None:
            with pyzipper.AESZipFile(zip_path, "r") as zip_file:
                zip_file.pwd = encoded_pwd
                zip_file.extractall(target_dir)
            return

        with zipfile.ZipFile(zip_path, "r") as zip_file:
            try:
                zip_file.extractall(target_dir, pwd=encoded_pwd)
            except NotImplementedError as error:
                raise RuntimeError(
                    "Ce zip semble utiliser un chiffrement AES. Installez la dependance 'pyzipper'."
                ) from error

    def _locate_data_directory(self, extracted_root: Path) -> Optional[Path]:
        direct_data = extracted_root / "data"
        if direct_data.exists() and direct_data.is_dir():
            return direct_data

        # Cas: le zip contient directement les JSON.
        if any(extracted_root.rglob("*.json")):
            subdirs = [path for path in extracted_root.iterdir() if path.is_dir()]
            if len(subdirs) == 1 and any(subdirs[0].rglob("*.json")):
                return subdirs[0]
            return extracted_root
        return None

    def _build_ui(self):
        central = QWidget()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)
        self.setCentralWidget(central)

        header = QFrame()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(14, 12, 14, 12)
        header_layout.setSpacing(8)
        self.patient_counter_label = QLabel("Patient 0/0")
        self.progress_label = QLabel("Evaluations finalisees: 0/0")
        self.status_label = QLabel(f"Dossier de données détecté: {self._data_origin_label}")
        self.save_progress_btn = QPushButton("Sauvegarder en cours")
        self.save_progress_btn.setProperty("actionButton", True)
        self.save_progress_btn.clicked.connect(self._save_progress_draft)
        header_layout.addWidget(self.patient_counter_label)
        header_layout.addWidget(self.progress_label)
        header_layout.addWidget(self.status_label)
        header_layout.addWidget(self.save_progress_btn)
        root_layout.addWidget(header)

        self.stack = QStackedWidget()
        root_layout.addWidget(self.stack, 1)

        # Page 1: evaluation des conclusions (blindees)
        self.page1 = QWidget()
        page1_layout = QVBoxLayout(self.page1)
        page1_layout.setContentsMargins(12, 12, 12, 12)
        page1_layout.setSpacing(12)

        self.page1_title_label = QLabel("Étape 1 - Évaluation des conclusions")
        page1_layout.addWidget(self.page1_title_label)

        description_group = QGroupBox("Description patient (à lire en premier)")
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

        questionnaire_group = QGroupBox("Noter chaque conclusion (1 à 5)")
        questionnaire_layout = QGridLayout(questionnaire_group)
        questionnaire_layout.addWidget(QLabel("Question"), 0, 0)
        questionnaire_layout.addWidget(QLabel("Conclusion 1"), 0, 1)
        questionnaire_layout.addWidget(QLabel("Conclusion 2"), 0, 2)

        for row, question in enumerate(self.questions, start=1):
            question_label = QLabel(f"{row}. {blind_question_text(question['text'])}")
            question_label.setWordWrap(True)
            questionnaire_layout.addWidget(question_label, row, 0)

            self.page1_groups[question["id"]] = {}
            for col, label in enumerate(("c1", "c2"), start=1):
                score_row = QHBoxLayout()
                score_row.setContentsMargins(0, 0, 0, 0)
                score_row.setSpacing(6)
                group = QButtonGroup(self)
                group.setExclusive(True)
                self.page1_groups[question["id"]][label] = group
                for score in range(1, 6):
                    button = QPushButton(str(score))
                    button.setCheckable(True)
                    button.setFixedSize(48, 38)
                    button.setProperty("scoreButton", True)
                    button.setProperty("scoreLevel", str(score))
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
        self.page1_next_btn.setProperty("actionButton", True)
        self.page1_next_btn.clicked.connect(self._on_page1_next)
        action_row.addWidget(self.page1_locked_label, 1)
        action_row.addWidget(self.page1_next_btn)
        page1_layout.addLayout(action_row)
        self.stack.addWidget(self._wrap_in_scroll_area(self.page1))

        # Page 2: évaluation de la réflexion IA
        self.page2 = QWidget()
        page2_layout = QVBoxLayout(self.page2)
        page2_layout.setContentsMargins(12, 12, 12, 12)
        page2_layout.setSpacing(12)

        self.page2_title_label = QLabel("Étape 2 - Évaluation de la réflexion IA (même patient)")
        page2_layout.addWidget(self.page2_title_label)

        reasoning_group = QGroupBox("Réflexion de l'IA")
        reasoning_layout = QVBoxLayout(reasoning_group)
        self.reasoning_text = QPlainTextEdit()
        self.reasoning_text.setReadOnly(True)
        self.reasoning_text.setMinimumHeight(140)
        self.reasoning_text.setMaximumHeight(210)
        reasoning_layout.addWidget(self.reasoning_text)
        page2_layout.addWidget(reasoning_group)

        qcm_group = QGroupBox("QCM réflexion IA")
        qcm_layout = QVBoxLayout(qcm_group)
        for question in self.reasoning_qcm:
            row = QHBoxLayout()
            row.setSpacing(10)
            label = QLabel(question["text"])
            label.setWordWrap(True)
            row.addWidget(label, 2)

            options_layout = QHBoxLayout()
            options_layout.setContentsMargins(0, 0, 0, 0)
            options_layout.setSpacing(8)
            group = QButtonGroup(self)
            group.setExclusive(True)
            self.page2_qcm_groups[question["id"]] = group
            self.page2_qcm_options[question["id"]] = question["options"]

            for index, (_, option_label) in enumerate(question["options"]):
                button = QPushButton(option_label)
                button.setCheckable(True)
                button.setProperty("scoreButton", True)
                button.setProperty("optionButton", True)
                group.addButton(button, index)
                options_layout.addWidget(button)
            row.addLayout(options_layout, 3)
            qcm_layout.addLayout(row)
        page2_layout.addWidget(qcm_group)

        comment_group = QGroupBox("Commentaire libre sur la réflexion IA")
        comment_layout = QVBoxLayout(comment_group)
        self.reasoning_comment_edit = QPlainTextEdit()
        self.reasoning_comment_edit.setPlaceholderText("Commentaire clinique libre sur la réflexion IA...")
        self.reasoning_comment_edit.setMinimumHeight(90)
        self.reasoning_comment_edit.setMaximumHeight(140)
        comment_layout.addWidget(self.reasoning_comment_edit)
        page2_layout.addWidget(comment_group)

        nav_row = QHBoxLayout()
        self.page2_previous_btn = QPushButton("Previous page")
        self.page2_previous_btn.setProperty("actionButton", True)
        self.page2_previous_btn.clicked.connect(self._on_page2_previous)
        self.page2_next_patient_btn = QPushButton("Go to the next patient")
        self.page2_next_patient_btn.setProperty("actionButton", True)
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
            QMainWindow { background: #f8fafc; color: #0f172a; }
            QFrame, QGroupBox {
                background: white;
                border: 1px solid #cbd5e1;
                border-radius: 12px;
            }
            QGroupBox {
                margin-top: 12px;
                padding-top: 12px;
                font-weight: 600;
            }
            QLabel {
                color: #0f172a;
                font-size: 15px;
                line-height: 1.3;
            }
            QPlainTextEdit {
                background: #ffffff;
                border: 1px solid #94a3b8;
                border-radius: 8px;
                padding: 8px;
                font-size: 16px;
                color: #0f172a;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            QPushButton {
                background: #ffffff;
                color: #0f172a;
                border: 1px solid #94a3b8;
                border-radius: 8px;
                padding: 9px 12px;
                font-weight: 600;
                font-size: 15px;
            }
            QPushButton:hover { background: #f8fafc; border: 1px solid #64748b; }
            QPushButton:focus { border: 2px solid #111827; }
            QPushButton:disabled { background: #f1f5f9; color: #94a3b8; border: 1px solid #cbd5e1; }
            QPushButton:checked { background: #065f46; color: #ffffff; border: 1px solid #064e3b; }
            QPushButton[actionButton="true"] {
                background: #1d4ed8;
                color: #ffffff;
                border: 1px solid #1d4ed8;
                min-height: 40px;
            }
            QPushButton[actionButton="true"]:hover { background: #1e40af; }
            QPushButton[actionButton="true"]:checked { background: #1e40af; color: #ffffff; border: 1px solid #1e3a8a; }
            QPushButton[scoreButton="true"] {
                min-height: 38px;
                min-width: 48px;
                max-height: 38px;
                max-width: 48px;
                font-size: 16px;
                border: 2px solid #94a3b8;
                border-radius: 10px;
            }
            QPushButton[optionButton="true"] {
                min-width: 130px;
                max-width: 220px;
                min-height: 38px;
                max-height: 38px;
                background: #eef2ff;
                color: #1e3a8a;
                border-color: #93c5fd;
            }
            QPushButton[optionButton="true"]:hover { background: #dbeafe; }
            QPushButton[optionButton="true"]:checked { background: #1d4ed8; color: #ffffff; border-color: #1e40af; }
            QPushButton[scoreButton="true"][scoreLevel="1"] { background: #fee2e2; color: #7f1d1d; border-color: #fca5a5; }
            QPushButton[scoreButton="true"][scoreLevel="2"] { background: #ffedd5; color: #9a3412; border-color: #fdba74; }
            QPushButton[scoreButton="true"][scoreLevel="3"] { background: #fef9c3; color: #854d0e; border-color: #fde047; }
            QPushButton[scoreButton="true"][scoreLevel="4"] { background: #dcfce7; color: #166534; border-color: #86efac; }
            QPushButton[scoreButton="true"][scoreLevel="5"] { background: #d1fae5; color: #065f46; border-color: #6ee7b7; }
            QPushButton[scoreButton="true"][scoreLevel="1"]:hover { background: #fecaca; }
            QPushButton[scoreButton="true"][scoreLevel="2"]:hover { background: #fed7aa; }
            QPushButton[scoreButton="true"][scoreLevel="3"]:hover { background: #fef08a; }
            QPushButton[scoreButton="true"][scoreLevel="4"]:hover { background: #bbf7d0; }
            QPushButton[scoreButton="true"][scoreLevel="5"]:hover { background: #a7f3d0; }
            QPushButton[scoreButton="true"][scoreLevel="1"]:checked { background: #b91c1c; color: #ffffff; border-color: #991b1b; }
            QPushButton[scoreButton="true"][scoreLevel="2"]:checked { background: #c2410c; color: #ffffff; border-color: #9a3412; }
            QPushButton[scoreButton="true"][scoreLevel="3"]:checked { background: #ca8a04; color: #111827; border-color: #a16207; }
            QPushButton[scoreButton="true"][scoreLevel="4"]:checked { background: #15803d; color: #ffffff; border-color: #166534; }
            QPushButton[scoreButton="true"][scoreLevel="5"]:checked { background: #047857; color: #ffffff; border-color: #065f46; }
            QPushButton[scoreButton="true"]:focus { border: 3px solid #111827; }
            """
        )

    def _set_status(self, text: str):
        self.status_label.setText(text)

    def _find_bundle_key(self, patient_id: str, batch_key: str) -> Optional[str]:
        patient_norm = normalize_pair_key(patient_id) if patient_id else ""
        batch_norm = normalize_pair_key(batch_key) if batch_key else ""
        for bundle in self.bundles:
            if batch_norm and normalize_pair_key(bundle.key) == batch_norm:
                return bundle.key
            if patient_norm and normalize_pair_key(bundle.patient_id) == patient_norm:
                return bundle.key
        return None

    def _read_csv_rows(self, csv_path: Path) -> List[Dict[str, Any]]:
        if not csv_path.exists():
            return []
        try:
            delimiter = detect_csv_delimiter(csv_path)
            with csv_path.open("r", newline="", encoding="utf-8-sig") as file:
                reader = csv.DictReader(file, delimiter=delimiter)
                return list(reader)
        except Exception:
            return []

    def _load_existing_progress(self):
        self.patient_states = {}
        self.completed_count = 0
        if not self.bundles:
            self.current_index = 0
            return

        # Étape 1: présence d'une ligne dans les CSV de conclusions
        stage1_rows = self._read_csv_rows(self.csv_conclusion_ia_path) + self._read_csv_rows(self.csv_conclusion_rcp_path)
        for row in stage1_rows:
            bundle_key = self._find_bundle_key(
                str(row.get("patient_id", "")),
                str(row.get("batch_key", "")),
            )
            if not bundle_key:
                continue
            state = self.patient_states.setdefault(bundle_key, {})
            state["stage1_saved"] = True
            if row.get("evaluation_id"):
                state["evaluation_id"] = row.get("evaluation_id")

        # Étape 2: présence d'une ligne dans le CSV de réflexion IA
        for row in self._read_csv_rows(self.csv_reasoning_path):
            bundle_key = self._find_bundle_key(
                str(row.get("patient_id", "")),
                str(row.get("batch_key", "")),
            )
            if not bundle_key:
                continue
            state = self.patient_states.setdefault(bundle_key, {})
            state["stage2_saved"] = True
            state["stage1_saved"] = True
            if row.get("evaluation_id"):
                state["evaluation_id"] = row.get("evaluation_id")

        self.completed_count = sum(
            1 for bundle in self.bundles if self.patient_states.get(bundle.key, {}).get("stage2_saved")
        )

        for index, bundle in enumerate(self.bundles):
            if not self.patient_states.get(bundle.key, {}).get("stage2_saved"):
                self.current_index = index
                return
        self.current_index = len(self.bundles) - 1

    def _save_progress_draft(self, silent: bool = False):
        if not self.bundles:
            return
        bundle = self.bundles[self.current_index]
        state = self.patient_states.get(bundle.key, {})
        if state.get("stage2_saved"):
            if self.progress_draft_path.exists():
                self.progress_draft_path.unlink(missing_ok=True)
            return
        draft = {
            "patient_key": bundle.key,
            "patient_id": bundle.patient_id,
            "current_index": self.current_index,
            "page_index": self.stack.currentIndex(),
            "page1_scores": {},
            "page2_answers": {},
            "page2_comment": self.reasoning_comment_edit.toPlainText().strip(),
        }

        for question in self.questions:
            qid = question["id"]
            draft["page1_scores"][qid] = {
                "c1": self.page1_groups[qid]["c1"].checkedId(),
                "c2": self.page1_groups[qid]["c2"].checkedId(),
            }

        for question in self.reasoning_qcm:
            qid = question["id"]
            draft["page2_answers"][qid] = self.page2_qcm_groups[qid].checkedId()

        self.progress_draft_path.parent.mkdir(parents=True, exist_ok=True)
        self.progress_draft_path.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if not silent:
            self._set_status(f"Progression sauvegardee: {self.progress_draft_path.name}")
            QMessageBox.information(self, "Sauvegarde en cours", "Progression sauvegardee. Vous pourrez reprendre plus tard.")

    def _restore_draft_progress_if_any(self):
        if not self.progress_draft_path.exists() or not self.bundles:
            return
        try:
            draft = json.loads(self.progress_draft_path.read_text(encoding="utf-8-sig"))
        except Exception:
            return

        draft_key = str(draft.get("patient_key", ""))
        if not draft_key:
            return
        for index, bundle in enumerate(self.bundles):
            if bundle.key == draft_key:
                self.current_index = index
                self._pending_draft = draft
                self._set_status("Brouillon detecte: reprise de progression chargee.")
                return

    def _apply_pending_draft_if_needed(self, bundle: PatientBundle):
        draft = getattr(self, "_pending_draft", None)
        if not draft or draft.get("patient_key") != bundle.key:
            return

        page1_scores = draft.get("page1_scores", {})
        for question in self.questions:
            qid = question["id"]
            scores = page1_scores.get(qid, {})
            c1_score = int(scores.get("c1", -1))
            c2_score = int(scores.get("c2", -1))
            if c1_score in (1, 2, 3, 4, 5):
                button = self.page1_groups[qid]["c1"].button(c1_score)
                if button:
                    button.setChecked(True)
            if c2_score in (1, 2, 3, 4, 5):
                button = self.page1_groups[qid]["c2"].button(c2_score)
                if button:
                    button.setChecked(True)

        page2_answers = draft.get("page2_answers", {})
        for question in self.reasoning_qcm:
            qid = question["id"]
            selected = int(page2_answers.get(qid, -1))
            if selected >= 0:
                button = self.page2_qcm_groups[qid].button(selected)
                if button:
                    button.setChecked(True)
        self.reasoning_comment_edit.setPlainText(str(draft.get("page2_comment", "")))

        page_index = int(draft.get("page_index", 0))
        if page_index in (0, 1):
            self.stack.setCurrentIndex(page_index)
        self._pending_draft = None

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
        return "Aucune réflexion IA fournie dans le JSON."

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
            f"Étape 1 - Évaluation des conclusions pour patient {bundle.patient_id}"
        )
        self.page2_title_label.setText(
            f"Étape 2 - Évaluation de la réflexion IA pour patient {bundle.patient_id}"
        )

        self.description_text.setPlainText(format_patient_description(bundle.patient_data))
        self.conclusion1_text.setPlainText(self.current_conclusion_mapping["c1_text"])
        self.conclusion2_text.setPlainText(self.current_conclusion_mapping["c2_text"])
        self.reasoning_text.setPlainText(self._extract_reasoning_text(bundle.ia_data))
        self._reset_page2_form()

        state = self.patient_states.get(bundle.key, {})
        if state.get("stage1_saved"):
            self.page1_locked_label.setText("Évaluation des conclusions déjà enregistrée. Modification désactivée.")
            self.page1_locked_label.show()
            self._set_page1_editable(False)
        else:
            self.page1_locked_label.hide()
            self._set_page1_editable(True)
            self._reset_page1_form()

        is_last = self.current_index == len(self.bundles) - 1
        self.page2_next_patient_btn.setText("Finish" if is_last else "Go to the next patient")
        self.stack.setCurrentIndex(0)
        self._apply_pending_draft_if_needed(bundle)
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
                row[f"question_{question_id}"] = blind_question_text(question["text"])
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
            QMessageBox.warning(self, "Étape 1 requise", "Enregistrez d'abord l'évaluation des conclusions (page 1).")
            return
        if state.get("stage2_saved"):
            QMessageBox.information(self, "Déjà enregistré", "L'évaluation de réflexion IA est déjà enregistrée pour ce patient.")
            return

        answers = self._collect_page2_answers()
        if answers is None:
            QMessageBox.warning(self, "QCM incomplet", "Merci de répondre à tout le QCM de réflexion IA.")
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
            QMessageBox.critical(self, "Erreur export CSV", f"Impossible d'enregistrer l'évaluation de réflexion IA:\n{error}")
            return

        if not state.get("stage2_saved"):
            state["stage2_saved"] = True
            self.completed_count += 1
        if self.progress_draft_path.exists():
            self.progress_draft_path.unlink(missing_ok=True)

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

    def closeEvent(self, event):
        self._save_progress_draft(silent=True)
        if self._temp_data_root and self._temp_data_root.exists():
            shutil.rmtree(self._temp_data_root, ignore_errors=True)
        super().closeEvent(event)

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
