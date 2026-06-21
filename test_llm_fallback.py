"""测试 LLM fallback 机制"""
import asyncio
from app.services.llm.client import get_llm_client

async def main():
    print("=" * 80)
    print("测试 LLM Fallback 机制")
    print("=" * 80)

    client = get_llm_client()

    print(f"\n主模型: {client.default_model}")
    print(f"Fallback 链: {' → '.join(client.fallback_models)}")

    print("\n" + "=" * 80)
    print("测试场景1: 正常调用(主模型可用)")
    print("=" * 80)

    try:
        result = await client.chat_completion(
            "你是一个数学助手,只输出计算结果数字。",
            "100+100-98=?",
            temperature=0.0,
        )
        print(f"✅ 成功: {result.strip()}")
    except Exception as e:
        print(f"❌ 失败: {e}")

    print("\n" + "=" * 80)
    print("测试场景2: 主模型不可用(强制使用不存在的模型)")
    print("=" * 80)

    try:
        result = await client.chat_completion(
            "你是一个数学助手,只输出计算结果数字。",
            "200+200-198=?",
            temperature=0.0,
            model="invalid-model-xxxxx",  # 强制指定一个不存在的模型
        )
        print(f"✅ Fallback 成功: {result.strip()}")
    except Exception as e:
        print(f"❌ 所有模型均失败: {str(e)[:200]}")

if __name__ == "__main__":
    asyncio.run(main())
