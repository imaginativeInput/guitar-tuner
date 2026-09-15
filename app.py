# bytes_per_frame = width * channels
# Stereo S16 is L R L R ..., 4 bytes per frame.

import wave, array, math, sys, subprocess, shutil

RATE, WIDTH, CH = 48000, 2, 1


with wave.open('tone.wav', 'wb') as w:
    w.setnchannels(CH)      # must be set before writeframes.
    w.setsampwidth(WIDTH)   # bytes, not bits
    w.setframerate(RATE)

    amp = 32767 * 10**(-6/20)
    buf = array.array(
            'h',
            (int(amp * math.sin(2*math.pi*440*n/RATE))
            for n in range(RATE)))
    if sys.byteorder == 'big': buf.byteswap()   # WAV is always little-endian
    w.writeframes(buf.tobytes())


with wave.open('tone.wav', 'rb') as r:
    p = r.getparams()
    print(p)        # _wave_params(nchannels=1, sampwidth=2, framerate=48000,
                    # nframes=48000, comptype='NONE', compname='not compressed')
    assert p.sampwidth == 2, 'this code only handles s16'
    raw = r.readframes(p.nframes)       # bytes, interleaved
    samples = array.array('h'); samples.frombytes(raw)
    duration = p.nframes / p.framerate


def record_to_wav(path, seconds, rate=48000, ch=1, target=None):
    if shutil.which('pw-record') is None:
        raise RuntimeError('install pipewire-utils')
    cmd = ['pw-record', '--rate', str(rate),
           '--channels', str(ch),
           '--format', 's16']
    if target: cmd += ['--target', str(target)]
    cmd.append(path)

    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE)
    try:
        proc.wait(timeout=seconds)      # it runs forever: the timeout is the duration
    except subprocess.TimeoutExpired:   # SIGTERM -> clean WAV header
        proc.terminate()
        try: proc.wait(timeout=2)
        except subprocess.TimeoutExpired: proc.kill()
    else:
        raise RuntimeError(proc.stderr.read().decode())

    with wave.open(path) as r:
        return r.getparams()

print(record_to_wav('/tmp/take01.wav', seconds=5))


# Capture pattern B - raw PCM over a pipe (PCM = Pulse Code Modulation)
import subprocess, wave, array, math, sys

RATE, CH, WIDTH = 48000, 1, 2
FRAMES = 1024
CHUNK  = FRAMES * CH * WIDTH          # 2048 bytes

cmd = ["parec", "--format=s16le", f"--rate={RATE}",
       f"--channels={CH}", "--latency-msec=20"]

proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        bufsize=0,)

with wave.open("/tmp/stream.wav", "wb") as w:
    w.setnchannels(CH); w.setsampwidth(WIDTH); w.setframerate(RATE)
    try:
        while True:
            buf = proc.stdout.read(CHUNK)            # blocks; short read only at EOF
            if not buf:
                err = proc.stderr.read().decode(errors='replace')
                print(f'parec exited with {proc.returncode}: {err}')
                break
            w.writeframes(buf)                   # persist unmodified bytes

            s = array.array("h"); s.frombytes(buf)  # and analyse a copy
            rms = math.sqrt(sum(v*v for v in s) / len(s))
            db  = 20*math.log10(rms/32768) if rms else -999
            bars = "█" * max(0, int((db + 60) / 2))
            print(f"\r{db:7.1f} dBFS |{bars:<30}|", end="", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate(); proc.wait(timeout=2)


# 24bit int
import struct

raw = b'\x00\x80\xff\x7f'       # -> 16bit
# 1 - array: native byte order, so swap on big-endian hosts
a = array.array('h')
a.frombytes(raw)
if sys.byteorder == 'big': a.byteswap()
# array('h', [-32768, 32767])

# 2 - struct: byte order is explicit in the format string, always portable
n = len(raw) // 2
b = struct.unpack(f'<{n}h', raw)    # '<' = little-endian, 'h' = int16

# 3 - 24-bit: three bytes, signed, little-endian
def s24_to_int(buf):
    return [
    int.from_bytes(buf[i:i+3], 'little', signed=True)
            for i in range(0, len(buf), 3)]


# Peak, RMS, and dBFS without audioop library
import array, math

FS = 32768.0

def as_int16(buf):
    a = array.array('h'); a.frombytes(buf); return a

def peak(a):        return max(max(a), -min(a)) / FS
def rms(a):         return math.sqrt(sum(v*v for v in a) / len(a)) / FS
def dbfs(x):        return 20*math.log10(x) if x > 1e-12 else -120.0
def dc_offset(a):   return sum(a) / len(a) / FS
def clipped(a):     return sum(1 for v in a if v >= 32767 or v <= -32768)

def to_mono(a, ch=2):
    return array.array('h', (sum(a[i:i+ch]) // ch
                        for i in range(0, len(a), ch)))

def split_channels(a, ch=2):
    return [array.array('h', a[c::ch]) for c in range(ch)]

'''
Two Traps in Four Lines

-min(a) overflows conceptually at -32768: its negation is 32768, which is
one past int16 peak. Clamp if you feed the result back into an array('h').
And log10(0) raises ValueError -- digital silence is genuinely −∞ dBFS,
so every real meter floors it, usually at -120 or -144 dB.
'''









