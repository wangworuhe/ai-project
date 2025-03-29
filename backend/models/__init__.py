from backend.extensions import db
from backend.models.user import User
from backend.models.recording import Recording
from backend.models.assessment import Assessment

def init_db(app):
    """ 初始化数据库 """
    db.init_app(app)
    with app.app_context():
        db.create_all()
