from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from config import get_active_model_config


def _build_llm():
    cfg = get_active_model_config()
    return ChatOpenAI(
        model=cfg["model_name"],
        api_key=cfg["api_key"],
        base_url=cfg["base_url"],
        temperature=0.3,
    )


def review_content(title: str, body: str) -> dict:
    llm = _build_llm()
    messages = [
        SystemMessage(content=(
            "你是小红书内容审核助手。检查帖子是否适合发布，返回 JSON："
            '{"ok": true/false, "reason": "简短说明"}。'
            "检查项：标题不为空，正文不为空，内容合理。"
        )),
        HumanMessage(content=f"标题：{title}\n正文：{body}"),
    ]
    response = llm.invoke(messages)
    import json
    try:
        return json.loads(response.content)
    except json.JSONDecodeError:
        return {"ok": True, "reason": "审核通过（JSON解析失败，默认放行）"}


def summarize_post(title: str, body: str) -> str:
    llm = _build_llm()
    messages = [
        SystemMessage(content="用一句话概括以下小红书帖子内容，不超过30字。"),
        HumanMessage(content=f"标题：{title}\n正文：{body}"),
    ]
    response = llm.invoke(messages)
    return response.content.strip()
