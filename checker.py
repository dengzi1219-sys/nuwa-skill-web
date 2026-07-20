"""
审核模块：对比蒸馏结果与原始语料，检测事实不一致
"""

# ==========================================
# System Prompt
# ==========================================

SYSTEM_CHECKER = (
    "你是一名质检员。你的任务是对比「原始语料」和「人格蒸馏结果（JSON）」之间的差异。"
    "只挑出明显不一致的地方——例如蒸馏结果中声称的具体事实/事件/时间/数字在语料中找不到依据，或与语料明确矛盾。"
    "合理的抽象归纳（将多个例子概括为一个模型）不算问题。"
    "标注了「（推测）」的内容不检查。"
    "如果没有发现问题，直接输出「### 无异常」。"
)

# ==========================================
# 构建审核提示词
# ==========================================

def build_checker_prompt(corpus: str, skill_json_str: str, person_name: str = "") -> str:
    """
    构建审核提示词。
    语料完整传入，不做截断（DS 有 1M 上下文，足以容纳）。
    """
    name_hint = f"关于「{person_name}」的" if person_name else ""

    return f"""## 任务

以下是{name_hint}完整原始语料和人格蒸馏结果。请对比检查蒸馏结果中的具体事实是否在语料中有依据。

## 重要说明

- 语料可能包含多个文件：群聊记录、私聊记录等。
- 私聊记录中的人物可能以昵称出现（如 Xenia、A 等），需要对应到蒸馏目标「{person_name}」。
- 如果蒸馏结果中提及了某个事件，请先在语料中仔细查找，确认是否以不同昵称或不同文件呈现。

## 原始语料（完整）

{corpus}

## 人格蒸馏结果（JSON）

{skill_json_str}

## 检查范围

逐条检查：
- mental_models 中每条 evidence（具体事件、时间、数字）
- timeline 中的具体事件
- identity 中的具体事实声明
- values 中标注了具体案例的条目

## 忽略项

- 合理的抽象归纳和概念命名
- 标注了「（推测）」的内容
- 措辞上的细微差异
- 多个例子概括为一个模型的表述

## 输出格式

如果发现问题：
### 发现的问题
1. [问题描述] — 蒸馏结果声称「XXX」，但语料中[找不到依据/实际为YYY]
2. ...

如果没有问题：
### 无异常
"""


# ==========================================
# 执行审核
# ==========================================

def run_checker(client, corpus: str, skill_json: dict, person_name: str = "") -> str:
    """执行审核，返回审核报告文本"""
    import json
    skill_json_str = json.dumps(skill_json, ensure_ascii=False, indent=2)
    prompt = build_checker_prompt(corpus, skill_json_str, person_name)

    response = client.chat.completions.create(
        model="deepseek-v4-flash",  # 省钱，可切换为 deepseek-v4-pro
        messages=[
            {"role": "system", "content": SYSTEM_CHECKER},
            {"role": "user", "content": prompt},
        ],
        stream=False,
    )
    return response.choices[0].message.content
