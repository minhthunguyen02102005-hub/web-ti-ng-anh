
document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".skill-fill[data-score]").forEach(function (bar) {
        const score = Number(bar.dataset.score);
        const safeScore = Math.min(100, Math.max(0, Number.isFinite(score) ? score : 0));
        bar.style.width = safeScore + "%";
    });
});
