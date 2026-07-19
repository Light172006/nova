import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
import torch

class STT:
    def __init__(self, model_size="base", device="cpu", compute_type="int8"):
        # base/int8 on CPU: good accuracy/speed tradeoff, zero GPU contention
        # bump to "small" if accuracy is rough for your mic/accent, at ~2x latency cost
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        self.sample_rate = 16000

        # Silero VAD — tiny, CPU-only, decides when speech starts/stops
        self.vad_model, self.vad_utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad", model="silero_vad", trust_repo=True
        )
        (self.get_speech_timestamps, _, _, _, _) = self.vad_utils

    def record_until_silence(self, max_seconds=15, silence_ms=800):
        """
        Records from mic, stops once VAD detects `silence_ms` of trailing silence.
        Returns raw float32 numpy audio at 16kHz.
        """
        chunk_duration = 0.5  # seconds per chunk fed to VAD
        chunk_samples = int(self.sample_rate * chunk_duration)
        buffer = []
        silence_chunks = 0
        max_silence_chunks = int((silence_ms / 1000) / chunk_duration)

        stream = sd.InputStream(samplerate=self.sample_rate, channels=1, dtype="float32")
        stream.start()

        for _ in range(int(max_seconds / chunk_duration)):
            chunk, _ = stream.read(chunk_samples)
            chunk = chunk.flatten()
            buffer.append(chunk)

            speech_ts = self.get_speech_timestamps(
                torch.from_numpy(chunk), self.vad_model, sampling_rate=self.sample_rate
            )
            if len(speech_ts) == 0:
                silence_chunks += 1
            else:
                silence_chunks = 0

            if silence_chunks >= max_silence_chunks and len(buffer) > 2:
                break

        stream.stop()
        stream.close()
        return np.concatenate(buffer)

    def transcribe(self, audio: np.ndarray) -> str:
        segments, _ = self.model.transcribe(audio, language="en", beam_size=5)
        return " ".join(seg.text.strip() for seg in segments)

    def listen(self) -> str:
        """Convenience wrapper: record + transcribe in one call."""
        audio = self.record_until_silence()
        return self.transcribe(audio)