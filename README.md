# 飞书群机器人 - 待办管理系统

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

一个基于飞书开放平台的群聊待办管理机器人，支持自动收集待办事项、智能提醒和任务管理。

## 功能特性

- ✅ **待办收集**: 通过特定格式消息快速添加待办事项
- ⏰ **智能提醒**: 每周固定时间和截止日当天自动@所有人提醒
- 📊 **任务管理**: 支持查看、完成、删除待办事项
- 🔧 **灵活配置**: 可自定义提醒时间
- 💾 **数据持久化**: SQLite数据库存储，轻量高效
- 🚀 **易于部署**: 支持systemd守护进程，稳定运行

## 快速开始

### 前置要求

- Python 3.8 或更高版本
- 飞书企业账号
- 具有公网访问能力的服务器（用于接收飞书回调）

### 1. 创建飞书应用

1. 访问[飞书开放平台](https://open.feishu.cn/)
2. 创建企业自建应用
3. 在"应用功能 - 机器人"中启用机器人功能
4. 在"权限管理"中添加以下权限：
   - `im:message` - 获取与发送单聊、群组消息
   - `im:message.group_at_msg` - 获取群组中所有消息
   - `im:chat` - 获取群组信息
5. 在"事件订阅"中添加以下事件：
   - `im.message.receive_v1` - 接收消息
6. 记录以下信息（稍后配置使用）：
   - App ID
   - App Secret
   - Verification Token
   - Encrypt Key（如果启用了加密）

### 2. 安装部署

#### 克隆代码

```bash
git clone <your-repo-url>
cd feishu-todo-bot
```

#### 创建虚拟环境

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

#### 安装依赖

```bash
pip install -r requirements.txt
```

#### 配置环境变量

复制 `.env.example` 为 `.env` 并填写配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```bash
# 飞书应用配置（从飞书开放平台获取）
FEISHU_APP_ID=cli_xxxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxx
FEISHU_VERIFICATION_TOKEN=xxxxxxxxxxxxxxxxxxxxxx
FEISHU_ENCRYPT_KEY=xxxxxxxxxxxxxxxxxxxxxx  # 可选

# Flask配置
FLASK_HOST=0.0.0.0
FLASK_PORT=8000
FLASK_DEBUG=False

# 数据库路径
DATABASE_PATH=./data/todos.db

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=./logs/bot.log
```

### 3. 本地测试

#### 启动应用

```bash
python app.py
```

#### 使用内网穿透工具

由于飞书需要回调公网地址，本地测试时需要使用内网穿透工具：

```bash
# 使用 ngrok（推荐）
ngrok http 8000

# 或使用 cpolar
cpolar http 8000
```

获取公网URL（如 `https://xxxx.ngrok.io`），然后：

1. 在飞书开放平台的"事件订阅"中配置请求网址：
   ```
   https://xxxx.ngrok.io/webhook/event
   ```

2. 保存配置，飞书会发送验证请求

3. 将机器人添加到测试群组

#### 测试功能

在群组中发送消息测试：

```
待办：完成项目文档 @2026-03-25
```

机器人应该回复确认消息。

发送命令测试：

```
@机器人 查看待办
@机器人 帮助
```

### 4. 生产部署

#### 方式一：使用 systemd（推荐）

1. 将代码部署到服务器（如 `/opt/feishu-todo-bot`）

2. 安装依赖：

```bash
cd /opt/feishu-todo-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. 配置 `.env` 文件

4. 复制 systemd 服务配置：

```bash
sudo cp deploy/feishu-bot.service /etc/systemd/system/
```

5. 修改服务配置中的路径和用户：

```bash
sudo nano /etc/systemd/system/feishu-bot.service
```

6. 启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable feishu-bot
sudo systemctl start feishu-bot
```

7. 查看状态：

```bash
sudo systemctl status feishu-bot
sudo journalctl -u feishu-bot -f  # 查看日志
```

#### 方式二：使用 Docker（可选）

创建 `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "app.py"]
```

构建和运行：

```bash
docker build -t feishu-todo-bot .
docker run -d --name feishu-bot \
  --env-file .env \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  feishu-todo-bot
```

### 5. 配置反向代理（Nginx）

为了安全和稳定性，建议使用Nginx作为反向代理：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location /webhook/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

配置HTTPS（使用Let's Encrypt）：

```bash
sudo certbot --nginx -d your-domain.com
```

## 使用说明

### 添加待办

在群组中发送消息（格式：`待办：任务描述 @截止日期`）：

```
待办：完成Q1季度报告 @2026-03-25
待办：提交代码review @2026-03-20
待办：准备月度会议 @2026-03-28
```

机器人会自动识别并保存待办事项。

### 查看待办

@机器人查看所有未完成的待办：

```
@机器人 查看待办
```

或：

```
@机器人 待办列表
```

### 完成待办

标记任务完成：

```
@机器人 完成 1
```

其中 `1` 是任务ID（在查看待办时显示）。

### 删除待办

删除任务（仅创建者可删除）：

```
@机器人 删除 1
```

### 设置提醒时间

配置每周提醒时间：

```
@机器人 设置提醒 周1 09:00
@机器人 设置提醒 周五 14:30
```

格式说明：
- 周X：1-7 或 一二三四五六日
- HH:MM：24小时制时间

### 查看帮助

```
@机器人 帮助
```

## 提醒规则

### 每周统一提醒

- 默认时间：每周一早上 9:00
- 可通过命令自定义时间
- 提醒内容：所有未完成的待办，按紧急程度分类

### 截止日提醒

- 自动在任务截止当天早上 9:00 提醒
- 每小时检查一次，防止遗漏
- 提醒后标记为已提醒，避免重复

## API接口

### 健康检查

```bash
GET /health
```

返回示例：

```json
{
  "status": "ok",
  "service": "feishu-todo-bot",
  "scheduler_running": true,
  "jobs": 3
}
```

### 获取待办列表

```bash
GET /api/todos?chat_id=oc_xxxxx
```

### 手动触发提醒

```bash
POST /api/reminder/trigger/weekly_reminder
POST /api/reminder/trigger/daily_deadline_reminder
```

### 查看定时任务

```bash
GET /api/jobs
```

## 项目结构

```
feishu-todo-bot/
├── app.py                      # Flask应用主入口
├── requirements.txt            # Python依赖
├── .env.example                # 环境变量模板
├── .env                        # 环境变量配置（不提交git）
├── .gitignore                  # Git忽略文件
├── README.md                   # 项目文档
├── bot/                        # 机器人核心模块
│   ├── __init__.py
│   ├── feishu_client.py        # 飞书API封装
│   ├── message_handler.py      # 消息处理逻辑
│   └── todo_parser.py          # 待办格式解析
├── scheduler/                  # 定时任务模块
│   ├── __init__.py
│   ├── jobs.py                 # 任务定义
│   └── reminder.py             # 提醒逻辑
├── database/                   # 数据库模块
│   ├── __init__.py
│   ├── db.py                   # 数据库操作
│   └── models.py               # 数据模型
├── config/                     # 配置模块
│   ├── __init__.py
│   └── settings.py             # 配置管理
├── deploy/                     # 部署配置
│   └── feishu-bot.service      # systemd服务配置
├── data/                       # 数据目录（自动创建）
│   └── todos.db                # SQLite数据库
└── logs/                       # 日志目录（自动创建）
    └── bot.log                 # 应用日志
```

## 数据库结构

### todos 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| chat_id | TEXT | 群聊ID |
| user_id | TEXT | 创建者用户ID |
| user_name | TEXT | 创建者姓名 |
| content | TEXT | 待办内容 |
| deadline | DATE | 截止日期 |
| created_at | TIMESTAMP | 创建时间 |
| reminded_daily | BOOLEAN | 是否已发送截止日提醒 |
| completed | BOOLEAN | 是否完成 |
| completed_at | TIMESTAMP | 完成时间 |

### reminder_config 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| chat_id | TEXT | 群聊ID |
| weekly_day | INTEGER | 每周提醒日期（1-7） |
| weekly_hour | INTEGER | 每周提醒小时（0-23） |
| weekly_minute | INTEGER | 每周提醒分钟（0-59） |
| daily_hour | INTEGER | 截止日提醒小时 |
| daily_minute | INTEGER | 截止日提醒分钟 |
| enabled | BOOLEAN | 是否启用提醒 |

## 常见问题

### 1. 机器人收不到消息

- 确认机器人已添加到群组
- 检查飞书应用是否已发布并启用
- 确认事件订阅配置正确
- 查看应用日志：`tail -f logs/bot.log`

### 2. 提醒功能不工作

- 检查调度器是否运行：访问 `/health` 接口
- 查看定时任务状态：访问 `/api/jobs` 接口
- 手动触发测试：`curl -X POST http://localhost:8000/api/reminder/trigger/weekly_reminder`

### 3. 数据库错误

- 检查 `data` 目录权限
- 查看数据库文件是否存在：`ls -l data/todos.db`
- 重新初始化数据库：删除 `todos.db` 后重启服务

### 4. 端口被占用

修改 `.env` 文件中的 `FLASK_PORT` 配置。

## 安全建议

- ✅ 不要将 `.env` 文件提交到代码仓库
- ✅ 定期备份数据库文件
- ✅ 使用 HTTPS 部署（配置SSL证书）
- ✅ 限制API接口访问（可添加认证）
- ✅ 定期更新依赖包

## 后续扩展

- [ ] 支持待办编辑功能
- [ ] 支持待办指派给特定成员
- [ ] 支持待办优先级和标签
- [ ] 添加统计报表功能
- [ ] 开发Web管理界面
- [ ] 支持多语言
- [ ] 支持周期性待办（每周/每月）

## 技术栈

- **语言**: Python 3.8+
- **Web框架**: Flask 3.0
- **飞书SDK**: lark-oapi 1.2.0
- **定时任务**: APScheduler 3.10.4
- **数据库**: SQLite3
- **部署**: systemd / Docker

## 贡献指南

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT License

## 联系方式

如有问题或建议，请提交 Issue 或联系维护者。

---

**享受高效的待办管理！** 📋✨
