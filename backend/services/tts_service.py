import azure.cognitiveservices.speech as speechsdk
import os

speech_key = os.getenv("AZURE_SPEECH_KEY")
service_region = os.getenv("AZURE_SPEECH_REGION")

def text_to_speech(text, voice="en-US-JennyNeural"):
    """ 调用 Azure API 进行语音合成 """
    try:
        speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
        speech_config.speech_synthesis_voice_name = voice

        output_file = f"./outputs/tts_output.mp3"
        audio_config = speechsdk.audio.AudioOutputConfig(filename=output_file)

        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
        result = synthesizer.speak_text_async(text).get()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            return {"file": output_file}
        else:
            return {"error": f"TTS 失败: {result.reason}"}
    except Exception as e:
        return {"error": str(e)}
