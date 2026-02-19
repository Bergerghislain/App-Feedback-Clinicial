import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk


DEFAULT_QUESTIONS = [
    {
        "id": "q1",
        "text": "La conclusion IA est-elle cliniquement pertinente pour ce patient ?",
    },
    {
        "id": "q2",
        "text": "Le niveau de detail de l'evaluation IA est-il suffisant ?",
    },
    {
        "id": "q3",
        "text": "L'evaluation IA est-elle globalement coherente avec la conclusion RCP ?",
    },
    {
        "id": "q4",
        "text": "L'evaluation IA aide-t-elle a la prise de decision clinique ?",
    },
]


def get_app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


APP_DIR = get_app_base_dir()
DEFAULT_RESULTS_DIR = APP_DIR / "results"
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


def get_first_present_value(source: dict, keys: list[str]):
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


def format_patient_description(patient_data: dict) -> str:
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

    lines = []
    used_keys = set()

    for label, aliases in known_fields.items():
        value = get_first_present_value(patient_data, aliases)
        if value is not None:
            lines.append(f"{label}: {format_value(value)}")
            for alias in aliases:
                if alias in patient_data:
                    used_keys.add(alias)

    remaining = []
    for key, value in patient_data.items():
        if key not in used_keys:
            remaining.append(f"- {key}: {format_value(value)}")

    if not lines and not remaining:
        return "Aucune information patient exploitable."

    if remaining:
        lines.append("\nAutres informations:")
        lines.extend(remaining)

    return "\n".join(lines)


def extract_evaluation_text(data) -> str:
    if isinstance(data, str):
        return data

    if isinstance(data, dict):
        text_keys = [
            "evaluation_text",
            "conclusion",
            "resume",
            "summary",
            "texte",
            "text",
            "analysis",
        ]
        value = get_first_present_value(data, text_keys)
        if value is not None:
            return format_value(value)
        return json.dumps(data, ensure_ascii=False, indent=2)

    return format_value(data)


def load_questions_from_json(path: Path) -> list[dict]:
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

    parsed_questions = []
    for index, item in enumerate(question_items, start=1):
        if isinstance(item, str):
            parsed_questions.append({"id": f"q{index}", "text": item})
            continue
        if isinstance(item, dict) and item.get("text"):
            qid = item.get("id") or f"q{index}"
            parsed_questions.append({"id": str(qid), "text": str(item["text"])})

    return parsed_questions or DEFAULT_QUESTIONS


def normalize_pair_key(raw_value: str) -> str:
    simplified = re.sub(r"[^a-z0-9]+", "", raw_value.lower())
    return simplified or raw_value.lower()


def tokenize_name(value: str) -> list[str]:
    tokens = re.split(r"[^a-z0-9]+", value.lower())
    return [token for token in tokens if token]


def infer_role_from_path(path: Path):
    tokens = tokenize_name(path.stem) + tokenize_name(path.parent.name)
    token_set = set(tokens)
    if "rcp" in token_set:
        return "rcp"
    if "ia" in token_set or "ai" in token_set:
        return "ia"
    if "patient" in token_set or "patients" in token_set or "pat" in token_set:
        return "patient"
    return None


def extract_patient_id_from_payload(payload):
    if not isinstance(payload, dict):
        return None

    simple_id = get_first_present_value(payload, ["patient_id", "id", "identifiant"])
    if simple_id is not None and not isinstance(simple_id, (dict, list)):
        return str(simple_id)

    nested_candidates = ["patient", "patient_data", "data", "metadata"]
    for key in nested_candidates:
        nested = payload.get(key)
        if isinstance(nested, dict):
            nested_id = get_first_present_value(nested, ["patient_id", "id", "identifiant"])
            if nested_id is not None and not isinstance(nested_id, (dict, list)):
                return str(nested_id)

    return None


def derive_key_from_filename(path: Path) -> str:
    tokens = tokenize_name(path.stem)
    filtered = [token for token in tokens if token not in PAIR_KEYWORD_STOPWORDS]
    base = "_".join(filtered) if filtered else path.stem.lower()
    return normalize_pair_key(base)


class ClinicianFeedbackApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Clinical Feedback - Evaluation IA vs RCP")
        self.geometry("1250x850")

        self.patient_path_var = tk.StringVar()
        self.rcp_path_var = tk.StringVar()
        self.ia_path_var = tk.StringVar()
        self.batch_dir_var = tk.StringVar()
        self.batch_progress_var = tk.StringVar(value="Batch: non charge")
        self.status_var = tk.StringVar(value="Pret.")

        default_csv = DEFAULT_RESULTS_DIR / f"evaluations_{datetime.now():%Y%m%d}.csv"
        self.output_csv_var = tk.StringVar(value=str(default_csv))

        self.questions_path = APP_DIR / "questions.json"
        self.questions = load_questions_from_json(self.questions_path)
        self.question_vars: dict[str, tk.IntVar] = {}
        self.current_patient_id = "inconnu"
        self.batch_pairs = []
        self.current_batch_index = None
        self.completed_batch_keys = set()

        self._build_ui()

    def _build_ui(self):
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(container, highlightthickness=0)
        self.v_scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.v_scrollbar.set)

        self.v_scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        content = ttk.Frame(self.canvas, padding=12)
        self.canvas_window_id = self.canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind("<Configure>", self._on_content_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.bind_all("<MouseWheel>", self._on_mousewheel)

        files_frame = ttk.LabelFrame(content, text="1) Charger les JSON", padding=10)
        files_frame.pack(fill="x")

        self._build_path_row(files_frame, 0, "JSON patient", self.patient_path_var)
        self._build_path_row(files_frame, 1, "JSON conclusion RCP", self.rcp_path_var)
        self._build_path_row(files_frame, 2, "JSON conclusion IA", self.ia_path_var)

        ttk.Button(files_frame, text="Charger les donnees", command=self.load_all_data).grid(
            row=3, column=0, pady=(8, 0), sticky="w"
        )
        ttk.Button(files_frame, text="Enregistrer cette evaluation", command=self.save_evaluation).grid(
            row=3, column=2, pady=(8, 0), sticky="e"
        )

        ttk.Separator(files_frame, orient="horizontal").grid(
            row=4, column=0, columnspan=3, sticky="ew", pady=8
        )

        self._build_dir_row(files_frame, 5, "Dossier batch", self.batch_dir_var)
        ttk.Button(files_frame, text="Charger le batch", command=self.load_batch_from_directory).grid(
            row=6, column=0, pady=(8, 0), sticky="w"
        )
        ttk.Button(files_frame, text="Patient precedent", command=self.go_to_previous_batch_item).grid(
            row=6, column=1, pady=(8, 0), sticky="w"
        )
        ttk.Button(files_frame, text="Patient suivant", command=self.go_to_next_batch_item).grid(
            row=6, column=2, pady=(8, 0), sticky="e"
        )
        ttk.Label(files_frame, textvariable=self.batch_progress_var).grid(
            row=7, column=0, columnspan=3, sticky="w", pady=(8, 0)
        )

        views_frame = ttk.LabelFrame(content, text="2) Lecture des informations (plain text)", padding=10)
        views_frame.pack(fill="both", expand=True, pady=(10, 0))
        views_frame.columnconfigure((0, 1, 2), weight=1, uniform="views")
        views_frame.rowconfigure(1, weight=1)

        ttk.Label(views_frame, text="Patient").grid(row=0, column=0, sticky="w")
        ttk.Label(views_frame, text="Evaluation RCP").grid(row=0, column=1, sticky="w")
        ttk.Label(views_frame, text="Evaluation IA").grid(row=0, column=2, sticky="w")

        self.patient_text = scrolledtext.ScrolledText(views_frame, wrap="word", height=14)
        self.rcp_text = scrolledtext.ScrolledText(views_frame, wrap="word", height=14)
        self.ia_text = scrolledtext.ScrolledText(views_frame, wrap="word", height=14)

        self.patient_text.grid(row=1, column=0, padx=(0, 8), sticky="nsew")
        self.rcp_text.grid(row=1, column=1, padx=4, sticky="nsew")
        self.ia_text.grid(row=1, column=2, padx=(8, 0), sticky="nsew")

        questionnaire_frame = ttk.LabelFrame(content, text="3) Questionnaire (notes de 1 a 5)", padding=10)
        questionnaire_frame.pack(fill="x", pady=(10, 0))

        for row_index, question in enumerate(self.questions):
            ttk.Label(
                questionnaire_frame,
                text=f"{row_index + 1}. {question['text']}",
                wraplength=760,
                justify="left",
            ).grid(row=row_index, column=0, sticky="w", pady=5)

            var = tk.IntVar(value=0)
            self.question_vars[question["id"]] = var
            grade_frame = ttk.Frame(questionnaire_frame)
            grade_frame.grid(row=row_index, column=1, sticky="w", padx=(8, 0))
            for score in range(1, 6):
                ttk.Radiobutton(grade_frame, text=str(score), value=score, variable=var).pack(
                    side="left", padx=4
                )

        comment_frame = ttk.LabelFrame(content, text="Commentaire libre (optionnel)", padding=10)
        comment_frame.pack(fill="both", expand=False, pady=(10, 0))
        self.comment_text = scrolledtext.ScrolledText(comment_frame, wrap="word", height=4)
        self.comment_text.configure(state="normal")
        self.comment_text.pack(fill="both", expand=True)

        output_frame = ttk.LabelFrame(content, text="4) Export CSV", padding=10)
        output_frame.pack(fill="x", pady=(10, 0))
        output_frame.columnconfigure(1, weight=1)

        ttk.Label(output_frame, text="Fichier CSV de sortie").grid(row=0, column=0, sticky="w")
        ttk.Entry(output_frame, textvariable=self.output_csv_var).grid(
            row=0, column=1, sticky="ew", padx=8
        )
        ttk.Button(output_frame, text="Choisir...", command=self.pick_output_csv).grid(
            row=0, column=2, sticky="e"
        )
        ttk.Button(output_frame, text="Enregistrer cette evaluation", command=self.save_evaluation).grid(
            row=1, column=0, pady=(10, 0), sticky="w"
        )

        status_frame = ttk.Frame(content, padding=(0, 8, 0, 0))
        status_frame.pack(fill="x")
        ttk.Label(status_frame, textvariable=self.status_var).pack(anchor="w")

    def _on_content_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self.canvas_window_id, width=event.width)

    def _on_mousewheel(self, event):
        if self.canvas.winfo_exists():
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _build_path_row(self, parent, row, label, var):
        parent.columnconfigure(1, weight=1)
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", padx=8, pady=4)
        ttk.Button(parent, text="Parcourir...", command=lambda v=var: self.pick_json_file(v)).grid(
            row=row, column=2, pady=4
        )

    def _build_dir_row(self, parent, row, label, var):
        parent.columnconfigure(1, weight=1)
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", padx=8, pady=4)
        ttk.Button(
            parent,
            text="Parcourir...",
            command=lambda v=var: self.pick_directory(v),
        ).grid(row=row, column=2, pady=4)

    def pick_json_file(self, var: tk.StringVar):
        selected = filedialog.askopenfilename(
            title="Choisir un fichier JSON",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if selected:
            var.set(selected)

    def pick_output_csv(self):
        selected = filedialog.asksaveasfilename(
            title="Choisir le fichier CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=Path(self.output_csv_var.get()).name if self.output_csv_var.get() else None,
        )
        if selected:
            self.output_csv_var.set(selected)

    def pick_directory(self, var: tk.StringVar):
        selected = filedialog.askdirectory(title="Choisir un dossier")
        if selected:
            var.set(selected)

    def load_json_file(self, path_str: str, label: str):
        path = Path(path_str)
        if not path_str.strip():
            raise ValueError(f"Le chemin du fichier {label} est vide.")
        if not path.exists():
            raise FileNotFoundError(f"Le fichier {label} est introuvable: {path}")

        with path.open("r", encoding="utf-8-sig") as file:
            return json.load(file)

    def normalize_patient_payload(self, payload):
        if isinstance(payload, dict):
            nested = get_first_present_value(payload, ["patient", "patient_data", "data"])
            if isinstance(nested, dict):
                return nested
        return payload

    def normalize_evaluation_payload(self, payload):
        if isinstance(payload, dict):
            nested = get_first_present_value(
                payload, ["evaluation", "evaluation_data", "result", "conclusion_data", "data"]
            )
            if nested is not None:
                return nested
        return payload

    def set_status(self, message: str):
        self.status_var.set(message)

    def reset_questionnaire(self):
        self.comment_text.configure(state="normal")
        for var in self.question_vars.values():
            var.set(0)
        self.comment_text.delete("1.0", tk.END)

    def get_current_batch_key(self) -> str:
        if self.current_batch_index is None or not self.batch_pairs:
            return ""
        if self.current_batch_index < 0 or self.current_batch_index >= len(self.batch_pairs):
            return ""
        return self.batch_pairs[self.current_batch_index]["key"]

    def update_batch_progress(self):
        if not self.batch_pairs:
            self.batch_progress_var.set("Batch: non charge")
            return

        total = len(self.batch_pairs)
        current_position = 0
        current_key = "-"
        if self.current_batch_index is not None and 0 <= self.current_batch_index < total:
            current_position = self.current_batch_index + 1
            current_key = self.batch_pairs[self.current_batch_index]["key"]
        done = len(self.completed_batch_keys)
        self.batch_progress_var.set(
            f"Batch: {current_position}/{total} | Patient: {current_key} | Evalues: {done}/{total}"
        )

    def load_from_paths(self, patient_path: str, rcp_path: str, ia_path: str, show_popup: bool):
        try:
            patient_data = self.normalize_patient_payload(self.load_json_file(patient_path, "patient"))
            rcp_data = self.normalize_evaluation_payload(self.load_json_file(rcp_path, "RCP"))
            ia_data = self.normalize_evaluation_payload(self.load_json_file(ia_path, "IA"))
        except Exception as error:
            messagebox.showerror("Erreur de chargement", str(error))
            self.set_status(f"Echec de chargement: {error}")
            return False

        self.current_patient_id = str(
            get_first_present_value(patient_data, ["patient_id", "id", "identifiant"]) or "inconnu"
        )

        self.write_readonly_text(self.patient_text, format_patient_description(patient_data))
        self.write_readonly_text(self.rcp_text, extract_evaluation_text(rcp_data))
        self.write_readonly_text(self.ia_text, extract_evaluation_text(ia_data))
        self.reset_questionnaire()

        if show_popup:
            messagebox.showinfo(
                "Chargement termine",
                f"Donnees chargees pour le patient: {self.current_patient_id}",
            )
        self.set_status(f"Donnees chargees pour le patient: {self.current_patient_id}")
        return True

    def load_all_data(self):
        self.current_batch_index = None
        self.update_batch_progress()
        self.load_from_paths(
            self.patient_path_var.get(),
            self.rcp_path_var.get(),
            self.ia_path_var.get(),
            show_popup=True,
        )

    def load_batch_from_directory(self):
        folder = self.batch_dir_var.get().strip()
        if not folder:
            messagebox.showwarning("Dossier manquant", "Choisissez un dossier batch.")
            return

        root = Path(folder)
        if not root.exists() or not root.is_dir():
            messagebox.showerror("Dossier invalide", f"Le dossier est introuvable: {root}")
            return

        entries = {}
        for json_file in root.rglob("*.json"):
            role = infer_role_from_path(json_file)
            if role is None:
                continue

            try:
                with json_file.open("r", encoding="utf-8-sig") as file:
                    payload = json.load(file)
            except Exception:
                continue

            possible_keys = [derive_key_from_filename(json_file)]
            key_from_json = extract_patient_id_from_payload(payload)
            if key_from_json:
                possible_keys.append(normalize_pair_key(key_from_json))

            for pair_key in dict.fromkeys(possible_keys):
                entry = entries.setdefault(
                    pair_key,
                    {"key": pair_key, "patient": None, "rcp": None, "ia": None},
                )
                if entry[role] is None:
                    entry[role] = str(json_file)

        pairs = []
        seen_triplets = set()
        for entry in entries.values():
            if entry["patient"] and entry["rcp"] and entry["ia"]:
                triplet = (entry["patient"], entry["rcp"], entry["ia"])
                if triplet in seen_triplets:
                    continue
                seen_triplets.add(triplet)
                pairs.append(entry)

        pairs.sort(key=lambda item: item["key"])
        self.batch_pairs = pairs
        self.completed_batch_keys = set()

        if not self.batch_pairs:
            self.current_batch_index = None
            self.update_batch_progress()
            messagebox.showwarning(
                "Aucun trio complet",
                "Aucun patient n'a les 3 JSON requis (patient + RCP + IA) dans ce dossier.",
            )
            self.set_status("Aucun trio JSON complet trouve dans le dossier batch.")
            return

        self.current_batch_index = 0
        self.load_current_batch_item(show_popup=False)
        self.update_batch_progress()
        self.set_status(f"Batch charge: {len(self.batch_pairs)} patients detectes.")
        messagebox.showinfo(
            "Batch charge",
            f"{len(self.batch_pairs)} patients prets a etre evalues.",
        )

    def load_current_batch_item(self, show_popup: bool):
        if self.current_batch_index is None:
            return
        if self.current_batch_index < 0 or self.current_batch_index >= len(self.batch_pairs):
            return

        entry = self.batch_pairs[self.current_batch_index]
        self.patient_path_var.set(entry["patient"])
        self.rcp_path_var.set(entry["rcp"])
        self.ia_path_var.set(entry["ia"])
        success = self.load_from_paths(entry["patient"], entry["rcp"], entry["ia"], show_popup=show_popup)
        if success:
            self.update_batch_progress()

    def go_to_previous_batch_item(self):
        if not self.batch_pairs:
            messagebox.showwarning("Batch non charge", "Chargez d'abord un dossier batch.")
            return
        if self.current_batch_index is None or self.current_batch_index <= 0:
            self.set_status("Vous etes deja sur le premier patient du batch.")
            return
        self.current_batch_index -= 1
        self.load_current_batch_item(show_popup=False)

    def go_to_next_batch_item(self):
        if not self.batch_pairs:
            messagebox.showwarning("Batch non charge", "Chargez d'abord un dossier batch.")
            return
        if self.current_batch_index is None:
            self.current_batch_index = 0
        elif self.current_batch_index >= len(self.batch_pairs) - 1:
            self.set_status("Vous etes deja sur le dernier patient du batch.")
            return
        else:
            self.current_batch_index += 1
        self.load_current_batch_item(show_popup=False)

    def write_readonly_text(self, text_widget: scrolledtext.ScrolledText, value: str):
        text_widget.configure(state="normal")
        text_widget.delete("1.0", tk.END)
        text_widget.insert("1.0", value)
        text_widget.configure(state="disabled")

    def save_evaluation(self):
        if self.patient_text.get("1.0", "end-1c").strip() == "":
            messagebox.showwarning("Attention", "Chargez les donnees JSON avant d'enregistrer.")
            return

        ratings = {}
        for question in self.questions:
            score = self.question_vars[question["id"]].get()
            if score not in (1, 2, 3, 4, 5):
                messagebox.showwarning(
                    "Questionnaire incomplet",
                    "Merci de renseigner toutes les notes de 1 a 5 avant d'enregistrer.",
                )
                return
            ratings[question["id"]] = score

        output_csv_path = Path(self.output_csv_var.get().strip())
        if not output_csv_path.name:
            messagebox.showerror("Chemin invalide", "Veuillez choisir un fichier CSV de sortie.")
            return

        output_csv_path.parent.mkdir(parents=True, exist_ok=True)

        row = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "patient_id": self.current_patient_id,
            "batch_key": self.get_current_batch_key(),
            "patient_json_path": self.patient_path_var.get(),
            "rcp_json_path": self.rcp_path_var.get(),
            "ia_json_path": self.ia_path_var.get(),
            "commentaire": self.comment_text.get("1.0", "end-1c").strip(),
        }
        for question in self.questions:
            row[f"score_{question['id']}"] = ratings[question["id"]]

        try:
            final_path = self.append_row_to_csv(output_csv_path, row)
        except Exception as error:
            messagebox.showerror("Erreur export CSV", str(error))
            return

        self.reset_questionnaire()

        if self.batch_pairs and self.current_batch_index is not None:
            current_key = self.get_current_batch_key()
            if current_key:
                self.completed_batch_keys.add(current_key)
            self.update_batch_progress()

            if self.current_batch_index < len(self.batch_pairs) - 1:
                self.current_batch_index += 1
                self.load_current_batch_item(show_popup=False)
                self.set_status(f"Evaluation enregistree dans {final_path}. Patient suivant charge.")
            else:
                self.set_status(f"Evaluation enregistree dans {final_path}. Batch termine.")
                messagebox.showinfo(
                    "Batch termine",
                    f"Toutes les evaluations du batch sont terminees.\nCSV: {final_path}",
                )
            return

        self.set_status(f"Evaluation enregistree dans {final_path}")
        messagebox.showinfo(
            "Evaluation enregistree",
            f"Les notes ont ete sauvegardees dans:\n{final_path}",
        )

    def append_row_to_csv(self, output_csv_path: Path, row: dict) -> Path:
        target_path = output_csv_path
        expected_columns = list(row.keys())

        if target_path.exists():
            with target_path.open("r", newline="", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                existing_columns = reader.fieldnames or []
            if existing_columns != expected_columns:
                # Evite de casser un CSV existant si les questions ont change.
                timestamp = datetime.now().strftime("%H%M%S")
                target_path = target_path.with_stem(f"{target_path.stem}_{timestamp}")

        file_exists = target_path.exists()
        with target_path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=expected_columns)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)

        return target_path


if __name__ == "__main__":
    app = ClinicianFeedbackApp()
    app.mainloop()
