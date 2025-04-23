import os
import json
import time
import requests
from dotenv import load_dotenv

"""
该脚本用于独立测试阿里云 DashScope 定制热词 API，放置于 tests/ 目录下，以符合项目结构约定。
运行方式：
$ python -m tests.test_hotwords_api
或者在 VSCode / PyCharm 中右键运行。
"""

BASE_URL = "https://dashscope.aliyuncs.com/api/v1/services/audio/asr/customization"


def load_api_key() -> str:
    """从 .env 或环境变量加载 API Key"""
    load_dotenv()
    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    if not api_key:
        raise RuntimeError("未设置 DASHSCOPE_API_KEY 环境变量，无法继续")
    return api_key


def pretty_print(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def headers(api_key: str):
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def list_vocab(api_key: str):
    """列出账号下所有热词表"""
    data = {
        "model": "speech-biasing",
        "input": {
            "action": "list_vocabulary",
            "page_index": 0,
            "page_size": 10,
        },
    }
    resp = requests.post(BASE_URL, headers=headers(api_key), json=data, timeout=30)
    print("[list_vocabulary] status:", resp.status_code)
    pretty_print(resp.json())


def create_simple_vocab(api_key: str):
    """创建一个仅包含一个中文词"测试"的热词表，返回 task_id"""
    payload = {
        "model": "speech-biasing",
        "input": {
            "action": "create_vocabulary",
            "target_model": "paraformer-v2",
            "prefix": "tpytest",
            "vocabulary": [
                {"text": "测试", "weight": 4, "lang": "zh"}
            ],
        },
    }
    resp = requests.post(BASE_URL, headers=headers(api_key), json=payload, timeout=30)
    print("[create_vocabulary] status:", resp.status_code)
    try:
        result = resp.json()
    except json.JSONDecodeError:
        print("返回内容不是 JSON:", resp.text)
        return None
    pretty_print(result)
    return result.get("output", {}).get("task_id")


def poll_task(api_key: str, task_id: str, max_try: int = 10):
    """轮询任务状态，直到 SUCCEED / FAILED 或达到最大次数"""
    query = {
        "model": "speech-biasing",
        "input": {
            "action": "query_task",
            "task_id": task_id,
        },
    }
    wait = 3
    for i in range(max_try):
        resp = requests.post(BASE_URL, headers=headers(api_key), json=query, timeout=30)
        status = resp.status_code
        print(f"[query_task] 第{i+1}次, HTTP {status}")
        try:
            data = resp.json()
        except json.JSONDecodeError:
            print("非 JSON 响应:", resp.text)
            break
        pretty_print(data)
        out = data.get("output", {})
        task_status = out.get("task_status") or out.get("status")
        if task_status == "SUCCEED":
            print("任务成功，vocabulary_id:", out.get("vocabulary_id"))
            return True
        if task_status == "FAILED":
            print("任务失败:", out.get("error_message"))
            return False
        time.sleep(wait)
        wait = min(wait * 1.5, 15)
    print("轮询超时/达到最大次数，退出")
    return False


if __name__ == "__main__":
    key = load_api_key()
    # 1. 查询现有热词表
    list_vocab(key)
    # 2. 创建热词表
    tid = create_simple_vocab(key)
    if tid:
        # 3. 查询任务状态
        poll_task(key, tid) 