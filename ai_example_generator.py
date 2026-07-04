# ai_example_generator.py
# -*- coding: utf-8 -*-

"""
AI 範例產生器：Gemini / GPT / Claude 前端切換版

這個檔案只負責：
1. 建立 prompt
2. 依照 provider 呼叫 Gemini / OpenAI GPT / Claude
3. 做簡單危險語句檢查
4. 回傳可寫入 functions.db 的範例程式碼

API Key 可以由前端傳入，也可以從 .env 讀取：
- Gemini: GEMINI_API_KEY
- GPT / OpenAI: OPENAI_API_KEY
- Claude: ANTHROPIC_API_KEY
"""

import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


DEFAULT_MODELS = {
    "gemini": "gemini-2.5-flash",
    "openai": "gpt-5.5",
    "claude": "claude-sonnet-4-5",
}


PROVIDER_ENV_KEYS = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
}


PROVIDER_DISPLAY_NAMES = {
    "gemini": "Gemini",
    "openai": "GPT / OpenAI",
    "claude": "Claude",
}


DANGEROUS_PATTERNS = [
    r"os\.remove",
    r"os\.rmdir",
    r"shutil\.rmtree",
    r"subprocess\.",
    r"eval\(",
    r"exec\(",
    r"while\s+True",
    r"format\s+c:",
    r"rm\s+-rf",
    r"DROP\s+TABLE",
    r"DELETE\s+FROM",
]


@dataclass
class AIExampleResult:
    ok: bool
    code: str
    message: str = ""


def normalize_provider(provider):
    """
    將前端傳來的 provider 名稱標準化。
    """

    value = (provider or "").strip().lower()

    if value in {"gemini", "google", "google gemini"}:
        return "gemini"

    if value in {"openai", "gpt", "chatgpt", "gpt / openai"}:
        return "openai"

    if value in {"claude", "anthropic"}:
        return "claude"

    return value


def get_default_model(provider):
    provider = normalize_provider(provider)
    return DEFAULT_MODELS.get(provider, "")


def get_env_key_name(provider):
    provider = normalize_provider(provider)
    return PROVIDER_ENV_KEYS.get(provider, "")


def load_api_key(provider, api_key_from_ui=""):
    """
    優先使用前端輸入的 API Key。
    如果前端沒有輸入，才讀取 .env / 環境變數。
    """

    provider = normalize_provider(provider)

    if api_key_from_ui and api_key_from_ui.strip():
        return api_key_from_ui.strip()

    load_dotenv()

    env_key = get_env_key_name(provider)

    if not env_key:
        return ""

    return os.getenv(env_key, "").strip()


def save_api_key_to_env(provider, api_key, env_path=".env"):
    """
    將前端輸入的 API Key 存到 .env。

    注意：
    .env 是純文字檔，不要上傳到 GitHub，也不要分享給別人。
    """

    provider = normalize_provider(provider)
    env_key = get_env_key_name(provider)

    if not env_key:
        return False, "不支援的 AI 服務。"

    api_key = (api_key or "").strip()

    if not api_key:
        return False, "API Key 是空的，沒有儲存。"

    path = Path(env_path)

    lines = []

    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()

    updated = False
    new_lines = []

    for line in lines:
        if line.startswith(f"{env_key}="):
            new_lines.append(f"{env_key}={api_key}")
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        new_lines.append(f"{env_key}={api_key}")

    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    return True, f"已儲存到 .env：{env_key}"


def strip_markdown_code_fence(text):
    """
    AI 有時會回傳 ```python ... ```。
    這裡只保留程式碼內容。
    """

    text = (text or "").strip()

    pattern = r"^```(?:python|py)?\s*(.*?)\s*```$"
    match = re.match(pattern, text, flags=re.DOTALL | re.IGNORECASE)

    if match:
        return match.group(1).strip()

    return text


def looks_dangerous(code):
    """
    簡單檢查是否包含危險語句。
    這不是完整安全沙盒，只是防呆。
    """

    lowered = (code or "").lower()

    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, lowered, flags=re.IGNORECASE):
            return True, pattern

    return False, ""


def build_prompt(name, package, category, description_zh, description_en, source_anchor):
    """
    建立給 AI 的提示詞。
    """

    description = description_zh or description_en or "無說明"

    return f"""
你是 Python 教學助教。請為下列 Python 套件 / 函式產生一個「適合初學者」的範例程式碼。

套件 / 型別：{package}
函式 / 類別 / 方法：{name}
分類：{category}
文件錨點：{source_anchor}
說明：
{description}

要求：
1. 只回傳 Python 程式碼，不要 Markdown，不要 ```。
2. 使用繁體中文註解。
3. 範例盡量 5 到 20 行。
4. 程式碼要可以直接閱讀，盡量可以直接執行。
5. 不要使用 os.remove、shutil.rmtree、subprocess、eval、exec。
6. 不要產生刪除檔案、格式化磁碟、系統指令、無限迴圈、資料庫刪表等危險操作。
7. 如果需要 API key、憑證、檔案路徑，請使用明顯的假資料或註解說明，不要要求真實密鑰。
8. 最後用註解補上「預期輸出」或「執行結果說明」。
""".strip()


def call_gemini(prompt, api_key, model_name):
    try:
        from google import genai
    except Exception as e:
        return AIExampleResult(
            ok=False,
            code="",
            message=f"無法匯入 google-genai。請先執行：pip install google-genai。錯誤：{e}"
        )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        return AIExampleResult(ok=True, code=getattr(response, "text", "") or "")
    except Exception as e:
        return AIExampleResult(ok=False, code="", message=f"Gemini 產生失敗：{e}")


def call_openai(prompt, api_key, model_name):
    try:
        from openai import OpenAI
    except Exception as e:
        return AIExampleResult(
            ok=False,
            code="",
            message=f"無法匯入 openai。請先執行：pip install openai。錯誤：{e}"
        )

    try:
        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model=model_name,
            input=prompt
        )
        return AIExampleResult(ok=True, code=getattr(response, "output_text", "") or "")
    except Exception as e:
        return AIExampleResult(ok=False, code="", message=f"GPT / OpenAI 產生失敗：{e}")


def call_claude(prompt, api_key, model_name):
    try:
        import anthropic
    except Exception as e:
        return AIExampleResult(
            ok=False,
            code="",
            message=f"無法匯入 anthropic。請先執行：pip install anthropic。錯誤：{e}"
        )

    try:
        client = anthropic.Anthropic(api_key=api_key)

        response = client.messages.create(
            model=model_name,
            max_tokens=1200,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        chunks = []

        for block in response.content:
            text = getattr(block, "text", "")
            if text:
                chunks.append(text)

        return AIExampleResult(ok=True, code="\n".join(chunks))
    except Exception as e:
        return AIExampleResult(ok=False, code="", message=f"Claude 產生失敗：{e}")


def generate_example_with_ai(
    name,
    package,
    category="",
    description_zh="",
    description_en="",
    source_anchor="",
    provider="gemini",
    api_key="",
    model_name=""
):
    """
    使用指定 AI 服務產生範例。

    provider：
    - gemini
    - openai
    - claude
    """

    provider = normalize_provider(provider)
    model_name = (model_name or "").strip() or get_default_model(provider)

    if provider not in {"gemini", "openai", "claude"}:
        return AIExampleResult(
            ok=False,
            code="",
            message="不支援的 AI 服務，請選 Gemini、GPT / OpenAI 或 Claude。"
        )

    real_api_key = load_api_key(provider, api_key_from_ui=api_key)

    if not real_api_key:
        env_key = get_env_key_name(provider)
        display = PROVIDER_DISPLAY_NAMES.get(provider, provider)
        return AIExampleResult(
            ok=False,
            code="",
            message=f"找不到 {display} API Key。請在前端 API Key 欄位輸入，或在 .env 加入 {env_key}=你的_API_KEY。"
        )

    prompt = build_prompt(
        name=name,
        package=package,
        category=category,
        description_zh=description_zh,
        description_en=description_en,
        source_anchor=source_anchor
    )

    if provider == "gemini":
        result = call_gemini(prompt, real_api_key, model_name)
    elif provider == "openai":
        result = call_openai(prompt, real_api_key, model_name)
    else:
        result = call_claude(prompt, real_api_key, model_name)

    if not result.ok:
        return result

    code = strip_markdown_code_fence(result.code)

    if not code.strip():
        return AIExampleResult(
            ok=False,
            code="",
            message="AI 沒有回傳內容，請稍後再試。"
        )

    dangerous, pattern = looks_dangerous(code)

    if dangerous:
        return AIExampleResult(
            ok=False,
            code=code,
            message=f"AI 產生的程式碼可能包含危險語句，已阻止寫入。命中規則：{pattern}"
        )

    return AIExampleResult(ok=True, code=code, message="AI 範例產生完成。")
