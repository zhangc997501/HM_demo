import wave
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd

FS = 16000            # 采样率
CHANNELS = 1
DTYPE = "int16"


def _find_project_root(start: Path) -> Path:
    """从脚本所在目录往上找，认 .env / app.py / main.py 作为项目根标记。"""
    for p in [start, *start.parents]:
        if (p / ".env").exists() or (p / "app.py").exists() or (p / "main.py").exists():
            return p
    return start          # 兜底：就当成脚本同目录


PROJECT_ROOT = _find_project_root(Path(__file__).resolve().parent)
AUDIO_DIR = PROJECT_ROOT / "Audioresources"


def record_until_enter(filename="rec.wav", stamp=False):
    """
    录到回车为止，保存为 wav。
    filename: 文件名（不含目录），或绝对路径
    stamp:    True 时在文件名后加时间戳，避免覆盖
    """
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)      # 不存在就建，已存在不报错

    frames = []

    def callback(indata, frame_count, time_info, status):
        if status:
            print("状态:", status)
        frames.append(indata.copy())                  # 必须 copy

    print("=== 可用录音设备 ===")
    print(sd.query_devices())
    print()

    stream = sd.InputStream(
        samplerate=FS,
        channels=CHANNELS,
        dtype=DTYPE,
        callback=callback,
    )
    stream.start()
    input(">>> 说话中，按回车结束录音...")
    stream.stop()
    stream.close()

    if not frames:
        print("没有录到任何数据")
        return None

    audio = np.concatenate(frames, axis=0)

    # 静音自检：正常说话峰值应在 1000 以上，<100 基本录成了静音
    peak = int(np.abs(audio).max())
    if peak < 100:
        print(f"[警告] 峰值只有 {peak}，几乎没录到声音。"
              f"检查 Windows 设置→隐私和安全性→麦克风→允许桌面应用访问")

    # 拼出最终路径
    name = Path(filename)
    if name.suffix.lower() != ".wav":
        name = name.with_suffix(".wav")
    if stamp:
        name = name.with_name(f"{name.stem}_{datetime.now():%Y%m%d_%H%M%S}{name.suffix}")

    out_path = name if name.is_absolute() else (AUDIO_DIR / name)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with wave.open(str(out_path), "wb") as f:         # wave 要 str 路径
        f.setnchannels(CHANNELS)
        f.setsampwidth(2)                             # int16 = 2 字节
        f.setframerate(FS)
        f.writeframes(audio.tobytes())

    print(f"录音时长 {len(audio)/FS:.2f} 秒，峰值 {peak}")
    print(f"已保存: {out_path}")
    return str(out_path)


if __name__ == "__main__":
    print(f"项目根目录: {PROJECT_ROOT}")
    print(f"音频目录  : {AUDIO_DIR}")
    record_until_enter(stamp=True)