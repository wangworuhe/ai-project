# Flask + Vue Speech Project

项目由 Flask 后端、Vue 3 前端和 SQLite 数据库组成。

## macOS 本地运行

后端：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m flask --app run.py run
```

前端：

```bash
cd frontend
npm install
npm run serve
```

默认访问地址：

- 前端：`http://127.0.0.1:8080`
- 后端 API：`http://127.0.0.1:5000/api`

## 环境配置

项目根目录的 `.env` 用于本地密钥配置，并已被 Git 忽略：

```dotenv
AZURE_SPEECH_KEY=
AZURE_SPEECH_REGION=
LOG_LEVEL=INFO
```

## 项目内运行数据

运行时文件统一保存在项目根目录的 `storage/` 中：

```text
storage/
├── database/database.db
├── logs/app.log
├── outputs/
└── uploads/assessment/
```

`storage/` 已被 Git 忽略，不会提交数据库、日志、录音或合成音频。

## 数据库迁移

```bash
.venv/bin/python -m flask --app run.py db migrate -m "update migration"
.venv/bin/python -m flask --app run.py db upgrade
```

## TTS 测试

```bash
curl -X POST http://127.0.0.1:5000/api/tts/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text":"你好，世界","voice":"zh-CN-XiaoxiaoNeural","style":"cheerful","rate":"+10%"}'
```
