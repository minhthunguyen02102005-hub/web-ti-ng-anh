
import json
from pathlib import Path

from app import app
from database import db, VocabularyQuestion

DATA_DIR = Path("data")

def import_vocabulary():
    total_added = 0
    total_skipped = 0

    with app.app_context():
        for unit in range(1, 7):
            file_path = DATA_DIR / f"vocabulary_unit{unit}.json"

            if not file_path.exists():
                print(f"Khong tim thay file: {file_path}")
                continue

            with file_path.open("r", encoding="utf-8") as file:
                data = json.load(file)

            questions = data.get("questions", [])
            added = 0
            skipped = 0

            for item in questions:
                question_text = item.get("question_text", "").strip()
                correct_answer = item.get("correct_answer", "").strip()

                if not question_text or not correct_answer:
                    skipped += 1
                    continue

                existing = VocabularyQuestion.query.filter_by(
                    unit=unit,
                    question_type=item.get("question_type"),
                    question_text=question_text
                ).first()

                if existing:
                    skipped += 1
                    continue

                options = item.get("options", [])

                question = VocabularyQuestion(
                    unit=unit,
                    topic=data.get("unit_title"),
                    word=item.get("word"),
                    question_type=item.get("question_type"),
                    question_text=question_text,
                    option_a=options[0] if len(options) > 0 else None,
                    option_b=options[1] if len(options) > 1 else None,
                    option_c=options[2] if len(options) > 2 else None,
                    option_d=options[3] if len(options) > 3 else None,
                    correct_answer=correct_answer,
                    explanation=item.get("explanation"),
                    difficulty=item.get("difficulty", "basic")
                )

                db.session.add(question)
                added += 1

            db.session.commit()

            total_added += added
            total_skipped += skipped

            print(
                f"Unit {unit}: Them {added} cau, "
                f"bo qua {skipped} cau."
            )

    print("\nHOAN THANH NHAP DU LIEU")
    print(f"Tong so cau da them: {total_added}")
    print(f"Tong so cau bo qua: {total_skipped}")


if __name__ == "__main__":
    import_vocabulary()
