import azure.cognitiveservices.speech as speechsdk
import os

speech_key = os.getenv("AZURE_SPEECH_KEY")
service_region = os.getenv("AZURE_SPEECH_REGION")

def recognize_speech_mic(output_folder):
    """ 使用麦克风进行语音识别，并保存录音 """
    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
    audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
    recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

    result = recognizer.recognize_once()
    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        filename = os.path.join(output_folder, "mic_recording.wav")
        # 这里可以添加保存录音逻辑
        return result.text, filename
    else:
        raise Exception("未识别到语音")

def recognize_speech_file(audio_file, output_folder):
    """ 识别上传的音频文件，并保存 """
    file_path = os.path.join(output_folder, audio_file.filename)
    audio_file.save(file_path)

    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
    audio_config = speechsdk.audio.AudioConfig(filename=file_path)
    recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

    result = recognizer.recognize_once()
    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        return result.text, file_path
    else:
        raise Exception("未识别到语音")
