try:
    from .config import client, TEXT_MODEL
except ImportError:
    from config import client, TEXT_MODEL

try:
    from .asr import asr
except ImportError:
    from asr import asr


def _call_model(prompt: str) -> str:
    """调一次文本大模型，返回模型的原始回复文本"""
    result = client.chat.completions.create(
        model=TEXT_MODEL,
        messages=[{"role": "system", "content": prompt}],
    )
    return result.choices[0].message.content

if __name__ == '__main__':

    print(_call_model(asr()))
