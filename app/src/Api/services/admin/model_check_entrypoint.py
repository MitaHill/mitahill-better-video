import json
import sys

from .model_checks import _warmup_transcription_model


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: model_check_entrypoint.py '<model-entry-json>'")
    print(json.dumps(_warmup_transcription_model(json.loads(sys.argv[1])), ensure_ascii=False))


if __name__ == "__main__":
    main()
