"""
报告生成模块：人格分析报告 + why-skill 报告占位
"""

# ==========================================
# 人格分析报告
# ==========================================

def render_analysis_report(skill: dict) -> str:
    """从蒸馏 JSON 生成冷静的叙事型人格分析报告"""
    meta = skill.get("meta", {})
    identity = skill.get("identity", {})
    models = skill.get("mental_models", [])
    heuristics = skill.get("decision_heuristics", [])
    dna = skill.get("expression_dna", {})
    values = skill.get("values", {})
    timeline = skill.get("timeline", [])
    boundaries = skill.get("honest_boundary", [])
    name = meta.get("name", "此人")

    report = f"# 【{name}】· 人格分析报告\n\n"

    # 一句话定位
    description = meta.get("description", "")
    if description:
        report += f"## 一句话定位\n\n{description}\n\n"

    # 起源
    report += "## 起源：他是怎么变成这样的\n\n"
    background = identity.get("background", "")
    if background:
        report += f"{background}\n\n"
    if timeline:
        for t in timeline:
            if isinstance(t, dict):
                report += (
                    f"- **{t.get('time', '')}**："
                    f"{t.get('event', '')}"
                )
                impact = t.get("impact", "")
                if impact:
                    report += f"——{impact}"
                report += "\n"
        report += "\n"

    # 思维模式
    report += "## 他是怎么想世界的\n\n"
    for i, m in enumerate(models, 1):
        if isinstance(m, dict):
            report += f"### {i}. {m.get('name', '')}\n\n"
            report += f"{m.get('one_liner', '')}\n\n"
            evidence = m.get("evidence", [])
            if evidence:
                report += "**事实支撑**：\n"
                for e in evidence:
                    report += f"- {e}\n"
                report += "\n"
            limitation = m.get("limitation", "")
            if limitation:
                report += f"**失效场景**：{limitation}\n\n"

    # 决策方式
    report += "## 他遇到事情会怎么做\n\n"
    for i, h in enumerate(heuristics, 1):
        if isinstance(h, dict):
            report += f"**{i}. {h.get('rule', '')}**\n"
            scene = h.get("scene", "")
            if scene:
                report += f"- 适用场景：{scene}\n"
            case = h.get("case", "")
            if case:
                report += f"- 已知案例：{case}\n"
            report += "\n"

    # 盲区
    report += "## 盲区：他自己看不到的\n\n"
    tensions = values.get("tensions", []) if isinstance(values, dict) else []
    if tensions:
        report += "**内在冲突**：\n"
        for t in tensions:
            report += f"- {t}\n"
        report += "\n"
    if boundaries:
        report += "**局限性**：\n"
        for b in boundaries:
            report += f"- {b}\n"
        report += "\n"

    # 摘要
    core_belief = identity.get("core_belief", "")
    if core_belief:
        report += f"## 一份摘要\n\n{core_belief}\n\n"

    report += (
        "---\n\n"
        "> 本报告由女娲自动生成，基于用户提供的私聊语料。"
        "所有判断均有语料出处，但语料本身的局限性（单一视角、特定时间段）"
        "意味着这份报告反映的是「他在这些对话中的样子」，而非他的全部。\n"
    )

    return report


# ==========================================
# why-skill 报告（占位）
# ==========================================

def render_whyskill_report(skill: dict) -> str:
    """why-skill 报告占位——后续开发"""
    _ = skill  # 保留接口
    return (
        "### why-skill 报告\n\n"
        "_此功能正在开发中，敬请期待。_\n"
    )
