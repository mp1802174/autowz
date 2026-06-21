"""LLM API 可用模型全面测试

测试策略:
1. 从配置读取 base_url 和 api_key
2. 列出所有可用模型
3. 对每个模型进行数学推理测试: "100+100-98=?"
4. 记录响应时间、成功率、输出质量
"""
import asyncio
import time
from openai import AsyncOpenAI
from app.core.config import get_settings

async def test_model(client: AsyncOpenAI, model: str) -> dict:
    """测试单个模型的可用性和推理能力"""
    result = {
        "model": model,
        "available": False,
        "response_time": None,
        "answer": None,
        "raw_output": None,
        "error": None,
    }

    try:
        start = time.time()
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个数学计算助手,只输出计算结果的数字,不要解释过程。"},
                {"role": "user", "content": "100+100-98=?"}
            ],
            temperature=0.0,
            max_tokens=50,
        )
        elapsed = time.time() - start

        answer = response.choices[0].message.content.strip()
        result["available"] = True
        result["response_time"] = round(elapsed, 2)
        result["answer"] = answer
        result["raw_output"] = answer

        # 验证答案
        if "102" in answer:
            result["correct"] = True
        else:
            result["correct"] = False

    except Exception as e:
        result["error"] = str(e)[:200]

    return result


async def list_models(client: AsyncOpenAI) -> list[str]:
    """列出所有可用模型"""
    try:
        models_response = await client.models.list()
        return [m.id for m in models_response.data]
    except Exception as e:
        print(f"❌ 无法列出模型: {e}")
        return []


async def main():
    settings = get_settings()

    print("=" * 80)
    print("LLM API 模型可用性测试")
    print("=" * 80)
    print(f"API Base URL: {settings.openai_base_url}")
    print(f"API Key: {settings.openai_api_key[:20]}..." if len(settings.openai_api_key) > 20 else settings.openai_api_key)
    print(f"默认模型: {settings.openai_model}")
    print()

    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )

    # 步骤1: 列出所有模型
    print("步骤1: 获取可用模型列表...")
    models = await list_models(client)

    if not models:
        print("⚠️  API 未返回模型列表,将测试配置中的默认模型")
        models = [settings.openai_model]
    else:
        print(f"✅ 发现 {len(models)} 个模型\n")
        for i, m in enumerate(models, 1):
            marker = " ← 当前配置" if m == settings.openai_model else ""
            print(f"  {i}. {m}{marker}")

    print(f"\n步骤2: 测试每个模型的数学推理能力 (100+100-98=?)")
    print("=" * 80)

    # 步骤2: 测试每个模型
    results = []
    for i, model in enumerate(models, 1):
        print(f"\n[{i}/{len(models)}] 测试模型: {model}")
        result = await test_model(client, model)
        results.append(result)

        if result["available"]:
            correct_marker = "✅ 正确" if result.get("correct") else "❌ 错误"
            print(f"  状态: ✅ 可用")
            print(f"  响应时间: {result['response_time']}s")
            print(f"  回答: {result['answer']}")
            print(f"  准确性: {correct_marker}")
        else:
            print(f"  状态: ❌ 不可用")
            print(f"  错误: {result['error']}")

    # 步骤3: 汇总报告
    print("\n" + "=" * 80)
    print("测试汇总")
    print("=" * 80)

    available = [r for r in results if r["available"]]
    correct = [r for r in results if r.get("correct")]

    print(f"总模型数: {len(results)}")
    print(f"可用模型: {len(available)}")
    print(f"推理正确: {len(correct)}")

    if correct:
        print(f"\n✅ 推荐使用的模型:")
        for r in sorted(correct, key=lambda x: x["response_time"]):
            current = " ← 当前配置" if r["model"] == settings.openai_model else ""
            print(f"  • {r['model']} ({r['response_time']}s){current}")

    if available and not correct:
        print(f"\n⚠️  可用但推理错误的模型:")
        for r in available:
            if not r.get("correct"):
                print(f"  • {r['model']} - 回答: {r['answer']}")

    unavailable = [r for r in results if not r["available"]]
    if unavailable:
        print(f"\n❌ 不可用的模型:")
        for r in unavailable:
            print(f"  • {r['model']}")
            print(f"    错误: {r['error'][:100]}")

    # 步骤4: 配置建议
    print("\n" + "=" * 80)
    print("配置建议")
    print("=" * 80)

    if settings.openai_model in [r["model"] for r in correct]:
        print(f"✅ 当前配置的模型 '{settings.openai_model}' 工作正常")
    elif correct:
        fastest = sorted(correct, key=lambda x: x["response_time"])[0]
        print(f"⚠️  当前配置的模型不可用或推理错误")
        print(f"建议修改 .env 为:")
        print(f"  OPENAI_MODEL={fastest['model']}")
    else:
        print(f"❌ 所有模型均不可用或无法正确推理")
        print(f"请检查:")
        print(f"  1. API 服务是否在线")
        print(f"  2. API Key 是否有效")
        print(f"  3. Base URL 是否正确")


if __name__ == "__main__":
    asyncio.run(main())
