
document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("placementForm");

    if (!form) return;

    const questions = form.querySelectorAll(".question-card");
    const progressFill = document.getElementById("progressFill");
    const progressText = document.getElementById("progressText");
    const message = document.getElementById("unansweredMessage");

    function updateProgress() {
        let answered = 0;

        questions.forEach(function (question) {
            if (question.querySelector('input[type="radio"]:checked')) {
                answered++;
            }
        });

        const total = questions.length;
        const percentage = total ? (answered / total) * 100 : 0;

        progressFill.style.width = percentage + "%";
        progressText.textContent = answered + "/" + total + " câu";

        if (answered === total) {
            message.textContent = "Bạn đã hoàn thành tất cả câu hỏi. Có thể nộp bài!";
        } else {
            message.textContent = "Bạn còn " + (total - answered) + " câu chưa trả lời.";
        }
    }

    form.addEventListener("change", updateProgress);

    form.addEventListener("submit", function (event) {
        const unanswered = [];

        questions.forEach(function (question, index) {
            if (!question.querySelector('input[type="radio"]:checked')) {
                unanswered.push(index + 1);
            }
        });

        if (unanswered.length > 0) {
            event.preventDefault();
            message.textContent = "Bạn chưa trả lời câu: " + unanswered.join(", ");
            questions[unanswered[0] - 1].scrollIntoView({
                behavior: "smooth",
                block: "center"
            });
        }
    });

    updateProgress();
});
