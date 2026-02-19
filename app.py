#!/usr/bin/env python3
"""Application desktop pour comparer des évaluations IA/RCP et collecter des retours cliniciens."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import filedialog, messagebox, ttk


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
            # Format dictionnaire: { "PATIENT_001": "..."} ou {"PATIENT_001": {"conclusion": "..."}}
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


class ClinicianFeedbackApp(tk.Tk):
    def __init__(self, prefill: dict[str, str]) -> None:
        super().__init__()
        self.title("Plateforme d'évaluation clinique IA vs RCP")
        self.geometry("1360x900")
        self.minsize(1080, 760)

        self.patient_file_var = tk.StringVar()
        self.rcp_file_var = tk.StringVar()
        self.ia_file_var = tk.StringVar()
        self.questions_file_var = tk.StringVar()
        self.output_csv_var = tk.StringVar()
        self.clinician_var = tk.StringVar()
        self.selected_patient_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Aucune donnée chargée.")

        self.patient_lookup: dict[str, Patient] = {}
        self.patients: list[Patient] = []
        self.rcp_by_patient: dict[str, str] = {}
        self.ia_by_patient: dict[str, str] = {}
        self.questions: list[Question] = []
        self.question_vars: dict[str, tk.IntVar] = {}
        self.completed_patients: set[str] = set()

        self.patient_text: tk.Text
        self.rcp_text: tk.Text
        self.ia_text: tk.Text
        self.comment_text: tk.Text
        self.patient_combo: ttk.Combobox
        self.save_button: ttk.Button
        self.questions_frame: ttk.Frame
        self.questions_canvas: tk.Canvas
        self.questions_canvas_window: int

        self._build_ui()
        self._prefill(prefill)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        config = ttk.LabelFrame(root, text="1) Configuration des fichiers")
        config.pack(fill="x", pady=(0, 10))
        config.columnconfigure(1, weight=1)

        self._add_path_row(
            parent=config,
            row_index=0,
            label_text="JSON patients:",
            variable=self.patient_file_var,
            browse_callback=lambda: self._browse_file(self.patient_file_var),
        )
        self._add_path_row(
            parent=config,
            row_index=1,
            label_text="JSON conclusions RCP:",
            variable=self.rcp_file_var,
            browse_callback=lambda: self._browse_file(self.rcp_file_var),
        )
        self._add_path_row(
            parent=config,
            row_index=2,
            label_text="JSON conclusions IA:",
            variable=self.ia_file_var,
            browse_callback=lambda: self._browse_file(self.ia_file_var),
        )
        self._add_path_row(
            parent=config,
            row_index=3,
            label_text="JSON questions (optionnel):",
            variable=self.questions_file_var,
            browse_callback=lambda: self._browse_file(self.questions_file_var),
        )
        self._add_path_row(
            parent=config,
            row_index=4,
            label_text="CSV de sortie:",
            variable=self.output_csv_var,
            browse_callback=self._browse_output_csv,
        )

        actions_config = ttk.Frame(config)
        actions_config.grid(row=5, column=0, columnspan=3, sticky="ew", padx=8, pady=(4, 8))
        actions_config.columnconfigure(0, weight=1)
        ttk.Button(
            actions_config,
            text="Charger les données JSON",
            command=self.load_data,
        ).pack(side="right")

        metadata = ttk.Frame(root)
        metadata.pack(fill="x", pady=(0, 10))
        metadata.columnconfigure(3, weight=1)
        ttk.Label(metadata, text="Nom du clinicien:").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(metadata, textvariable=self.clinician_var, width=35).grid(row=0, column=1, sticky="w")
        ttk.Label(metadata, textvariable=self.status_var).grid(row=0, column=3, sticky="e")

        selector = ttk.Frame(root)
        selector.pack(fill="x", pady=(0, 8))
        ttk.Label(selector, text="2) Patient à évaluer:").pack(side="left")
        self.patient_combo = ttk.Combobox(
            selector,
            textvariable=self.selected_patient_var,
            state="readonly",
            width=60,
        )
        self.patient_combo.pack(side="left", padx=8)
        self.patient_combo.bind("<<ComboboxSelected>>", self._on_patient_change)

        content_pane = ttk.Panedwindow(root, orient="horizontal")
        content_pane.pack(fill="both", expand=True)

        patient_frame = ttk.LabelFrame(content_pane, text="Description patient")
        patient_frame.columnconfigure(0, weight=1)
        patient_frame.rowconfigure(0, weight=1)
        self.patient_text = self._make_text_widget(patient_frame, height=20)
        self.patient_text.grid(row=0, column=0, sticky="nsew")
        content_pane.add(patient_frame, weight=1)

        eval_frame = ttk.Frame(content_pane)
        eval_frame.columnconfigure(0, weight=1)
        eval_frame.rowconfigure(0, weight=1)
        eval_frame.rowconfigure(1, weight=1)

        rcp_box = ttk.LabelFrame(eval_frame, text="Conclusion RCP (texte)")
        rcp_box.columnconfigure(0, weight=1)
        rcp_box.rowconfigure(0, weight=1)
        self.rcp_text = self._make_text_widget(rcp_box, height=10)
        self.rcp_text.grid(row=0, column=0, sticky="nsew")
        rcp_box.grid(row=0, column=0, sticky="nsew", pady=(0, 6))

        ia_box = ttk.LabelFrame(eval_frame, text="Conclusion IA (texte)")
        ia_box.columnconfigure(0, weight=1)
        ia_box.rowconfigure(0, weight=1)
        self.ia_text = self._make_text_widget(ia_box, height=10)
        self.ia_text.grid(row=0, column=0, sticky="nsew")
        ia_box.grid(row=1, column=0, sticky="nsew", pady=(6, 0))

        content_pane.add(eval_frame, weight=2)

        questionnaire = ttk.LabelFrame(root, text="3) Questionnaire (notes de 1 à 5)")
        questionnaire.pack(fill="both", expand=True, pady=(10, 8))

        self.questions_canvas = tk.Canvas(questionnaire, highlightthickness=0, height=240)
        scroll_questions = ttk.Scrollbar(
            questionnaire,
            orient="vertical",
            command=self.questions_canvas.yview,
        )
        self.questions_canvas.configure(yscrollcommand=scroll_questions.set)
        self.questions_canvas.pack(side="left", fill="both", expand=True)
        scroll_questions.pack(side="right", fill="y")

        self.questions_frame = ttk.Frame(self.questions_canvas)
        self.questions_canvas_window = self.questions_canvas.create_window(
            (0, 0),
            window=self.questions_frame,
            anchor="nw",
        )
        self.questions_frame.bind(
            "<Configure>",
            lambda _event: self.questions_canvas.configure(
                scrollregion=self.questions_canvas.bbox("all")
            ),
        )
        self.questions_canvas.bind(
            "<Configure>",
            lambda event: self.questions_canvas.itemconfigure(
                self.questions_canvas_window,
                width=event.width,
            ),
        )

        comments = ttk.LabelFrame(root, text="4) Commentaire global (optionnel)")
        comments.pack(fill="x")
        self.comment_text = tk.Text(comments, height=4, wrap="word")
        self.comment_text.pack(fill="x", padx=8, pady=8)

        bottom_actions = ttk.Frame(root)
        bottom_actions.pack(fill="x", pady=(10, 0))
        ttk.Button(bottom_actions, text="Réinitialiser les notes", command=self.reset_ratings).pack(
            side="right"
        )
        self.save_button = ttk.Button(
            bottom_actions,
            text="Enregistrer l'évaluation",
            command=self.save_current_feedback,
            state="disabled",
        )
        self.save_button.pack(side="right", padx=(0, 8))

        self._set_text(self.patient_text, "Chargez des JSON pour démarrer.")
        self._set_text(self.rcp_text, "Chargez des JSON pour démarrer.")
        self._set_text(self.ia_text, "Chargez des JSON pour démarrer.")

    def _add_path_row(
        self,
        parent: ttk.LabelFrame,
        row_index: int,
        label_text: str,
        variable: tk.StringVar,
        browse_callback: Any,
    ) -> None:
        ttk.Label(parent, text=label_text, width=28).grid(
            row=row_index,
            column=0,
            sticky="w",
            padx=(8, 0),
            pady=4,
        )
        ttk.Entry(parent, textvariable=variable).grid(
            row=row_index,
            column=1,
            sticky="ew",
            padx=8,
            pady=4,
        )
        ttk.Button(parent, text="Parcourir", command=browse_callback).grid(
            row=row_index,
            column=2,
            sticky="e",
            padx=(0, 8),
            pady=4,
        )

    def _make_text_widget(self, parent: tk.Widget, height: int) -> tk.Text:
        container = ttk.Frame(parent)
        container.grid(sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        widget = tk.Text(container, wrap="word", height=height)
        widget.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=widget.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        widget.configure(yscrollcommand=scrollbar.set)
        widget.configure(state="disabled")
        return widget

    def _prefill(self, prefill: dict[str, str]) -> None:
        self.patient_file_var.set(prefill.get("patients", ""))
        self.rcp_file_var.set(prefill.get("rcp", ""))
        self.ia_file_var.set(prefill.get("ia", ""))
        self.questions_file_var.set(prefill.get("questions", ""))
        self.output_csv_var.set(prefill.get("output", ""))
        if not self.output_csv_var.get():
            self.output_csv_var.set(str(Path.cwd() / "resultats_questionnaire.csv"))

    def _browse_file(self, variable: tk.StringVar) -> None:
        path = filedialog.askopenfilename(
            title="Sélectionner un fichier JSON",
            filetypes=[("JSON", "*.json"), ("Tous les fichiers", "*.*")],
        )
        if path:
            variable.set(path)

    def _browse_output_csv(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Choisir le fichier CSV de sortie",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Tous les fichiers", "*.*")],
        )
        if path:
            self.output_csv_var.set(path)

    def _render_questions(self) -> None:
        for child in self.questions_frame.winfo_children():
            child.destroy()

        self.question_vars.clear()
        self.questions_frame.columnconfigure(0, weight=1)

        legend = ttk.Label(
            self.questions_frame,
            text="Échelle: 1 = Très faible pertinence, 5 = Très forte pertinence",
        )
        legend.grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))

        for index, question in enumerate(self.questions, start=1):
            row = ttk.Frame(self.questions_frame)
            row.grid(row=index, column=0, sticky="ew", padx=8, pady=6)
            row.columnconfigure(0, weight=1)

            ttk.Label(
                row,
                text=f"{index}. {question.text}",
                justify="left",
                wraplength=900,
            ).grid(row=0, column=0, sticky="w")

            score_var = tk.IntVar(value=0)
            self.question_vars[question.question_id] = score_var

            selector = ttk.Frame(row)
            selector.grid(row=0, column=1, sticky="e", padx=(10, 0))
            for score in range(1, 6):
                ttk.Radiobutton(
                    selector,
                    text=str(score),
                    variable=score_var,
                    value=score,
                ).pack(side="left", padx=2)

    def _set_text(self, widget: tk.Text, content: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert("1.0", content or "-")
        widget.configure(state="disabled")

    def _patient_choice_label(self, patient: Patient) -> str:
        return f"{patient.patient_id} | {patient.display_name}"

    def _update_status(self) -> None:
        total = len(self.patients)
        completed = len(self.completed_patients)
        if total == 0:
            self.status_var.set("Aucune donnée chargée.")
            return
        self.status_var.set(f"Patients évalués: {completed}/{total}")

    def load_data(self) -> None:
        patient_path = self.patient_file_var.get().strip()
        rcp_path = self.rcp_file_var.get().strip()
        ia_path = self.ia_file_var.get().strip()
        questions_path = self.questions_file_var.get().strip()

        if not patient_path or not rcp_path or not ia_path:
            messagebox.showerror(
                "Fichiers manquants",
                "Merci de renseigner au minimum les JSON patients, RCP et IA.",
            )
            return

        try:
            patients_raw = load_json_file(patient_path)
            rcp_raw = load_json_file(rcp_path)
            ia_raw = load_json_file(ia_path)
            questions_raw = load_json_file(questions_path) if questions_path else None

            self.patients = normalize_patients(patients_raw)
            self.rcp_by_patient = normalize_evaluations(rcp_raw)
            self.ia_by_patient = normalize_evaluations(ia_raw)
            self.questions = normalize_questions(questions_raw)

            self.completed_patients.clear()
            self._render_questions()

            self.patient_lookup.clear()
            labels: list[str] = []
            for patient in self.patients:
                label = self._patient_choice_label(patient)
                labels.append(label)
                self.patient_lookup[label] = patient

            self.patient_combo["values"] = labels
            if labels:
                self.selected_patient_var.set(labels[0])
                self._on_patient_change()

            self.save_button.configure(state="normal")
            self._update_status()
            messagebox.showinfo(
                "Chargement terminé",
                f"{len(self.patients)} patient(s) chargé(s) et {len(self.questions)} question(s) prêtes.",
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Erreur de chargement", str(exc))

    def _on_patient_change(self, _event: Any | None = None) -> None:
        patient = self.patient_lookup.get(self.selected_patient_var.get())
        if not patient:
            return

        self._set_text(self.patient_text, patient.plain_text)
        self._set_text(
            self.rcp_text,
            self.rcp_by_patient.get(patient.patient_id, "Aucune conclusion RCP trouvée pour ce patient."),
        )
        self._set_text(
            self.ia_text,
            self.ia_by_patient.get(patient.patient_id, "Aucune conclusion IA trouvée pour ce patient."),
        )
        self.reset_ratings(clear_comment=True)

    def reset_ratings(self, clear_comment: bool = True) -> None:
        for variable in self.question_vars.values():
            variable.set(0)
        if clear_comment:
            self.comment_text.delete("1.0", tk.END)

    def save_current_feedback(self) -> None:
        patient = self.patient_lookup.get(self.selected_patient_var.get())
        if not patient:
            messagebox.showerror("Patient manquant", "Sélectionnez un patient avant d'enregistrer.")
            return

        clinician_name = self.clinician_var.get().strip()
        if not clinician_name:
            messagebox.showerror("Clinicien manquant", "Merci de renseigner votre nom.")
            return

        missing_questions = [
            question.text
            for question in self.questions
            if self.question_vars.get(question.question_id) is None
            or self.question_vars[question.question_id].get() == 0
        ]
        if missing_questions:
            messagebox.showerror(
                "Questionnaire incomplet",
                "Merci de répondre à toutes les questions avant d'enregistrer.",
            )
            return

        csv_output = self.output_csv_var.get().strip()
        if not csv_output:
            messagebox.showerror("CSV manquant", "Merci de choisir un fichier CSV de sortie.")
            return

        now = datetime.now().isoformat(timespec="seconds")
        global_comment = self.comment_text.get("1.0", tk.END).strip()
        rcp_text = self.rcp_by_patient.get(patient.patient_id, "")
        ia_text = self.ia_by_patient.get(patient.patient_id, "")

        rows: list[dict[str, Any]] = []
        for question in self.questions:
            score = self.question_vars[question.question_id].get()
            rows.append(
                {
                    "timestamp": now,
                    "clinicien": clinician_name,
                    "patient_id": patient.patient_id,
                    "patient_nom": patient.display_name,
                    "question_id": question.question_id,
                    "question_texte": question.text,
                    "score": score,
                    "commentaire_global": global_comment,
                    "conclusion_rcp": rcp_text,
                    "conclusion_ia": ia_text,
                }
            )

        try:
            append_feedback_rows(csv_output, rows)
            self.completed_patients.add(patient.patient_id)
            self._update_status()
            messagebox.showinfo(
                "Enregistré",
                f"Évaluation enregistrée pour le patient {patient.patient_id}.",
            )
            self.reset_ratings(clear_comment=True)
            self._move_to_next_patient()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Erreur CSV", str(exc))

    def _move_to_next_patient(self) -> None:
        values = list(self.patient_combo["values"])
        if not values:
            return
        current = self.selected_patient_var.get()
        try:
            current_index = values.index(current)
        except ValueError:
            return
        if current_index + 1 < len(values):
            self.selected_patient_var.set(values[current_index + 1])
            self._on_patient_change()


def resolve_prefill_path(raw: str | None) -> str:
    if not raw:
        return ""
    return str(Path(raw).expanduser().resolve())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interface d'évaluation clinicienne pour comparer IA et RCP."
    )
    parser.add_argument("--patients", help="Chemin du JSON patients")
    parser.add_argument("--rcp", help="Chemin du JSON conclusions RCP")
    parser.add_argument("--ia", help="Chemin du JSON conclusions IA")
    parser.add_argument("--questions", help="Chemin du JSON questions (optionnel)")
    parser.add_argument("--output", help="Chemin du CSV de sortie")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prefill = {
        "patients": resolve_prefill_path(args.patients),
        "rcp": resolve_prefill_path(args.rcp),
        "ia": resolve_prefill_path(args.ia),
        "questions": resolve_prefill_path(args.questions),
        "output": resolve_prefill_path(args.output),
    }

    app = ClinicianFeedbackApp(prefill=prefill)
    app.mainloop()


if __name__ == "__main__":
    main()
