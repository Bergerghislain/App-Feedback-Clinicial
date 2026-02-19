import csv
import tempfile
import unittest
from pathlib import Path

from core import (
    QUESTION_HEADERS,
    append_feedback_rows,
    load_json_file,
    normalize_evaluations,
    normalize_patients,
    normalize_questions,
)


class AppLogicTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sample_dir = Path(__file__).resolve().parents[1] / "sample_data"

    def test_normalize_patients_from_sample(self) -> None:
        data = load_json_file(str(self.sample_dir / "patients.json"))
        patients = normalize_patients(data)
        self.assertEqual(len(patients), 3)
        self.assertEqual(patients[0].patient_id, "P001")
        self.assertIn("Description clinique", patients[0].plain_text)

    def test_normalize_evaluations_from_sample(self) -> None:
        data = load_json_file(str(self.sample_dir / "ai_evaluations.json"))
        evaluations = normalize_evaluations(data)
        self.assertIn("P002", evaluations)
        self.assertIn("immunothérapie", evaluations["P002"])

    def test_normalize_questions_from_sample(self) -> None:
        data = load_json_file(str(self.sample_dir / "questions.json"))
        questions = normalize_questions(data)
        self.assertEqual(len(questions), 5)
        self.assertEqual(questions[0].question_id, "Q1")

    def test_append_feedback_rows_creates_header_once(self) -> None:
        rows = [
            {
                "timestamp": "2026-02-19T12:00:00",
                "clinicien": "Dr Test",
                "patient_id": "P001",
                "patient_nom": "Mme A.",
                "question_id": "Q1",
                "question_texte": "Question 1",
                "score": 4,
                "commentaire_global": "RAS",
                "conclusion_rcp": "RCP",
                "conclusion_ia": "IA",
            }
        ]
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_csv = Path(tmp_dir) / "feedback.csv"
            append_feedback_rows(str(out_csv), rows)
            append_feedback_rows(str(out_csv), rows)

            with out_csv.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                self.assertEqual(reader.fieldnames, QUESTION_HEADERS)
                data_rows = list(reader)
                self.assertEqual(len(data_rows), 2)
                self.assertEqual(data_rows[1]["clinicien"], "Dr Test")


if __name__ == "__main__":
    unittest.main()
