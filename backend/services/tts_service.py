import os
import uuid
import azure.cognitiveservices.speech as speechsdk

from flask import current_app

def _build_ssml(text, locale, voice, style, styledegree, role, rate, pitch, volume):
    # prosody
    prosody_attrs = []
    if rate:
        prosody_attrs.append(f'rate="{rate}"')
    if pitch:
        prosody_attrs.append(f'pitch="{pitch}"')
    if volume:
        prosody_attrs.append(f'volume="{volume}"')
    prosody_open = f"<prosody {' '.join(prosody_attrs)}>" if prosody_attrs else ""
    prosody_close = "</prosody>" if prosody_attrs else ""

    # express-as (mstts)
    expr_open = expr_close = ""
    if style or styledegree or role:
        attrs = []
        if style:
            attrs.append(f'style="{style}"')
        if styledegree:
            attrs.append(f'styledegree="{styledegree}"')
        if role:
            attrs.append(f'role="{role}"')
        expr_open = f'<mstts:express-as {" ".join(attrs)}>'
        expr_close = '</mstts:express-as>'

    ssml = (
        f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        f'xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="{locale}">'
        f'<voice name="{voice}">'
        f'{expr_open}{prosody_open}{text}{prosody_close}{expr_close}'
        f'</voice></speak>'
    )
    return ssml

def text_to_speech(text, locale="en-US", voice="en-US-JennyNeural",
                   style=None, styledegree=None, role=None,
                   rate=None, pitch=None, volume=None):
    """调用 Azure Speech SDK（Neural TTS），返回本地文件路径"""
    key = os.getenv("AZURE_SPEECH_KEY")
    region = os.getenv("AZURE_SPEECH_REGION")
    speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
    speech_config.speech_synthesis_voice_name = voice
    # 可根据需要调整输出格式
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio48Khz192KBitRateMonoMp3
    )

    ssml = _build_ssml(text, locale, voice, style, styledegree, role, rate, pitch, volume)
    synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config,
        audio_config=None  # 不在此指定文件，让后续写入
    )
    result = synthesizer.speak_ssml_async(ssml).get()

    if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
        err = result.cancellation_details.reason  # type: ignore
        return {"error": f"TTS 失败: {err}"}

    # 写文件
    out_dir = "./outputs"
    os.makedirs(out_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.mp3"
    path = os.path.join(out_dir, filename)
    with open(path, "wb") as f:
        f.write(result.audio_data)  # type: ignore
    return {"file": path}
