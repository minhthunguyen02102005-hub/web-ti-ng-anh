document.addEventListener("DOMContentLoaded", function () {
    const widget = document.getElementById("aiTutorWidget");

    if (!widget) return;

    const panel = document.getElementById("aiTutorPanel");
    const launcher = document.getElementById("aiTutorLauncher");
    const closeButton = document.getElementById("aiTutorClose");
    const newChatButton = document.getElementById("aiTutorNewChat");
    const form = document.getElementById("aiTutorForm");
    const input = document.getElementById("aiTutorInput");
    const sendButton = document.getElementById("aiTutorSend");
    const messages = document.getElementById("aiTutorMessages");
    const welcome = document.getElementById("aiTutorWelcome");
    const errorBox = document.getElementById("aiTutorError");
    const contextText = document.getElementById("aiTutorContextText");

    const apiUrl = widget.dataset.apiUrl;

    const CHAT_ID_KEY = "aiTutorChatId";
    const MESSAGES_KEY = "aiTutorMessages";

    let chatId = sessionStorage.getItem(CHAT_ID_KEY);
    let conversation = [];

    try {
        conversation = JSON.parse(
            sessionStorage.getItem(MESSAGES_KEY) || "[]"
        );

        if (!Array.isArray(conversation)) {
            conversation = [];
        }
    } catch {
        conversation = [];
    }

    function getPageContext() {
        const path = window.location.pathname;
        const title = document.title || "Trang học tiếng Anh";

        const unitMatch = (
            path.match(/unit[-_/]?(\d+)/i) ||
            path.match(/(?:^|\/)(\d+)(?:\/|$)/)
        );

        const unitFromElement = document.querySelector(
            "[data-unit], [data-current-unit]"
        );

        const unit = unitFromElement
            ? (
                unitFromElement.dataset.unit ||
                unitFromElement.dataset.currentUnit ||
                ""
            )
            : (unitMatch ? unitMatch[1] : "");

        let pageTitle = title
            .replace(/\s*[|–-]\s*English.*$/i, "")
            .trim();

        if (!pageTitle) {
            pageTitle = "Trang học tiếng Anh";
        }

        return {
            page_title: pageTitle,
            unit: unit ? `Unit ${unit}` : "",
            page_url: path
        };
    }

    function updateContextLabel() {
        const context = getPageContext();

        if (context.unit) {
            contextText.textContent =
                `${context.page_title} · ${context.unit}`;
        } else {
            contextText.textContent = context.page_title;
        }
    }

    function saveConversation() {
        sessionStorage.setItem(
            MESSAGES_KEY,
            JSON.stringify(conversation.slice(-60))
        );

        if (chatId) {
            sessionStorage.setItem(CHAT_ID_KEY, chatId);
        } else {
            sessionStorage.removeItem(CHAT_ID_KEY);
        }
    }

    function scrollToBottom() {
        messages.scrollTop = messages.scrollHeight;
    }

    function hideWelcome() {
        if (welcome) {
            welcome.style.display = "none";
        }
    }

    function showError(message) {
        errorBox.textContent = message;
        errorBox.classList.add("is-visible");
    }

    function clearError() {
        errorBox.textContent = "";
        errorBox.classList.remove("is-visible");
    }

    function createTutorAvatar() {
        const avatar = document.createElement("div");
        avatar.className = "ai-tutor-message-avatar";

        avatar.innerHTML = `
            <svg viewBox="0 0 100 100" aria-hidden="true">
                <circle cx="50" cy="50" r="48" fill="#f0edff"/>
                <path d="M18 91 Q20 66 50 65 Q80 66 82 91" fill="#7868d8"/>
                <path d="M38 61 L38 72 Q50 86 62 72 L62 61" fill="#f0bd98"/>
                <path d="M26 42 Q22 13 51 13 Q80 13 75 48 L70 63 Q64 76 50 76 Q34 75 29 60Z" fill="#51382f"/>
                <path d="M29 43 Q27 24 44 20 Q64 13 73 34 L70 48 Q65 35 54 33 Q42 44 29 43Z" fill="#51382f"/>
                <path d="M34 43 Q35 34 45 35 Q50 35 50 42 Q50 35 57 35 Q68 35 68 44 L66 56 Q63 68 50 69 Q37 68 34 56Z" fill="#f6c9a8"/>
                <circle cx="43" cy="48" r="2.2" fill="#302d43"/>
                <circle cx="59" cy="48" r="2.2" fill="#302d43"/>
                <path d="M46 58 Q50 61 55 58" fill="none" stroke="#b96e65" stroke-width="2" stroke-linecap="round"/>
                <rect x="30" y="40" width="17" height="14" rx="6" fill="none" stroke="#5c4db8" stroke-width="2.5"/>
                <rect x="53" y="40" width="17" height="14" rx="6" fill="none" stroke="#5c4db8" stroke-width="2.5"/>
                <path d="M47 46 H53" stroke="#5c4db8" stroke-width="2"/>
            </svg>
        `;

        return avatar;
    }

    function addMessage(role, text, save = true) {
        hideWelcome();

        const message = document.createElement("div");
        message.className = `ai-tutor-message ${role}`;

        if (role === "assistant") {
            message.appendChild(createTutorAvatar());
        }

        const bubble = document.createElement("div");
        bubble.className = "ai-tutor-bubble";
        bubble.textContent = text;

        message.appendChild(bubble);
        messages.appendChild(message);

        if (save) {
            conversation.push({
                role: role,
                text: text
            });

            saveConversation();
        }

        scrollToBottom();

        return message;
    }

    function addTypingIndicator() {
        const message = document.createElement("div");
        message.className = "ai-tutor-message assistant";
        message.id = "aiTutorTypingIndicator";

        message.appendChild(createTutorAvatar());

        const typing = document.createElement("div");
        typing.className = "ai-tutor-typing";

        for (let i = 0; i < 3; i++) {
            typing.appendChild(document.createElement("span"));
        }

        message.appendChild(typing);
        messages.appendChild(message);

        scrollToBottom();
    }

    function removeTypingIndicator() {
        const indicator = document.getElementById(
            "aiTutorTypingIndicator"
        );

        if (indicator) {
            indicator.remove();
        }
    }

    function renderSavedMessages() {
        if (!conversation.length) return;

        hideWelcome();

        conversation.forEach(function (item) {
            if (
                !item ||
                !["user", "assistant"].includes(item.role) ||
                typeof item.text !== "string"
            ) {
                return;
            }

            addMessage(item.role, item.text, false);
        });

        scrollToBottom();
    }

    function openPanel() {
        panel.classList.add("is-open");
        panel.setAttribute("aria-hidden", "false");
        launcher.setAttribute("aria-expanded", "true");

        setTimeout(function () {
            input.focus();
            scrollToBottom();
        }, 150);
    }

    function closePanel() {
        panel.classList.remove("is-open");
        panel.setAttribute("aria-hidden", "true");
        launcher.setAttribute("aria-expanded", "false");
    }

    function resetChat() {
        chatId = null;
        conversation = [];

        sessionStorage.removeItem(CHAT_ID_KEY);
        sessionStorage.removeItem(MESSAGES_KEY);

        messages.innerHTML = "";
        messages.appendChild(welcome);
        welcome.style.display = "";

        clearError();
        input.value = "";
        input.style.height = "auto";
        input.focus();
    }

    async function sendQuestion(question) {
        question = question.trim();

        if (!question || sendButton.disabled) return;

        if (question.length > 2000) {
            showError("Câu hỏi không được vượt quá 2000 ký tự.");
            return;
        }

        clearError();

        addMessage("user", question);

        input.value = "";
        input.style.height = "auto";

        sendButton.disabled = true;
        addTypingIndicator();

        try {
            const response = await fetch(apiUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                body: JSON.stringify({
                    question: question,
                    chat_id: chatId ? Number(chatId) : null,
                    context: getPageContext()
                })
            });

            const data = await response.json();

            removeTypingIndicator();

            if (!response.ok) {
                throw new Error(
                    data.error || "Không thể gửi câu hỏi. Bạn thử lại nhé!"
                );
            }

            if (!data.answer) {
                throw new Error("Gia sư chưa trả về câu trả lời.");
            }

            chatId = data.chat_id
                ? String(data.chat_id)
                : chatId;

            addMessage("assistant", data.answer);
            saveConversation();

        } catch (error) {
            removeTypingIndicator();

            showError(
                error.message ||
                "Không thể kết nối với gia sư. Bạn thử lại sau nhé!"
            );

        } finally {
            sendButton.disabled = false;
            input.focus();
        }
    }

    launcher.addEventListener("click", function () {
        if (panel.classList.contains("is-open")) {
            closePanel();
        } else {
            openPanel();
        }
    });

    closeButton.addEventListener("click", closePanel);

    newChatButton.addEventListener("click", function () {
        resetChat();
    });

    form.addEventListener("submit", function (event) {
        event.preventDefault();
        sendQuestion(input.value);
    });

    input.addEventListener("input", function () {
        input.style.height = "auto";
        input.style.height = `${Math.min(input.scrollHeight, 100)}px`;
    });

    input.addEventListener("keydown", function (event) {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            form.requestSubmit();
        }
    });

    document.querySelectorAll(
        "#aiTutorWidget [data-question]"
    ).forEach(function (button) {
        button.addEventListener("click", function () {
            input.value = button.dataset.question || "";
            input.focus();
            input.dispatchEvent(new Event("input"));
        });
    });

    document.addEventListener("keydown", function (event) {
        if (
            event.key === "Escape" &&
            panel.classList.contains("is-open")
        ) {
            closePanel();
        }
    });

    updateContextLabel();
    renderSavedMessages();
});