# Flask Web Project

This is a simple Flask web project with SQLite database.

## Installation

启动虚拟环境
azure-venv\Scripts\activate

运行flask
flask --app run.py run

前端项目
cd .\ai-project\frontend\
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

git archive --format=zip HEAD -o ai-project.zip
