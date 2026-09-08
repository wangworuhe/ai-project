"""Google Translate TTS integration kept separate from Azure TTS."""

import re
from io import BytesIO

from gtts import gTTS
from gtts.tts import gTTSError

from backend.services.audio_output_service import create_timestamped_mp3_path


MAX_TEXT_LENGTH = 10_000
ALLOWED_TLDS = {"com", "co.uk", "com.au", "ca", "co.in"}


def clean_text_for_tts(text: str) -> str:
    """Normalize pasted text so Google TTS receives natural sentence spacing."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\n", " ").replace("_", "")
    text = re.sub(r"\.\s*\.\s*\.", "...", text)
    text = text.replace("…", "...")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    text = re.sub(r"([,.!?;:])([^\s\"'])", r"\1 \2", text)
    text = re.sub(r"\.\s*\.\s*\.", "...", text)
    return re.sub(r'([?.!])["“”\']+\s*$', r"\1", text).strip()


def text_to_google_speech(text: str, lang: str, tld: str, slow: bool) -> dict:
    """Generate an MP3 with gTTS and store it in the existing media directory."""
    if len(text) > MAX_TEXT_LENGTH:
        return {"error": f"文本过长，最长 {MAX_TEXT_LENGTH} 个字符", "status": 400}

    cleaned_text = clean_text_for_tts(text)
    if not cleaned_text:
        return {"error": "文本清洗后为空，请检查输入内容", "status": 400}
    if tld not in ALLOWED_TLDS:
        return {"error": "不支持的英语地区口音", "status": 400}

    try:
        buffer = BytesIO()
        gTTS(text=cleaned_text, lang=lang, tld=tld, slow=slow).write_to_fp(buffer)
    except ValueError as error:
        return {"error": f"Google TTS 参数错误: {error}", "status": 400}
    except gTTSError:
        return {"error": "无法连接 Google TTS，请检查网络后重试", "status": 502}
    except Exception:
        return {"error": "Google TTS 生成失败，请稍后重试", "status": 500}

    path, media_path = create_timestamped_mp3_path("google")
    with open(path, "wb") as output_file:
        output_file.write(buffer.getvalue())

    return {"file": path, "url": f"/api/media/{media_path}"}
