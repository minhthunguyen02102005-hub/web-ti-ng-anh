
document.addEventListener("DOMContentLoaded", function () {
    const skillBars = document.querySelectorAll(".progress-skill-fill[data-score]");

    skillBars.forEach(function (bar) {
        const score = Number(bar.dataset.score);
        const safeScore = Math.min(100, Math.max(0, Number.isFinite(score) ? score : 0));

        requestAnimationFrame(function () {
            bar.style.width = safeScore + "%";
        });
    });
});
