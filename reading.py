
import json
import re
from pathlib import Path
from functools import wraps
from ai_engine import evaluate_reading
from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, abort
)
from flask_login import login_required, current_user

from database import (
    db, ReadingPassage, ReadingQuestion,
    ReadingAttempt, LearningProfile
)


reading_bp = Blueprint("reading", __name__)


def student_required(function):
    @wraps(function)
    @login_required
    def wrapper(*args, **kwargs):
        if current_user.role != "student":
            abort(403)

        return function(*args, **kwargs)

    return wrapper


def normalize(value):
    value = (value or "").strip().casefold()
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def check_answer(question, user_answer):
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

        if answer == expected:
            return True

        correct_option = options.get(expected)

        if correct_option:
            return answer == normalize(correct_option)

        return answer == expected

    if question.question_type in (
        "true_false_not_given",
        "true_false",
        "tfng"
    ):

        answer_aliases = {
            "t": "true",
            "true": "true",
            "f": "false",
            "false": "false",
            "ng": "not given",
            "not given": "not given"
        }

        expected_answer = answer_aliases.get(
            expected,
            expected
        )

        user_answer = answer_aliases.get(
            answer,
            answer
        )

        return user_answer == expected_answer

    return answer == expected


def get_reading_unlock_state(user_id):
    completed_rows = db.session.query(
        ReadingQuestion.passage_id
    ).join(
        ReadingAttempt,
        ReadingAttempt.question_id == ReadingQuestion.id
    ).filter(
        ReadingAttempt.user_id == user_id
    ).distinct().all()

    completed_ids = {
        row[0]
        for row in completed_rows
    }

    unit_passages = {
        number: ReadingPassage.query.filter_by(
            section_type="unit",
            unit=number
        ).first()
        for number in range(1, 7)
    }

    review_passages = {
        number: ReadingPassage.query.filter_by(
            section_type="review",
            review_number=number
        ).first()
        for number in range(1, 3)
    }

    review1 = review_passages[1]

    review1_completed = (
        review1 is not None
        and review1.id in completed_ids
    )

    unit_unlocked = {
        1: True,
        2: True,
        3: True,
        4: review1_completed,
        5: review1_completed,
        6: review1_completed
    }

    review1_unlocked = all(
        unit_passages[number] is not None
        and unit_passages[number].id in completed_ids
        for number in (1, 2, 3)
    )

    review2_unlocked = (
        review1_completed
        and all(
            unit_passages[number] is not None
            and unit_passages[number].id in completed_ids
            for number in (4, 5, 6)
        )
    )

    return {
        "completed_ids": completed_ids,
        "unit_unlocked": unit_unlocked,
        "review_unlocked": {
            1: review1_unlocked,
            2: review2_unlocked
        }
    }


def load_reading_data(app):
    data_folder = (
        Path(__file__).resolve().parent
        / "data"
        / "reading"
    )

    files = [
        (f"unit_{unit}.json", "unit", unit)
        for unit in range(1, 7)
    ]

    files.extend([
        ("review_1.json", "review", 1),
        ("review_2.json", "review", 2)
    ])

    with app.app_context():

        for filename, section_type, number in files:

            file_path = data_folder / filename

            if not file_path.exists():
                print(f"[Reading] Khong tim thay {filename}")
                continue

            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    data = json.load(file)

                if isinstance(data, list):
                    passages = data
                elif isinstance(data, dict):
                    passages = data.get("passages", [data])
                else:
                    print(f"[Reading] Sai dinh dang JSON: {filename}")
                    continue

                if not isinstance(passages, list):
                    print(
                        f"[Reading] Danh sach bai doc khong hop le: "
                        f"{filename}"
                    )
                    continue

                synced_count = 0

                for item in passages:

                    if not isinstance(item, dict):
                        continue

                    title = item.get("title")

                    if not title:
                        continue

                    question_data_list = item.get("questions", [])

                    if not isinstance(question_data_list, list):
                        print(
                            f"[Reading] Danh sach cau hoi khong hop le: "
                            f"{title}"
                        )
                        continue

                    valid_questions = []

                    for question_data in question_data_list:

                        if not isinstance(question_data, dict):
                            continue

                        question_text = question_data.get("question_text")
                        correct_answer = question_data.get("correct_answer")

                        if not question_text or correct_answer is None:
                            continue

                        if not str(correct_answer).strip():
                            continue

                        options = question_data.get("options", {})

                        if isinstance(options, dict):
                            option_a = options.get("A") or options.get("a")
                            option_b = options.get("B") or options.get("b")
                            option_c = options.get("C") or options.get("c")
                            option_d = options.get("D") or options.get("d")

                        elif isinstance(options, list):
                            option_a = options[0] if len(options) > 0 else None
                            option_b = options[1] if len(options) > 1 else None
                            option_c = options[2] if len(options) > 2 else None
                            option_d = options[3] if len(options) > 3 else None

                        else:
                            option_a = None
                            option_b = None
                            option_c = None
                            option_d = None

                        valid_questions.append({
                            "task_type": question_data.get("task_type", "A"),
                            "question_type": question_data.get(
                                "question_type",
                                "multiple_choice"
                            ),
                            "question_text": question_text,
                            "option_a": question_data.get("option_a") or option_a,
                            "option_b": question_data.get("option_b") or option_b,
                            "option_c": question_data.get("option_c") or option_c,
                            "option_d": question_data.get("option_d") or option_d,
                            "correct_answer": correct_answer,
                            "explanation": question_data.get("explanation"),
                            "difficulty": question_data.get("difficulty", "basic")
                        })

                    filters = {
                        "section_type": section_type,
                        "title": title
                    }

                    if section_type == "unit":
                        filters["unit"] = number
                    else:
                        filters["review_number"] = number

                    passage = ReadingPassage.query.filter_by(
                        **filters
                    ).first()

                    if passage is None:
                        passage = ReadingPassage(
                            section_type=section_type,
                            unit=number if section_type == "unit" else None,
                            review_number=number if section_type == "review" else None,
                            title=title,
                            topic=item.get("topic"),
                            description=item.get("description"),
                            content=item.get("content", ""),
                            difficulty=item.get("difficulty", "basic")
                        )

                        db.session.add(passage)
                        db.session.flush()

                    existing_questions = ReadingQuestion.query.filter_by(
                        passage_id=passage.id
                    ).order_by(
                        ReadingQuestion.id
                    ).all()

                    existing_ids = [
                        question.id
                        for question in existing_questions
                    ]

                    has_attempts = False

                    if existing_ids:
                        has_attempts = ReadingAttempt.query.filter(
                            ReadingAttempt.question_id.in_(existing_ids)
                        ).first() is not None

                    if has_attempts:
                        print(
                            f"[Reading] Bo qua '{title}' vi da co "
                            f"lich su lam bai. Khong thay doi cau hoi cu."
                        )
                        continue

                    passage.title = title
                    passage.topic = item.get("topic")
                    passage.description = item.get("description")
                    passage.content = item.get("content", "")
                    passage.difficulty = item.get("difficulty", "basic")

                    for index, question_data in enumerate(valid_questions):

                        if index < len(existing_questions):
                            question = existing_questions[index]
                        else:
                            question = ReadingQuestion(
                                passage_id=passage.id
                            )
                            db.session.add(question)

                        question.task_type = question_data["task_type"]
                        question.question_type = question_data["question_type"]
                        question.question_text = question_data["question_text"]
                        question.option_a = question_data["option_a"]
                        question.option_b = question_data["option_b"]
                        question.option_c = question_data["option_c"]
                        question.option_d = question_data["option_d"]
                        question.correct_answer = question_data["correct_answer"]
                        question.explanation = question_data["explanation"]
                        question.difficulty = question_data["difficulty"]

                    extra_questions = existing_questions[len(valid_questions):]

                    for question in extra_questions:
                        db.session.delete(question)

                    db.session.commit()

                    synced_count += len(valid_questions)

                    print(
                        f"[Reading] {title}: "
                        f"{len(existing_questions)} -> "
                        f"{len(valid_questions)} cau."
                    )

                print(
                    f"[Reading] Da dong bo {synced_count} cau "
                    f"tu {filename}."
                )

            except Exception as error:
                db.session.rollback()
                print(f"[Reading] Loi nap {filename}: {error}")


@reading_bp.route("/reading")
@student_required
def reading_home():

    unit_titles = {
        1: "Hobbies",
        2: "Healthy Living",
        3: "Community Service",
        4: "Music and Arts",
        5: "Food and Drink",
        6: "A Visit to a School"
    }

    unlock_state = get_reading_unlock_state(
        current_user.id
    )

    units = []

    for unit in range(1, 7):

        passage = ReadingPassage.query.filter_by(
            section_type="unit",
            unit=unit
        ).first()

        completed = (
            passage is not None
            and passage.id in unlock_state["completed_ids"]
        )

        units.append({
            "number": unit,
            "title": unit_titles[unit],
            "total": len(passage.questions) if passage else 0,
            "passage_id": passage.id if passage else None,
            "locked": not unlock_state["unit_unlocked"][unit],
            "completed": completed
        })

    reviews = []

    for number in range(1, 3):

        passage = ReadingPassage.query.filter_by(
            section_type="review",
            review_number=number
        ).first()

        completed = (
            passage is not None
            and passage.id in unlock_state["completed_ids"]
        )

        reviews.append({
            "number": number,
            "title": f"Review {number}",
            "total": len(passage.questions) if passage else 0,
            "passage_id": passage.id if passage else None,
            "locked": not unlock_state["review_unlocked"][number],
            "completed": completed
        })

    return render_template(
        "reading.html",
        units=units,
        reviews=reviews
    )


@reading_bp.route(
    "/reading/practice/<int:passage_id>",
    methods=["GET", "POST"]
)
@student_required
def reading_practice(passage_id):

    passage = ReadingPassage.query.get_or_404(
        passage_id
    )

    unlock_state = get_reading_unlock_state(
        current_user.id
    )

    if passage.section_type == "unit":
        unlocked = unlock_state["unit_unlocked"].get(
            passage.unit,
            False
        )
    else:
        unlocked = unlock_state["review_unlocked"].get(
            passage.review_number,
            False
        )

    if not unlocked:
        flash(
            "Bạn cần hoàn thành các bài học trước để mở khóa bài này.",
            "warning"
        )

        return redirect(
            url_for("reading.reading_home")
        )

    questions = ReadingQuestion.query.filter_by(
        passage_id=passage.id
    ).order_by(
        ReadingQuestion.id
    ).all()

    if request.method == "POST":

        if not questions:
            flash(
                "Bai doc nay chua co cau hoi.",
                "error"
            )

            return redirect(
                url_for("reading.reading_home")
            )

        results = []
        correct_count = 0

        for question in questions:

            answer = request.form.get(
                f"question_{question.id}",
                ""
            ).strip()

            is_correct = check_answer(
                question,
                answer
            )

            if is_correct:
                correct_count += 1

            db.session.add(
                ReadingAttempt(
                    user_id=current_user.id,
                    question_id=question.id,
                    user_answer=answer,
                    is_correct=is_correct
                )
            )

            results.append({
                "question": question,
                "user_answer": answer,
                "is_correct": is_correct
            })

        total = len(questions)

        percentage = round(
            correct_count / total * 100,
            2
        )

        profile = LearningProfile.query.filter_by(
            user_id=current_user.id
        ).first()

        if not profile:
            profile = LearningProfile(
                user_id=current_user.id
            )

            db.session.add(profile)

        db.session.flush()

        all_attempts = ReadingAttempt.query.filter_by(
            user_id=current_user.id
        ).all()

        all_total = len(all_attempts)

        all_correct = sum(
            1
            for item in all_attempts
            if item.is_correct
        )

        profile.reading_score = (
            round(
                all_correct / all_total * 100,
                2
            )
            if all_total
            else percentage
        )

        db.session.commit()

        ai_evaluation = evaluate_reading(
            passage,
            results,
            percentage
        )

        return render_template(
            "reading_result.html",
            passage=passage,
            results=results,
            correct_count=correct_count,
            total=total,
            percentage=percentage,
            ai_evaluation=ai_evaluation
        )

    return render_template(
        "reading_practice.html",
        passage=passage,
        questions=questions
    )


@reading_bp.route("/reading/progress")
@student_required
def reading_progress():

    attempts = db.session.query(
        ReadingAttempt,
        ReadingQuestion.passage_id
    ).join(
        ReadingQuestion,
        ReadingAttempt.question_id == ReadingQuestion.id
    ).filter(
        ReadingAttempt.user_id == current_user.id
    ).all()

    total_attempts = len(attempts)

    correct_attempts = sum(
        1
        for attempt, passage_id in attempts
        if attempt.is_correct
    )

    accuracy = (
        round(
            correct_attempts / total_attempts * 100,
            2
        )
        if total_attempts
        else 0
    )

    passage_results = []

    passages = ReadingPassage.query.all()

    passages.sort(
        key=lambda passage: (
            0 if passage.section_type == "unit" else 1,
            passage.unit
            if passage.unit is not None
            else passage.review_number
        )
    )

    for passage in passages:

        passage_attempts = [
            attempt
            for attempt, passage_id in attempts
            if passage_id == passage.id
        ]

        passage_total = len(passage_attempts)

        passage_correct = sum(
            1
            for attempt in passage_attempts
            if attempt.is_correct
        )

        passage_results.append({
            "passage": passage,
            "total": passage_total,
            "correct": passage_correct,
            "accuracy": (
                round(
                    passage_correct / passage_total * 100,
                    2
                )
                if passage_total
                else 0
            )
        })

    return render_template(
        "reading_progress.html",
        total_attempts=total_attempts,
        correct_attempts=correct_attempts,
        accuracy=accuracy,
        passage_results=passage_results
    )
