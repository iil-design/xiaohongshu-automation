# 小红书自动发帖助手 — 设计文档

## 概述

个人使用的小红书帖子定时发布工具。用户上传图片+文案，设置发布时间，Agent 到点自动发布。

## 技术选型

| 层 | 技术 | 理由 |
|---|---|---|
| 后端框架 | FastAPI | 异步支持好，轻量，Python 生态 |
| 前端 | Jinja2 + Tailwind CSS CDN | 无构建步骤，服务端渲染，最快 |
| 数据库 | SQLite | 个人单用户，零配置，足够 |
| 任务调度 | APScheduler | FastAPI 进程内，简单可靠 |
| Agent | LangChain | 编排内容→调度流程 |
| Agent LLM | qwen-coder-turbo-0919 | 阿里云 DashScope (OpenAI 兼容) |

## 页面结构

3 个页面，扁平结构：

1. **帖子管理（首页 /**）** — 草稿箱列表，按状态分组（草稿/待发/已发），+新建按钮，立即发布按钮
2. **新建/编辑帖子（/editor）** — 图片上传区（最多9张），标题输入，正文输入，发布时间选择，保存草稿/定时发布
3. **发布历史（/history）** — 全部记录时间线，状态标签，失败可重试

## 目录结构

```
d:\桌面\agent\
├── .venv/                 # 虚拟环境
├── static/uploads/        # 上传图片存储
├── templates/             # Jinja2 模板
│   ├── base.html          # 公共布局 (Tailwind CDN)
│   ├── index.html         # 帖子管理首页
│   ├── editor.html        # 新建/编辑帖子
│   └── history.html       # 发布历史
├── web/routes.py          # FastAPI 路由
├── agent/poster_agent.py  # LangChain Agent 编排
├── scheduler/scheduler.py # APScheduler 管理
├── publisher/publisher.py # 发布接口 (可插拔)
├── models/models.py       # SQLAlchemy 模型
├── main.py                # FastAPI 入口
└── config.py              # 配置
```

## 数据库设计

### posts — 帖子内容
```
id            INTEGER PK
title         TEXT       -- 标题
body          TEXT       -- 正文
images        TEXT       -- JSON 数组存图片路径
status        TEXT       -- draft | scheduled | published | failed
scheduled_at  TEXT       -- 计划发布时间
published_at  TEXT       -- 实际发布时间
error_msg     TEXT       -- 失败原因
created_at    TEXT
updated_at    TEXT
```

### schedules — 调度任务
```
id       INTEGER PK
post_id  INTEGER FK → posts.id
run_at   TEXT       -- 执行时间
status   TEXT       -- pending | done | failed
job_id   TEXT       -- APScheduler job ID
```

### publish_logs — 发布日志
```
id         INTEGER PK
post_id    INTEGER FK → posts.id
action     TEXT       -- scheduled | manual | retry
result     TEXT       -- success | failed
message    TEXT       -- 详细信息
created_at TEXT
```

## Agent 调度流程

```
用户创建帖子 → 写入 SQLite
     ↓
Agent 检测新帖子 → 注册 APScheduler 定时任务
     ↓
到时间 → APScheduler 触发 → 调用 Publisher
     ↓
Publisher 执行发布 → 写 publish_logs → 更新 posts.status
```

Agent 职责：
- 内容组装：接收图片+标题+正文 → 组装为 Post 对象
- 调度编排：根据 scheduled_at 注册定时任务
- 触发执行：到时间调用 Publisher
- 日志记录：写发布结果，更新帖子状态

## Publisher 接口

当前版本：留空接口，返回模拟成功。

```
class BasePublisher:
    def publish(post: Post) -> PublishResult:
        raise NotImplementedError
```

后续可接入：
- 浏览器自动化 (Playwright)
- 小红书开放 API（如果有）
- 手动确认模式

## Agent LLM 配置

使用阿里云百炼 DashScope 的 qwen-coder-turbo-0919（OpenAI 兼容接口）：

```json
{
  "provider":   "openai_compatible",
  "model_name": "qwen-coder-turbo-0919",
  "api_key":    "sk-2779612cd26547fab22f55d641926d9f",
  "base_url":   "https://dashscope.aliyuncs.com/compatible-mode/v1",
  "stream":     false
}
```

## 非功能要点

- 个人单用户，无登录/鉴权
- 服务重启后从数据库恢复 pending 调度任务
- 图片最多 9 张，单张限制 10MB
- 前端无构建步骤，Tailwind 通过 CDN 引入
