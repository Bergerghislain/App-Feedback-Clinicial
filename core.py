"""Logique métier indépendante de l'interface graphique (JSON, normalisation, CSV)."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_QUESTIONS = [
    {
        "id": "Q1",
        "text": "La conclusion IA est-elle globalement pertinente pour ce patient ?",
    },
    {
        "id": "Q2",
        "text": "Le niveau de détail de l'évaluation IA est-il suffisant ?",
    },
    {
        "id": "Q3",
        "text": "La comparaison IA vs RCP vous semble-t-elle cohérente ?",
    },
    {
        "id": "Q4",
        "text": "La conclusion IA vous paraît-elle cliniquement utile ?",
    },
]

QUESTION_HEADERS = [
    "timestamp",
    "clinicien",
    "patient_id",
    "patient_nom",
    "question_id",
    "question_texte",
    "score",
    "commentaire_global",
    "conclusion_rcp",
    "conclusion_ia",
]


@dataclass
class Question:
    question_id: str
    text: str


@dataclass
class Patient:
    patient_id: str
    display_name: str
    plain_text: str
    raw: dict[str, Any]


def load_json_file(path: str) -> Any:
    with Path(path).expanduser().open("r", encoding="utf-8") as handle:
        return json.load(handle)


def value_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


def detect_patient_id(record: dict[str, Any], fallback_index: int) -> str:
    for key in ("patient_id", "id", "patientId", "patientID", "uuid"):
        candidate = record.get(key)
        if candidate:
            return str(candidate)
    return f"PATIENT_{fallback_index:03d}"


def detect_patient_name(record: dict[str, Any], patient_id: str) -> str:
    for key in ("nom", "name", "patient_name", "display_name", "full_name"):
        candidate = record.get(key)
        if candidate:
            return str(candidate)
    return patient_id


def patient_plain_text(record: dict[str, Any], patient_id: str, display_name: str) -> str:
    lines: list[str] = [
        f"Identifiant patient: {patient_id}",
        f"Nom / libellé: {display_name}",
    ]

    description = record.get("description") or record.get("resume") or record.get("summary")
    if description:
        lines.append("")
        lines.append("Description clinique:")
        lines.append(value_to_text(description))

    ignored = {
        "patient_id",
        "id",
        "patientId",
        "patientID",
        "uuid",
        "nom",
        "name",
        "patient_name",
        "display_name",
        "full_name",
        "description",
        "resume",
        "summary",
    }

    extra_keys = [key for key in record.keys() if key not in ignored]
    if extra_keys:
        lines.append("")
        lines.append("Autres informations:")
        for key in sorted(extra_keys):
            lines.append(f"- {key}: {value_to_text(record.get(key))}")

    return "\n".join(lines)


def normalize_patients(data: Any) -> list[Patient]:
    records: list[dict[str, Any]]

    if isinstance(data, dict):
        if "patients" in data and isinstance(data["patients"], list):
            records = [item for item in data["patients"] if isinstance(item, dict)]
        elif "data" in data and isinstance(data["data"], list):
            records = [item for item in data["data"] if isinstance(item, dict)]
        elif all(isinstance(item, dict) for item in data.values()):
            records = []
            for key, value in data.items():
                enriched = dict(value)
                enriched.setdefault("patient_id", key)
                records.append(enriched)
        else:
            raise ValueError("Format JSON patient non reconnu.")
    elif isinstance(data, list):
        records = [item for item in data if isinstance(item, dict)]
    else:
        raise ValueError("Le JSON patient doit être une liste ou un objet.")

    patients: list[Patient] = []
    for index, record in enumerate(records, start=1):
        patient_id = detect_patient_id(record, index)
        display_name = detect_patient_name(record, patient_id)
        plain = patient_plain_text(record, patient_id, display_name)
        patients.append(
            Patient(
                patient_id=patient_id,
                display_name=display_name,
                plain_text=plain,
                raw=record,
            )
        )

    if not patients:
        raise ValueError("Aucun patient exploitable trouvé dans le JSON patient.")
    return patients


def pick_evaluation_text(record: dict[str, Any]) -> str:
    for key in (
        "conclusion",
        "evaluation",
        "texte",
        "text",
        "summary",
        "resume",
        "result",
        "report",
    ):
        value = record.get(key)
        if value:
            return value_to_text(value)

    stripped = {
        key: value
        for key, value in record.items()
        if key not in {"patient_id", "id", "patientId", "patientID", "uuid"}
    }
    if stripped:
        return value_to_text(stripped)
    return ""


def normalize_evaluations(data: Any) -> dict[str, str]:
    output: dict[str, str] = {}

    if isinstance(data, dict):
        if "evaluations" in data and isinstance(data["evaluations"], list):
            entries = data["evaluations"]
        elif "data" in data and isinstance(data["data"], list):
            entries = data["data"]
        else:
            entries = None

        if entries is not None:
            for index, item in enumerate(entries, start=1):
                if not isinstance(item, dict):
                    continue
                patient_id = detect_patient_id(item, index)
                output[patient_id] = pick_evaluation_text(item)
        else:
            for key, value in data.items():
                if isinstance(value, dict):
                    enriched = dict(value)
                    enriched.setdefault("patient_id", key)
                    output[str(key)] = pick_evaluation_text(enriched)
                else:
                    output[str(key)] = value_to_text(value)

    elif isinstance(data, list):
        for index, item in enumerate(data, start=1):
            if not isinstance(item, dict):
                continue
            patient_id = detect_patient_id(item, index)
            output[patient_id] = pick_evaluation_text(item)
    else:
        raise ValueError("Le JSON d'évaluation doit être une liste ou un objet.")

    return output


def normalize_questions(data: Any | None) -> list[Question]:
    if data is None:
        source = DEFAULT_QUESTIONS
    elif isinstance(data, dict):
        if "questions" in data and isinstance(data["questions"], list):
            source = data["questions"]
        else:
            raise ValueError("Le JSON questions doit contenir une clé 'questions' de type liste.")
    elif isinstance(data, list):
        source = data
    else:
        raise ValueError("Le JSON questions doit être une liste ou un objet.")

    questions: list[Question] = []
    for index, item in enumerate(source, start=1):
        if isinstance(item, str):
            text = item.strip()
            question_id = f"Q{index}"
        elif isinstance(item, dict):
            text = value_to_text(item.get("text") or item.get("question") or item.get("libelle") or item.get("label")).strip()
            raw_qid = item.get("id") or item.get("question_id") or item.get("key") or f"Q{index}"
            question_id = str(raw_qid)
        else:
            continue

        if text:
            questions.append(Question(question_id=question_id, text=text))

    if not questions:
        raise ValueError("Aucune question valide trouvée.")
    return questions


def append_feedback_rows(path: str, rows: list[dict[str, Any]]) -> None:
    output = Path(path).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    file_exists = output.exists()

    with output.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=QUESTION_HEADERS)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)
