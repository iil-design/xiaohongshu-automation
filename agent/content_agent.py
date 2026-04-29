import json
import os

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from config import SYSTEM_PROMPT_FILE, get_active_model_config


def _load_system_prompt():
    """从文件加载系统提示词，每次调用都重新读取"""
    if os.path.exists(SYSTEM_PROMPT_FILE):
        with open(SYSTEM_PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return "你是一个内容处理助手。"


def _build_llm():
    """使用动态 AI 配置构建 LLM"""
    cfg = get_active_model_config()
    return ChatOpenAI(
        model=cfg["model_name"],
        api_key=cfg["api_key"],
        base_url=cfg["base_url"],
        temperature=cfg.get("temperature", 0.7),
        request_timeout=120,
    )


def _strip_json(text: str) -> str:
    """从响应文本中提取 JSON 块"""
    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start)
        return text[start:end].strip()
    elif "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start)
        return text[start:end].strip()
    return text.strip()


def _validate_image_prompts(result: dict) -> bool:
    """校验 image_prompts 字段：必须存在、恰好3个、每个非空字符串"""
    prompts = result.get("image_prompts")
    if not isinstance(prompts, list):
        return False
    if len(prompts) != 3:
        return False
    if not all(isinstance(p, str) and p.strip() for p in prompts):
        return False
    return True


def _call_llm(system_prompt: str, user_input: str) -> str:
    """单次 LLM 调用"""
    llm = _build_llm()
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_input),
    ]
    response = llm.invoke(messages)
    return response.content


def process_content(user_input: str) -> str:
    """调用 agent 处理用户输入，返回 LLM 响应文本"""
    return _call_llm(_load_system_prompt(), user_input)


def process_content_json(user_input: str, max_retries: int = 3) -> dict:
    """调用 agent 处理用户输入，返回解析后的 JSON。
    如果缺少 image_prompts 字段，会自动重试（最多 max_retries 次）。
    """
    system_prompt = _load_system_prompt()
    original_input = user_input
    current_input = user_input

    for attempt in range(1, max_retries + 1):
        text = _call_llm(system_prompt, current_input)

        # 解析 JSON
        try:
            result = json.loads(_strip_json(text))
        except (json.JSONDecodeError, ValueError):
            if attempt < max_retries:
                current_input = (
                    f"上一次响应无法解析为 JSON，请严格在末尾输出 JSON 代码块。\n\n"
                    f"---原始内容---\n{original_input}"
                )
                continue
            return {"raw": text, "error": "JSON 解析失败，已达最大重试次数"}

        # 校验 image_prompts
        if _validate_image_prompts(result):
            return result

        if attempt < max_retries:
            current_input = (
                f"上一次响应缺少 image_prompts 字段或格式不正确。"
                f"image_prompts 必须是恰好 3 段中文文生图提示词的数组，这是最高优先级要求。\n\n"
                f"---原始内容---\n{original_input}"
            )

    return {"raw": text, "error": "image_prompts 校验失败，已达最大重试次数"}


def import_to_content_db(source_plat: str, result: dict) -> int:
    """将 agent 处理结果导入素材库，返回新记录的 ID"""
    from models.content import SessionLocal, Content

    db = SessionLocal()
    try:
        item = Content(
            source_plat=source_plat,
            title=result.get("title", ""),
            body=result.get("body", result.get("raw", "")),
            tags=json.dumps(result.get("tags", []), ensure_ascii=False),
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item.id
    finally:
        db.close()


if __name__ == "__main__":
    cfg = get_active_model_config()
    print(f"System prompt loaded ({len(_load_system_prompt())} chars)")
    print(f"Model: {cfg['model_name']}")
    print("Agent ready. Usage:")
    print("  from agent.content_agent import process_content, import_to_content_db")
    print("  result = process_content('你的输入')")
