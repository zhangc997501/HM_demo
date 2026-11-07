import wave
from pathlib import Path

import dashscope

try:
    from .config import API_KEY
except ImportError:
    from config import API_KEY

try:
    from dashscope.audio.asr import Recognition
except ImportError:
    from dashscope.legacy_1x.audio.asr import Recognition

dashscope.api_key = API_KEY          # 直接传值，不要 os.getenv(API_KEY)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = PROJECT_ROOT / "Audioresources"

# 后缀 → Recognition 的 format 参数
FORMAT_BY_SUFFIX = {".wav": "wav", ".mp3": "mp3", ".pcm": "pcm"}


# ---------------- 路径与音频信息 ----------------

def _resolve(p) -> Path:
    """把文件名/相对路径/绝对路径统一成绝对路径。"""
    p = Path(p)
    if p.is_absolute():
        return p.resolve()
    if p.exists():                    # 相对当前工作目录能找到，就尊重它
        return p.resolve()
    return (AUDIO_DIR / p).resolve()  # 否则当成 Audioresources 里的文件


def list_audio(audio_dir=None):
    """列出音频文件，最新的排最前。"""
    d = Path(audio_dir) if audio_dir else AUDIO_DIR
    if not d.exists():
        return []
    files = [f for f in d.iterdir()
             if f.is_file() and f.suffix.lower() in FORMAT_BY_SUFFIX]
    return sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)


def latest_audio(audio_dir=None):
    """取 Audioresources 里最新的一个音频，没有则返回 None。"""
    files = list_audio(audio_dir)
    return files[0] if files else None


def inspect_wav(path: Path):
    """wav 的采样率/声道数自查，非 wav 或读不了返回 None。"""
    try:
        with wave.open(str(path), "rb") as f:
            return {
                "rate": f.getframerate(),
                "channels": f.getnchannels(),
                "width": f.getsampwidth(),
                "seconds": f.getnframes() / f.getframerate(),
            }
    except Exception:
        return None


# ---------------- 核心识别 ----------------

def asr(wav_path=None) -> str:
    """
    识别单个音频。
    wav_path 为 None 时自动取 Audioresources 里最新的文件。
    """
    if wav_path is None:
        wav_path = latest_audio()
        if wav_path is None:
            raise FileNotFoundError(f"Audioresources 里没有音频文件: {AUDIO_DIR}")
    else:
        wav_path = _resolve(wav_path)

    if not wav_path.exists():
        raise FileNotFoundError(
            f"找不到音频文件: {wav_path}\n"
            f"当前工作目录: {Path.cwd()}\n"
            f"音频目录: {AUDIO_DIR}\n"
            f"目录内文件: {[f.name for f in list_audio()]}"
        )

    suffix = wav_path.suffix.lower()
    fmt = FORMAT_BY_SUFFIX.get(suffix)
    if fmt is None:
        raise ValueError(f"不支持的后缀 {suffix}，仅支持 {list(FORMAT_BY_SUFFIX)}")

    # 音频参数自检：paraformer 要 16k 单声道，不符会识别出错或为空
    meta = inspect_wav(wav_path)
    sample_rate = 16000
    if meta:
        if meta["rate"] != 16000:
            print(f"[ASR][警告] 采样率 {meta['rate']}Hz，建议转成 16000Hz")
            sample_rate = meta["rate"]          # 按实际采样率传，避免识别乱码
        if meta["channels"] != 1:
            print(f"[ASR][警告] 声道数 {meta['channels']}，建议转成单声道")
        print(f"[ASR] {wav_path.name}  时长 {meta['seconds']:.2f}s  "
              f"{meta['rate']}Hz/{meta['channels']}ch")

    print(f"[ASR] 识别文件: {wav_path.name}")

    recognition = Recognition(
        model="paraformer-realtime-v2",
        format=fmt,
        sample_rate=sample_rate,
        callback=None,
    )
    result = recognition.call(file=str(wav_path))   # 必须 str 绝对路径

    # 绝对不要 print(result)，legacy 层 __str__ 有 bug
    print(f"[ASR] status={result.status_code} message={result.message}")

    if result.status_code != 200:
        raise RuntimeError(f"ASR 失败: {result.status_code} {result.message}")

    sentences = result.get_sentence() or []
    print(f"[ASR] 识别到 {len(sentences)} 句")
    return "".join(s.get("text", "") for s in sentences).strip()


def asr_all(audio_dir=None) -> dict:
    """
    批量识别整个目录。单个失败不影响其他文件。
    返回 {文件名: 文本}，失败的值为 "[失败] 原因"。
    """
    files = list_audio(audio_dir)
    if not files:
        print(f"[ASR] {AUDIO_DIR} 里没有音频文件")
        return {}

    results = {}
    for i, f in enumerate(files, 1):
        print(f"\n--- ({i}/{len(files)}) {f.name} ---")
        try:
            results[f.name] = asr(f)
        except Exception as e:
            print(f"[ASR] 失败: {e}")
            results[f.name] = f"[失败] {e}"
    return results


if __name__ == "__main__":
    import sys

    print(f"音频目录: {AUDIO_DIR}")
    files = list_audio()
    if not files:
        print("目录里还没有音频文件，先跑录音脚本")
        sys.exit(0) # 退出程序

    print(f"共 {len(files)} 个文件:")
    for f in files:
        print(f"  {f.name}")

    arg = sys.argv[1] if len(sys.argv) > 1 else None

    if arg == "--all":
        out = asr_all()
        print("\n===== 汇总 =====")
        for name, text in out.items():
            print(f"{name}: {text}")
    elif arg:
        print(f"\n=== 识别结果 {arg} ===")
        print(asr(arg))
    else:
        print(f"\n=== 识别最新文件 {files[0].name} ===")
        print(asr())