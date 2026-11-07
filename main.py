import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from modules.config import API_KEY  # noqa: F401  导入即触发 .env 加载
from modules.voice_api import router as voice_router

app = FastAPI(title="Agent")

# 路由注册必须在模块层，不能放在 if __name__ == "__main__" 里
# 语音路由 include_router(voice_router)是注册路由
app.include_router(voice_router)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8989, reload=True)


"""
#  逻辑步骤：
第 0 步：启动时（一次性）
第 1 步：uvicorn 建 socket、收字节
uvicorn  →  socket.listen(0.0.0.0:8989)  →  等连接
ESP32 发来 TCP 连接  →  uvicorn 读 HTTP 报文头  →  解析出：
    method = POST
    path   = /api/voice/raw
    query  = device_sn=ESP32-SIM-0001&sample_rate=16000
    body   = 109440 字节的 PCM（还在陆续到达）
    
第 2 步：FastAPI 查路由表、派发
app  →  Router.__call__  →  按 path+method 查表  →  命中 APIRoute
     →  解析参数：
            device_sn   ← query 里的 "ESP32-SIM-0001"       （因为标了 Query()）
            session_id  ← query 里没有 → None
            sample_rate ← query 里的 16000
            request     ← 类型注解是 Request，直接注入原始请求对象
     →  调用 voice_raw(request, device_sn, session_id, sample_rate)
     
第 3 步：voice_raw() —— 接收 + 落盘    
modules/voice_api.py 里的 voice_raw()，做四件事：
request.stream() 是 Starlette 提供的异步字节流迭代器。它在 body 每到达一块时唤醒一次，
你写一块，内存里最多只有一块（1KB~64KB），不会把 10MB 全塞进 RAM。
产物：Audioresources/ESP32-SIM-0001_20261106_195211_123.pcm
然后两道校验：
if total < MIN_BYTES:  → 400 "音频太短"
if total % 2 != 0:     → 400 "不是 16bit"
_pcm_to_wav() —— 补 WAV 头
裸 PCM 只有采样数据，没有“我是什么格式”的说明。wave 模块会补上 44 字节的文件头（RIFF/WAVE/fmt/data），
里面写明 16000Hz、16bit、单声道。这一步不可省——DashScope 的识别接口要读 WAV 头来判断格式。
产物：同名 .wav，.pcm 自动删掉。
第 5 步：_chat_from_wav() —— 编排核心
# ① 语音转文字
user_text = await run_in_threadpool(asr, wav_path)
# ② 文字送大模型
reply = await run_in_threadpool(_ask_llm, session_id, user_text)
为什么必须包 run_in_threadpool：asr() 内部是同步阻塞的 HTTP 请求（DashScope），_ask_llm() 也是同步的（OpenAI SDK）。
如果直接 await 调用它们（或者忘了 await），整个事件循环会被卡住——这期间其他设备的请求全部排队等着，表现为“只有一个设备能用”。
run_in_threadpool 把它们丢进 Starlette 维护的线程池，事件循环立刻空出来继续接别的请求。

_ask_llm() 内部：
history = SESSIONS.setdefault(session_id, [])       # 按 session_id 取历史
history.append({"role": "user", "content": user_text})
messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history[-20:]
resp = client.chat.completions.create(model=TEXT_MODEL, messages=messages)
reply = resp.choices[0].message.content
history.append({"role": "assistant", "content": reply})   # 存回历史

多轮上下文的全部实现就是这三行 SESSIONS 字典操作。session_id 相同，历史就在同一个列表里。

第 6 步：返回 dict → JSON → 写回 socket
_chat_from_wav() 返回一个普通 Python dict：

FastAPI 拿到返回值后自动：
    1.用 jsonable_encoder 转成可序列化结构
    2.包成 JSONResponse，序列化成 JSON 字节
    3.加上响应头 Content-Type: application/json、Content-Length: ...
    4.交给 uvicorn
    
第 7 步：uvicorn 写回同一条连接
这里有个关键点：服务端没有“主动发给 ESP32”，它是在 ESP32 发起的那条 TCP 连接上写响应。
ESP32  ──── TCP connect ────→  你的电脑
ESP32  ──── POST /api/voice/raw ────→
                                uvicorn 收到，调用你的函数
ESP32  ←─── 200 OK + JSON ────  写回同一条连接
ESP32  ──── 关闭连接（或 Keep-Alive 复用）

所以 ESP32 那边是同步阻塞等的：esp_http_client_perform() 或 fetch_headers() + read() 会一直卡到服务端返回。
ASR + 大模型要 2 秒，ESP32 就等 2 秒。这就是为什么设备端 timeout_ms 要设 30 秒——设 3 秒会大量超时失败。


ESP32-S3                    uvicorn/FastAPI              你的代码                外部服务
   │                              │                          │                      │
   ├─ TCP connect :8989 ─────────→│                          │                      │
   ├─ POST /api/voice/raw ───────→│                          │                      │
   │   + 109440B PCM              ├─ 查路由表 ──────────────→│                      │
   │   (chunked)                  ├─ 解析 query              │                      │
   │                              ├─ 调用 voice_raw() ──────→│                      │
   │                              │                          ├─ _resolve_session()  │
   │── PCM 分片陆续到达 ──────────→│                          │                      │
   │                              │                          ├─ request.stream()    │
   │                              │                          │   → 写 .pcm 文件      │
   │                              │                          ├─ _pcm_to_wav()       │
   │                              │                          ├─ _chat_from_wav()    │
   │                              │                          │    ├─ asr() ────────→ │ DashScope
   │                              │                          │    │   ← 文本 ←───────┤
   │                              │                          │    └─ _ask_llm() ───→ │ Qwen
   │                              │                          │        ← 回复 ←───────┤
   │                              │←─ 返回 dict ─────────────┤                      │
   │←── 200 + JSON ───────────────┤ JSONResponse             │                      │
   │                              │                          │                      │
   ├─ cJSON_Parse → reply         │                          │                      │
   └─ LVGL 显示                   │                          │                      │
    
"""