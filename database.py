
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    avatar = db.Column(db.String(255), nullable=True)
    role = db.Column(db.String(20), default="student")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    profile = db.relationship(
        "LearningProfile",
        backref="user",
        uselist=False,
        cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class LearningProfile(db.Model):
    __tablename__ = "learning_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        unique=True,
        nullable=False
    )

    current_level = db.Column(db.String(30), default="Chưa đánh giá")
    vocabulary_score = db.Column(db.Float, default=0)
    grammar_score = db.Column(db.Float, default=0)
    reading_score = db.Column(db.Float, default=0)
    listening_score = db.Column(db.Float, default=0)
    speaking_score = db.Column(db.Float, default=0)
    writing_score = db.Column(db.Float, default=0)

    strengths = db.Column(db.Text)
    weaknesses = db.Column(db.Text)
    learning_goal = db.Column(db.Text)


class Question(db.Model):
    __tablename__ = "questions"

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(255))
    option_b = db.Column(db.String(255))
    option_c = db.Column(db.String(255))
    option_d = db.Column(db.String(255))
    correct_answer = db.Column(db.String(1))
    skill = db.Column(db.String(30))
    difficulty = db.Column(db.String(20))


class TestResult(db.Model):
    __tablename__ = "test_results"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    score = db.Column(db.Float, default=0)
    total_questions = db.Column(db.Integer, default=0)
    level = db.Column(db.String(30))
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Lưu kết quả phân tích của AI dưới dạng JSON
    ai_analysis = db.Column(db.Text)


class Lesson(db.Model):
    __tablename__ = "lessons"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    unit = db.Column(db.String(100))
    description = db.Column(db.Text)
    content = db.Column(db.Text)
    skill = db.Column(db.String(30))
    difficulty = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class LearningProgress(db.Model):
    __tablename__ = "learning_progress"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    lesson_id = db.Column(db.Integer, db.ForeignKey("lessons.id"))

    status = db.Column(db.String(20), default="not_started")
    score = db.Column(db.Float, default=0)
    completed_at = db.Column(db.DateTime)


class LearningMaterial(db.Model):
    __tablename__ = "learning_materials"

    id = db.Column(db.Integer, primary_key=True)

    # Thông tin học liệu
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)

    # Phân loại theo Unit 1-7
    unit = db.Column(db.Integer, nullable=True)

    # Phân loại theo kỹ năng
    skill = db.Column(db.String(30), nullable=True)

    # Loại tài liệu: pdf, docx, pptx, image...
    material_type = db.Column(db.String(30))

    # Đường dẫn và tên file
    file_path = db.Column(db.String(500))
    original_filename = db.Column(db.String(255))
    file_size = db.Column(db.Integer)

    # Người tải học liệu lên
    uploaded_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )

    uploader = db.relationship(
        "User",
        backref=db.backref("learning_materials", lazy=True)
    )

    uploaded_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )



class ChatSession(db.Model):
    __tablename__ = "chat_sessions"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    title = db.Column(
        db.String(200),
        default="Cuộc trò chuyện mới"
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    conversations = db.relationship(
        "AIConversation",
        backref="chat_session",
        order_by="AIConversation.created_at",
        cascade="all, delete-orphan"
    )


class AIConversation(db.Model):
    __tablename__ = "ai_conversations"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id")
    )

    session_id = db.Column(
        db.Integer,
        db.ForeignKey("chat_sessions.id"),
        nullable=True
    )

    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


class VocabularyQuestion(db.Model):
    __tablename__ = "vocabulary_questions"

    id = db.Column(db.Integer, primary_key=True)
    unit = db.Column(db.Integer, nullable=False)
    topic = db.Column(db.String(100))
    word = db.Column(db.String(100))
    question_type = db.Column(db.String(50), nullable=False)
    question_text = db.Column(db.Text, nullable=False)

    option_a = db.Column(db.Text)
    option_b = db.Column(db.Text)
    option_c = db.Column(db.Text)
    option_d = db.Column(db.Text)

    correct_answer = db.Column(db.Text, nullable=False)
    explanation = db.Column(db.Text)

    difficulty = db.Column(db.String(30), default="basic")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class VocabularyAttempt(db.Model):
    __tablename__ = "vocabulary_attempts"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    question_id = db.Column(
        db.Integer,
        db.ForeignKey("vocabulary_questions.id"),
        nullable=False
    )

    user_answer = db.Column(db.Text)
    is_correct = db.Column(db.Boolean, default=False)
    attempted_at = db.Column(db.DateTime, default=datetime.utcnow)


class GrammarQuestion(db.Model):
    __tablename__ = "grammar_questions"

    id = db.Column(db.Integer, primary_key=True)

    unit = db.Column(db.Integer, nullable=False)
    topic = db.Column(db.String(150), nullable=False)

    question_type = db.Column(db.String(50), default="multiple_choice")
    question_text = db.Column(db.Text, nullable=False)

    option_a = db.Column(db.Text)
    option_b = db.Column(db.Text)
    option_c = db.Column(db.Text)
    option_d = db.Column(db.Text)

    correct_answer = db.Column(db.Text, nullable=False)
    explanation = db.Column(db.Text)

    difficulty = db.Column(db.String(30), default="basic")
    error_tag = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class GrammarAttempt(db.Model):
    __tablename__ = "grammar_attempts"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    question_id = db.Column(
        db.Integer,
        db.ForeignKey("grammar_questions.id"),
        nullable=False
    )

    user_answer = db.Column(db.Text)
    is_correct = db.Column(db.Boolean, default=False)
    attempted_at = db.Column(db.DateTime, default=datetime.utcnow)


class ReadingPassage(db.Model):
    __tablename__ = "reading_passages"

    id = db.Column(db.Integer, primary_key=True)
    section_type = db.Column(db.String(20), nullable=False, default="unit")
    unit = db.Column(db.Integer, nullable=True)
    review_number = db.Column(db.Integer, nullable=True)
    title = db.Column(db.String(200), nullable=False)
    topic = db.Column(db.String(100))
    description = db.Column(db.Text)
    content = db.Column(db.Text, nullable=False)
    difficulty = db.Column(db.String(30), default="basic")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    questions = db.relationship(
        "ReadingQuestion",
        backref="passage",
        cascade="all, delete-orphan",
        order_by="ReadingQuestion.id"
    )


class ReadingQuestion(db.Model):
    __tablename__ = "reading_questions"

    id = db.Column(db.Integer, primary_key=True)
    passage_id = db.Column(
        db.Integer,
        db.ForeignKey("reading_passages.id"),
        nullable=False
    )
    task_type = db.Column(db.String(10), nullable=False)
    question_type = db.Column(db.String(50), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.Text)
    option_b = db.Column(db.Text)
    option_c = db.Column(db.Text)
    option_d = db.Column(db.Text)
    correct_answer = db.Column(db.Text, nullable=False)
    explanation = db.Column(db.Text)
    difficulty = db.Column(db.String(30), default="basic")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ReadingAttempt(db.Model):
    __tablename__ = "reading_attempts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )
    question_id = db.Column(
        db.Integer,
        db.ForeignKey("reading_questions.id"),
        nullable=False
    )
    user_answer = db.Column(db.Text)
    is_correct = db.Column(db.Boolean, default=False)
    attempted_at = db.Column(db.DateTime, default=datetime.utcnow)

    question = db.relationship(
        "ReadingQuestion",
        backref="attempts"
    )


class SpeakingTopic(db.Model):
    __tablename__ = "speaking_topics"

    id = db.Column(db.Integer, primary_key=True)
    section_type = db.Column(db.String(20), nullable=False, default="unit")
    unit = db.Column(db.Integer, nullable=True)
    review_number = db.Column(db.Integer, nullable=True)
    title = db.Column(db.String(200), nullable=False)
    topic = db.Column(db.String(200))
    description = db.Column(db.Text)
    prompt = db.Column(db.Text, nullable=False)
    suggested_vocabulary = db.Column(db.Text)
    sample_answer = db.Column(db.Text)
    difficulty = db.Column(db.String(30), default="basic")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SpeakingAttempt(db.Model):
    __tablename__ = "speaking_attempts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )
    topic_id = db.Column(
        db.Integer,
        db.ForeignKey("speaking_topics.id"),
        nullable=False
    )
    transcript = db.Column(db.Text)
    audio_path = db.Column(db.String(500))
    pronunciation_score = db.Column(db.Float)
    fluency_score = db.Column(db.Float)
    vocabulary_score = db.Column(db.Float)
    grammar_score = db.Column(db.Float)
    overall_score = db.Column(db.Float)
    ai_feedback = db.Column(db.Text)
    attempted_at = db.Column(db.DateTime, default=datetime.utcnow)

    speaking_topic = db.relationship(
        "SpeakingTopic",
        backref="attempts"
    )


class WritingUnit(db.Model):
    __tablename__ = "writing_units"

    id = db.Column(db.Integer, primary_key=True)

    unit = db.Column(db.Integer, nullable=False, unique=True)
    title = db.Column(db.String(200), nullable=False)
    topic = db.Column(db.String(200))

    writing_type = db.Column(db.String(100))
    writing_topic = db.Column(db.Text)
    grammar_focus = db.Column(db.Text)

    sentence_guide = db.Column(db.Text)
    ordering_exercises = db.Column(db.Text)
    completion_exercises = db.Column(db.Text)

    writing_prompt = db.Column(db.Text)
    outline = db.Column(db.Text)

    sample_basic = db.Column(db.Text)
    sample_intermediate = db.Column(db.Text)
    sample_advanced = db.Column(db.Text)

    rubric = db.Column(db.Text)
    common_errors = db.Column(db.Text)
    self_editing_checklist = db.Column(db.Text)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


class WritingAttempt(db.Model):
    __tablename__ = "writing_attempts"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    writing_unit_id = db.Column(
        db.Integer,
        db.ForeignKey("writing_units.id"),
        nullable=False
    )

    user_text = db.Column(db.Text, nullable=False)
    word_count = db.Column(db.Integer, default=0)

    task_score = db.Column(db.Float, default=0)
    organization_score = db.Column(db.Float, default=0)
    grammar_score = db.Column(db.Float, default=0)
    vocabulary_score = db.Column(db.Float, default=0)
    spelling_score = db.Column(db.Float, default=0)

    total_score = db.Column(db.Float, default=0)
    ai_feedback = db.Column(db.Text)

    submitted_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    writing_unit = db.relationship(
        "WritingUnit",
        backref="attempts"
    )



def init_db(app):
    with app.app_context():
        db.create_all()
        user_columns = {
            column["name"]
            for column in db.inspect(db.engine).get_columns("users")
        }

        if "avatar" not in user_columns:
            with db.engine.begin() as connection:
                connection.execute(
                    db.text(
                        "ALTER TABLE users "
                        "ADD COLUMN avatar VARCHAR(255)"
                    )
                )
        conversation_columns = {
            column["name"]
            for column in db.inspect(db.engine).get_columns(
                "ai_conversations"
            )
        }

        if "session_id" not in conversation_columns:
            with db.engine.begin() as connection:
                connection.execute(
                    db.text(
                        "ALTER TABLE ai_conversations "
                        "ADD COLUMN session_id INTEGER "
                        "REFERENCES chat_sessions(id)"
                    )
                )

        result_columns = {
            column["name"]
            for column in db.inspect(db.engine).get_columns(
                "test_results"
            )
        }

        if "ai_analysis" not in result_columns:
            with db.engine.begin() as connection:
                connection.execute(
                    db.text(
                        "ALTER TABLE test_results "
                        "ADD COLUMN ai_analysis TEXT"
                    )
                )

        material_columns = {
            column["name"]
            for column in db.inspect(db.engine).get_columns(
                "learning_materials"
            )
        }

        new_columns = {
            "unit": "INTEGER",
            "skill": "VARCHAR(30)",
            "material_type": "VARCHAR(30)",
            "original_filename": "VARCHAR(255)",
            "file_size": "INTEGER"
        }

        for column_name, column_type in new_columns.items():
            if column_name not in material_columns:
                with db.engine.begin() as connection:
                    connection.execute(
                        db.text(
                            f"ALTER TABLE learning_materials "
                            f"ADD COLUMN {column_name} {column_type}"
                        )
                    )
