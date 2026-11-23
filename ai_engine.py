
import requests
import json
import re

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL_NAME = "qwen2.5:3b"

SYSTEM_PROMPT = """
Bạn là gia sư AI chuyên dạy tiếng Anh lớp 7 theo chương trình Global Success.

Nhiệm vụ:
- Giải thích ngữ pháp, từ vựng, đọc hiểu và các kiến thức tiếng Anh lớp 7.
- Giải thích lỗi sai rõ ràng, dễ hiểu, phù hợp với học sinh lớp 7.
- Hướng dẫn từng bước, không chỉ đưa đáp án.
- Có thể tạo bài tập luyện tập theo chủ điểm khi học sinh yêu cầu.
- Khuyến khích học sinh tự suy nghĩ trước khi xem đáp án.
- Sử dụng tiếng Việt để giải thích, giữ nguyên các ví dụ tiếng Anh.
- Trình bày rõ ràng, ngắn gọn, thân thiện.
- Không tự nhận nội dung chưa được cung cấp là học liệu chính thức của sách.
"""


def ask_ai(question, history=None):
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]

    if history:
        for item in history:
            messages.append({
                "role": "user",
                "content": item.question
            })

            if item.answer:
                messages.append({
                    "role": "assistant",
                    "content": item.answer
                })

    messages.append({
        "role": "user",
        "content": question
    })

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "messages": messages,
                "stream": False
            },
            timeout=180
        )

        response.raise_for_status()
        data = response.json()

        return data["message"]["content"].strip()

    except requests.exceptions.Timeout:
        return "AI đang mất nhiều thời gian xử lý. Bạn hãy thử lại nhé."

    except requests.exceptions.ConnectionError:
        return "Không thể kết nối Ollama. Hãy kiểm tra Ollama đã được khởi động chưa."

    except (
        requests.exceptions.RequestException,
        KeyError,
        ValueError
    ) as error:
        print("AI ERROR:", error)
        return "Đã xảy ra lỗi khi xử lý câu hỏi. Bạn hãy thử lại nhé."


def evaluate_writing(user_text, unit):
    prompt = f"""
Đánh giá bài Writing tiếng Anh lớp 7 theo chương trình Global Success.

THÔNG TIN:
Unit: {unit.unit}
Chủ đề: {unit.topic or unit.writing_topic or "Không có thông tin"}
Dạng bài: {unit.writing_type or "Writing"}
Yêu cầu: {unit.writing_prompt or "Đánh giá theo chủ đề"}
Ngữ pháp trọng tâm: {unit.grammar_focus or "Ngữ pháp lớp 7"}

BÀI VIẾT:
{user_text}

Chấm 5 tiêu chí, mỗi tiêu chí từ 0 đến 2 điểm:
- task_score: Hoàn thành yêu cầu đề bài.
- organization_score: Bố cục và liên kết.
- grammar_score: Ngữ pháp.
- vocabulary_score: Từ vựng.
- spelling_score: Chính tả và dấu câu.

total_score là tổng 5 điểm trên, tối đa 10.

Viết feedback bằng tiếng Việt, ngắn gọn, phù hợp học sinh lớp 7.
Feedback cần có:
- Hai điểm tốt của bài viết.
- Tối đa 3 lỗi quan trọng. Với mỗi lỗi, trích phần sai và đưa câu sửa bằng tiếng Anh.
- Hai lời khuyên cải thiện.

Không bịa lỗi. Chấm công bằng theo nội dung thực tế.
Không viết lại toàn bộ bài văn.
Không tạo bài mẫu.
Không dùng Markdown.

Chỉ trả về JSON hợp lệ theo cấu trúc:
{{
    "task_score": 0,
    "organization_score": 0,
    "grammar_score": 0,
    "vocabulary_score": 0,
    "spelling_score": 0,
    "total_score": 0,
    "feedback": "Nhận xét ngắn gọn bằng tiếng Việt"
}}
"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Bạn là giáo viên tiếng Anh lớp 7. "
                            "Đánh giá công bằng và chỉ trả về JSON hợp lệ."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.1,
                    "num_ctx": 2048,
                    "num_predict": 450
                },
                "keep_alive": "5m"
            },
            timeout=(10, 120)
        )

        response.raise_for_status()

        data = response.json()
        content = data.get("message", {}).get("content", "").strip()

        if not content:
            print("WRITING AI ERROR: Ollama trả về nội dung rỗng.")
            return None

        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", content)

            if not match:
                print("WRITING AI ERROR: Không tìm thấy JSON hợp lệ.")
                print("AI RESPONSE:", content)
                return None

            result = json.loads(match.group(0))

        score_fields = [
            "task_score",
            "organization_score",
            "grammar_score",
            "vocabulary_score",
            "spelling_score"
        ]

        scores = {}

        for field in score_fields:
            value = result.get(field)

            if value is None:
                raise ValueError(f"Thiếu trường điểm: {field}")

            score = float(value)

            if not 0 <= score <= 2:
                raise ValueError(
                    f"Điểm {field} không nằm trong khoảng 0-2."
                )

            scores[field] = round(score, 1)

        feedback = str(result.get("feedback", "")).strip()

        if not feedback:
            raise ValueError("AI không trả về nhận xét.")

        total_score = round(sum(scores.values()), 1)

        return {
            **scores,
            "total_score": total_score,
            "feedback": feedback
        }

    except requests.exceptions.Timeout:
        print("WRITING AI ERROR: Ollama vượt quá thời gian chờ 120 giây.")
        return None

    except requests.exceptions.ConnectionError as error:
        print("WRITING AI CONNECTION ERROR:", error)
        return None

    except requests.exceptions.RequestException as error:
        print("WRITING AI REQUEST ERROR:", error)
        return None

    except (
        KeyError,
        ValueError,
        TypeError,
        json.JSONDecodeError
    ) as error:
        print("WRITING AI DATA ERROR:", error)
        return None

    except Exception as error:
        print("WRITING AI UNKNOWN ERROR:", error)
        return None


def evaluate_speaking(transcript, topic):
    if not transcript or not transcript.strip():
        return None

    prompt = f"""
Bạn là giáo viên tiếng Anh lớp 7 theo chương trình Global Success.

Đánh giá bài nói của học sinh dựa trên bản chuyển giọng nói thành văn bản.

CHỦ ĐỀ: {topic.title}
NỘI DUNG YÊU CẦU: {topic.prompt}
TỪ VỰNG GỢI Ý: {topic.suggested_vocabulary or "Không có"}

BẢN CHÉP LỜI HỌC SINH:
{transcript}

Chấm 3 tiêu chí, mỗi tiêu chí từ 0 đến 100:
- fluency_score: Mức độ mạch lạc, liên kết và phát triển ý trong câu trả lời dựa trên văn bản.
- vocabulary_score: Mức độ phù hợp, đa dạng và chính xác của từ vựng.
- grammar_score: Độ chính xác của ngữ pháp và cấu trúc câu.

Không đánh giá phát âm, tốc độ nói, ngữ điệu hoặc độ rõ giọng nói vì chỉ có bản chép lời.
Không tự suy đoán những lỗi không thể xác định từ văn bản.
Điểm tổng là trung bình cộng của 3 tiêu chí trên.

Viết feedback bằng tiếng Việt, phù hợp học sinh lớp 7, gồm:
- Nhận xét mức độ hoàn thành chủ đề.
- Điểm tốt.
- Các lỗi quan trọng và cách sửa.
- Lời khuyên cải thiện.

Không dùng Markdown. Không viết lại toàn bộ câu trả lời.

Chỉ trả về JSON hợp lệ:
{{
    "fluency_score": 0,
    "vocabulary_score": 0,
    "grammar_score": 0,
    "overall_score": 0,
    "feedback": "Nhận xét bằng tiếng Việt"
}}
"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Bạn là giáo viên tiếng Anh lớp 7. "
                            "Chấm công bằng và chỉ trả về JSON hợp lệ."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.1,
                    "num_ctx": 2048,
                    "num_predict": 350
                },
                "keep_alive": "5m"
            },
            timeout=(10, 120)
        )

        response.raise_for_status()

        content = response.json().get(
            "message", {}
        ).get("content", "").strip()

        if not content:
            print("SPEAKING AI ERROR: Nội dung trả về rỗng.")
            return None

        result = json.loads(content)

        fields = [
            "fluency_score",
            "vocabulary_score",
            "grammar_score"
        ]

        scores = {}

        for field in fields:
            value = float(result[field])

            if not 0 <= value <= 100:
                raise ValueError(
                    f"Điểm {field} không nằm trong khoảng 0-100."
                )

            scores[field] = round(value, 1)

        feedback = str(result.get("feedback", "")).strip()

        if not feedback:
            raise ValueError("AI không trả về nhận xét.")

        overall_score = round(sum(scores.values()) / 3, 1)

        return {
            **scores,
            "overall_score": overall_score,
            "feedback": feedback
        }

    except requests.exceptions.Timeout:
        print("SPEAKING AI ERROR: Ollama vượt quá 120 giây.")
        return None

    except requests.exceptions.RequestException as error:
        print("SPEAKING AI REQUEST ERROR:", error)
        return None

    except (
        KeyError,
        ValueError,
        TypeError,
        json.JSONDecodeError
    ) as error:
        print("SPEAKING AI DATA ERROR:", error)
        return None

    except Exception as error:
        print("SPEAKING AI UNKNOWN ERROR:", error)
        return None


def evaluate_reading(passage, results, percentage):
    if not results:
        return None

    try:
        question_data = []

        for index, item in enumerate(results, start=1):
            question = item["question"]

            options = {
                "A": question.option_a,
                "B": question.option_b,
                "C": question.option_c,
                "D": question.option_d
            }

            user_answer = (item.get("user_answer") or "").strip()
            correct_answer = (question.correct_answer or "").strip()

            if question.question_type in (
                "true_false_not_given",
                "true_false",
                "tfng"
            ):
                labels = {
                    "T": "True",
                    "TRUE": "True",
                    "F": "False",
                    "FALSE": "False",
                    "NG": "Not Given",
                    "NOT GIVEN": "Not Given"
                }

                display_user = labels.get(
                    user_answer.upper(),
                    user_answer or "Chưa trả lời"
                )

                display_correct = labels.get(
                    correct_answer.upper(),
                    correct_answer
                )
            else:
                display_user = options.get(
                    user_answer.upper(),
                    user_answer or "Chưa trả lời"
                )

                display_correct = options.get(
                    correct_answer.upper(),
                    correct_answer
                )

            question_data.append({
                "number": index,
                "question": question.question_text,
                "user_answer": display_user,
                "correct_answer": display_correct,
                "is_correct": bool(item.get("is_correct"))
            })

        passage_content = (passage.content or "")[:3000]

        prompt = f"""
Bạn là gia sư tiếng Anh lớp 7 theo chương trình Global Success.

Hãy đánh giá kết quả Reading dựa trên dữ liệu thực tế.

BÀI ĐỌC:
{passage.title}
{passage_content}

KẾT QUẢ:
Điểm: {percentage}%
Số câu: {len(results)}

CHI TIẾT CÂU TRẢ LỜI:
{json.dumps(question_data, ensure_ascii=False)}

YÊU CẦU:
1. Strengths: tối đa 2 điểm mạnh, dựa trên câu đúng.
2. Weaknesses: tối đa 2 điểm cần cải thiện, dựa trên câu sai.
3. Feedback: 1-2 câu nhận xét tổng quan bằng tiếng Việt.
4. Recommendations: tối đa 2 lời khuyên luyện tập cụ thể.

Không bịa lỗi hoặc suy đoán năng lực ngoài dữ liệu.
Không lặp lại cùng một nhận xét.
Nếu học sinh đúng toàn bộ, hãy ghi nhận điểm mạnh và đề xuất nâng cao.
Nếu học sinh sai toàn bộ, tập trung vào những kỹ năng cần luyện tập.

Chỉ trả về JSON hợp lệ, không có Markdown hay nội dung bên ngoài:
{{
    "strengths": ["Điểm mạnh"],
    "weaknesses": ["Điểm cần cải thiện"],
    "feedback": "Nhận xét tổng quan",
    "recommendations": ["Lời khuyên"]
}}
"""

        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Bạn là gia sư tiếng Anh lớp 7. "
                            "Trả lời bằng tiếng Việt. "
                            "Chỉ xuất một JSON object hoàn chỉnh. "
                            "Không viết giải thích bên ngoài JSON."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.1,
                    "num_ctx": 4096,
                    "num_predict": 500
                },
                "keep_alive": "5m"
            },
            timeout=(5, 120)
        )

        response.raise_for_status()

        data = response.json()

        content = data.get(
            "message", {}
        ).get("content", "").strip()

        if not content:
            print("READING AI ERROR: Ollama trả về nội dung rỗng.")
            return None

        if data.get("done_reason") == "length":
            print("READING AI ERROR: Phản hồi bị giới hạn token.")

        try:
            result = json.loads(content)

        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", content)

            if not match:
                print("READING AI ERROR: JSON không hoàn chỉnh.")
                print("AI RESPONSE:", content[:2000])
                return None

            result = json.loads(match.group(0))

        if not isinstance(result, dict):
            raise ValueError("Kết quả AI không phải JSON object.")

        def clean_list(value, limit=2):
            if not isinstance(value, list):
                return []

            cleaned = []
            seen = set()

            for item in value:
                text = str(item).strip()

                if not text:
                    continue

                key = text.casefold()

                if key in seen:
                    continue

                seen.add(key)
                cleaned.append(text)

                if len(cleaned) >= limit:
                    break

            return cleaned

        feedback = str(
            result.get("feedback", "")
        ).strip()

        if not feedback:
            raise ValueError("AI không trả về nhận xét tổng quan.")

        return {
            "strengths": clean_list(
                result.get("strengths")
            ),
            "weaknesses": clean_list(
                result.get("weaknesses")
            ),
            "feedback": feedback,
            "recommendations": clean_list(
                result.get("recommendations")
            )
        }

    except requests.exceptions.Timeout:
        print("READING AI ERROR: Ollama vượt quá 120 giây.")
        return None

    except requests.exceptions.ConnectionError as error:
        print("READING AI CONNECTION ERROR:", error)
        return None

    except requests.exceptions.HTTPError as error:
        print("READING AI HTTP ERROR:", error)
        return None

    except requests.exceptions.RequestException as error:
        print("READING AI REQUEST ERROR:", error)
        return None

    except (
        KeyError,
        ValueError,
        TypeError,
        json.JSONDecodeError
    ) as error:
        print("READING AI DATA ERROR:", error)
        return None

    except Exception as error:
        print("READING AI UNKNOWN ERROR:", error)
        return None


def evaluate_grammar(unit, results, percentage):
    """
    AI phân tích kết quả bài luyện tập Grammar.
    Chỉ đưa ra nhận xét dựa trên câu hỏi và đáp án thực tế.
    """

    question_details = []

    for index, item in enumerate(results, start=1):
        question = item["question"]

        options = {}

        if question.question_type == "multiple_choice":
            options = {
                "A": question.option_a,
                "B": question.option_b,
                "C": question.option_c,
                "D": question.option_d
            }

        question_details.append({
            "number": index,
            "topic": question.topic,
            "question_type": question.question_type,
            "question": question.question_text,
            "options": options,
            "user_answer": item["user_answer"] or "Chưa trả lời",
            "correct_answer": question.correct_answer,
            "is_correct": item["is_correct"],
            "explanation": question.explanation or ""
        })

    prompt = f"""
Bạn là giáo viên tiếng Anh THCS, chuyên dạy ngữ pháp lớp 7
theo chương trình Global Success.

Hãy phân tích kết quả luyện tập Grammar của học sinh.

THÔNG TIN:
- Unit: {unit}
- Độ chính xác: {percentage}%
- Chi tiết bài làm:
{json.dumps(question_details, ensure_ascii=False, indent=2)}

YÊU CẦU:
1. Strengths: tối đa 3 điểm mạnh dựa trên câu đúng.
2. Weaknesses: tối đa 3 điểm cần cải thiện dựa trên câu sai.
3. Feedback: nhận xét tổng quan ngắn gọn từ 1 đến 3 câu.
4. Recommendations: tối đa 3 lời khuyên ôn tập cụ thể.

NGUYÊN TẮC:
- Chỉ nhận xét dựa trên dữ liệu bài làm.
- Không tự suy diễn kiến thức học sinh chưa được kiểm tra.
- Không lặp lại cùng một nhận xét.
- Nếu học sinh làm đúng tất cả, ghi nhận và đề xuất cách nâng cao.

Trả lời bằng JSON hợp lệ, không có Markdown:
{{
    "strengths": ["Điểm mạnh 1"],
    "weaknesses": ["Điểm cần cải thiện 1"],
    "feedback": "Nhận xét tổng quan",
    "recommendations": ["Lời khuyên 1"]
}}
"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Bạn là giáo viên tiếng Anh lớp 7. "
                            "Luôn trả lời bằng JSON hợp lệ theo yêu cầu."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "format": "json",
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_ctx": 4096,
                    "num_predict": 500
                },
                "keep_alive": "5m"
            },
            timeout=(5, 120)
        )

        response.raise_for_status()

        data = response.json()
        content = data.get("message", {}).get("content", "").strip()

        if not content:
            print("[Grammar AI] Phản hồi rỗng.")
            return None

        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", content)

            if not match:
                print("[Grammar AI] Phản hồi không có JSON hợp lệ:", content)
                return None

            result = json.loads(match.group())

        def clean_list(value):
            if not isinstance(value, list):
                return []

            cleaned = []

            for item in value:
                if isinstance(item, str) and item.strip():
                    text = item.strip()

                    if text not in cleaned:
                        cleaned.append(text)

            return cleaned[:3]

        return {
            "strengths": clean_list(result.get("strengths")),
            "weaknesses": clean_list(result.get("weaknesses")),
            "feedback": str(result.get("feedback", "")).strip(),
            "recommendations": clean_list(
                result.get("recommendations")
            )
        }

    except requests.exceptions.Timeout:
        print("[Grammar AI] Hết thời gian chờ phản hồi.")

    except requests.exceptions.ConnectionError:
        print("[Grammar AI] Không kết nối được Ollama.")

    except requests.exceptions.RequestException as error:
        print(f"[Grammar AI] Lỗi request: {error}")

    except (
        ValueError,
        TypeError,
        KeyError,
        json.JSONDecodeError
    ) as error:
        print(f"[Grammar AI] Lỗi xử lý dữ liệu: {error}")

    except Exception as error:
        print(f"[Grammar AI] Lỗi không xác định: {error}")

    return None


def evaluate_vocabulary(unit, results, percentage):
    """
    AI phân tích kết quả bài luyện tập Vocabulary.
    Đánh giá dựa trên từ vựng, dạng bài và câu trả lời thực tế.
    """

    if not results:
        return None

    question_details = []

    for index, item in enumerate(results, start=1):
        question = item["question"]

        question_type = getattr(
            question, "question_type", ""
        )

        options = {}

        if question_type == "multiple_choice":
            options = {
                "A": getattr(question, "option_a", "") or "",
                "B": getattr(question, "option_b", "") or "",
                "C": getattr(question, "option_c", "") or "",
                "D": getattr(question, "option_d", "") or ""
            }

        question_details.append({
            "number": index,
            "word": getattr(question, "word", "") or "",
            "topic": getattr(question, "topic", "") or "",
            "question_type": question_type,
            "question": getattr(question, "question_text", "") or "",
            "options": options,
            "user_answer": item.get("user_answer") or "Chưa trả lời",
            "correct_answer": getattr(question, "correct_answer", "") or "",
            "is_correct": bool(item.get("is_correct")),
            "explanation": getattr(question, "explanation", "") or "",
            "difficulty": getattr(question, "difficulty", "basic") or "basic"
        })

    prompt = f"""
Bạn là giáo viên tiếng Anh THCS, chuyên dạy từ vựng lớp 7
theo chương trình Global Success.

Hãy phân tích kết quả luyện tập Vocabulary của học sinh.

THÔNG TIN:
- Unit: {unit}
- Điểm chính xác: {percentage}%
- Số câu: {len(results)}

CHI TIẾT BÀI LÀM:
{json.dumps(question_details, ensure_ascii=False, indent=2)}

NHIỆM VỤ:

1. Strengths:
Xác định tối đa 3 điểm mạnh dựa trên những câu học sinh trả lời đúng.

2. Weaknesses:
Xác định tối đa 3 điểm cần cải thiện dựa trên những câu trả lời sai.
Chú ý các dạng bài và nhóm từ học sinh còn nhầm lẫn.

3. Feedback:
Đưa ra nhận xét tổng quan bằng tiếng Việt, ngắn gọn,
phù hợp với học sinh lớp 7.

4. Recommendations:
Đề xuất tối đa 3 cách ôn tập cụ thể.
Có thể gợi ý học lại nghĩa từ, cách sử dụng từ trong câu,
dạng từ hoặc từ vựng theo ngữ cảnh nếu dữ liệu cho thấy cần thiết.

NGUYÊN TẮC:
- Chỉ phân tích những gì thể hiện trong dữ liệu.
- Không tự suy diễn những từ học sinh chưa được kiểm tra.
- Không bịa lỗi hoặc nhận xét chung chung.
- Không nhầm lẫn giữa câu chưa trả lời và câu trả lời sai.
- Nếu học sinh đúng tất cả, ghi nhận kết quả và đề xuất nâng cao.
- Nếu học sinh sai nhiều, ưu tiên những nội dung cần ôn tập.
- Không đưa ra đáp án mới hoặc tạo bài tập mới.

Chỉ trả về JSON hợp lệ, không sử dụng Markdown:

{{
    "strengths": ["Điểm mạnh 1"],
    "weaknesses": ["Điểm cần cải thiện 1"],
    "feedback": "Nhận xét tổng quan bằng tiếng Việt.",
    "recommendations": ["Lời khuyên ôn tập 1"]
}}

Mỗi danh sách tối đa 3 ý.
"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Bạn là giáo viên tiếng Anh lớp 7. "
                            "Phân tích kết quả học tập công bằng. "
                            "Chỉ trả về một JSON object hợp lệ bằng tiếng Việt."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "format": "json",
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_ctx": 4096,
                    "num_predict": 500
                },
                "keep_alive": "5m"
            },
            timeout=(5, 120)
        )

        response.raise_for_status()

        data = response.json()
        content = data.get(
            "message", {}
        ).get("content", "").strip()

        if not content:
            print("[Vocabulary AI] Ollama trả về nội dung rỗng.")
            return None

        try:
            result = json.loads(content)

        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", content)

            if not match:
                print("[Vocabulary AI] Không tìm thấy JSON hợp lệ.")
                print("AI RESPONSE:", content[:2000])
                return None

            result = json.loads(match.group(0))

        if not isinstance(result, dict):
            raise ValueError("Kết quả AI không phải JSON object.")

        def clean_list(value):
            if not isinstance(value, list):
                return []

            cleaned = []
            seen = set()

            for item in value:
                if not isinstance(item, str):
                    continue

                text = item.strip()

                if not text:
                    continue

                key = text.casefold()

                if key not in seen:
                    seen.add(key)
                    cleaned.append(text)

                if len(cleaned) == 3:
                    break

            return cleaned

        feedback = str(
            result.get("feedback", "")
        ).strip()

        if not feedback:
            raise ValueError("AI không trả về nhận xét.")

        return {
            "strengths": clean_list(
                result.get("strengths")
            ),
            "weaknesses": clean_list(
                result.get("weaknesses")
            ),
            "feedback": feedback,
            "recommendations": clean_list(
                result.get("recommendations")
            )
        }

    except requests.exceptions.Timeout:
        print("[Vocabulary AI] Ollama vượt quá thời gian chờ 120 giây.")

    except requests.exceptions.ConnectionError as error:
        print("[Vocabulary AI] Không kết nối được Ollama:", error)

    except requests.exceptions.RequestException as error:
        print("[Vocabulary AI] Lỗi request:", error)

    except (
        KeyError,
        ValueError,
        TypeError,
        json.JSONDecodeError
    ) as error:
        print("[Vocabulary AI] Lỗi xử lý dữ liệu:", error)

    except Exception as error:
        print("[Vocabulary AI] Lỗi không xác định:", error)

    return None

def evaluate_placement(skill_scores, percentage, level, total_questions):
    """
    AI phân tích kết quả kiểm tra đầu vào.
    Điểm số do Python tính; AI chỉ phân tích và đề xuất.
    """

    if not skill_scores:
        return None

    skill_names = {
        "vocabulary": "Từ vựng",
        "grammar": "Ngữ pháp",
        "reading": "Đọc hiểu",
        "listening": "Nghe",
        "speaking": "Nói",
        "writing": "Viết",
        "general": "Kiến thức tổng hợp"
    }

    skill_data = []

    for skill, values in skill_scores.items():
        correct = int(values.get("correct", 0))
        total = int(values.get("total", 0))

        if total <= 0:
            continue

        score = round(correct / total * 100, 2)

        skill_data.append({
            "skill": skill,
            "skill_name": skill_names.get(skill, skill),
            "correct": correct,
            "total": total,
            "score": score
        })

    if not skill_data:
        return None

    prompt = f"""
Bạn là chuyên gia đánh giá năng lực tiếng Anh THCS,
chuyên hỗ trợ học sinh lớp 7 theo chương trình Global Success.

Hãy phân tích kết quả bài kiểm tra đầu vào dưới đây.

KẾT QUẢ TỔNG QUAN:
- Điểm tổng: {percentage}%
- Trình độ sơ bộ do hệ thống phân loại: {level}
- Tổng số câu hỏi: {total_questions}

KẾT QUẢ TỪNG KỸ NĂNG:
{json.dumps(skill_data, ensure_ascii=False, indent=2)}

NHIỆM VỤ:

1. strengths:
Nêu tối đa 3 điểm mạnh, dựa trên kỹ năng có kết quả tốt.

2. weaknesses:
Nêu tối đa 3 điểm yếu, dựa trên kỹ năng có kết quả thấp.
Không suy diễn kiến thức chưa được kiểm tra.

3. feedback:
Viết nhận xét tổng quan từ 2 đến 4 câu.
Giải thích ngắn gọn năng lực hiện tại của học sinh.

4. skill_analysis:
Với từng kỹ năng xuất hiện trong dữ liệu, đưa ra một nhận xét ngắn.
Chỉ nhận xét các kỹ năng đã được kiểm tra.

5. recommendations:
Đề xuất tối đa 3 nội dung học sinh nên ưu tiên ôn tập.

6. learning_path:
Đề xuất lộ trình học gồm 3 giai đoạn:
- foundation: Nội dung cần củng cố trước.
- practice: Nội dung cần luyện tập tiếp theo.
- development: Nội dung nâng cao sau khi đã củng cố kiến thức.

NGUYÊN TẮC:
- Không thay đổi điểm số được cung cấp.
- Không tự tạo điểm cho kỹ năng chưa được kiểm tra.
- Không khẳng định học sinh yếu kỹ năng nghe, nói hoặc viết nếu không có dữ liệu.
- Không đưa ra nhận xét mâu thuẫn với kết quả.
- Sử dụng tiếng Việt dễ hiểu, phù hợp học sinh lớp 7.
- Đề xuất nội dung học tập cụ thể, tránh lời khuyên chung chung.
- Trình độ sơ bộ chỉ là căn cứ tham khảo từ bài kiểm tra hiện tại.

Chỉ trả về JSON hợp lệ, không dùng Markdown:

{{
    "strengths": ["Điểm mạnh"],
    "weaknesses": ["Điểm cần cải thiện"],
    "feedback": "Nhận xét tổng quan",
    "skill_analysis": [
        {{
            "skill": "vocabulary",
            "comment": "Nhận xét kỹ năng"
        }}
    ],
    "recommendations": ["Nội dung cần ôn tập"],
    "learning_path": {{
        "foundation": ["Kiến thức nền tảng"],
        "practice": ["Nội dung luyện tập"],
        "development": ["Nội dung phát triển"]
    }}
}}
"""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Bạn là chuyên gia đánh giá năng lực "
                            "tiếng Anh lớp 7. Phân tích công bằng, "
                            "không suy diễn dữ liệu. "
                            "Chỉ trả về JSON hợp lệ bằng tiếng Việt."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.1,
                    "num_ctx": 4096,
                    "num_predict": 700
                },
                "keep_alive": "5m"
            },
            timeout=(10, 150)
        )

        response.raise_for_status()

        data = response.json()
        content = data.get(
            "message", {}
        ).get("content", "").strip()

        if not content:
            print("[Placement AI] Ollama trả về nội dung rỗng.")
            return None

        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", content)

            if not match:
                print("[Placement AI] Không tìm thấy JSON hợp lệ.")
                print("AI RESPONSE:", content[:2000])
                return None

            result = json.loads(match.group(0))

        if not isinstance(result, dict):
            raise ValueError("Kết quả AI không phải JSON object.")

        def clean_list(value, limit=3):
            if not isinstance(value, list):
                return []

            cleaned = []
            seen = set()

            for item in value:
                if not isinstance(item, str):
                    continue

                text = item.strip()

                if not text:
                    continue

                key = text.casefold()

                if key not in seen:
                    seen.add(key)
                    cleaned.append(text)

                if len(cleaned) >= limit:
                    break

            return cleaned

        feedback = str(
            result.get("feedback", "")
        ).strip()

        if not feedback:
            raise ValueError("AI không trả về nhận xét tổng quan.")

        # Điểm kỹ năng luôn lấy từ kết quả Python tính toán.
        # AI chỉ cung cấp phần nhận xét.
        ai_skill_comments = result.get("skill_analysis", [])

        comment_map = {}

        if isinstance(ai_skill_comments, list):
            for item in ai_skill_comments:
                if isinstance(item, dict):
                    skill = str(item.get("skill", "")).strip()
                    comment = str(item.get("comment", "")).strip()

                    if skill and comment:
                        comment_map[skill] = comment

        final_skill_analysis = []

        for item in skill_data:
            final_skill_analysis.append({
                **item,
                "comment": comment_map.get(
                    item["skill"],
                    "Chưa có nhận xét chi tiết cho kỹ năng này."
                )
            })

        learning_path = result.get("learning_path", {})

        if not isinstance(learning_path, dict):
            learning_path = {}

        return {
            "percentage": percentage,
            "level": level,
            "strengths": clean_list(result.get("strengths")),
            "weaknesses": clean_list(result.get("weaknesses")),
            "feedback": feedback,
            "skill_analysis": final_skill_analysis,
            "recommendations": clean_list(
                result.get("recommendations")
            ),
            "learning_path": {
                "foundation": clean_list(
                    learning_path.get("foundation")
                ),
                "practice": clean_list(
                    learning_path.get("practice")
                ),
                "development": clean_list(
                    learning_path.get("development")
                )
            }
        }

    except requests.exceptions.Timeout:
        print("[Placement AI] Ollama vượt quá thời gian chờ.")

    except requests.exceptions.ConnectionError as error:
        print("[Placement AI] Không kết nối được Ollama:", error)

    except requests.exceptions.RequestException as error:
        print("[Placement AI] Lỗi request:", error)

    except (
        KeyError,
        ValueError,
        TypeError,
        json.JSONDecodeError
    ) as error:
        print("[Placement AI] Lỗi xử lý dữ liệu:", error)

    except Exception as error:
        print("[Placement AI] Lỗi không xác định:", error)

    return None
