import io
import re
import wave
import numpy as np
import sounddevice as sd
from piper import PiperVoice
from piper.config import SynthesisConfig

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> list[str]:
    """Cheap sentence splitter — good enough for TTS chunking, not NLP-grade."""
    parts = _SENTENCE_SPLIT_RE.split(text.strip())
    return [p for p in parts if p]


class TextToSpeech:
    def __init__(self, model_path: str, config_path: str = None):
        self.voice = PiperVoice.load(model_path, config_path)
        self.sample_rate = self.voice.config.sample_rate

    def _synthesize_wav_bytes(self, text: str, speaker_id: int = None) -> bytes:
        syn_config = SynthesisConfig(speaker_id=speaker_id) if speaker_id is not None else None
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav_file:
            self.voice.synthesize_wav(text, wav_file, syn_config=syn_config)
        return buf.getvalue()

    def synthesize_to_wav_bytes(self, text: str, speaker_id: int = None) -> bytes:
        return self._synthesize_wav_bytes(text, speaker_id)

    def speak(self, text: str, speaker_id: int = None):
        """Non-streaming — whole reply synthesized before any audio plays."""
        wav_bytes = self._synthesize_wav_bytes(text, speaker_id)
        buf = io.BytesIO(wav_bytes)
        with wave.open(buf, "rb") as wav_file:
            n_frames = wav_file.getnframes()
            audio = np.frombuffer(wav_file.readframes(n_frames), dtype=np.int16)
        sd.play(audio, samplerate=self.sample_rate)
        sd.wait()

    def speak_stream(self, text: str, speaker_id: int = None):
        """
        Splits text into sentences and speaks each one as soon as it's
        synthesized, instead of waiting for the whole reply. Cuts
        time-to-first-sound from 'whole reply' to 'first sentence'.
        """
        syn_config = SynthesisConfig(speaker_id=speaker_id) if speaker_id is not None else None
        sentences = split_sentences(text)

        stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="int16",
        )
        stream.start()
        try:
            for sentence in sentences:
                for chunk in self.voice.synthesize(sentence, syn_config=syn_config):
                    stream.write(chunk.audio_int16_array)
        finally:
            stream.stop()
            stream.close()


def load_tts(config: dict) -> TextToSpeech:
    return TextToSpeech(
        model_path=config["tts"]["model_path"],
        config_path=config["tts"].get("config_path"),
    )