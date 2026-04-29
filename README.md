
# 小红书自动化创作平台

基于 AI 的小红书内容创作与发布管理平台。支持 AI 生成文案、自动生成配图、定时发布、扫码登录等功能。

## 功能概览

- **帖子管理** — 创建、编辑、删除、草稿保存
- <img width="2175" height="1118" alt="5fa93f7800906fe3b518ce2c6646685f" src="https://github.com/user-attachments/assets/cad07ee7-e039-49cc-8760-5358ed4c23a1" />

- **AI 内容创作** — 基于大模型自动生成标题、正文、话题标签和配图提示词
- <img width="1605" height="998" alt="image" src="https://github.com/user-attachments/assets/1b8fd2c1-5850-4a50-85b7-e4541dec6bec" />

- **AI 图片生成** — 根据文案自动生成配图（DashScope wan2.6-t2i）
- **内容素材库** — 抓取外部热点内容（GitHub Trending、抖查查等），AI 加工后导入草稿
- <img width="2175" height="1118" alt="09befd64bd7fb4c7c349fd9d57e5beeb" src="https://github.com/user-attachments/assets/ca12c6fc-a915-4f3a-aea2-e90347f9caab" />

- **定时发布** — 支持设定发布时间，后台自动发布
- 
- **扫码登录** — 通过 MCP 服务扫码登录小红书账号
- **发布历史** — 记录每次发布操作的成功/失败日志
- <img width="1531" height="775" alt="4c2a22facc3ad0e7a4c9e8b89b697aed" src="https://github.com/user-attachments/assets/e40420ad-9fa4-4ffe-bccd-eb9271ef2f60" />

- **AI 配置** — 可视化调整模型、温度、图片生成参数、系统提示词
- <img width="2175" height="1118" alt="a4e2a768b611d38e5617a4ae77844521" src="https://github.com/user-attachments/assets/66d8b9b7-4469-4a77-96d2-dac54401fb93" />


## 技术栈

| 层级 | 技术 |
|------|------|
| Web 框架 | FastAPI + Uvicorn |
| 模板引擎 | Jinja2 |
| 前端样式 | Tailwind CSS |
| 数据库 | SQLite + SQLAlchemy ORM |
| AI 模型 | 通义千问 VL (DashScope) |
| 图片生成 | DashScope wan2.6-t2i |
| 定时任务 | APScheduler |
| MCP 集成 | MCP Python SDK |

## 快速开始

### 环境要求

- Python 3.9+
- Windows 系统（MCP 服务为 Windows 二进制文件）
- Google Chrome 浏览器（MCP 扫码登录需要）

### 安装

```bash
# 克隆项目
git clone https://github.com/iil-design/xiaohongshu-automation.git
cd xiaohongshu-automation

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env，填入你的 DashScope API Key
# DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxx
```

> API Key 获取地址：[DashScope 百炼控制台](https://dashscope.console.aliyun.com/apiKey)

### 启动

```bash
python main.py
```

启动后访问 http://127.0.0.1:8890

### 发布帖子

1. 首次使用需扫码登录：点击导航栏「扫码登录」，扫描二维码完成登录
2. 创建帖子（手动编写或从素材库 AI 生成）
3. 点击「立即发布」或设置定时发布时间

## 文件说明

### 根目录

| 文件 | 用途 |
| --- | --- |
| `main.py` | 应用入口。启动 FastAPI 服务器（端口 8890）、管理 MCP 服务的生命周期（启动/停止/健康检查）、挂载静态文件和模板引擎 |
| `config.py` | 全局配置中心。数据库连接、上传路径、AI 模型参数、MCP 服务地址、环境变量加载、AI 配置的持久化读写 |
| `requirements.txt` | Python 依赖清单（FastAPI、SQLAlchemy、LangChain、APScheduler 等） |
| `.env.example` | 环境变量模板，仅包含 `DASHSCOPE_API_KEY` |
| `CLAUDE.md` | Claude Code 项目指令，要求部署前必须测试验证 |
| `.gitignore` | Git 忽略规则：排除 `.env`、数据库文件、日志、二进制文件、虚拟环境等 |

### agent/ — AI Agent 模块

| 文件 | 用途 |
| --- | --- |
| `content_agent.py` | 内容创作 Agent。调用大模型将原始素材加工为结构化 JSON，生成优化后的标题、正文、话题标签和 3 条配图提示词，包含 JSON 解析重试机制 |
| `poster_agent.py` | 帖子审核 Agent。提供 `review_content`（检查帖子是否适合发布）和 `summarize_post`（将帖子概括为 ≤30 字摘要） |
| `image_generator.py` | AI 图片生成模块。后台线程调用 DashScope wan2.6-t2i 将提示词转为图片，下载存储到本地，通过模块级字典追踪生成进度供前端轮询 |
| `system_prompt.md` | AI 系统提示词，定义内容创作 Agent 的行为规范和输出格式 |
| `__init__.py` | 导出 `review_content` 和 `summarize_post` |

### web/ — Web 路由

| 文件 | 用途 |
| --- | --- |
| `routes.py` | FastAPI 路由（全部 API + 页面）。包含帖子 CRUD、AI 加工、图片状态轮询、MCP 启停与工具查询、扫码登录、Cookie 管理、定时爬虫触发、素材库导入等 20+ 端点 |

### models/ — 数据库模型

| 文件 | 用途 |
| --- | --- |
| `models.py` | 帖子系统 ORM 模型（Post、Schedule、PublishLog）。SQLite + SQLAlchemy，含图片和标签的 JSON 序列化、自动时间戳 |
| `content.py` | 素材库 ORM 模型（Content、ProcessedContent）。存储爬取的原始素材和 AI 加工结果，含图片提示词和生成图片管理 |

### publisher/ — 发布模块

| 文件 | 用途 |
| --- | --- |
| `publisher.py` | 发布器抽象层。定义 PublishResult 和 BasePublisher，实现 MCPPublisher（通过 MCP 发布）和 MockPublisher（测试用），负责图片路径转绝对 URL |
| `mcp_client.py` | MCP HTTP 客户端。通过 Streamable HTTP 协议与 Go MCP 服务（端口 28002）通信，封装 publish_content、check_login_status、get_login_qrcode、delete_cookies 等工具调用 |
| `__init__.py` | 导出所有发布相关类和 `get_publisher` 工厂函数 |

### scheduler/ — 定时任务

| 文件 | 用途 |
| --- | --- |
| `scheduler.py` | 基于 APScheduler 的后台调度器。管理定时发布任务（DateTrigger），提供 start_scheduler、shutdown_scheduler、add_schedule、remove_schedule |

### templates/ — 前端页面

| 文件 | 用途 |
| --- | --- |
| `base.html` | 基础模板。包含导航栏、登录/登出按钮、MCP 状态指示、扫码登录弹窗，其他页面均继承此模板 |
| `index.html` | 首页帖子管理面板。展示所有帖子列表（状态标签：草稿/已定时/已发布/失败），提供发布/重试/删除操作 |
| `editor.html` | 帖子编辑器。标题输入、正文编辑、图片上传（最多 9 张）、话题标签、定时发布时间选择器 |
| `library.html` | 素材库页面。左侧选择原始素材，右侧展示 AI 加工结果，支持重新生成、配图预览与轮询、一键导入草稿 |
| `history.html` | 发布历史页面。展示所有发布操作日志（手动/重试/定时），记录成功/失败结果及错误信息 |
| `settings.html` | AI 设置页面。模型选择、温度调节、图片生成参数配置、系统提示词编辑器 |

### 内容脚本/ — 外部内容抓取

| 文件 | 用途 |
| --- | --- |
| `github_trending_rpa.py` | GitHub Trending 爬虫，抓取 GitHub 热门仓库信息作为内容素材 |
| `scrape_douchacha.py` | 抖查查爬虫，抓取抖音热门话题和内容趋势 |

### 其他目录

| 目录 | 说明 |
| --- | --- |
| `static/` | 静态资源（CSS、JS），`uploads/` 子目录存储用户上传和 AI 生成的图片（已 gitignore） |
| `mcp-server/` | MCP 服务二进制文件存放目录，需从 [xiaohongshu-mcp-server](https://github.com/Turbo1125/xiaohongshu-mcp-server) 下载 |
| `docs/` | 设计文档和实施计划 |
| `config/` | 运行时生成的 `ai_settings.json` 存放目录 |

## 注意事项

- MCP 服务二进制文件需从 [xiaohongshu-mcp-server](https://github.com/Turbo1125/xiaohongshu-mcp-server) 下载，放入 `mcp-server/` 目录
- API Key 请通过 `.env` 文件配置，不要硬编码在代码中
- 数据库文件 (`*.db`) 和上传图片 (`static/uploads/`) 不会被提交到 Git
- 发布功能依赖小红书 MCP 服务正常运行

## License

MIT
