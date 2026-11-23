
import os
import json
import random

from functools import wraps
from datetime import datetime
from uuid import uuid4

from werkzeug.utils import secure_filename
from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, abort, session,
    send_from_directory, jsonify
)
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, current_user
)

from config import Config
from database import (
    db, init_db, User, LearningProfile,
    Question, TestResult, Lesson,
    LearningProgress, LearningMaterial,
    ChatSession, AIConversation,
    VocabularyQuestion, VocabularyAttempt,
    GrammarQuestion, GrammarAttempt,
    ReadingPassage, ReadingQuestion, ReadingAttempt,
    SpeakingTopic, SpeakingAttempt,
    WritingUnit, WritingAttempt
)
from grammar import grammar_bp, load_grammar_data
from reading import reading_bp, load_reading_data
from speaking import speaking_bp, load_speaking_data
from writing import writing_bp, load_writing_data

from ai_engine import (
    ask_ai,
    evaluate_vocabulary,
    evaluate_placement
)


app = Flask(__name__)
app.config.from_object(Config)

app.register_blueprint(grammar_bp)
app.register_blueprint(reading_bp)
app.register_blueprint(writing_bp)
app.register_blueprint(speaking_bp)

os.makedirs("instance", exist_ok=True)
os.makedirs("uploads", exist_ok=True)
os.makedirs(os.path.join(app.root_path, "data"), exist_ok=True)

MATERIAL_UPLOAD_FOLDER = os.path.join(
    app.root_path,
    "uploads",
    "learning_materials"
)
AVATAR_UPLOAD_FOLDER = os.path.join(
    app.root_path,
    "static",
    "uploads",
    "avatars"
)

ALLOWED_AVATAR_EXTENSIONS = {
    "png", "jpg", "jpeg", "webp"
}

os.makedirs(AVATAR_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(MATERIAL_UPLOAD_FOLDER, exist_ok=True)

app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

ALLOWED_MATERIAL_EXTENSIONS = {
    "pdf", "doc", "docx",
    "ppt", "pptx", "txt",
    "png", "jpg", "jpeg", "webp",
    "mp3", "wav", "m4a"
}

MATERIAL_SKILLS = [
    "vocabulary",
    "grammar",
    "reading",
    "listening",
    "speaking",
    "writing"
]

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Vui lòng đăng nhập để tiếp tục."


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def role_required(*roles):
    def decorator(function):
        @wraps(function)
        @login_required
        def wrapper(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)

            return function(*args, **kwargs)

        return wrapper

    return decorator


def save_material_file(uploaded_file):
    if not uploaded_file or not uploaded_file.filename:
        return None

    original_filename = secure_filename(
        uploaded_file.filename
    )

    if not original_filename or "." not in original_filename:
        return None

    extension = original_filename.rsplit(".", 1)[1].lower()

    if extension not in ALLOWED_MATERIAL_EXTENSIONS:
        return None

    stored_filename = f"{uuid4().hex}.{extension}"

    file_path = os.path.join(
        MATERIAL_UPLOAD_FOLDER,
        stored_filename
    )

    uploaded_file.save(file_path)

    file_size = os.path.getsize(file_path)

    return {
        "file_path": stored_filename,
        "original_filename": original_filename,
        "material_type": extension,
        "file_size": file_size
    }


def delete_material_file(filename):
    if not filename:
        return

    safe_filename = os.path.basename(filename)

    file_path = os.path.join(
        MATERIAL_UPLOAD_FOLDER,
        safe_filename
    )

    if os.path.isfile(file_path):
        os.remove(file_path)


def load_placement_questions():

    file_path = os.path.join(
        app.root_path,
        "data",
        "placement_questions.json"
    )

    if not os.path.exists(file_path):
        print(
            f"[Placement] Không tìm thấy file: {file_path}"
        )
        return

    try:
        with open(file_path, "r", encoding="utf-8-sig") as file:
            questions_data = json.load(file)

        if not isinstance(questions_data, list):
            print(
                "[Placement] Dữ liệu JSON phải là một danh sách câu hỏi."
            )
            return

        added = 0
        skipped = 0

        required_fields = [
            "content",
            "option_a",
            "option_b",
            "option_c",
            "option_d",
            "correct_answer",
            "skill",
            "difficulty"
        ]

        for item in questions_data:

            if not isinstance(item, dict):
                skipped += 1
                continue

            if not all(
                field in item and item[field] is not None
                for field in required_fields
            ):
                print(
                    "[Placement] Câu hỏi thiếu dữ liệu:",
                    item
                )
                skipped += 1
                continue

            content = str(item["content"]).strip()

            if not content:
                skipped += 1
                continue

            existing = Question.query.filter(
                db.func.lower(Question.content) == content.lower()
            ).first()

            if existing:
                skipped += 1
                continue

            options = [
                str(item["option_a"]).strip(),
                str(item["option_b"]).strip(),
                str(item["option_c"]).strip(),
                str(item["option_d"]).strip()
            ]

            if any(not option for option in options):
                skipped += 1
                continue

            correct_answer = str(
                item["correct_answer"]
            ).strip().upper()

            if correct_answer not in ["A", "B", "C", "D"]:
                skipped += 1
                continue

            skill = str(item["skill"]).strip().lower()
            difficulty = str(item["difficulty"]).strip().lower()

            if not skill or not difficulty:
                skipped += 1
                continue

            question = Question(
                content=content,
                option_a=options[0],
                option_b=options[1],
                option_c=options[2],
                option_d=options[3],
                correct_answer=correct_answer,
                skill=skill,
                difficulty=difficulty
            )

            db.session.add(question)
            added += 1

        db.session.commit()

        print(f"[Placement] Đã thêm: {added} câu.")
        print(f"[Placement] Đã bỏ qua: {skipped} câu.")
        print(
            f"[Placement] Tổng ngân hàng: {Question.query.count()} câu."
        )

    except (json.JSONDecodeError, OSError) as error:

        db.session.rollback()

        print(
            "[Placement] Không đọc được file JSON:",
            error
        )

    except Exception as error:

        db.session.rollback()

        print(
            "[Placement] Lỗi khi nạp ngân hàng câu hỏi:",
            error
        )


def seed_data():
    with app.app_context():

        accounts = [
            {
                "full_name": "Quản trị viên",
                "username": "admin",
                "email": "admin@example.com",
                "password": "Admin123!",
                "role": "admin"
            },
            {
                "full_name": "Giáo viên tiếng Anh",
                "username": "teacher",
                "email": "teacher@example.com",
                "password": "Teacher123!",
                "role": "teacher"
            },
            {
                "full_name": "Học sinh lớp 7",
                "username": "student",
                "email": "student@example.com",
                "password": "Student123!",
                "role": "student"
            }
        ]

        for account in accounts:

            user = User.query.filter_by(
                username=account["username"]
            ).first()

            if not user:

                user = User(
                    full_name=account["full_name"],
                    username=account["username"],
                    email=account["email"],
                    role=account["role"]
                )

                user.set_password(account["password"])

                db.session.add(user)
                db.session.flush()

                if user.role == "student":

                    profile = LearningProfile(
                        user_id=user.id
                    )

                    db.session.add(profile)

        if Lesson.query.count() == 0:

            lessons = [
                {
                    "title": "My Hobbies",
                    "unit": "Unit 1",
                    "description": "Học từ vựng và cách nói về sở thích.",
                    "content": "Learn vocabulary about hobbies and free-time activities.",
                    "skill": "vocabulary",
                    "difficulty": "easy"
                },
                {
                    "title": "Healthy Living",
                    "unit": "Unit 2",
                    "description": "Tìm hiểu từ vựng về lối sống lành mạnh.",
                    "content": "Learn vocabulary about healthy habits, food and exercise.",
                    "skill": "vocabulary",
                    "difficulty": "easy"
                },
                {
                    "title": "Present Simple",
                    "unit": "Grammar",
                    "description": "Ôn tập thì hiện tại đơn.",
                    "content": "Learn how to use the present simple tense.",
                    "skill": "grammar",
                    "difficulty": "easy"
                }
            ]

            for lesson in lessons:
                db.session.add(Lesson(**lesson))

        db.session.commit()

        load_placement_questions()


@app.route("/")
def index():

    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():

    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        full_name = request.form.get(
            "full_name", ""
        ).strip()

        username = request.form.get(
            "username", ""
        ).strip()

        email = request.form.get(
            "email", ""
        ).strip().lower()

        password = request.form.get(
            "password", ""
        )

        confirm_password = request.form.get(
            "confirm_password", ""
        )

        if not all([full_name, username, password]):

            flash(
                "Vui lòng điền đầy đủ thông tin.",
                "error"
            )

            return redirect(url_for("register"))

        if password != confirm_password:

            flash(
                "Mật khẩu xác nhận không khớp.",
                "error"
            )

            return redirect(url_for("register"))

        if len(password) < 8:

            flash(
                "Mật khẩu phải có ít nhất 8 ký tự.",
                "error"
            )

            return redirect(url_for("register"))

        if User.query.filter_by(
            username=username
        ).first():

            flash(
                "Tên đăng nhập đã tồn tại.",
                "error"
            )

            return redirect(url_for("register"))

        if email and User.query.filter_by(
            email=email
        ).first():

            flash(
                "Email đã được sử dụng.",
                "error"
            )

            return redirect(url_for("register"))

        user = User(
            full_name=full_name,
            username=username,
            email=email or None,
            role="student"
        )

        user.set_password(password)

        db.session.add(user)
        db.session.flush()

        db.session.add(
            LearningProfile(user_id=user.id)
        )

        db.session.commit()

        flash(
            "Đăng ký thành công! Hãy đăng nhập.",
            "success"
        )

        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        username = request.form.get(
            "username", ""
        ).strip()

        password = request.form.get(
            "password", ""
        )

        user = User.query.filter_by(
            username=username
        ).first()

        if user and user.check_password(password):

            login_user(user)

            flash(
                "Đăng nhập thành công!",
                "success"
            )

            return redirect(url_for("dashboard"))

        flash(
            "Tên đăng nhập hoặc mật khẩu không chính xác.",
            "error"
        )

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():

    logout_user()

    flash(
        "Bạn đã đăng xuất.",
        "success"
    )

    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():

    if current_user.role == "admin":
        return redirect(url_for("admin_dashboard"))

    if current_user.role == "teacher":
        return redirect(url_for("teacher_dashboard"))

    profile = LearningProfile.query.filter_by(
        user_id=current_user.id
    ).first()

    latest_result = TestResult.query.filter_by(
        user_id=current_user.id
    ).order_by(
        TestResult.completed_at.desc()
    ).first()

    completed_lessons = LearningProgress.query.filter_by(
        user_id=current_user.id,
        status="completed"
    ).count()

    total_lessons = Lesson.query.count()

    return render_template(
        "dashboard.html",
        profile=profile,
        latest_result=latest_result,
        completed_lessons=completed_lessons,
        total_lessons=total_lessons
    )


@app.route("/placement-test", methods=["GET", "POST"])
@role_required("student")
def placement_test():

    PLACEMENT_QUESTION_COUNT = 40

    if request.method == "POST":

        question_data = session.get(
            "placement_question_data"
        )

        if not question_data:

            flash(
                "Phiên kiểm tra đã hết hạn. Vui lòng bắt đầu lại.",
                "error"
            )

            return redirect(url_for("placement_test"))

        question_ids = [
            int(item["id"])
            for item in question_data
        ]

        question_map = {
            question.id: question
            for question in Question.query.filter(
                Question.id.in_(question_ids)
            ).all()
        }

        questions = [
            question_map[int(item["id"])]
            for item in question_data
            if int(item["id"]) in question_map
        ]

        if not questions:

            session.pop(
                "placement_question_data",
                None
            )

            flash(
                "Không tìm thấy câu hỏi kiểm tra.",
                "error"
            )

            return redirect(url_for("placement_test"))

        score = 0
        skill_scores = {}

        for question in questions:

            answer = request.form.get(
                f"question_{question.id}", ""
            ).strip().upper()

            saved_item = next(
                (
                    item for item in question_data
                    if int(item["id"]) == question.id
                ),
                None
            )

            correct_displayed_answer = (
                saved_item.get(
                    "correct_displayed_answer",
                    ""
                )
                if saved_item else ""
            )

            skill = (
                question.skill or "general"
            ).lower()

            if skill not in skill_scores:

                skill_scores[skill] = {
                    "correct": 0,
                    "total": 0
                }

            skill_scores[skill]["total"] += 1

            if (
                answer
                and answer == correct_displayed_answer
            ):

                score += 1
                skill_scores[skill]["correct"] += 1

        total_questions = len(questions)

        percentage = round(
            score / total_questions * 100,
            2
        )

        if percentage < 40:
            level = "Cơ bản"

        elif percentage < 70:
            level = "Trung bình"

        else:
            level = "Khá"

        result = TestResult(
            user_id=current_user.id,
            score=percentage,
            total_questions=total_questions,
            level=level
        )

        db.session.add(result)

        profile = LearningProfile.query.filter_by(
            user_id=current_user.id
        ).first()

        if not profile:

            profile = LearningProfile(
                user_id=current_user.id
            )

            db.session.add(profile)

        profile.current_level = level

        for skill, values in skill_scores.items():

            if values["total"] <= 0:
                continue

            skill_score = round(
                values["correct"] / values["total"] * 100,
                2
            )

            if skill == "vocabulary":
                profile.vocabulary_score = skill_score

            elif skill == "grammar":
                profile.grammar_score = skill_score

            elif skill == "reading":
                profile.reading_score = skill_score

            elif skill == "listening":
                profile.listening_score = skill_score

            elif skill == "speaking":
                profile.speaking_score = skill_score

            elif skill == "writing":
                profile.writing_score = skill_score

        db.session.commit()

        ai_evaluation = None

        try:

            ai_evaluation = evaluate_placement(
                skill_scores=skill_scores,
                percentage=percentage,
                level=level,
                total_questions=total_questions
            )

        except Exception as error:

            print(
                "[Placement AI] Lỗi gọi AI:",
                error
            )

        if ai_evaluation:

            try:

                result.ai_analysis = json.dumps(
                    ai_evaluation,
                    ensure_ascii=False
                )

                profile.strengths = "\n".join(
                    ai_evaluation.get("strengths", [])
                )

                profile.weaknesses = "\n".join(
                    ai_evaluation.get("weaknesses", [])
                )

                db.session.commit()

            except Exception as error:

                db.session.rollback()

                print(
                    "[Placement AI] Lỗi lưu kết quả AI:",
                    error
                )

        session.pop(
            "placement_question_data",
            None
        )

        flash(
            f"Bạn hoàn thành bài kiểm tra với kết quả {percentage}%.",
            "success"
        )

        return redirect(
            url_for(
                "placement_result",
                result_id=result.id
            )
        )

    all_questions = Question.query.all()

    if len(all_questions) < PLACEMENT_QUESTION_COUNT:

        flash(
            f"Ngân hàng hiện có {len(all_questions)} câu. "
            f"Cần tối thiểu {PLACEMENT_QUESTION_COUNT} câu để bắt đầu.",
            "error"
        )

        return redirect(url_for("dashboard"))

    skills = ["vocabulary", "grammar", "reading", "application"]

    selected_questions = []

    for skill in skills:
        skill_questions = Question.query.filter_by(skill=skill).all()

        if len(skill_questions) < 10:
            flash(
                f"Ngân hàng câu hỏi {skill} chưa đủ 10 câu.",
                "danger"
            )
            return redirect(url_for("dashboard"))

        selected_questions.extend(random.sample(skill_questions, 10))

    random.shuffle(selected_questions)

    question_data = []
    question_options = {}

    for question in selected_questions:

        options = [
            {
                "text": question.option_a,
                "original": "A"
            },
            {
                "text": question.option_b,
                "original": "B"
            },
            {
                "text": question.option_c,
                "original": "C"
            },
            {
                "text": question.option_d,
                "original": "D"
            }
        ]

        options = [
            option for option in options
            if (
                option["text"] is not None
                and str(option["text"]).strip()
            )
        ]

        random.shuffle(options)

        displayed_options = []
        correct_displayed_answer = ""

        original_correct_answer = (
            question.correct_answer or ""
        ).strip().upper()

        for index, option in enumerate(options):

            displayed_letter = chr(65 + index)

            displayed_options.append({
                "letter": displayed_letter,
                "text": option["text"]
            })

            if option["original"] == original_correct_answer:
                correct_displayed_answer = displayed_letter

        question_options[question.id] = displayed_options

        question_data.append({
            "id": question.id,
            "correct_displayed_answer": correct_displayed_answer
        })

    session["placement_question_data"] = question_data

    return render_template(
        "placement_test.html",
        questions=selected_questions,
        question_options=question_options
    )


@app.route("/placement-result/<int:result_id>")
@role_required("student")
def placement_result(result_id):

    result = TestResult.query.filter_by(
        id=result_id,
        user_id=current_user.id
    ).first_or_404()

    ai_evaluation = None

    if result.ai_analysis:

        try:

            ai_evaluation = json.loads(
                result.ai_analysis
            )

        except (ValueError, TypeError):

            ai_evaluation = None

    return render_template(
        "placement_result.html",
        result=result,
        ai_evaluation=ai_evaluation
    )


@app.route("/vocabulary")
@role_required("student")
def vocabulary():

    units = []

    for unit in range(1, 7):

        total_questions = VocabularyQuestion.query.filter_by(
            unit=unit
        ).count()

        units.append({
            "number": unit,
            "title": f"Unit {unit}",
            "total": total_questions
        })

    return render_template(
        "vocabulary.html",
        units=units
    )


@app.route("/vocabulary/practice/<int:unit>", methods=["GET", "POST"])
@role_required("student")
def vocabulary_practice(unit):

    if unit < 1 or unit > 6:
        abort(404)

    question_type = request.args.get(
        "type", ""
    ).strip()

    question_types = [
        {
            "value": "matching",
            "label": "Nối từ với nghĩa"
        },
        {
            "value": "fill_blank",
            "label": "Điền từ vào chỗ trống"
        },
        {
            "value": "multiple_choice",
            "label": "Trắc nghiệm từ vựng"
        },
        {
            "value": "word_form",
            "label": "Dạng từ"
        },
        {
            "value": "find_mistake",
            "label": "Tìm và sửa lỗi"
        },
        {
            "value": "contextual_vocabulary",
            "label": "Từ vựng theo ngữ cảnh"
        }
    ]

    valid_types = [
        item["value"]
        for item in question_types
    ]

    if question_type and question_type not in valid_types:
        abort(404)

    query = VocabularyQuestion.query.filter_by(
        unit=unit
    )

    if question_type:

        query = query.filter_by(
            question_type=question_type
        )

    questions = query.order_by(
        VocabularyQuestion.id
    ).all()

    if request.method == "POST":

        if not questions:

            flash(
                "Unit này hiện chưa có câu hỏi.",
                "error"
            )

            return redirect(url_for("vocabulary"))

        results = []
        correct_count = 0

        def normalize(value):

            return " ".join(
                (value or "").split()
            ).casefold()

        for question in questions:

            answer = request.form.get(
                f"question_{question.id}", ""
            ).strip()

            expected = (
                question.correct_answer or ""
            ).strip()

            if question.question_type == "find_mistake":

                if "→" in expected:

                    expected = expected.split(
                        "→", 1
                    )[1].strip()

                elif "->" in expected:

                    expected = expected.split(
                        "->", 1
                    )[1].strip()

            is_correct = False

            if answer:

                normalized_answer = normalize(answer)
                normalized_expected = normalize(expected)

                if normalized_answer == normalized_expected:

                    is_correct = True

                elif question.question_type == "multiple_choice":

                    options = {
                        "A": question.option_a,
                        "B": question.option_b,
                        "C": question.option_c,
                        "D": question.option_d
                    }

                    answer_text = options.get(
                        answer.upper()
                    )

                    expected_text = options.get(
                        expected.upper()
                    )

                    if (
                        answer_text
                        and normalize(answer_text) == normalized_expected
                    ):

                        is_correct = True

                    elif (
                        expected_text
                        and normalize(expected_text) == normalized_answer
                    ):

                        is_correct = True

            if is_correct:
                correct_count += 1

            db.session.add(
                VocabularyAttempt(
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

        previous_attempts = VocabularyAttempt.query.filter_by(
            user_id=current_user.id
        ).all()

        previous_correct = sum(
            1 for item in previous_attempts
            if item.is_correct
        )

        previous_total = len(previous_attempts)

        profile.vocabulary_score = round(
            previous_correct / previous_total * 100,
            2
        ) if previous_total else percentage

        db.session.commit()

        ai_evaluation = None

        try:

            ai_evaluation = evaluate_vocabulary(
                unit=unit,
                results=results,
                percentage=percentage
            )

        except Exception as error:

            print(
                f"[Vocabulary AI] Loi goi ham danh gia: {error}"
            )

        return render_template(
            "vocabulary_result.html",
            unit=unit,
            results=results,
            correct_count=correct_count,
            total=total,
            percentage=percentage,
            ai_evaluation=ai_evaluation
        )

    return render_template(
        "vocabulary_practice.html",
        unit=unit,
        questions=questions,
        question_types=question_types,
        selected_type=question_type
    )


@app.route("/vocabulary/progress")
@role_required("student")
def vocabulary_progress():

    attempts = db.session.query(
        VocabularyAttempt,
        VocabularyQuestion.unit
    ).join(
        VocabularyQuestion,
        VocabularyAttempt.question_id == VocabularyQuestion.id
    ).filter(
        VocabularyAttempt.user_id == current_user.id
    ).all()

    total_attempts = len(attempts)

    correct_attempts = sum(
        1 for attempt, unit in attempts
        if attempt.is_correct
    )

    accuracy = round(
        correct_attempts / total_attempts * 100,
        2
    ) if total_attempts else 0

    unit_results = []

    for unit in range(1, 7):

        unit_attempts = [
            attempt
            for attempt, question_unit in attempts
            if question_unit == unit
        ]

        unit_total = len(unit_attempts)

        unit_correct = sum(
            1 for attempt in unit_attempts
            if attempt.is_correct
        )

        unit_accuracy = round(
            unit_correct / unit_total * 100,
            2
        ) if unit_total else 0

        unit_results.append({
            "unit": unit,
            "total": unit_total,
            "correct": unit_correct,
            "accuracy": unit_accuracy
        })

    return render_template(
        "vocabulary_progress.html",
        total_attempts=total_attempts,
        correct_attempts=correct_attempts,
        accuracy=accuracy,
        unit_results=unit_results
    )


@app.route("/profile", methods=["GET", "POST"])
@role_required("student")
def profile():

    profile = LearningProfile.query.filter_by(
        user_id=current_user.id
    ).first()

    if not profile:

        profile = LearningProfile(
            user_id=current_user.id
        )

        db.session.add(profile)
        db.session.commit()

    if request.method == "POST":

        profile.learning_goal = request.form.get(
            "learning_goal", ""
        ).strip()

        db.session.commit()

        flash(
            "Đã cập nhật mục tiêu học tập.",
            "success"
        )

        return redirect(url_for("profile"))

    return render_template(
        "profile.html",
        profile=profile
    )

@app.route("/profile/avatar", methods=["POST"])
@role_required("student")
def upload_profile_avatar():

    file = request.files.get("avatar")

    if not file or not file.filename:
        flash("Bạn chưa chọn ảnh đại diện.", "error")
        return redirect(url_for("profile"))

    original_name = secure_filename(file.filename)

    if "." not in original_name:
        flash("File ảnh không hợp lệ.", "error")
        return redirect(url_for("profile"))

    extension = original_name.rsplit(".", 1)[1].lower()

    if extension not in ALLOWED_AVATAR_EXTENSIONS:
        flash("Chỉ hỗ trợ ảnh PNG, JPG hoặc WEBP.", "error")
        return redirect(url_for("profile"))

    file.stream.seek(0, os.SEEK_END)
    file_size = file.stream.tell()
    file.stream.seek(0)

    if file_size > 5 * 1024 * 1024:
        flash("Ảnh không được vượt quá 5MB.", "error")
        return redirect(url_for("profile"))

    filename = f"{uuid4().hex}.{extension}"
    file_path = os.path.join(AVATAR_UPLOAD_FOLDER, filename)

    old_avatar = current_user.avatar

    try:
        file.save(file_path)

        current_user.avatar = filename
        db.session.commit()

        if old_avatar:
            old_path = os.path.join(
                AVATAR_UPLOAD_FOLDER,
                old_avatar
            )

            if os.path.isfile(old_path):
                os.remove(old_path)

        flash("Đã cập nhật ảnh đại diện.", "success")

    except Exception:
        db.session.rollback()

        if os.path.isfile(file_path):
            os.remove(file_path)

        flash("Không thể cập nhật ảnh đại diện.", "error")

    return redirect(url_for("profile"))

@app.route("/learning-path")
@role_required("student")
def learning_path():

    unit_titles = {
        1: "My Hobbies",
        2: "Healthy Living",
        3: "Community Service",
        4: "Music and Arts",
        5: "Food and Drink",
        6: "A Visit to a School",
        7: "Traffic"
    }

    units = []

    for unit_number, unit_title in unit_titles.items():

        available_skills = 0

        if VocabularyQuestion.query.filter_by(
            unit=unit_number
        ).first():
            available_skills += 1

        if GrammarQuestion.query.filter_by(
            unit=unit_number
        ).first():
            available_skills += 1

        if ReadingPassage.query.filter_by(
            section_type="unit",
            unit=unit_number
        ).first():
            available_skills += 1

        if LearningMaterial.query.filter_by(
            unit=unit_number,
            skill="listening"
        ).first():
            available_skills += 1

        if SpeakingTopic.query.filter_by(
            section_type="unit",
            unit=unit_number
        ).first():
            available_skills += 1

        if WritingUnit.query.filter_by(
            unit=unit_number
        ).first():
            available_skills += 1

        units.append({
            "number": unit_number,
            "title": unit_title,
            "available_skills": available_skills,
            "total_skills": 6
        })

    return render_template(
        "learning_path.html",
        units=units
    )
@app.route("/learning-path/unit/<int:unit_number>")
@role_required("student")
def unit_detail(unit_number):

    if unit_number < 1 or unit_number > 7:
        abort(404)

    unit_titles = {
        1: "My Hobbies",
        2: "Healthy Living",
        3: "Community Service",
        4: "Music and Arts",
        5: "Food and Drink",
        6: "A Visit to a School",
        7: "Traffic"
    }

    unit_title = unit_titles[unit_number]

    # ==============================
    # VOCABULARY
    # ==============================

    vocabulary_count = VocabularyQuestion.query.filter_by(
        unit=unit_number
    ).count()

    # ==============================
    # GRAMMAR
    # ==============================

    grammar_count = GrammarQuestion.query.filter_by(
        unit=unit_number
    ).count()

    # ==============================
    # READING
    # ==============================

    reading_passage = ReadingPassage.query.filter_by(
        section_type="unit",
        unit=unit_number
    ).first()

    reading_count = (
        len(reading_passage.questions)
        if reading_passage else 0
    )

    # ==============================
    # SPEAKING
    # ==============================

    speaking_topics = SpeakingTopic.query.filter_by(
        section_type="unit",
        unit=unit_number
    ).order_by(
        SpeakingTopic.id
    ).all()

    # ==============================
    # WRITING
    # ==============================

    writing_unit = WritingUnit.query.filter_by(
        unit=unit_number
    ).first()

    # ==============================
    # LISTENING
    # ==============================

    listening_materials = LearningMaterial.query.filter_by(
        unit=unit_number,
        skill="listening"
    ).order_by(
        LearningMaterial.uploaded_at.desc()
    ).all()

    # ==============================
    # DANH SÁCH KỸ NĂNG
    # ==============================

    skills = [
        {
            "name": "Vocabulary",
            "title": "Từ vựng",
            "description": "Học và luyện tập từ vựng theo chủ đề của Unit.",
            "icon": "📚",
            "url": (
                url_for(
                    "vocabulary_practice",
                    unit=unit_number
                )
                if vocabulary_count > 0 else None
            ),
            "total": vocabulary_count
        },
        {
            "name": "Grammar",
            "title": "Ngữ pháp",
            "description": "Ôn tập cấu trúc và thực hành bài tập ngữ pháp.",
            "icon": "📝",
            "url": (
                url_for(
                    "grammar.grammar_practice",
                    unit=unit_number
                )
                if grammar_count > 0 else None
            ),
            "total": grammar_count
        },
        {
            "name": "Reading",
            "title": "Đọc hiểu",
            "description": "Đọc văn bản và trả lời các câu hỏi đọc hiểu.",
            "icon": "📖",
            "url": (
                url_for(
                    "reading.reading_practice",
                    passage_id=reading_passage.id
                )
                if reading_passage and reading_count > 0 else None
            ),
            "total": reading_count
        },
        {
            "name": "Listening",
            "title": "Nghe",
            "description": "Luyện nghe thông qua học liệu của từng Unit.",
            "icon": "🎧",
            "url": (
                url_for(
                    "material_detail",
                    material_id=listening_materials[0].id
                )
                if listening_materials else None
            ),
            "total": len(listening_materials)
        },
        {
            "name": "Speaking",
            "title": "Nói",
            "description": "Luyện nói theo chủ đề và gợi ý tiếng Anh.",
            "icon": "🎤",
            "url": (
                url_for(
                    "speaking.speaking_practice",
                    topic_id=speaking_topics[0].id
                )
                if speaking_topics else None
            ),
            "total": len(speaking_topics)
        },
        {
            "name": "Writing",
            "title": "Viết",
            "description": "Thực hành viết câu và đoạn văn theo chủ đề.",
            "icon": "✍️",
            "url": (
                url_for(
                    "writing.writing_practice",
                    unit_number=unit_number
                )
                if writing_unit else None
            ),
            "total": 1 if writing_unit else 0
        }
    ]

    return render_template(
        "unit_detail.html",
        unit_number=unit_number,
        unit_title=unit_title,
        skills=skills,
        speaking_topics=speaking_topics,
        listening_materials=listening_materials,
        reading_passage=reading_passage
    )
@app.route("/lesson/<int:lesson_id>", methods=["GET", "POST"])
@role_required("student")
def lesson(lesson_id):

    lesson_item = db.session.get(
        Lesson,
        lesson_id
    )

    if not lesson_item:
        abort(404)

    progress = LearningProgress.query.filter_by(
        user_id=current_user.id,
        lesson_id=lesson_id
    ).first()

    if request.method == "POST":

        if not progress:

            progress = LearningProgress(
                user_id=current_user.id,
                lesson_id=lesson_id
            )

            db.session.add(progress)

        progress.status = "completed"
        progress.completed_at = datetime.utcnow()

        db.session.commit()

        flash(
            "Bạn đã hoàn thành bài học!",
            "success"
        )

        return redirect(url_for("learning_path"))

    return render_template(
        "lesson.html",
        lesson=lesson_item,
        progress=progress
    )


@app.route("/tutor", methods=["GET", "POST"])
@role_required("student")
def tutor():

    chat_id = request.args.get(
        "chat_id",
        type=int
    )

    chat = None

    if chat_id:

        chat = ChatSession.query.filter_by(
            id=chat_id,
            user_id=current_user.id
        ).first()

        if not chat:
            abort(404)

    if request.method == "POST":

        question = request.form.get(
            "question", ""
        ).strip()

        chat_id = request.form.get(
            "chat_id",
            type=int
        )

        if question:

            chat = None

            if chat_id:

                chat = ChatSession.query.filter_by(
                    id=chat_id,
                    user_id=current_user.id
                ).first()

            if not chat:

                chat = ChatSession(
                    user_id=current_user.id,
                    title=question[:40]
                )

                db.session.add(chat)
                db.session.flush()

            history = AIConversation.query.filter_by(
                user_id=current_user.id,
                session_id=chat.id
            ).order_by(
                AIConversation.created_at.asc()
            ).all()

            answer = ask_ai(
                question,
                history=history
            )

            conversation = AIConversation(
                user_id=current_user.id,
                session_id=chat.id,
                question=question,
                answer=answer
            )

            chat.updated_at = datetime.utcnow()

            db.session.add(conversation)
            db.session.commit()

            return redirect(
                url_for(
                    "tutor",
                    chat_id=chat.id
                )
            )

        return redirect(
            url_for("tutor", chat_id=chat_id)
            if chat_id else url_for("tutor")
        )

    conversations = []

    if chat:

        conversations = AIConversation.query.filter_by(
            user_id=current_user.id,
            session_id=chat.id
        ).order_by(
            AIConversation.created_at.asc()
        ).all()

    chat_sessions = ChatSession.query.filter_by(
        user_id=current_user.id
    ).order_by(
        ChatSession.updated_at.desc()
    ).all()

    return render_template(
        "tutor.html",
        conversations=conversations,
        chat=chat,
        chat_sessions=chat_sessions
    )
@app.route("/api/tutor/chat", methods=["POST"])
@role_required("student")
def tutor_chat_api():

    data = request.get_json(silent=True) or {}

    question = str(
        data.get("question", "")
    ).strip()

    if not question:
        return jsonify({
            "error": "Bạn hãy nhập câu hỏi trước nhé!"
        }), 400

    if len(question) > 2000:
        return jsonify({
            "error": "Câu hỏi không được vượt quá 2000 ký tự."
        }), 400

    context = data.get("context") or {}

    if not isinstance(context, dict):
        context = {}

    page_title = str(
        context.get("page_title", "Trang học tiếng Anh")
    )[:150]

    unit = str(
        context.get("unit", "")
    )[:10]

    page_url = str(
        context.get("page_url", "")
    )[:200]

    chat_id = data.get("chat_id")

    chat = None

    if chat_id is not None:

        try:
            chat_id = int(chat_id)
        except (TypeError, ValueError):
            return jsonify({
                "error": "Phiên trò chuyện không hợp lệ."
            }), 400

        chat = ChatSession.query.filter_by(
            id=chat_id,
            user_id=current_user.id
        ).first()

        if not chat:
            return jsonify({
                "error": "Không tìm thấy cuộc trò chuyện."
            }), 404

    try:

        if not chat:

            chat = ChatSession(
                user_id=current_user.id,
                title=question[:40]
            )

            db.session.add(chat)
            db.session.flush()

        history = AIConversation.query.filter_by(
            user_id=current_user.id,
            session_id=chat.id
        ).order_by(
            AIConversation.created_at.asc()
        ).all()

        context_prompt = (
            "Thông tin trang học hiện tại:\n"
            f"- Trang: {page_title}\n"
            f"- Unit: {unit or 'Chưa xác định'}\n"
            f"- Đường dẫn: {page_url or 'Không xác định'}\n\n"
            "Hãy sử dụng thông tin này để hiểu ngữ cảnh câu hỏi. "
            "Bạn đang hỗ trợ học sinh lớp 7 học tiếng Anh. "
            "Giải thích thân thiện, dễ hiểu, phù hợp trình độ lớp 7. "
            "Nếu câu hỏi liên quan đến bài học, hãy ưu tiên nội dung "
            "đang học và không tự khẳng định thông tin chưa có căn cứ.\n\n"
            f"Câu hỏi của học sinh: {question}"
        )

        answer = ask_ai(
            context_prompt,
            history=history
        )

        if not answer:
            raise ValueError("AI không trả về câu trả lời.")

        conversation = AIConversation(
            user_id=current_user.id,
            session_id=chat.id,
            question=question,
            answer=answer
        )

        chat.updated_at = datetime.utcnow()

        db.session.add(conversation)
        db.session.commit()

        return jsonify({
            "answer": answer,
            "chat_id": chat.id
        })

    except Exception as error:

        db.session.rollback()

        print(
            "[Tutor Widget] Lỗi gọi AI:",
            error
        )

        return jsonify({
            "error": "Gia sư đang gặp sự cố. Bạn thử lại sau nhé!"
        }), 500

@app.route("/progress")
@role_required("student")
def progress():

    profile = LearningProfile.query.filter_by(
        user_id=current_user.id
    ).first()

    if not profile:

        profile = LearningProfile(
            user_id=current_user.id
        )

        db.session.add(profile)
        db.session.commit()

    test_results = TestResult.query.filter_by(
        user_id=current_user.id
    ).order_by(
        TestResult.completed_at.desc()
    ).all()

    completed_lessons = LearningProgress.query.filter_by(
        user_id=current_user.id,
        status="completed"
    ).count()

    return render_template(
        "progress.html",
        profile=profile,
        test_results=test_results,
        completed_lessons=completed_lessons
    )


@app.route("/teacher")
@role_required("teacher", "admin")
def teacher_dashboard():

    students = User.query.filter_by(
        role="student"
    ).order_by(
        User.full_name.asc()
    ).all()

    lessons = Lesson.query.order_by(
        Lesson.id.desc()
    ).all()

    materials = LearningMaterial.query.order_by(
        LearningMaterial.uploaded_at.desc()
    ).all()

    student_stats = {
        student.id: {
            "student": student,
            "question_attempts": 0,
            "question_correct": 0,
            "placement_tests": 0,
            "placement_score_total": 0,
            "speaking_submissions": 0,
            "speaking_score_total": 0,
            "speaking_scored_count": 0,
            "writing_submissions": 0,
            "writing_score_total": 0,
            "writing_scored_count": 0,
            "completed_lessons": 0,
            "activity_count": 0,
            "latest_activity": None
        }
        for student in students
    }

    def record_activity(user_id, activity_time):

        stats = student_stats.get(user_id)

        if not stats:
            return

        stats["activity_count"] += 1

        if activity_time and (
            stats["latest_activity"] is None
            or activity_time > stats["latest_activity"]
        ):
            stats["latest_activity"] = activity_time

    question_attempt_models = [
        VocabularyAttempt,
        GrammarAttempt,
        ReadingAttempt
    ]

    for model in question_attempt_models:

        attempts = model.query.all()

        for attempt in attempts:

            stats = student_stats.get(attempt.user_id)

            if not stats:
                continue

            stats["question_attempts"] += 1

            if attempt.is_correct:
                stats["question_correct"] += 1

            record_activity(
                attempt.user_id,
                attempt.attempted_at
            )

    for result in TestResult.query.all():

        stats = student_stats.get(result.user_id)

        if not stats:
            continue

        stats["placement_tests"] += 1
        stats["placement_score_total"] += result.score or 0

        record_activity(
            result.user_id,
            result.completed_at
        )

    for attempt in SpeakingAttempt.query.all():

        stats = student_stats.get(attempt.user_id)

        if not stats:
            continue

        stats["speaking_submissions"] += 1

        if attempt.overall_score is not None:

            stats["speaking_score_total"] += attempt.overall_score
            stats["speaking_scored_count"] += 1

        record_activity(
            attempt.user_id,
            attempt.attempted_at
        )

    for attempt in WritingAttempt.query.all():

        stats = student_stats.get(attempt.user_id)

        if not stats:
            continue

        stats["writing_submissions"] += 1

        if attempt.total_score is not None:

            stats["writing_score_total"] += attempt.total_score
            stats["writing_scored_count"] += 1

        record_activity(
            attempt.user_id,
            attempt.submitted_at
        )

    for progress_record in LearningProgress.query.filter_by(
        status="completed"
    ).all():

        stats = student_stats.get(progress_record.user_id)

        if not stats:
            continue

        stats["completed_lessons"] += 1

        record_activity(
            progress_record.user_id,
            progress_record.completed_at
        )

    student_overview = []

    for student in students:

        stats = student_stats[student.id]

        placement_average = (
            round(
                stats["placement_score_total"] /
                stats["placement_tests"],
                2
            )
            if stats["placement_tests"] else None
        )

        speaking_average = (
            round(
                stats["speaking_score_total"] /
                stats["speaking_scored_count"],
                2
            )
            if stats["speaking_scored_count"] else None
        )

        writing_average = (
            round(
                stats["writing_score_total"] /
                stats["writing_scored_count"],
                2
            )
            if stats["writing_scored_count"] else None
        )

        accuracy = (
            round(
                stats["question_correct"] /
                stats["question_attempts"] * 100,
                2
            )
            if stats["question_attempts"] else 0
        )

        student_overview.append({
            "student": student,
            "question_attempts": stats["question_attempts"],
            "question_correct": stats["question_correct"],
            "accuracy": accuracy,
            "placement_tests": stats["placement_tests"],
            "placement_average": placement_average,
            "speaking_submissions": stats["speaking_submissions"],
            "speaking_average": speaking_average,
            "writing_submissions": stats["writing_submissions"],
            "writing_average": writing_average,
            "completed_lessons": stats["completed_lessons"],
            "activity_count": stats["activity_count"],
            "latest_activity": stats["latest_activity"]
        })

    total_students = len(students)

    active_students = sum(
        1 for item in student_overview
        if item["activity_count"] > 0
    )

    total_question_attempts = sum(
        item["question_attempts"]
        for item in student_overview
    )

    total_question_correct = sum(
        item["question_correct"]
        for item in student_overview
    )

    total_placement_tests = sum(
        item["placement_tests"]
        for item in student_overview
    )

    total_speaking_submissions = sum(
        item["speaking_submissions"]
        for item in student_overview
    )

    total_writing_submissions = sum(
        item["writing_submissions"]
        for item in student_overview
    )

    total_completed_lessons = sum(
        item["completed_lessons"]
        for item in student_overview
    )

    overall_accuracy = (
        round(
            total_question_correct /
            total_question_attempts * 100,
            2
        )
        if total_question_attempts else 0
    )

    student_overview.sort(
        key=lambda item: (
            item["latest_activity"] is not None,
            item["latest_activity"] or datetime.min
        ),
        reverse=True
    )

    return render_template(
        "teacher_dashboard.html",
        students=students,
        lessons=lessons,
        materials=materials,
        student_overview=student_overview,
        total_students=total_students,
        active_students=active_students,
        total_question_attempts=total_question_attempts,
        total_question_correct=total_question_correct,
        overall_accuracy=overall_accuracy,
        total_placement_tests=total_placement_tests,
        total_speaking_submissions=total_speaking_submissions,
        total_writing_submissions=total_writing_submissions,
        total_completed_lessons=total_completed_lessons
    )


@app.route("/admin")
@role_required("admin")
def admin_dashboard():

    total_users = User.query.count()

    total_students = User.query.filter_by(
        role="student"
    ).count()

    total_teachers = User.query.filter_by(
        role="teacher"
    ).count()

    total_lessons = Lesson.query.count()

    total_questions = Question.query.count()

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_students=total_students,
        total_teachers=total_teachers,
        total_lessons=total_lessons,
        total_questions=total_questions
    )


@app.route("/materials")
@login_required
def materials():

    query = LearningMaterial.query

    unit = request.args.get(
        "unit",
        type=int
    )

    skill = request.args.get(
        "skill",
        ""
    ).strip()

    keyword = request.args.get(
        "q",
        ""
    ).strip()

    if unit is not None:

        if unit < 1 or unit > 6:
            abort(404)

        query = query.filter_by(
            unit=unit
        )

    if skill:

        if skill not in MATERIAL_SKILLS:
            abort(404)

        query = query.filter_by(
            skill=skill
        )

    if keyword:

        query = query.filter(
            LearningMaterial.title.ilike(
                f"%{keyword}%"
            )
        )

    material_list = query.order_by(
        LearningMaterial.uploaded_at.desc()
    ).all()

    return render_template(
        "materials/materials.html",
        materials=material_list,
        selected_unit=unit,
        selected_skill=skill,
        keyword=keyword,
        skills=MATERIAL_SKILLS,
        units=range(1, 7)
    )


@app.route("/materials/upload", methods=["GET", "POST"])
@role_required("teacher")
def material_upload():

    if request.method == "POST":

        title = request.form.get(
            "title",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        unit = request.form.get(
            "unit",
            type=int
        )

        skill = request.form.get(
            "skill",
            ""
        ).strip()

        uploaded_file = request.files.get("file")

        if not title or unit not in range(1, 7):

            flash(
                "Vui lòng nhập tên và chọn Unit từ 1 đến 6.",
                "error"
            )

            return redirect(url_for("material_upload"))

        if skill not in MATERIAL_SKILLS:

            flash(
                "Vui lòng chọn kỹ năng hợp lệ.",
                "error"
            )

            return redirect(url_for("material_upload"))

        if not uploaded_file or not uploaded_file.filename:

            flash(
                "Vui lòng chọn tài liệu cần tải lên.",
                "error"
            )

            return redirect(url_for("material_upload"))

        file_data = save_material_file(uploaded_file)

        if not file_data:

            flash(
                "File không hợp lệ hoặc định dạng chưa được hỗ trợ.",
                "error"
            )

            return redirect(url_for("material_upload"))

        material = LearningMaterial(
            title=title,
            description=description,
            unit=unit,
            skill=skill,
            material_type=file_data["material_type"],
            file_path=file_data["file_path"],
            original_filename=file_data["original_filename"],
            file_size=file_data["file_size"],
            uploaded_by=current_user.id
        )

        try:

            db.session.add(material)
            db.session.commit()

        except Exception:

            db.session.rollback()
            delete_material_file(file_data["file_path"])

            flash(
                "Không thể lưu học liệu. Vui lòng thử lại.",
                "error"
            )

            return redirect(url_for("material_upload"))

        flash(
            "Đã tải học liệu lên thành công!",
            "success"
        )

        return redirect(url_for("materials"))

    return render_template(
        "materials/material_upload.html",
        units=range(1, 7),
        skills=MATERIAL_SKILLS
    )


@app.route("/materials/<int:material_id>")
@login_required
def material_detail(material_id):

    material = db.get_or_404(
        LearningMaterial,
        material_id
    )

    return render_template(
        "materials/material_detail.html",
        material=material
    )


@app.route("/materials/download/<int:material_id>")
@login_required
def material_download(material_id):

    material = db.get_or_404(
        LearningMaterial,
        material_id
    )

    filename = os.path.basename(
        material.file_path or ""
    )

    if not filename:
        abort(404)

    return send_from_directory(
        MATERIAL_UPLOAD_FOLDER,
        filename,
        as_attachment=True,
        download_name=(
            material.original_filename or filename
        )
    )


@app.route("/materials/edit/<int:material_id>", methods=["GET", "POST"])
@role_required("teacher")
def material_edit(material_id):

    material = LearningMaterial.query.filter_by(
        id=material_id,
        uploaded_by=current_user.id
    ).first_or_404()

    if request.method == "POST":

        title = request.form.get(
            "title",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        unit = request.form.get(
            "unit",
            type=int
        )

        skill = request.form.get(
            "skill",
            ""
        ).strip()

        if not title or unit not in range(1, 7):

            flash(
                "Thông tin tên hoặc Unit không hợp lệ.",
                "error"
            )

            return redirect(
                url_for(
                    "material_edit",
                    material_id=material.id
                )
            )

        if skill not in MATERIAL_SKILLS:

            flash(
                "Kỹ năng không hợp lệ.",
                "error"
            )

            return redirect(
                url_for(
                    "material_edit",
                    material_id=material.id
                )
            )

        material.title = title
        material.description = description
        material.unit = unit
        material.skill = skill

        uploaded_file = request.files.get("file")
        new_file_data = None
        old_file = None

        if uploaded_file and uploaded_file.filename:

            new_file_data = save_material_file(uploaded_file)

            if not new_file_data:

                flash(
                    "File mới không hợp lệ.",
                    "error"
                )

                return redirect(
                    url_for(
                        "material_edit",
                        material_id=material.id
                    )
                )

            old_file = material.file_path

            material.file_path = new_file_data["file_path"]
            material.original_filename = new_file_data["original_filename"]
            material.material_type = new_file_data["material_type"]
            material.file_size = new_file_data["file_size"]

        try:

            db.session.commit()

        except Exception:

            db.session.rollback()

            if new_file_data:
                delete_material_file(new_file_data["file_path"])

            flash(
                "Không thể cập nhật học liệu.",
                "error"
            )

            return redirect(
                url_for(
                    "material_edit",
                    material_id=material.id
                )
            )

        if new_file_data:
            delete_material_file(old_file)

        flash(
            "Đã cập nhật học liệu.",
            "success"
        )

        return redirect(url_for("materials"))

    return render_template(
        "materials/material_edit.html",
        material=material,
        units=range(1, 7),
        skills=MATERIAL_SKILLS
    )


@app.route("/materials/delete/<int:material_id>", methods=["POST"])
@role_required("teacher")
def material_delete(material_id):

    material = LearningMaterial.query.filter_by(
        id=material_id,
        uploaded_by=current_user.id
    ).first_or_404()

    filename = material.file_path

    try:

        db.session.delete(material)
        db.session.commit()

    except Exception:

        db.session.rollback()

        flash(
            "Không thể xóa học liệu.",
            "error"
        )

        return redirect(url_for("materials"))

    delete_material_file(filename)

    flash(
        "Đã xóa học liệu.",
        "success"
    )

    return redirect(url_for("materials"))


@app.errorhandler(403)
def forbidden(error):

    return (
        "Bạn không có quyền truy cập chức năng này.",
        403
    )


@app.errorhandler(404)
def not_found(error):

    return (
        "Không tìm thấy trang bạn yêu cầu.",
        404
    )


@app.errorhandler(413)
def file_too_large(error):

    return (
        "File tải lên vượt quá dung lượng tối đa 20 MB.",
        413
    )


if __name__ == "__main__":

    init_db(app)

    seed_data()

    load_grammar_data(app)
    load_reading_data(app)

    with app.app_context():
        load_speaking_data()

    load_writing_data(app)

    with app.app_context():

        print(
            "\n========== KIỂM TRA WRITING TEMPLATE =========="
        )

        print(
            "Thư mục app.py:",
            app.root_path
        )

        print(
            "Thư mục templates:",
            app.template_folder
        )

        template = app.jinja_env.get_template(
            "writing/writing_practice.html"
        )

        print(
            "FILE TEMPLATE FLASK ĐANG ĐỌC:",
            template.filename
        )

        print(
            "================================================\n"
        )

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
