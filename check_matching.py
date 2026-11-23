from app import app
from database import VocabularyQuestion

with app.app_context():
    questions = VocabularyQuestion.query.filter_by(
        unit=1,
        question_type="matching"
    ).all()

    print("So cau Matching:", len(questions))

    for question in questions:
        print(question.question_text)
        print("Dap an:", question.correct_answer)