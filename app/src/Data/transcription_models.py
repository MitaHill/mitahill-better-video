WHISPER_MODELS = {
    "tiny.en": {"repository": "Systran/faster-whisper-tiny.en", "vocabulary": "vocabulary.txt", "feature_size": 80},
    "tiny": {"repository": "Systran/faster-whisper-tiny", "vocabulary": "vocabulary.txt", "feature_size": 80},
    "base.en": {"repository": "Systran/faster-whisper-base.en", "vocabulary": "vocabulary.txt", "feature_size": 80},
    "base": {"repository": "Systran/faster-whisper-base", "vocabulary": "vocabulary.txt", "feature_size": 80},
    "small.en": {"repository": "Systran/faster-whisper-small.en", "vocabulary": "vocabulary.txt", "feature_size": 80},
    "small": {"repository": "Systran/faster-whisper-small", "vocabulary": "vocabulary.txt", "feature_size": 80},
    "medium.en": {"repository": "Systran/faster-whisper-medium.en", "vocabulary": "vocabulary.txt", "feature_size": 80},
    "medium": {"repository": "Systran/faster-whisper-medium", "vocabulary": "vocabulary.txt", "feature_size": 80},
    "large-v1": {"repository": "Systran/faster-whisper-large-v1", "vocabulary": "vocabulary.txt", "feature_size": 80},
    "large-v2": {"repository": "Systran/faster-whisper-large-v2", "vocabulary": "vocabulary.txt", "feature_size": 80},
    "large-v3": {"repository": "Systran/faster-whisper-large-v3", "vocabulary": "vocabulary.json", "feature_size": 128},
}


def get_whisper_model(model_id):
    return WHISPER_MODELS.get(str(model_id or "").strip().lower())
