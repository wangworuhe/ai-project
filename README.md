# Flask Web Project

This is a simple Flask web project with SQLite database.

## Installation

启动虚拟环境
azure-venv\Scripts\activate

运行flask
flask --app run.py run

前端项目
cd .\frontend\
npm run serve

退出环境
deactivate
初始化配置文件
pip install -r requirements.txt

set FLASK_APP=run.py
flask run

flask --app run.py run

数据迁移
flask --app run.py db init
flask --app run.py db migrate -m "update migration."
flask --app run.py db upgrade

npm run serve

# 打包
git archive --format=zip HEAD -o ai-project.zip


git commit -a -m "somethings"
git push origin kailasa

# 表处理
sqlite3 database.db
DELETE FROM alembic_version;


curl -X POST http://localhost:5000/tts/synthesize -H "Content-Type: application/json" -d '{"text":"你好，世界","voice":"zh-CN-XiaoxiaoNeural","style":"cheerful","rate":"+10%"}'
