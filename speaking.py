
import json
import os
import uuid

from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    current_app,
    url_for
)
from flask_login import current_user
from database import SpeakingTopic, SpeakingAttempt, db
from ai_engine import evaluate_speaking

speaking_bp = Blueprint("speaking", __name__)


def load_speaking_data():
    data_folder = os.path.join(
        os.path.dirname(__file__),
        "data",
        "speaking"
    )

    for number in range(1, 7):
        file_path = os.path.join(data_folder, f"unit_{number}.json")

        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)

            save_speaking_topics(data, "unit", number, None)

    for number in range(1, 3):
        file_path = os.path.join(data_folder, f"review_{number}.json")

        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)

            save_speaking_topics(data, "review", None, number)


def save_speaking_topics(data, section_type, unit, review_number):
    topics = data if isinstance(data, list) else data.get("topics", [])

    for item in topics:
        existing = SpeakingTopic.query.filter_by(
            section_type=section_type,
            unit=unit,
            review_number=review_number,
            title=item["title"]
        ).first()

        if existing:
            continue

        topic = SpeakingTopic(
            section_type=section_type,
            unit=unit,
            review_number=review_number,
            title=item["title"],
            topic=item.get("topic"),
            description=item.get("description"),
            prompt=item["prompt"],
            suggested_vocabulary=json.dumps(
                item.get("suggested_vocabulary", []),
                ensure_ascii=False
            ),
            sample_answer=item.get("sample_answer"),
            difficulty=item.get("difficulty", "basic")
        )

        db.session.add(topic)

    db.session.commit()


@speaking_bp.route("/speaking")
def speaking_home():
    units = []

    for number in range(1, 7):
        topics = SpeakingTopic.query.filter_by(
            section_type="unit",
            unit=number
        ).all()

        units.append({
            "number": number,
            "topics": topics
        })

    reviews = []

    for number in range(1, 3):
        topics = SpeakingTopic.query.filter_by(
            section_type="review",
            review_number=number
        ).all()

        reviews.append({
            "number": number,
            "topics": topics
        })

    return render_template(
        "speaking/speaking.html",
        units=units,
        reviews=reviews
    )


@speaking_bp.route("/speaking/practice/<int:topic_id>")
def speaking_practice(topic_id):
    topic = SpeakingTopic.query.get_or_404(topic_id)

    suggested_vocabulary = json.loads(
        topic.suggested_vocabulary or "[]"
    )

    return render_template(
        "speaking/speaking_practice.html",
        topic=topic,
        suggested_vocabulary=suggested_vocabulary
    )


@speaking_bp.route("/speaking/result/<int:attempt_id>")
def speaking_result(attempt_id):
    if not current_user.is_authenticated:
        return jsonify({
            "success": False,
            "message": "Bạn cần đăng nhập để xem kết quả."
        }), 401

    attempt = SpeakingAttempt.query.filter_by(
        id=attempt_id,
        user_id=current_user.id
    ).first_or_404()

    return render_template(
        "speaking/speaking_result.html",
        attempt=attempt
    )


@speaking_bp.route("/speaking/progress")
def speaking_progress():
    if not current_user.is_authenticated:
        return jsonify({
            "success": False,
            "message": "Bạn cần đăng nhập để xem tiến độ."
        }), 401

    attempts = SpeakingAttempt.query.join(
        SpeakingTopic,
        SpeakingAttempt.topic_id == SpeakingTopic.id
    ).filter(
        SpeakingAttempt.user_id == current_user.id
    ).order_by(
        SpeakingAttempt.attempted_at.desc()
    ).all()

    total_attempts = len(attempts)

    scored_attempts = [
        attempt for attempt in attempts
        if attempt.overall_score is not None
    ]

    average_score = (
        round(
            sum(attempt.overall_score for attempt in scored_attempts)
            / len(scored_attempts),
            1
        )
        if scored_attempts else 0
    )

    unit_results = []

    for number in range(1, 7):
        unit_attempts = [
            attempt for attempt in attempts
            if attempt.speaking_topic.unit == number
        ]

        unit_scored = [
            attempt for attempt in unit_attempts
            if attempt.overall_score is not None
        ]

        unit_average = (
            round(
                sum(attempt.overall_score for attempt in unit_scored)
                / len(unit_scored),
                1
            )
            if unit_scored else 0
        )

        unit_results.append({
            "unit": number,
            "total": len(unit_attempts),
            "average": unit_average
        })

    return render_template(
        "speaking/speaking_progress.html",
        total_attempts=total_attempts,
        average_score=average_score,
        unit_results=unit_results,
        attempts=attempts
    )


@speaking_bp.route("/speaking/save", methods=["POST"])
def save_speaking_attempt():
    if not current_user.is_authenticated:
        return jsonify({
            "success": False,
            "message": "Bạn cần đăng nhập để lưu bài."
        }), 401

    topic_id = request.form.get("topic_id", type=int)
    transcript = request.form.get("transcript", "").strip()
    audio = request.files.get("audio")

    if not topic_id:
        return jsonify({
            "success": False,
            "message": "Không tìm thấy chủ đề luyện nói."
        }), 400

    topic = SpeakingTopic.query.get(topic_id)

    if not topic:
        return jsonify({
            "success": False,
            "message": "Chủ đề không tồn tại."
        }), 404

    if not transcript and not audio:
        return jsonify({
            "success": False,
            "message": "Chưa có nội dung hoặc bản ghi âm."
        }), 400

    audio_path = None

    try:
        if audio and audio.filename:
            upload_folder = os.path.join(
                current_app.static_folder,
                "uploads",
                "speaking"
            )

            os.makedirs(upload_folder, exist_ok=True)

            filename = f"{uuid.uuid4().hex}.webm"
            file_path = os.path.join(upload_folder, filename)

            audio.save(file_path)
            audio_path = f"uploads/speaking/{filename}"

        attempt = SpeakingAttempt(
            user_id=current_user.id,
            topic_id=topic.id,
            transcript=transcript,
            audio_path=audio_path
        )

        db.session.add(attempt)
        db.session.commit()

        attempt_id = attempt.id

        if transcript:
            evaluation = evaluate_speaking(transcript, topic)

            if evaluation:
                attempt.fluency_score = evaluation["fluency_score"]
                attempt.vocabulary_score = evaluation["vocabulary_score"]
                attempt.grammar_score = evaluation["grammar_score"]
                attempt.overall_score = evaluation["overall_score"]
                attempt.ai_feedback = evaluation["feedback"]

                db.session.commit()

                return jsonify({
                    "success": True,
                    "evaluated": True,
                    "message": "Đã lưu và chấm điểm bài Speaking thành công.",
                    "attempt_id": attempt_id,
                    "redirect_url": url_for(
                        "speaking.speaking_result",
                        attempt_id=attempt_id
                    ),
                    "scores": {
                        "fluency": attempt.fluency_score,
                        "vocabulary": attempt.vocabulary_score,
                        "grammar": attempt.grammar_score,
                        "overall": attempt.overall_score
                    },
                    "feedback": attempt.ai_feedback
                })

        return jsonify({
            "success": True,
            "evaluated": False,
            "message": (
                "Đã lưu bài luyện nói. Chưa thể chấm điểm vì chưa có transcript."
                if not transcript
                else "Đã lưu bài nhưng AI chưa trả về kết quả chấm điểm."
            ),
            "attempt_id": attempt_id
        })

    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Không thể lưu hoặc chấm bài Speaking"
        )

        return jsonify({
            "success": False,
            "message": "Có lỗi xảy ra khi lưu bài Speaking."
        }), 500
