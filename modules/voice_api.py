# modules/voice_api.py
import time
import uuid
import wave
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool

try:
    from .asr import asr
    from .config import TEXT_MODEL, client
except ImportError:
    from modules.asr import asr
    from modules.config import TEXT_MODEL, client


# 创建一个路由，用于处理语音相关请求
router = APIRouter(tags=["voice"])
# 音频文件保存目录
AUDIO_DIR = Path(__file__).resolve().parent.parent / "Audioresources"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# 最大音频文件大小为 10MB
MAX_BYTES = 10 * 1024 * 1024      # 10MB
# 最小音频文件大小为 0.1 秒
MIN_BYTES = 3200                  # 0.1 秒 16k/16bit 单声道
# 每次读取 64KB
CHUNK = 64 * 1024                 # 每次读 64KB

# ---- 临时上下文（代替 Redis，重启即丢）----
SESSIONS: dict[str, list] = {}  # 会话历史记录
MAX_ROUNDS = 10  # 最大轮数
SYSTEM_PROMPT = "你是一个智能终端助手，回答简洁口语化，不超过三句话，不要用 Markdown。"  # 系统提示


# ==================== 内部工具 ====================

# 当前时间戳，毫秒级
def _now_ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]

# 校验并生成会话 ID
def _resolve_session(session_id: str | None, device_sn: str) -> str:
    """校验并生成会话 ID：d{设备SN}-{随机串}。"""
    if session_id and not session_id.startswith(f"d{device_sn}-"):
        raise HTTPException(
            403,
            f"session_id 不属于该设备"
            f"（session_id={session_id!r}, device_sn={device_sn!r}）",
        )
    return session_id or f"d{device_sn}-{uuid.uuid4().hex[:12]}"

# 裸 PCM（16bit 单声道）补 44 字节 WAV 头
"""
PCM是Pulse Code Modulation的缩写，中文意思是脉冲编码调制。
"""
def _pcm_to_wav(pcm_path: Path, sample_rate: int) -> Path:
    """裸 PCM（16bit 单声道）补 44 字节 WAV 头。"""
    wav_path = pcm_path.with_suffix(".wav")
    # 这行代码的意思是，打开一个 PCM 文件进行读操作，打开一个 WAV 文件进行写操作。
    with open(pcm_path, "rb") as src, wave.open(str(wav_path), "wb") as dst:
        dst.setnchannels(1) # 设置声道数为单声道
        dst.setsampwidth(2) # 设置采样宽度为 16bit
        dst.setframerate(sample_rate) # 设置采样率为输入的 sample_rate
        dst.writeframes(src.read()) # 写入 PCM 数据
    pcm_path.unlink(missing_ok=True)  # 删除原始 PCM 文件
    return wav_path  # 返回 WAV 文件路径

# 同步调用大模型，由外层丢进线程池
def _ask_llm(session_id: str, user_text: str) -> str:
    """同步调用大模型，由外层丢进线程池。"""
    history = SESSIONS.setdefault(session_id, []) # 获取会话历史记录，没有则创建一个空列表
    history.append({"role": "user", "content": user_text}) # 添加用户输入到会话历史记录

    # 构造消息列表，包含系统提示和最近的会话历史：系统提示 + 最近的会话历史
    # -MAX_ROUNDS * 2: 最多包含 MAX_ROUNDS 轮对话，每轮对话包含用户输入和模型输出
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history[-MAX_ROUNDS * 2:]
    # 调用大模型
    resp = client.chat.completions.create(model=TEXT_MODEL, messages=messages)
    # 获取模型的回复内容
    reply = resp.choices[0].message.content or ""
    # 添加模型的回复到会话历史记录
    history.append({"role": "assistant", "content": reply})
    return reply.strip() # 去除回复内容两端的空白字符并返回

# 核心逻辑：wav 文件 → ASR → 大模型 → 统一响应
# 参数：会话 ID、wav 文件路径、请求开始时间 t0
async def _chat_from_wav(session_id: str, wav_path: Path, t0: float) -> dict:
    """
    核心逻辑：wav 文件 → ASR → 大模型 → 统一响应。
    voice_chat（multipart）和 voice_raw（裸 PCM）共用这一段。
    """
    try:
        # 这里是音频转文本（ASR）
        user_text = await run_in_threadpool(asr, wav_path)
    except Exception as e:
        raise HTTPException(502, f"ASR 失败: {e}")

    # 如果 ASR 结果为空，则返回错误信息
    if not user_text:
        return {
            "code": 1, # 1 表示错误
            "session_id": session_id, # 会话 ID
            "user_text": "", # 用户输入
            "reply": "没听清，请再说一遍。", # 模型的回复
            "audio": wav_path.name, # 音频文件名
            "elapsed_ms": int((time.perf_counter() - t0) * 1000), # 请求耗时
        }

    try:
        # 这里是大模型生成回复
        reply = await run_in_threadpool(_ask_llm, session_id, user_text)
    except Exception as e:
        raise HTTPException(502, f"LLM 失败: {e}")
    # 返回统一响应
    return {
        "code": 0, # 0 表示成功
        "session_id": session_id, # 会话 ID
        "user_text": user_text, # 用户输入
        "reply": reply, # 模型的回复
        "audio": wav_path.name, # 音频文件名
        "elapsed_ms": int((time.perf_counter() - t0) * 1000), # 请求耗时
    }


# ==================== 接口 ====================

# 设备上电自检：能打通说明 WiFi、IP、端口、防火墙全通
@router.get("/api/voice/ping")
async def voice_ping():
    """
    设备上电自检：能打通说明 WiFi、IP、端口、防火墙全通。
    curl http://192.168.x.x:8989/api/voice/ping
    """
    return {
        "ok": True,
        "server_time": datetime.now().isoformat(timespec="seconds"),
        "max_bytes": MAX_BYTES,
        "sessions": len(SESSIONS),
    }

# 浏览器 / 上位机用：multipart/form-data 上传完整 wav
@router.post("/api/voice/chat")
async def voice_chat(
    audio: UploadFile = File(...),
    device_sn: str = Form("PC-SIM"),
    session_id: str | None = Form(None),
    sample_rate: int = Form(16000),
):
    """
    浏览器 / 上位机用：multipart/form-data 上传完整 wav。
    返回 session_id，多轮对话时把它带回来。
    """
    t0 = time.perf_counter()
    session_id = _resolve_session(session_id, device_sn)

    save_path = AUDIO_DIR / f"{device_sn}_{_now_ts()}.wav"

    total = 0
    try:
        with open(save_path, "wb") as f:
            while chunk := await audio.read(CHUNK):
                total += len(chunk)
                if total > MAX_BYTES:
                    raise HTTPException(413, f"音频超过 {MAX_BYTES // 1024 // 1024}MB")
                f.write(chunk)
    except HTTPException:
        save_path.unlink(missing_ok=True)
        raise
    except Exception as e:
        save_path.unlink(missing_ok=True)
        raise HTTPException(500, f"保存音频失败: {e}")

    if total < MIN_BYTES:
        save_path.unlink(missing_ok=True)
        raise HTTPException(400, f"音频太短（{total} 字节）")

    return await _chat_from_wav(session_id, save_path, t0)

# 设备用：直接把裸 PCM（16bit 小端单声道）塞进 body，参数走 URL query
"""
参数说明：
    device_sn: 设备序列号，用于标识设备
    session_id: 会话 ID，用于多轮对话
    sample_rate: 采样率，用于音频转文本（ASR）

"""
@router.post("/api/voice/raw")
async def voice_raw(
    request: Request,
    device_sn: str = Query("ESP32-S3"),
    session_id: str | None = Query(None),
    sample_rate: int = Query(16000),
):
    """
    设备用：直接把裸 PCM（16bit 小端单声道）塞进 body，参数走 URL query。
    设备端不需要拼 multipart boundary，省事也省 RAM。

      POST /api/voice/raw?device_sn=ESP32-S3-0001&sample_rate=16000
      Content-Type: application/octet-stream
      body = 采样字节流
    """
    # 获取请求开始时间
    t0 = time.perf_counter()
    # 校验并生成会话 ID
    session_id = _resolve_session(session_id, device_sn)

    # 保存 PCM 文件路径
    pcm_path = AUDIO_DIR / f"{device_sn}_{_now_ts()}.pcm"

    # 接收 PCM 数据并保存为文件，边收边写，内存恒定
    total = 0
    try:
        with open(pcm_path, "wb") as f:
            # request.stream()就是请求体的流，可以边读边写入文件
            async for chunk in request.stream():     # 边收边写，内存恒定
                total += len(chunk)   # 接收音频字节
                if total > MAX_BYTES:
                    # 音频超过 10MB
                    raise HTTPException(413, f"音频超过 {MAX_BYTES // 1024 // 1024}MB")
                # 写入 PCM 数据
                f.write(chunk)
    except HTTPException:
        # 删除保存的 PCM 文件
        pcm_path.unlink(missing_ok=True)
        raise
    except Exception as e:
        # 删除保存的 PCM 文件
        pcm_path.unlink(missing_ok=True)
        raise HTTPException(500, f"接收音频失败: {e}")

    # 音频太短
    if total < MIN_BYTES:
        pcm_path.unlink(missing_ok=True)
        raise HTTPException(400, f"音频太短（{total} 字节）")
    # PCM 字节数不是偶数，格式可能不是 16bit
    if total % 2 != 0:                                # 16bit 单声道，字节数必须是偶数
        pcm_path.unlink(missing_ok=True)
        raise HTTPException(400, f"PCM 字节数 {total} 不是偶数，格式可能不是 16bit")
    # 裸 PCM 转 WAV 文件
    wav_path = _pcm_to_wav(pcm_path, sample_rate)
    # 调用核心逻辑：wav 文件 → ASR → 大模型 → 统一响应
    return await _chat_from_wav(session_id, wav_path, t0)