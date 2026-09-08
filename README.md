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

## 英语语法电子书

`/grammar` 使用统一的 Vue 阅读器，目录、正文、练习、图片和答案均来自 SQLite。新增 Unit
不新增页面；只需准备 `storage/grammar/import-packages/unit-NNN.json` 数据包并由通用导入器
写入。学习者答案只保存到浏览器本地存储，目前不会上传或批改。

原书完整 `Key to Exercises` 已作为独立答案索引导入，可先于 Unit 正文存在。重新校验或按
范围增量导入答案：

```bash
.venv/bin/python scripts/import-grammar-answer-key.py --validate-only
.venv/bin/python scripts/import-grammar-answer-key.py --unit-start 1 --unit-end 25
.venv/bin/python scripts/import-grammar-answer-key.py --audit-only
```

导入一个新的 Unit：

```bash
.venv/bin/python scripts/import-grammar-unit.py --unit 3 --validate-only
.venv/bin/python scripts/import-grammar-unit.py --unit 3 --status reviewed
```

首次部署或原书页面资源被清理后，按现有 Unit 数据包生成引用页：

```bash
.venv/bin/python scripts/build-grammar-book-assets.py --unit 1 --unit 2
```

默认来源是 `~/Documents/04-Resources/MacShare/` 中的 English Grammar in Use PDF；如需使用
其他位置的同一版本，可设置 `GRAMMAR_BOOK_SOURCE_PDF` 环境变量。生成结果位于
`storage/grammar/book-pages/`，并由 `/api/grammar/book-pages/<page>` 私有提供。

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

## macOS 常驻服务与 Tailscale 访问

生产式本地运行使用 Waitress、Caddy 和 macOS `launchd`，不要使用 Flask/Vue 的开发服务器：

```bash
brew install caddy
.venv/bin/python -m pip install -r requirements.txt
cd frontend && npm ci && npm run build && cd ..
./scripts/install-local-services.sh
# 8443 avoids replacing an existing Tailscale Funnel/Serve that uses 443.
tailscale serve --bg --https=8443 8080
./scripts/status-local-services.sh
```

服务只监听本机回环地址；Tailscale Serve 提供 Tailnet 内的 HTTPS 地址（本机当前使用 8443）。日后更新请运行：

```bash
./scripts/update-and-restart.sh
```
