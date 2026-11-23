
import re
import json
from pathlib import Path
from functools import wraps

from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, abort, current_app
)
from flask_login import login_required, current_user

from database import db, WritingUnit, WritingAttempt
from ai_engine import evaluate_writing

writing_bp = Blueprint("writing", __name__)


def student_required(function):
    @wraps(function)
    @login_required
    def wrapper(*args, **kwargs):
        if current_user.role != "student":
            abort(403)

        return function(*args, **kwargs)

    return wrapper


def count_words(text):
    return len(re.findall(r"\b[\w'-]+\b", text or ""))


def load_writing_data(app):
    data_dir = Path(app.root_path) / "data" / "writing"

    with app.app_context():
        for unit_number in range(1, 7):
            file_path = data_dir / f"unit_{unit_number}.json"

            if not file_path.exists():
                continue

            try:
                with open(file_path, "r", encoding="utf-8-sig") as file:
                    data = json.load(file)
            except (json.JSONDecodeError, OSError) as error:
                print(f"Không đọc được {file_path}: {error}")
                continue

            if not isinstance(data, dict) or not data:
                continue

            unit = WritingUnit.query.filter_by(
                unit=unit_number
            ).first()

            if unit is None:
                unit = WritingUnit(unit=unit_number)
                db.session.add(unit)

            unit.title = data.get("title", f"Unit {unit_number}")
            unit.topic = data.get("topic", "")
            unit.writing_type = data.get("writing_type", "")
            unit.writing_topic = data.get("writing_topic", "")
            unit.grammar_focus = data.get("grammar_focus", "")
            unit.sentence_guide = data.get("sentence_guide", "")
            unit.ordering_exercises = json.dumps(
                data.get("ordering_exercises", []),
                ensure_ascii=False
            )
            unit.completion_exercises = json.dumps(
                data.get("completion_exercises", []),
                ensure_ascii=False
            )
            unit.writing_prompt = data.get("writing_prompt", "")
            unit.outline = data.get("outline", "")
            unit.sample_basic = data.get("sample_basic", "")
            unit.sample_intermediate = data.get("sample_intermediate", "")
            unit.sample_advanced = data.get("sample_advanced", "")
            unit.rubric = json.dumps(
                data.get("rubric", []),
                ensure_ascii=False
            )
            unit.common_errors = data.get("common_errors", "")
            unit.self_editing_checklist = json.dumps(
                data.get("self_editing_checklist", []),
                ensure_ascii=False
            )

        db.session.commit()
        print("Đã hoàn tất nạp dữ liệu Writing.")


def ensure_writing_data():
    existing_units = {
        unit.unit
        for unit in WritingUnit.query.all()
    }

    missing_units = set(range(1, 7)) - existing_units

    if missing_units:
        load_writing_data(current_app._get_current_object())


def get_writing_unit(unit_number):
    unit = WritingUnit.query.filter_by(
        unit=unit_number
    ).first()

    if unit is None:
        load_writing_data(current_app._get_current_object())

        unit = WritingUnit.query.filter_by(
            unit=unit_number
        ).first()

    return unit


def get_writing_units():
    ensure_writing_data()

    units = WritingUnit.query.order_by(
        WritingUnit.unit
    ).all()

    unit_data = []

    for unit in units:
        attempts = WritingAttempt.query.filter_by(
            user_id=current_user.id,
            writing_unit_id=unit.id
        ).order_by(
            WritingAttempt.submitted_at.desc()
        ).all()

        unit_data.append({
            "unit": unit,
            "attempts": attempts,
            "completed": len(attempts) > 0,
            "latest_attempt": attempts[0] if attempts else None
        })

    return unit_data


@writing_bp.route("/writing")
@student_required
def writing_home():
    units = get_writing_units()

    completed_units = sum(
        1 for item in units
        if item["completed"]
    )

    total_attempts = sum(
        len(item["attempts"])
        for item in units
    )

    return render_template(
        "writing/writing.html",
        units=units,
        completed_units=completed_units,
        total_units=6,
        total_attempts=total_attempts
    )


@writing_bp.route("/writing/unit/<int:unit_number>")
@student_required
def writing_unit(unit_number):
    if unit_number < 1 or unit_number > 6:
        abort(404)

    unit = get_writing_unit(unit_number)

    if unit is None:
        flash(
            f"Chưa tìm thấy dữ liệu Writing Unit {unit_number}.",
            "warning"
        )
        return redirect(url_for("writing.writing_home"))

    return redirect(
        url_for(
            "writing.writing_practice",
            unit_number=unit.unit
        )
    )


@writing_bp.route(
    "/writing/practice/<int:unit_number>",
    methods=["GET", "POST"]
)
@student_required
def writing_practice(unit_number):
    if unit_number < 1 or unit_number > 6:
        abort(404)

    unit = get_writing_unit(unit_number)

    if unit is None:
        flash(
            f"Chưa tìm thấy dữ liệu Writing Unit {unit_number}.",
            "warning"
        )
        return redirect(url_for("writing.writing_home"))

    if request.method == "POST":
        user_text = request.form.get(
            "user_text",
            ""
        ).strip()

        if not user_text:
            flash(
                "Bạn hãy nhập bài viết trước khi nộp.",
                "warning"
            )

            return redirect(
                url_for(
                    "writing.writing_practice",
                    unit_number=unit_number
                )
            )

        attempt = WritingAttempt(
            user_id=current_user.id,
            writing_unit_id=unit.id,
            user_text=user_text,
            word_count=count_words(user_text)
        )

        db.session.add(attempt)
        db.session.commit()

        attempt_id = attempt.id

        try:
            evaluation = evaluate_writing(user_text, unit)

            if evaluation:
                attempt.task_score = evaluation["task_score"]
                attempt.organization_score = evaluation["organization_score"]
                attempt.grammar_score = evaluation["grammar_score"]
                attempt.vocabulary_score = evaluation["vocabulary_score"]
                attempt.spelling_score = evaluation["spelling_score"]
                attempt.total_score = evaluation["total_score"]
                attempt.ai_feedback = evaluation["feedback"]

                db.session.commit()

                flash(
                    "Bài viết đã được AI đánh giá thành công!",
                    "success"
                )
            else:
                flash(
                    "Bài viết đã được lưu nhưng AI chưa thể đánh giá. Bạn hãy thử lại sau.",
                    "warning"
                )

        except Exception as error:
            db.session.rollback()
            print("WRITING EVALUATION ERROR:", error)

            flash(
                "Bài viết đã được lưu nhưng xảy ra lỗi khi AI chấm điểm.",
                "warning"
            )

        return redirect(
            url_for(
                "writing.writing_result",
                attempt_id=attempt_id
            )
        )

    return render_template(
        "writing/writing_practice.html",
        unit=unit
    )


@writing_bp.route("/writing/result/<int:attempt_id>")
@student_required
def writing_result(attempt_id):
    attempt = WritingAttempt.query.filter_by(
        id=attempt_id,
        user_id=current_user.id
    ).first_or_404()

    return render_template(
        "writing/writing_result.html",
        attempt=attempt
    )


@writing_bp.route("/writing/progress")
@student_required
def writing_progress():
    ensure_writing_data()

    attempts = WritingAttempt.query.filter_by(
        user_id=current_user.id
    ).order_by(
        WritingAttempt.submitted_at.desc()
    ).all()

    unit_results = []

    for unit_number in range(1, 7):
        unit = WritingUnit.query.filter_by(
            unit=unit_number
        ).first()

        if not unit:
            continue

        unit_attempts = [
            attempt
            for attempt in attempts
            if attempt.writing_unit_id == unit.id
        ]

        unit_results.append({
            "unit": unit,
            "total": len(unit_attempts),
            "latest_attempt": (
                unit_attempts[0]
                if unit_attempts
                else None
            )
        })

    return render_template(
        "writing/writing_progress.html",
        attempts=attempts,
        unit_results=unit_results,
        total_attempts=len(attempts)
    )
