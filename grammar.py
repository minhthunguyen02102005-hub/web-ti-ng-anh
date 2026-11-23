
import json
import re
from pathlib import Path
from functools import wraps

from ai_engine import evaluate_grammar

from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, abort
)
from flask_login import login_required, current_user

from database import (
    db, GrammarQuestion, GrammarAttempt, LearningProfile
)


grammar_bp = Blueprint("grammar", __name__)


def student_required(function):
    @wraps(function)
    @login_required
    def wrapper(*args, **kwargs):
        if current_user.role != "student":
            abort(403)
        return function(*args, **kwargs)
    return wrapper


def normalize(value):
    """Chuan hoa dap an: khong phan biet hoa thuong, gom khoang trang."""
    value = (value or "").strip().casefold()
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_fill_answer(value):
    """
    Chuan hoa dap an dien tu.
    Chap nhan vi du:
    Does / work
    Does/work
    Does work
    """
    value = normalize(value)
    value = re.sub(r"\s*[/,]\s*", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def check_answer(question, user_answer):
    """Kiem tra dap an theo tung dang cau hoi."""

    answer = normalize(user_answer)
    expected = normalize(question.correct_answer)

    if not answer:
        return False

    if question.question_type == "multiple_choice":
        options = {
            "a": question.option_a,
            "b": question.option_b,
            "c": question.option_c,
            "d": question.option_d
        }

        correct_letter = expected.upper().lower()

        if answer == correct_letter:
            return True

        correct_option = options.get(correct_letter)

        if correct_option:
            return answer == normalize(correct_option)

        return False

    if question.question_type == "fill_in":
        return (
            normalize_fill_answer(user_answer)
            == normalize_fill_answer(question.correct_answer)
        )

    if question.question_type == "error_correction":
        correct_answer = question.correct_answer or ""

        separator = "→" if "→" in correct_answer else (
            "->" if "->" in correct_answer else None
        )

        if separator:
            parts = correct_answer.split(separator, 1)

            if len(parts) == 2:
                right_part = parts[1].strip()

                accepted_answers = {
                    normalize(correct_answer),
                    normalize(right_part)
                }

                return answer in accepted_answers

        return answer == expected

    return answer == expected


def load_grammar_data(app):
    """Import cau hoi Grammar tu 6 file JSON."""

    data_folder = Path(__file__).resolve().parent / "data"

    with app.app_context():
        for unit in range(1, 7):
            file_path = data_folder / f"grammar_unit{unit}.json"

            if not file_path.exists():
                print(f"[Grammar] Khong tim thay {file_path.name}")
                continue

            existing = GrammarQuestion.query.filter_by(
                unit=unit
            ).count()

            if existing > 0:
                print(f"[Grammar] Unit {unit} da co {existing} cau.")
                continue

            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    questions = json.load(file)

                for item in questions:
                    question = GrammarQuestion(
                        unit=item["unit"],
                        topic=item["topic"],
                        question_type=item["question_type"],
                        question_text=item["question_text"],
                        option_a=item.get("option_a"),
                        option_b=item.get("option_b"),
                        option_c=item.get("option_c"),
                        option_d=item.get("option_d"),
                        correct_answer=item["correct_answer"],
                        explanation=item.get("explanation"),
                        difficulty=item.get("difficulty", "basic"),
                        error_tag=item.get("error_tag")
                    )

                    db.session.add(question)

                db.session.commit()

                print(
                    f"[Grammar] Da nap {len(questions)} "
                    f"cau cho Unit {unit}."
                )

            except Exception as error:
                db.session.rollback()
                print(f"[Grammar] Loi nap Unit {unit}: {error}")


@grammar_bp.route("/grammar")
@student_required
def grammar_home():
    unit_titles = {
        1: "My New School",
        2: "My House",
        3: "My Friends",
        4: "My Neighbourhood",
        5: "Natural Wonders of Viet Nam",
        6: "Our Tet Holiday"
    }

    units = []

    for unit in range(1, 7):
        total = GrammarQuestion.query.filter_by(unit=unit).count()

        units.append({
            "number": unit,
            "title": unit_titles[unit],
            "total": total
        })

    return render_template("grammar.html", units=units)


@grammar_bp.route("/grammar/practice/<int:unit>", methods=["GET", "POST"])
@student_required
def grammar_practice(unit):
    if unit < 1 or unit > 6:
        abort(404)

    question_types = [
        {"value": "multiple_choice", "label": "Trắc nghiệm"},
        {"value": "fill_in", "label": "Điền từ"},
        {"value": "error_correction", "label": "Tìm và sửa lỗi"}
    ]

    valid_types = [item["value"] for item in question_types]

    question_type = request.args.get("type", "").strip()

    if question_type and question_type not in valid_types:
        abort(404)

    query = GrammarQuestion.query.filter_by(unit=unit)

    if question_type:
        query = query.filter_by(question_type=question_type)

    questions = query.order_by(GrammarQuestion.id).all()

    if request.method == "POST":
        if not questions:
            flash("Unit này chưa có câu hỏi.", "error")
            return redirect(url_for("grammar.grammar_home"))

        results = []
        correct_count = 0

        for question in questions:
            answer = request.form.get(
                f"question_{question.id}", ""
            ).strip()

            is_correct = check_answer(question, answer)

            if is_correct:
                correct_count += 1

            db.session.add(GrammarAttempt(
                user_id=current_user.id,
                question_id=question.id,
                user_answer=answer,
                is_correct=is_correct
            ))

            results.append({
                "question": question,
                "user_answer": answer,
                "is_correct": is_correct
            })

        total = len(questions)
        percentage = round(correct_count / total * 100, 2)

        profile = LearningProfile.query.filter_by(
            user_id=current_user.id
        ).first()

        if not profile:
            profile = LearningProfile(user_id=current_user.id)
            db.session.add(profile)

        db.session.flush()

        all_attempts = GrammarAttempt.query.filter_by(
            user_id=current_user.id
        ).all()

        all_total = len(all_attempts)
        all_correct = sum(
            1 for item in all_attempts if item.is_correct
        )

        profile.grammar_score = (
            round(all_correct / all_total * 100, 2)
            if all_total else percentage
        )

        db.session.commit()

        # Danh gia bai lam hien tai bang AI.
        # Neu AI gap loi, ket qua bai lam van duoc hien thi binh thuong.
        ai_evaluation = None

        try:
            ai_evaluation = evaluate_grammar(
                unit=unit,
                results=results,
                percentage=percentage
            )
        except Exception as error:
            print(f"[Grammar AI] Loi goi ham danh gia: {error}")

        return render_template(
            "grammar_result.html",
            unit=unit,
            results=results,
            correct_count=correct_count,
            total=total,
            percentage=percentage,
            ai_evaluation=ai_evaluation
        )

    return render_template(
        "grammar_practice.html",
        unit=unit,
        questions=questions,
        question_types=question_types,
        selected_type=question_type
    )


@grammar_bp.route("/grammar/progress")
@student_required
def grammar_progress():
    attempts = db.session.query(
        GrammarAttempt,
        GrammarQuestion.unit,
        GrammarQuestion.error_tag
    ).join(
        GrammarQuestion,
        GrammarAttempt.question_id == GrammarQuestion.id
    ).filter(
        GrammarAttempt.user_id == current_user.id
    ).all()

    total_attempts = len(attempts)

    correct_attempts = sum(
        1 for attempt, unit, tag in attempts if attempt.is_correct
    )

    accuracy = (
        round(correct_attempts / total_attempts * 100, 2)
        if total_attempts else 0
    )

    unit_results = []

    for unit in range(1, 7):
        unit_attempts = [
            attempt
            for attempt, question_unit, tag in attempts
            if question_unit == unit
        ]

        unit_total = len(unit_attempts)

        unit_correct = sum(
            1 for attempt in unit_attempts if attempt.is_correct
        )

        unit_results.append({
            "unit": unit,
            "total": unit_total,
            "correct": unit_correct,
            "accuracy": (
                round(unit_correct / unit_total * 100, 2)
                if unit_total else 0
            )
        })

    error_stats = {}

    for attempt, unit, tag in attempts:
        if not tag:
            continue

        if tag not in error_stats:
            error_stats[tag] = {
                "total": 0,
                "incorrect": 0
            }

        error_stats[tag]["total"] += 1

        if not attempt.is_correct:
            error_stats[tag]["incorrect"] += 1

    return render_template(
        "grammar_progress.html",
        total_attempts=total_attempts,
        correct_attempts=correct_attempts,
        accuracy=accuracy,
        unit_results=unit_results,
        error_stats=error_stats
    )
