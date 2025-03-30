import requests
from bs4 import BeautifulSoup

def get_cambridge_pronunciation(word: str) -> dict:
    url = f"https://dictionary.cambridge.org/dictionary/english/{word}"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        return {"error": f"Failed to fetch data for '{word}'"}

    soup = BeautifulSoup(resp.text, "html.parser")

    # --- 美式音标与音频 ---
    ipa_us = None
    audio_us = None
    us_block = soup.select_one(".us.dpron-i")
    if us_block:
        ipa_tag = us_block.select_one(".pron .ipa")
        audio_tag = us_block.select_one("source[type='audio/mpeg']")
        ipa_us = ipa_tag.text if ipa_tag else None
        if audio_tag and audio_tag.get("src", "").startswith("/"):
            audio_us = "https://dictionary.cambridge.org" + audio_tag["src"]

    # --- 英式音标与音频 ---
    ipa_uk = None
    audio_uk = None
    uk_block = soup.select_one(".uk.dpron-i")
    if uk_block:
        ipa_tag = uk_block.select_one(".pron .ipa")
        audio_tag = uk_block.select_one("source[type='audio/mpeg']")
        ipa_uk = ipa_tag.text if ipa_tag else None
        if audio_tag and audio_tag.get("src", "").startswith("/"):
            audio_uk = "https://dictionary.cambridge.org" + audio_tag["src"]

    return {
        "word": word,
        "us": {
            "ipa": ipa_us,
            "audio": audio_us
        },
        "uk": {
            "ipa": ipa_uk,
            "audio": audio_uk
        }
    }
