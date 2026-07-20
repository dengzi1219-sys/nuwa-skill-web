"""
女娲 · 提示词模板
包含：缺口分析提示词、蒸馏提示词（方法论+JSON Schema+few-shot）、Markdown 渲染
"""

# 三反引号常量——避免源码中出现 ``` 导致代码块断裂
BT = "```"

# ==========================================
# System Prompts（极短角色定义）
# ==========================================

SYSTEM_DISTILL = (
    "你是人格蒸馏引擎。基于用户提供的语料，提取心智模型、决策启发式、表达DNA。"
    "严格遵守 JSON Schema 输出，不编造信息，不确定处标注「推测」。"
)

SYSTEM_GAPS = (
    "你是语料分析助手。阅读用户提供的文本，执行两项分析：\n"
    "1. 识别其中可能涉及网络可查证的实体或事件（只列出查证后能实质提升人格蒸馏质量的实体）\n"
    "2. 识别语料中是否存在单方面严重指控结构（被蒸馏对象指控他人，但缺少被指控者的直接对话记录）\n"
    "两项分析独立进行，互不影响。输出简洁的结构化报告，不编造。"
)


# ==========================================
# 缺口分析提示词
# ==========================================

def build_gap_prompt(person_name: str, corpus: str) -> str:
    return f"""## 任务

阅读以下关于「{person_name}」的私聊语料，找出对话中提到的**如果查证能实质提升人格蒸馏质量**的实体/事件。

**关键判断标准**：查了这个东西，你能更准确地提取「{person_name}」的心智模型、价值观或决策模式吗？如果不能，就不列。

## 你应该找什么

- 被讨论的**具体公开事件**（新闻、社会事件）——如果此人对此事件发表了独特观点，查证事件全貌能帮你理解他的思维框架
- 被引用的**作品**（书、电影、游戏、文章）——如果此人深度讨论或频繁引用，查证作品内容能帮你理解他的智识谱系
- 被提到的**公开人物**——如果此人以此人为参照系定义自己的立场

## 你不应该找什么

- 「{person_name}的教育背景是什么」——私聊语料，网上查不到
- 「周围人如何评价他」——同上
- 任何需要搜索 {person_name} 本身才能回答的问题
- **纯私人标识符**：QQ号、手机号、具体门牌号、真实姓名等——不存在公开记录
- **背景性常识实体**：大学名称、平台名称（抖音/闲鱼/B站）、常见品牌——这些东西的存在是常识，查了也不会让你更理解此人怎么思考。只有在此人对该实体发表了**非共识级别的独特观点**时才考虑列出
- **背景性常识实体**：大学名称、平台名称（抖音/闲鱼/B站）、常见品牌——这些东西的存在是常识，查了也不会让你更理解此人怎么思考。只有在此人对该实体发表了**非共识级别的独特观点**时才考虑列出

## 你应该检查什么（视角完整性）          ← 在这里插入

阅读语料时，注意识别是否存在**单方面指控结构**：
- 被蒸馏对象是否在对话中对他人的行为做出了严重负面描述（霸凌、背叛、欺骗、暴力等）
- 这些被指控的对象是否在语料中有**直接的对话记录**（即他们本人的发言），还是全部通过被蒸馏对象的转述呈现

如果存在「A 严重指控 B，但语料中完全没有 B 的直接发言」，则在报告中指出：

### 视角缺失建议

**缺失视角：[B的身份，如「室友」「母亲」「女友」]**
- 语料中关于[B]的所有信息均来自[A]的转述，缺少[B]的直接对话记录
- 缺少该视角可能导致蒸馏结果严重偏向[A]的叙事
- 建议：如果用户手头有与[B]的聊天记录，补充后能显著提升蒸馏结果的客观性

## 语料                                


{corpus}

## 输出格式

如果确实找到了值得查证的实体（按上述标准筛选后），逐项输出：

### 值得查证的实体/事件

**实体1: [名称]**
- 在对话中的位置和上下文（引用原句）
- 查证后对蒸馏的具体帮助（能帮你提取什么心智特征）

### 搜索建议
- [关键词1]

### 可以直接蒸馏吗？
建议查证以上实体后效果更好

---

如果**没有**找到符合上述标准的实体（这是大多数私聊语料的正常情况），直接输出：

### 可以直接蒸馏吗？
可以。未发现查证后能实质提升蒸馏质量的公开实体。私聊语料的核心价值在对话本身，建议直接进入蒸馏。
"""

# ==========================================
# 蒸馏提示词（核心，放在 user message 中）
# ==========================================

def build_distill_prompt(person_name: str, corpus: str, supplementary: str = "") -> str:
    supp_block = ""
    if supplementary.strip():
        supp_block = f"\n## 用户补充搜索信息\n\n{supplementary[:6000]}\n"

    return f"""## 任务

基于以下语料，提取「{person_name}」的认知操作系统，输出 JSON。

重要提示：语料仅为私聊记录。不要仅聚焦最理性的片段，注意捕捉日常互动中的情感模式、社交策略和表达习惯。

如果语料包含多个文件（来自不同对话者或不同时间段），请注意：
- 每个文件头部已标注了「对话者」信息，请据此区分不同关系中的表现
- 识别哪些特征在多个对话中一致出现（核心特质）
- 哪些特征只在特定对话者面前出现（社交面具）
- 在诚实边界中标注语料来源的局限性
- 在表达DNA中标注此人面对不同对象时的表达差异
### 事实归属原则
注意区分语料中不同人物的事件归属：
- 只有被蒸馏对象（{person_name}）本人参与或亲述的事件，才应归入该对象的时间线
- 其他对话者（如用户本人、第三方转述者）在聊天中提及的自身经历，不应归入蒸馏对象的名下
- 跨文件出现的同一事实优先属于该事件的实际发生者，而非被蒸馏对象

以下是完整语料，请全面阅读后提炼。

---

## 萃取方法论

### 心智模型的三重验证
一个论点要被认定为「心智模型」（而非随口一说），需通过三重验证：

1. **跨域复现**：同一思维框架出现在至少 2 个不同话题/场景中
2. **有生成力**：用这个模型能推断此人对新问题的可能立场
3. **有排他性**：不是所有聪明人都这样想，体现了此人的独特视角

三重通过 → 心智模型（3-7个）；仅 1-2 重 → 降级为决策启发式；0 重 → 丢弃。

每个心智模型必须包含：名称、一句话描述、至少 2 个场景证据、应用方式、局限性。

### 表达 DNA 量化
从语料中提取：句式偏好、高频词/禁忌词、节奏、幽默方式、确定性语气、引用习惯。

### 矛盾处理原则
保留矛盾，不粉饰。三种类型：时间性（观点演化）、领域性（不同场景不同规则）、本质性张力（价值观冲突）。

### 诚实边界
必须列出：信息截止时间、语料局限性、推测成分、此人不公开的领域。

---

## 输出 JSON Schema

{BT}json
{{
  "meta": {{
    "name": "人物名",
    "created_at": "YYYY-MM-DD",
    "source_word_count": 数字,
    "description": "300字以内。一句定位 + 3-5个核心触发语 + 一句防呆声明。禁止堆长尾关键词。"
  }},
  "identity": {{
    "self_description": "用此人语气写的50字自我介绍",
    "background": "关键背景",
    "current_status": "最近动态",
    "core_belief": "一句最能代表其思维方式的原话"
  }},
  "role_play_rules": {{
    "activation": "如何激活此角色",
    "taboos": ["不说「XX会认为...」", "不跳出角色做meta分析"],
    "exit_triggers": ["退出", "切回正常"]
  }},
  "mental_models": [
    {{
      "name": "模型名",
      "one_liner": "一句话描述",
      "evidence": ["场景1", "场景2"],
      "application": "用于什么类型的问题",
      "limitation": "在什么情况下失效"
    }}
  ],
  "decision_heuristics": [
    {{
      "rule": "如果X则Y",
      "scene": "适用场景",
      "case": "已知案例"
    }}
  ],
  "expression_dna": {{
    "sentence_style": "描述",
    "vocabulary": {{"high_freq": ["词1"], "taboo": ["禁词1"]}},
    "rhythm": "先结论/先铺垫",
    "humor": "讽刺/自嘲/冷幽默/不幽默",
    "certainty": "很确定型/我不确定型",
    "quote_habit": "描述"
  }},
  "timeline": [
    {{"time": "年份", "event": "事件", "impact": "对思维的影响"}}
  ],
  "values": {{
    "pursued": ["价值观"],
    "rejected": ["反模式"],
    "tensions": ["内在矛盾: 既...又..."]
  }},
  "intellectual_lineage": {{
    "influenced_by": ["受谁影响"],
    "influenced": ["影响谁"]
  }},
  "honest_boundary": ["局限1", "局限2", "局限3"],
  "sources": {{
    "primary": ["一手来源"],
    "secondary": ["二手来源"],
    "key_quotes": ["原话 —— 出处"]
  }},
  "quick_reference": {{
    "first_questions": ["先问什么"],
    "never_does": ["绝对不做什么"]
  }},
  "_self_check": {{
    "心智模型数量": "N个 (应3-7)",
    "每个模型有局限性": true,
    "表达DNA特征数": "N项 (应≥3)",
    "诚实边界条数": "N条 (应≥3)",
    "内在张力对数": "N对 (应≥2)",
    "每个模型有2个以上证据": true,
    "未通过项": ["如有不通过，说明原因"]
  }}
}}
{BT}

## Few-shot 示例（费曼的一个心智模型）

{BT}json
{{
  "name": "命名 ≠ 理解",
  "one_liner": "知道一个东西叫什么，和理解它怎么运作，是完全不同的两件事。",
  "evidence": [
    "父亲的鸟故事——贯穿费曼几乎所有著作",
    "巴西教学经历——学生能背公式但换个问法就不会"
  ],
  "application": "尝试用六年级学生能听懂的话解释它。如果解释不了，你只是记住了名字。",
  "limitation": "某些高度抽象的数学/物理概念难以用日常语言精确表达。"
}}
{BT}

## 硬性要求

- 心智模型 **3-7 个**，宁少勿多
- 决策启发式 **5-10 条**，每条有场景+案例
- 诚实边界 **至少 3 条**
- 内在张力 **至少 2 对**
- 不确定处用「（推测）」标注
- description 控制在 **300 字以内**

---

{supp_block}

## 主要语料

{corpus}

---

请直接输出完整 JSON。"""


# ==========================================
# JSON → Markdown 渲染
# ==========================================

def render_markdown(skill: dict) -> str:
    """将蒸馏 JSON 渲染为可读 Markdown"""
    if not isinstance(skill, dict):
        return "_渲染失败：输入不是有效字典_"

    meta = skill.get("meta", {})
    identity = skill.get("identity", {})
    models = skill.get("mental_models", [])
    heuristics = skill.get("decision_heuristics", [])
    dna = skill.get("expression_dna", {})
    values = skill.get("values", {})
    timeline = skill.get("timeline", [])
    lineage = skill.get("intellectual_lineage", {})
    boundaries = skill.get("honest_boundary", [])
    sources = skill.get("sources", {})
    quick = skill.get("quick_reference", {})
    rules = skill.get("role_play_rules", {})
    name = meta.get("name", "未知")

    md = f"""---
name: {name}-perspective
description: |
  {meta.get('description', '')}
---

# {name} · 思维操作系统

> {identity.get('core_belief', '')}

## 角色扮演规则

**此Skill激活后，直接以{name}的身份回应。**

"""
    for r in rules.get("taboos", []):
        md += f"- ❌ {r}\n"
    exit_words = '、'.join(rules.get('exit_triggers', ['退出', '切回正常']))
    md += f"\n**退出角色**：{exit_words}时恢复正常模式。\n\n"

    md += f"""## 身份卡

**我是谁**：{identity.get('self_description', '')}
**我的起点**：{identity.get('background', '')}
**我现在在做什么**：{identity.get('current_status', '')}

## 核心心智模型

"""
    for i, m in enumerate(models, 1):
        if isinstance(m, dict):
            md += f"### 模型{i}: {m.get('name', '')}\n\n"
            md += f"> {m.get('one_liner', '')}\n\n**证据**：\n"
            for e in m.get("evidence", []):
                md += f"- {e}\n"
            md += f"\n**应用**：{m.get('application', '')}\n\n"
            md += f"**局限**：{m.get('limitation', '')}\n\n"

    md += "## 决策启发式\n\n"
    for i, h in enumerate(heuristics, 1):
        if isinstance(h, dict):
            md += f"{i}. **{h.get('rule', '')}**\n"
            md += f"   - 场景：{h.get('scene', '')}\n"
            md += f"   - 案例：{h.get('case', '')}\n\n"

    vocab = dna.get("vocabulary", {}) if isinstance(dna, dict) else {}
    md += f"""## 表达DNA

- 句式：{dna.get('sentence_style', '') if isinstance(dna, dict) else ''}
- 高频词：{', '.join(vocab.get('high_freq', []))}
- 禁忌词：{', '.join(vocab.get('taboo', []))}
- 节奏：{dna.get('rhythm', '') if isinstance(dna, dict) else ''}
- 幽默：{dna.get('humor', '') if isinstance(dna, dict) else ''}
- 确定性：{dna.get('certainty', '') if isinstance(dna, dict) else ''}
- 引用习惯：{dna.get('quote_habit', '') if isinstance(dna, dict) else ''}

## 人物时间线

| 时间 | 事件 | 影响 |
|------|------|------|
"""
    for t in timeline:
        if isinstance(t, dict):
            md += f"| {t.get('time', '')} | {t.get('event', '')} | {t.get('impact', '')} |\n"

    md += f"""
## 价值观与反模式

**追求**：{'、'.join(values.get('pursued', [])) if isinstance(values, dict) else ''}
**拒绝**：{'、'.join(values.get('rejected', [])) if isinstance(values, dict) else ''}
**内在张力**：
"""
    if isinstance(values, dict):
        for t in values.get("tensions", []):
            md += f"- {t}\n"

    md += f"""
## 智识谱系

影响来源 → **{name}** → 影响去向

- 受谁影响：{'、'.join(lineage.get('influenced_by', [])) if isinstance(lineage, dict) else ''}
- 影响了谁：{'、'.join(lineage.get('influenced', [])) if isinstance(lineage, dict) else ''}

## 诚实边界
"""
    for b in boundaries:
        md += f"- {b}\n"

    md += "\n## 快速参考\n\n**首先会问**：\n"
    for q in quick.get("first_questions", []):
        md += f"- {q}\n"
    md += "\n**绝不会做**：\n"
    for nd in quick.get("never_does", []):
        md += f"- {nd}\n"

    md += "\n## 调研来源\n\n### 一手来源\n"
    for s in sources.get("primary", []):
        md += f"- {s}\n"
    md += "\n### 二手来源\n"
    for s in sources.get("secondary", []):
        md += f"- {s}\n"
    md += "\n### 关键引用\n"
    for q in sources.get("key_quotes", []):
        md += f"> {q}\n"

    md += f"""
---

> 本Skill由 [女娲 · Skill造人术](https://github.com/alchaincyf/nuwa-skill) 生成
> 创建时间：{meta.get('created_at', '')}
"""
    return md
