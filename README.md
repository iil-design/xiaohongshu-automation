<img width="1531" height="775" alt="4c2a22facc3ad0e7a4c9e8b89b697aed" src="https://github.com/user-attachments/assets/c7262616-99c3-446d-8aca-a7d9855b166c" /># 小红书发帖助手

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
git clone https://github.com/你的用户名/项目名.git
cd 项目名

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

- 首页 (`/`) — 帖子管理面板
- 编辑器 (`/editor`) — 创建/编辑帖子
- 素材库 (`/library`) — AI 内容加工
- 发布历史 (`/history`) — 发布日志
- AI 设置 (`/settings`) — 模型参数配置

### 发布帖子

1. 首次使用需扫码登录：点击导航栏「扫码登录」，扫描二维码完成登录
2. 创建帖子（手动编写或从素材库 AI 生成）
3. 点击「立即发布」或设置定时发布时间

## 项目结构

```
├── main.py                 # 应用入口，MCP 服务生命周期管理
├── config.py               # 配置管理（数据库、API、上传路径等）
├── requirements.txt        # Python 依赖
├── .env.example            # 环境变量模板
├── agent/                  # AI Agent 模块
│   ├── content_agent.py    # 内容创作 Agent
│   ├── poster_agent.py     # 帖子审核 Agent
│   ├── image_generator.py  # 图片生成模块
│   └── system_prompt.md    # AI 系统提示词
├── web/
│   └── routes.py           # FastAPI 路由（API + 页面）
├── models/
│   ├── models.py           # 帖子/定时/日志数据模型
│   └── content.py          # 素材库数据模型
├── publisher/
│   ├── publisher.py        # 发布器抽象层
│   └── mcp_client.py       # MCP HTTP 客户端
├── scheduler/
│   └── scheduler.py        # 定时发布调度器
├── templates/              # Jinja2 页面模板
├── static/                 # 静态资源
│   └── uploads/            # 上传图片（已 gitignore）
├── 内容脚本/               # 外部内容抓取脚本
└── mcp-server/             # MCP 服务二进制文件（需自行下载）
```

## 注意事项

- MCP 服务二进制文件需从 [xiaohongshu-mcp-server](https://github.com/Turbo1125/xiaohongshu-mcp-server) 下载，放入 `mcp-server/` 目录
- API Key 请通过 `.env` 文件配置，不要硬编码在代码中
- 数据库文件 (`*.db`) 和上传图片 (`static/uploads/`) 不会被提交到 Git
- 发布功能依赖小红书 MCP 服务正常运行

## License

MIT
