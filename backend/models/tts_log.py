import datetime as dt
from backend.extensions import db

class SynthesisLog(db.Model):
    __tablename__ = "synthesis_log"

    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    locale = db.Column(db.String(16), nullable=False)
    voice = db.Column(db.String(64), nullable=False)
    style = db.Column(db.String(32))
    styledegree = db.Column(db.String(8))
    role = db.Column(db.String(32))
    rate = db.Column(db.String(16))
    pitch = db.Column(db.String(16))
    volume = db.Column(db.String(16))
    file_path = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow)
