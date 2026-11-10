"""Bounded PCM/WAV helpers. No model or platform dependencies."""
import array
import io
import math
import sys
import wave


def read_wav(data, maximum_seconds=120):
    try:
        with wave.open(io.BytesIO(data), 'rb') as wav:
            rate, channels, width = wav.getframerate(), wav.getnchannels(), wav.getsampwidth()
            if channels != 1 or width != 2 or wav.getcomptype() != 'NONE' or not 8000 <= rate <= 48000:
                raise ValueError('音频必须为8–48kHz、单声道PCM16 WAV')
            frames = wav.getnframes()
            if not 0 < frames <= maximum_seconds * rate:
                raise ValueError('音频长度无效或超过限制')
            pcm = wav.readframes(frames)
            if len(pcm) != frames * 2:
                raise ValueError('WAV音频不完整')
            return pcm, rate
    except (wave.Error, EOFError) as exc:
        raise ValueError('WAV格式无效') from exc


def wav_bytes(pcm, rate=16000):
    if not pcm or len(pcm) % 2 or not 8000 <= rate <= 48000:
        raise ValueError('PCM音频参数无效')
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
        wav.writeframes(pcm)
    return output.getvalue()


class PCMResampler:
    """Windowed-sinc streaming resampler; preserves state across arbitrary chunks.

    Output is delayed by 16 source samples so the filter has both past and future
    context. finish() emits the tail once. It never joins complete utterances.
    """
    radius = 16

    def __init__(self, source_rate, target_rate=16000):
        if not all(type(x) is int and 8000 <= x <= 48000 for x in (source_rate, target_rate)):
            raise ValueError('重采样采样率无效')
        self.source_rate, self.target_rate = source_rate, target_rate
        self.samples = [0] * self.radius
        self.offset = -self.radius
        self.input_count = self.output_count = 0
        self.pending = b''
        self.kernels = {}
        self.closed = False

    def kernel(self, phase):
        if phase not in self.kernels:
            fraction = phase / self.target_rate
            cutoff = min(1, self.target_rate / self.source_rate) * .9
            weights = []
            for tap in range(-self.radius + 1, self.radius + 1):
                distance = tap - fraction
                sinc = cutoff if abs(distance) < 1e-12 else math.sin(math.pi * cutoff * distance) / (math.pi * distance)
                window = .5 + .5 * math.cos(math.pi * distance / self.radius)
                weights.append(sinc * window)
            total = sum(weights)
            self.kernels[phase] = [weight / total for weight in weights]
        return self.kernels[phase]

    def feed(self, data):
        if self.closed:
            raise ValueError('重采样器已结束')
        data = self.pending + data
        self.pending = data[len(data) // 2 * 2:]
        data = data[:len(data) // 2 * 2]
        if self.source_rate == self.target_rate:
            self.input_count += len(data) // 2
            self.output_count = self.input_count
            return data
        samples = array.array('h')
        samples.frombytes(data)
        if sys.byteorder != 'little':
            samples.byteswap()
        self.samples.extend(samples)
        self.input_count += len(samples)
        return self._emit(False)

    def finish(self):
        if self.closed:
            return b''
        self.closed = True
        if self.pending:
            raise ValueError('PCM音频在半个采样点处结束')
        if self.source_rate == self.target_rate:
            return b''
        self.samples.extend([0] * (self.radius + 1))
        return self._emit(True)

    def _emit(self, final):
        output = array.array('h')
        maximum = self.input_count * self.target_rate // self.source_rate
        while self.output_count < maximum:
            center, phase = divmod(self.output_count * self.source_rate, self.target_rate)
            if not final and center + self.radius >= self.offset + len(self.samples):
                break
            start = center - self.radius + 1 - self.offset
            weights = self.kernel(phase)
            value = sum(self.samples[start + tap] * weight for tap, weight in enumerate(weights))
            output.append(max(-32768, min(32767, round(value))))
            self.output_count += 1
        next_center = self.output_count * self.source_rate // self.target_rate
        discard = max(0, next_center - self.radius - self.offset)
        if discard:
            del self.samples[:discard]
            self.offset += discard
        if sys.byteorder != 'little':
            output.byteswap()
        return output.tobytes()
