import azure.cognitiveservices.speech as speechsdk
import os
import datetime
from pydub import AudioSegment
from pydub.utils import mediainfo
import ffmpeg
import json
import logging
from flask import request, current_app

speech_key = os.getenv("AZURE_SPEECH_KEY")
service_region = os.getenv("AZURE_SPEECH_REGION")

UPLOAD_FOLDER = "uploads/kailasa"  # 存储音频的目录
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # 确保目录存在

def save_audio_file(audio_blob, user_id):
    """
    保存音频文件为 WebM 格式，并转换为 WAV（PCM 16kHz 单声道）
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    webm_filename = f"recording_{timestamp}.webm"
    wav_filename = f"recording_{timestamp}.wav"

    webm_path = os.path.join(UPLOAD_FOLDER, webm_filename).replace("\\", "/")
    wav_path = os.path.join(UPLOAD_FOLDER, wav_filename).replace("\\", "/")

    # **保存 WebM 文件**
    audio_blob.save(webm_path)

    # **转换为 PCM WAV 格式**
    try:
        (
            ffmpeg
            .input(webm_path, acodec='libopus')
            .output(wav_path, format="wav", acodec="pcm_s16le", ar="16000", ac="1")
            .run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg._run.Error as e:
        stderr_output = e.stderr.decode()
        if "Error parsing Opus packet header" not in stderr_output:
            # 抛出其他致命错误
            raise Exception(f"音频转换失败: {stderr_output}")

    # **删除原始 WebM 文件**
    os.remove(webm_path)

    return wav_path  # 返回转换后的 WAV 文件路径

def evaluate_pronunciation_from_file(audio_path, reference_text, assessment_type="scripted"):
    """
    使用 Azure Speech SDK 对音频文件进行语音评估，并返回所有评分项
    """
    speech_key = os.getenv("AZURE_SPEECH_KEY")
    service_region = os.getenv("AZURE_SPEECH_REGION")

    if not speech_key or not service_region:
        raise ValueError("Azure 语音服务密钥未设置")


    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
    audio_config = speechsdk.audio.AudioConfig(filename=audio_path)

    pronunciation_config = speechsdk.PronunciationAssessmentConfig(
        reference_text=reference_text,
        grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
        granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
        # phoneme_alphabet="IPA",
        enable_miscue=True  # 启用语音错误分析（如果适用）
    )

    pronunciation_config.phoneme_alphabet = "IPA"

    pronunciation_config.enable_prosody_assessment() 
    pronunciation_config.enable_content_assessment_with_topic("greeting")

    if assessment_type == "unscripted":
        pronunciation_config.enable_miscue = True  # 启用未脚本化评估

    recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
    pronunciation_config.apply_to(recognizer)

    result = recognizer.recognize_once()

    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        pronunciation_result = speechsdk.PronunciationAssessmentResult(result)
  
        # 尝试获取详细评估结果的 JSON 数据
        raw_json = result.properties.get(speechsdk.PropertyId.SpeechServiceResponse_JsonResult)

        try:
            detailed_result = json.loads(raw_json) if raw_json else {}
        except json.JSONDecodeError:
            detailed_result = {"error": "Invalid JSON format in SpeechServiceResponseJsonResult"}

        # 计算音频时长
        try:
            audio_info = mediainfo(audio_path)
            duration = float(audio_info.get("duration", 0))
        except Exception:
            duration = 0.0  # 发生错误时默认 0.0

        # 获取内容评估结果和单词列表
        content_assessment = pronunciation_result.content_assessment_result
        words_list = pronunciation_result.words
        # 将单词对象列表转为可序列化的字典列表（根据实际需要提取字段）
        words_data = [{
            "word": word.word,
            "accuracy_score": word.accuracy_score,
            "error_type": word.error_type
        } for word in words_list] if words_list else []
        # 处理内容评估结果（根据实际字段提取）
        content_data = {
            "grammar_score": content_assessment.grammar_score,
            "vocabulary_score": content_assessment.vocabulary_score,
            "topic_score": content_assessment.topic_score
        } if content_assessment else {}

        # print("detailed_result: ", detailed_result)
        # print("-------------------")
        # print("words_data: ", words_data)

        return {
            "pronunciation_score": pronunciation_result.pronunciation_score,
            "pron_score": pronunciation_result.pronunciation_score, # 发音总分
            "accuracy_score": pronunciation_result.accuracy_score, # 准确度评分
            "fluency_score": pronunciation_result.fluency_score, # 流利度评分
            "completeness_score": pronunciation_result.completeness_score, # 完整度评分
            "prosody_score": getattr(pronunciation_result, 'prosody_score', 0), # 韵律评分
            # "vocabulary_score": pronunciation_result.vocabulary_score, # 词汇评分
            # "grammar_score": pronunciation_result.grammar_score, # 语法评分
            # "topic_score": pronunciation_result.topic_score, # 主题评分
            # 修改点1：从ContentAssessment获取词汇/语法/主题评分（带空值保护）
            "vocabulary_score": getattr(pronunciation_result.content_assessment, 'vocabulary_score', 0) 
                if hasattr(pronunciation_result, 'content_assessment') 
                else 0,
            "grammar_score": getattr(pronunciation_result.content_assessment, 'grammar_score', 0) 
                if hasattr(pronunciation_result, 'content_assessment') 
                else 0,
            "topic_score": getattr(pronunciation_result.content_assessment, 'topic_score', 0) 
                if hasattr(pronunciation_result, 'content_assessment') 
                else 0,
            "content_assessment_result": content_data, # 内容评估结果
            "words": words_data, # 单词级别的评估结果
            "audio_duration": duration, # 音频时长
            "detailed_result": detailed_result  # 详细评估信息
        }

    else:
        raise Exception("语音评估失败")

def evaluate_pronunciation(reference_text):
    """ 使用麦克风评估用户发音 """
    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
    audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
    recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

    pronunciation_config = speechsdk.PronunciationAssessmentConfig(
        reference_text=reference_text,
        grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
        granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme
    )
    pronunciation_config.apply_to(recognizer)

    result = recognizer.recognize_once()
    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        pronunciation_result = speechsdk.PronunciationAssessmentResult(result)
        return {
            "text": result.text,
            "pronunciation_score": pronunciation_result.pronunciation_score,
            "accuracy_score": pronunciation_result.accuracy_score,
            "fluency_score": pronunciation_result.fluency_score,
            "completeness_score": pronunciation_result.completeness_score
        }
    else:
        raise Exception("语音评估失败")
