#!/usr/bin/env python3
"""
意图识别测试脚本

用于测试和调试意图识别的准确率
"""
import asyncio
import sys
import os
from typing import List, Dict

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.intent.router import get_intent_router


class IntentTester:
    """意图测试器"""

    # 测试用例集
    TEST_CASES = {
        # 任务相关
        "task_list": [
            ("我当前有哪些任务？", "query_task_list"),
            ("查看我的待办任务", "query_task_list"),
            ("分配给我的任务有哪些", "query_task_list"),
            ("查一下我参与的项目", "query_project_list"),
            ("我负责的任务", "query_task_list"),
        ],

        # 任务状态
        "task_status": [
            ("进行中的任务有哪些？", "query_task_status"),
            ("查看待处理的任务", "query_task_status"),
            ("已完成的任务", "query_task_status"),
            ("状态是进行中的任务", "query_task_status"),
        ],

        # 按日期查询
        "task_date": [
            ("今天截止的任务", "query_task_list"),
            ("本周的任务有哪些", "query_task_list"),
            ("明天到期的任务", "query_task_list"),
            ("最近创建的任务", "query_task_list"),
        ],

        # 创建任务
        "create_task": [
            ("创建一个新任务", "create_task"),
            ("我想新建一个任务", "create_task"),
            ("帮我添加一个任务", "create_task"),
            ("新建一个任务来完成这个", "create_task"),
        ],

        # 任务评分
        "task_score": [
            ("这个任务得了多少分？", "query_score"),
            ("查看任务的评分", "query_score"),
            ("任务完成质量怎么样", "query_score"),
            ("给这个任务打个分", "create_score"),
            ("给任务评分", "create_score"),
        ],

        # 邀请评分
        "invitation_score": [
            ("邀请张三给这个任务评分", "create_invitation_score"),
            ("请李四评价一下这个任务", "create_invitation_score"),
            ("发起一个评分邀请", "create_invitation_score"),
        ],

        # 催办
        "remind_score": [
            ("催一下王五评分", "remind_score"),
            ("提醒李四完成评分", "remind_score"),
            ("催办评分", "remind_score"),
        ],

        # 评分记录
        "score_record": [
            ("查看评分历史记录", "query_score_record"),
            ("评分记录有哪些", "query_score_record"),
            ("历史评分", "query_score_record"),
        ],

        # 相似任务
        "similar_task": [
            ("有没有类似的任务？", "rag_similar"),
            ("查找相似任务", "rag_similar"),
            ("参考一下以前的任务", "rag_similar"),
        ],

        # 项目相关
        "project": [
            ("我的项目有哪些？", "query_project_list"),
            ("查看项目详情", "query_project_detail"),
            ("创建一个新项目", "create_project"),
        ],

        # 执行内容
        "execution": [
            ("查看任务的执行内容", "query_task_list"),
            ("执行清单有哪些", "query_task_list"),
            ("子任务进度", "query_task_list"),
        ],

        # 通用对话
        "general_chat": [
            ("你好", "general_chat"),
            ("今天天气怎么样", "general_chat"),
            ("谢谢", "general_chat"),
        ],
    }

    def __init__(self):
        self.router = get_intent_router()

    async def test_single(self, user_input: str, expected: str) -> Dict:
        """测试单个用例"""
        result = await self.router.recognize(user_input, debug=True)

        is_correct = result.intent.value == expected

        return {
            "input": user_input,
            "expected": expected,
            "actual": result.intent.value,
            "confidence": result.confidence,
            "correct": is_correct,
            "reasoning": result.reasoning,
            "entities": result.entities,
            "confidence_breakdown": result.confidence_breakdown,
        }

    async def run_tests(self, category: str = None) -> Dict:
        """运行测试"""
        print("=" * 60)
        print("意图识别测试")
        print("=" * 60)

        total = 0
        correct = 0
        results_by_category = {}

        categories = [category] if category else self.TEST_CASES.keys()

        for cat in categories:
            if cat not in self.TEST_CASES:
                continue

            print(f"\n📂 分类: {cat}")
            print("-" * 40)

            category_results = []
            for user_input, expected in self.TEST_CASES[cat]:
                result = await self.test_single(user_input, expected)
                category_results.append(result)
                total += 1

                if result["correct"]:
                    correct += 1
                    status = "✅"
                else:
                    status = "❌"

                print(f"{status} 输入: {result['input'][:30]}...")
                print(f"   期望: {result['expected']:20} | 实际: {result['actual']}")
                print(f"   置信度: {result['confidence']:.2f}")

            results_by_category[cat] = category_results

        # 打印统计
        print("\n" + "=" * 60)
        print("📊 测试统计")
        print("=" * 60)
        print(f"总计: {total} | 正确: {correct} | 错误: {total - correct}")
        print(f"准确率: {correct / total * 100:.1f}%")

        print("\n📋 各分类准确率:")
        for cat, results in results_by_category.items():
            cat_correct = sum(1 for r in results if r["correct"])
            cat_total = len(results)
            cat_acc = cat_correct / cat_total * 100 if cat_total > 0 else 0
            print(f"  {cat}: {cat_correct}/{cat_total} ({cat_acc:.1f}%)")

        return results_by_category

    async def interactive_test(self):
        """交互式测试"""
        print("\n🔍 交互式测试 (输入 'q' 退出)")
        print("-" * 40)

        while True:
            user_input = input("\n请输入测试内容: ").strip()
            if user_input.lower() == 'q':
                break

            result = await self.router.recognize(user_input, debug=True)

            print(f"\n📌 识别结果:")
            print(f"   意图: {result.intent.value}")
            print(f"   置信度: {result.confidence:.2f}")
            print(f"   路由目标: {result.routing_target.value}")
            print(f"   推荐模型: {result.suggested_model}")

            if result.entities:
                print(f"   提取实体: {result.entities}")

            if result.confidence_breakdown:
                print(f"   置信度分解: {result.confidence_breakdown}")

            if result.needs_clarification:
                print(f"   ⚠️ 需要澄清: {result.clarification_question}")

            print(f"\n💡 推理过程: {result.reasoning}")


async def main():
    """主函数"""
    tester = IntentTester()

    if len(sys.argv) > 1:
        # 命令行测试
        category = sys.argv[1]
        if category == "interactive":
            await tester.interactive_test()
        else:
            await tester.run_tests(category)
    else:
        # 运行所有测试
        await tester.run_tests()


if __name__ == "__main__":
    asyncio.run(main())
