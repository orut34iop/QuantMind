"""LLM Prompt 构建器 - 策略生成和修复的提示模板"""

from textwrap import dedent
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..api.schemas.generation import GenerateRequest


def build_strategy_prompt(body: "GenerateRequest", dsl: str) -> str:
    """构建策略生成的 LLM 提示词。

    从 steps/step5_generation.py._build_llm_prompt 提取。
    """
    buy_desc = ", ".join([b.name for b in body.buyRules]) or "无特定买入规则"
    sell_desc = ", ".join([s.name for s in body.sellRules]) or "无特定卖出规则"
    symbols = []
    if body.context and isinstance(body.context.get("symbols"), list):
        symbols = [s for s in body.context.get("symbols", []) if s]
    symbol_context = ", ".join(symbols) if symbols else "不限"
    risk_desc = body.risk.rebalanceFrequency or "monthly"
    prompt = dedent(f"""
        你是一个专注于量化策略的 AI 工程师，正在用 Qwen-max 生成 Python 策略。
        请基于以下 DSL 规则和用户输入，输出完整的 Python 代码，必须以 import pandas as pd 开始，并定义：
        def generated_strategy(data: pd.DataFrame):
            # 你可以在函数内部添加注释来描述 DSL 和规则
            ...
        当前平台使用的是 Qlib 回测框架，正确的格式请参考下面的约定：
        1. data 是一个按日期索引的 pd.DataFrame，列名与 DSL 因子名一致，Qlib 常用的 dataset 结构可以参考 qlib.data.dataset Dataset。
        2. 你的返回结果要支持 Qlib 的 backtest 输入，具体来说，signals DataFrame 应包含 position 或 signal 列，索引与 data 对齐，用于表达持仓/信号值。
        3. 不要少于示例代码中的 import + qlib 相关辅助工具，便于后端直接用 qlib.backtest 运行。
        DSL: {dsl}
        买入规则: {buy_desc}
        卖出规则: {sell_desc}
        风控周期: {risk_desc}
        目标股票池示例: {symbol_context}
        输出要求：只能返回 Python 代码（带必要的注释），不要额外补充解释性文字，最后返回一个包含 signals 的字典，signals 应该是以 data.index 为索引的 DataFrame。
        """)
    return prompt.strip()


def build_repair_prompt(code: str, err: str) -> str:
    """构建代码修复的 LLM 提示词。

    从 steps/step5_generation.py._repair_prompt 提取。
    """
    return dedent(f"""
        下面是一段 Python 代码，存在语法/结构问题：{err}

        请你修复它，要求：
        1. 输出必须是完整的 Python 代码文件
        2. 保持原有功能和结构，尽量少改动
        3. 不要输出 markdown 代码块，不要解释，只输出代码

        待修复代码：
        {code}
        """).strip()
