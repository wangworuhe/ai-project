from backend.extensions import db

class Assessment(db.Model):
    __tablename__ = "assessments"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # 评估记录ID
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)  # 用户ID
    text = db.Column(db.Text, nullable=True)  # 评估的文本内容
    pronunciation_score = db.Column(db.Float, nullable=True)  # 发音评分
    accuracy_score = db.Column(db.Float, nullable=True)  # 准确度评分
    fluency_score = db.Column(db.Float, nullable=True)  # 流利度评分
    completeness_score = db.Column(db.Float, nullable=True)  # 完整度评分
    content_assessment_result = db.Column(db.Text, nullable=True)  # 内容评估结果
    words = db.Column(db.Text, nullable=True)  # 单词级别的评估结果
    prosody_score = db.Column(db.Float, nullable=True)  # 韵律评分
    vocabulary_score = db.Column(db.Float, nullable=True)  # 词汇评分
    grammar_score = db.Column(db.Float, nullable=True)  # 语法评分
    topic_score = db.Column(db.Float, nullable=True)  # 主题评分
    audio_path = db.Column(db.String(255), nullable=False)  # 存储 MP3 文件路径
    audio_duration = db.Column(db.Float, nullable=True)  # 音频时长（秒）
    language = db.Column(db.String(10), nullable=True)  # 语音评估的语言（如 en-US）
    assessment_type = db.Column(db.String(20), nullable=True)  # 评估类型（scripted / unscripted）
    error_message = db.Column(db.Text, nullable=True)  # 评估失败的错误信息
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())  # 记录创建时间
    processed_at = db.Column(db.DateTime, nullable=True)  # 记录评估完成时间