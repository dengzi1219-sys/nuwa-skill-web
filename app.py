"""
女娲 · 人格蒸馏网页版 v1.4
================================
用法：python app.py  →  自动启动 Streamlit，打开浏览器
依赖：pip install streamlit openai httpx
"""

import sys
import os
import json
import re
import copy
import streamlit as st
from openai import OpenAI
from datetime import datetime

from prompts import (
    SYSTEM_DISTILL,
    SYSTEM_GAPS,
    build_gap_prompt,
    build_distill_prompt,
    render_markdown,
)
from checker import SYSTEM_CHECKER, build_checker_prompt, run_checker
from reports import render_analysis_report, render_whyskill_report

# ==========================================
# 0. 自动启动 Streamlit
# ==========================================
if not st.runtime.exists():
    import streamlit.web.cli as stcli
    sys.argv = ["streamlit", "run", sys.argv[0]]
    sys.exit(stcli.main())

# ==========================================
# 1. 工具函数
# ==========================================
def detect_proxy():
    for var in ["HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY"]:
        val = os.environ.get(var)
        if val:
            return val
    return ""


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', '_', name).strip()


def extract_json_from_text(raw: str) -> dict | None:
    """三层 JSON 提取：直接解析 → 代码块 → 括号配对"""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    match = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    start = raw.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(raw)):
        if raw[i] == "{":
            depth += 1
        elif raw[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(raw[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def desensitize_skill(skill: dict, person_name: str) -> dict:
    """脱敏：替换真实姓名、学校名、QQ号、手机号。返回深拷贝。"""

    def _redact(text: str) -> str:
        if not isinstance(text, str):
            return text
        if person_name and person_name.strip():
            text = text.replace(person_name, "【甲】")
        text = re.sub(r"[\u4e00-\u9fa5]{2,6}(大学|学院|中学|小学)", "[某学校]", text)
        text = re.sub(r"\b[1-9]\d{4,10}\b", "[已脱敏]", text)
        text = re.sub(r"\b1[3-9]\d{9}\b", "[已脱敏]", text)
        return text

    def _walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str):
                    obj[k] = _redact(v)
                elif isinstance(v, (dict, list)):
                    _walk(v)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                if isinstance(v, str):
                    obj[i] = _redact(v)
                elif isinstance(v, (dict, list)):
                    _walk(v)

    result = copy.deepcopy(skill)
    _walk(result)
    return result


# ==========================================
# 2. 页面配置
# ==========================================
st.set_page_config(page_title="女娲 · 人格蒸馏", page_icon="🌌", layout="wide")

# ==========================================
# 3. 状态初始化
# ==========================================
DEFAULTS = {
    "stage": "setup",
    "person_name": "",
    "corpus": "",
    "supplementary": "",
    "gap_report": "",
    "skill_json": None,
    "skill_md": "",
    "full_stream": "",
    "checker_result": "",
    "analysis_report": "",
}
for key, val in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val

if "file_labels" not in st.session_state:
    st.session_state.file_labels = {}

# ==========================================
# 4. 侧边栏
# ==========================================
with st.sidebar:
    st.header("⚙️ 配置")

    api_key = st.text_input(
        "DeepSeek API Key",
        type="password",
        help="platform.deepseek.com 注册获取",
    )

    model_option = st.selectbox(
        "模型",
        ["deepseek-v4-flash", "deepseek-v4-pro"],
        help="v4-flash 已替代原 deepseek-chat，更快更省；v4-pro 推理更深但较慢",
    )

    # 代理
    detected = detect_proxy()
    if detected:
        st.caption(f"🟢 检测到系统代理：`{detected}`")

    proxy_url = st.text_input(
        "代理地址（可选）",
        value=detected,
        placeholder="留空则直连。例：http://127.0.0.1:7890",
        help="Clash 默认 7890，v2ray 默认 10809。自动填入系统代理。",
    )

    st.divider()

    # ── 报告开关 ──
    enable_report = st.checkbox(
        "📄 同时生成人格分析报告",
        value=True,
        help="蒸馏完成后自动生成一份冷静的叙事型人格分析报告。",
    )

    # ── 审核开关 ──
    enable_checker = st.checkbox(
        "🔍 蒸馏后自动核查（对比语料，检测不一致）",
        value=False,
        help="蒸馏完成后用独立模型对比蒸馏结果与原始语料，找出明显的事实不一致。",
    )

    st.divider()

    # ── 脱敏开关 ──
    enable_desensitize = st.checkbox(
        "🔒 脱敏输出（替换真实姓名为代号）",
        value=False,
        help="勾选后，展示和下载的 JSON/MD 中会替换真实姓名、学校、QQ号等信息。",
    )

    st.divider()

    st.caption("🔗 相关链接")
    st.markdown("[原版女娲 (GitHub)](https://github.com/alchaincyf/nuwa-skill)")
    st.markdown("[DeepSeek 开放平台](https://platform.deepseek.com)")
    st.markdown("[🌌 我的女娲网页版 (GitHub)](https://github.com/dengzi1219-sys/nuwa-skill-web)")
    st.link_button("⚡ 支持我（爱发电）", "https://ifdian.net/a/xiaomiyou")
    st.caption("_why-skill 链接（即将上线）_")

    st.divider()

    # ── 预留功能 ──
    with st.expander("📌 预留功能"):
        st.markdown("- why-skill 网页版（即将上线）")
        st.markdown("- 女娲使用技巧")
        st.markdown("- 常见问题攻略")
        st.markdown("- 反馈与建议")

    st.divider()

    if st.button("🧹 重置全部", use_container_width=True):
        for key in DEFAULTS:
            st.session_state[key] = DEFAULTS[key]
        st.session_state.file_labels = {}
        st.rerun()

# ==========================================
# 5. OpenAI Client 工厂（支持代理）
# ==========================================
def get_client():
    kwargs = {"api_key": api_key, "base_url": "https://api.deepseek.com"}
    if proxy_url and proxy_url.strip():
        import httpx
        kwargs["http_client"] = httpx.Client(proxy=proxy_url.strip())
    return OpenAI(**kwargs)

# ==========================================
# 6. 主界面
# ==========================================
st.title("🌌 女娲 · 人格蒸馏")
st.caption("上传语料 → 缺口分析 → 补充确认 → 生成结构化人格 JSON")

# ── 阶段 1：输入 ──
if st.session_state.stage == "setup":
    col1, col2 = st.columns([2, 1])

    with col1:
        st.session_state.person_name = st.text_input(
            "🎯 目标人物姓名",
            value=st.session_state.person_name,
            placeholder="例如：张三（网名/代号/真名均可）",
        )

        uploaded_files = st.file_uploader(
            "📂 上传语料（可多选）(.txt / .md / .json)",
            type=["txt", "md", "json"],
            accept_multiple_files=True,
        )

        if uploaded_files:
            st.caption("✏️ 标注对话者身份（可选，帮助AI理解多文件关系）：")
            for f in uploaded_files:
                default_label = st.session_state.file_labels.get(f.name, "")
                label = st.text_input(
                    f"「{f.name}」的对话双方",
                    value=default_label,
                    placeholder="例如：我 ↔ 甲",
                    key=f"label_{f.name}",
                )
                st.session_state.file_labels[f.name] = label

        file_text = ""
        if uploaded_files:
            try:
                all_parts = []
                for f in uploaded_files:
                    raw = f.read().decode("utf-8")
                    fname = f.name.lower()

                    if fname.endswith(".json"):
                        data = json.loads(raw)
                        msgs = data.get("messages", [])
                        lines = []
                        for m in msgs:
                            if not isinstance(m, dict):
                                continue
                            if m.get("system") or m.get("recalled"):
                                continue
                            sender = m.get("sender", {}).get("name", "未知")
                            text = m.get("content", {}).get("text", "")
                            text = re.sub(
                                r"\[表情\d+\]|\[/汪汪\]|\[\[.*?\]\]", "", text
                            ).strip()
                            if text:
                                lines.append(f"{sender}：{text}")
                        content = "\n".join(lines)
                    else:
                        content = raw

                    header = f"### 文件：{f.name}"
                    interlocutor = st.session_state.file_labels.get(f.name, "")
                    if interlocutor.strip():
                        header += f"\n### 对话者：{interlocutor.strip()}"
                    all_parts.append(f"{header}\n\n{content}")

                file_text = "\n\n---\n\n".join(all_parts)
                total_chars = len(file_text)
                st.success(
                    f"✅ 已读取 {len(uploaded_files)} 个文件，共 {total_chars} 字符"
                )
            except Exception as e:
                st.error(f"读取失败：{e}")

        pasted_text = st.text_area(
            "或直接粘贴语料（会和上传文件合并）：",
            height=200,
            placeholder="把大段文字粘贴在这里...\n可以同时上传文件和粘贴文本，两边的内容会合并。",
        )

        parts = []
        if file_text:
            parts.append(file_text)
        if pasted_text.strip():
            parts.append(f"### 手动粘贴内容\n\n{pasted_text.strip()}")
        st.session_state.corpus = "\n\n---\n\n".join(parts)

        if st.session_state.corpus:
            st.caption(
                f"📊 当前语料总计：{len(st.session_state.corpus)} 字符"
            )

        no_network = st.checkbox(
            "🚫 不联网查询（跳过缺口分析，直接蒸馏）",
            value=False,
            help="勾选后直接进入蒸馏。私聊语料推荐勾选。",
        )

    with col2:
        st.info(
            "**使用流程**：\n\n"
            "1. 输入人名 + 上传文件/粘贴语料（可同时）\n"
            "2. 可选：标注每个文件是谁和谁的对话\n"
            "3. 不联网查询默认跳过缺口分析\n"
            "4. AI 综合蒸馏 → 下载 JSON + Markdown + 分析报告"
        )

    if st.button("🔍 开始分析", type="primary", use_container_width=True):
        if not api_key:
            st.error("请先填入 API Key")
        elif not st.session_state.person_name.strip():
            st.error("请输入目标人物姓名")
        elif not st.session_state.corpus.strip():
            st.error("请上传文件或粘贴语料")
        else:
            if no_network:
                st.session_state.gap_report = "（已跳过缺口分析）"
                st.session_state.stage = "distill"
            else:
                st.session_state.stage = "gaps"
            st.rerun()

# ── 阶段 2：缺口分析 ──
elif st.session_state.stage == "gaps":

    if not st.session_state.gap_report:
        with st.spinner(
            f"🔍 正在分析「{st.session_state.person_name}」的语料..."
        ):
            try:
                client = get_client()
                response = client.chat.completions.create(
                    model="deepseek-v4-flash",
                    messages=[
                        {"role": "system", "content": SYSTEM_GAPS},
                        {
                            "role": "user",
                            "content": build_gap_prompt(
                                st.session_state.person_name,
                                st.session_state.corpus,
                            ),
                        },
                    ],
                    stream=False,
                )
                st.session_state.gap_report = (
                    response.choices[0].message.content
                )
            except Exception as e:
                st.error(f"分析失败：{e}")
                if st.button("⬅️ 返回修改"):
                    st.session_state.stage = "setup"
                    st.rerun()
                st.stop()

    st.subheader("📋 语料覆盖度分析")
    st.markdown(st.session_state.gap_report)

    st.divider()
    st.subheader("✏️ 补充信息（可选）")
    st.info("💡 可以粘贴外部搜索结果，也可以上传相关文件。留空直接跳过。")

    supp_pasted = st.text_area(
        "粘贴外部搜索结果：",
        height=200,
        placeholder="搜索结果粘贴在这里...",
        key="supp_pasted",
    )
    supp_files = st.file_uploader(
        "或上传相关文件（可选）",
        type=["txt", "md", "json"],
        accept_multiple_files=True,
        key="supp_files",
    )

    supp_parts = []
    if supp_pasted.strip():
        supp_parts.append(supp_pasted.strip())
    if supp_files:
        for f in supp_files:
            try:
                supp_parts.append(
                    f"### 补充文件：{f.name}\n\n{f.read().decode('utf-8')}"
                )
            except Exception:
                pass
    st.session_state.supplementary = "\n\n---\n\n".join(supp_parts)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🚀 提交并开始蒸馏", type="primary", use_container_width=True):
            st.session_state.stage = "distill"
            st.rerun()
    with c2:
        if st.button("⬅️ 返回重新上传"):
            st.session_state.gap_report = ""
            st.session_state.stage = "setup"
            st.rerun()

# ── 阶段 3：蒸馏（流式输出 + 可选审核）──
elif st.session_state.stage == "distill":
    st.subheader(f"🧠 正在蒸馏「{st.session_state.person_name}」...")

    if "v4-pro" in model_option or "pro" in model_option:
        st.info(
            "🧠 正在深度推理中（thinking 阶段不输出文字），请耐心等待 1-2 分钟..."
        )

    status = st.empty()
    placeholder = st.empty()
    st.session_state.full_stream = ""

    try:
        client = get_client()
        user_msg = build_distill_prompt(
            st.session_state.person_name,
            st.session_state.corpus,
            st.session_state.supplementary,
        )

        status.text("正在调用模型（流式）...")

        response = client.chat.completions.create(
            model=model_option,
            messages=[
                {"role": "system", "content": SYSTEM_DISTILL},
                {"role": "user", "content": user_msg},
            ],
            stream=True,
        )

        full_stream = ""

        for chunk in response:
            delta = chunk.choices[0].delta

            if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                full_stream += delta.reasoning_content
                st.session_state.full_stream += delta.reasoning_content

            if delta.content:
                full_stream += delta.content
                st.session_state.full_stream += delta.content
                if len(full_stream) % 120 == 0:
                    placeholder.markdown(full_stream + "▌")

        placeholder.markdown(full_stream)
        status.text("解析 JSON...")

        skill_json = extract_json_from_text(full_stream)

        if skill_json is None:
            st.error(
                "JSON 解析失败。请查看结果页「完整输出」Tab 中的原始内容。"
            )
            st.session_state.skill_json = {}
            st.session_state.skill_md = ""
            st.session_state.stage = "result"
            st.rerun()

        if not skill_json.get("meta", {}).get("name"):
            skill_json.setdefault("meta", {})["name"] = (
                st.session_state.person_name
            )
            st.warning(
                f"⚠️ 模型未返回人物名称，已回退为「{st.session_state.person_name}」"
            )

        st.session_state.skill_json = skill_json
        st.session_state.skill_md = render_markdown(skill_json)

               # ── 蒸馏后审核 ──
        if enable_checker:
            status.text("正在审核蒸馏结果...")
            try:
                st.session_state.checker_result = run_checker(
                    get_client(),
                    st.session_state.corpus,
                    skill_json,
                    st.session_state.person_name  # ← 新增：传入人物名称
                )
            except Exception as e:
                st.session_state.checker_result = f"审核失败：{e}"
        else:
            st.session_state.checker_result = ""

        # ── 生成分析报告 ──
        if enable_report:
            st.session_state.analysis_report = render_analysis_report(skill_json)
        else:
            st.session_state.analysis_report = ""

        st.session_state.stage = "result"
        st.rerun()

    except Exception as e:
        status.empty()
        placeholder.empty()
        st.error(f"蒸馏失败：{e}")
        if st.button("⬅️ 返回重试"):
            st.session_state.stage = "gaps"
            st.rerun()

# ── 阶段 4：结果 ──
elif st.session_state.stage == "result":
    skill_original = st.session_state.skill_json or {}

    if not skill_original:
        st.error("无结果数据")
        st.caption("蒸馏阶段未能提取到有效的 JSON，请查看下方的原始输出，或在侧边栏点击「重置全部」后重试。")
        
        full_stream = st.session_state.get("full_stream", "")
        if full_stream:
            with st.expander("📜 查看原始流式输出（用于排查问题）", expanded=True):
                st.text_area("完整流式输出", full_stream, height=400)
                st.download_button(
                    "⬇️ 下载原始输出",
                    data=full_stream,
                    file_name="debug_full_stream.txt",
                    mime="text/plain",
                )
        else:
            st.info("无原始流式输出记录（可能是旧版本运行或未开启流式）。")
        
        if st.button("⬅️ 返回重新蒸馏"):
            st.session_state.stage = "setup"
            st.rerun()
        st.stop()

    # 仅在 skill_original 非空时执行以下代码
    if enable_desensitize:
        skill = desensitize_skill(skill_original, st.session_state.person_name)
    else:
        skill = skill_original

    display_name = skill.get("meta", {}).get("name", st.session_state.person_name)
    st.success(f"✅ 「{display_name}」蒸馏完成！")

    # 自检
    sc = skill.get("_self_check", {})
    failures = [
        f
        for f in sc.get("未通过项", [])
        if f and f != "如有不通过，说明原因" and not str(f).startswith("无")
    ]
    if failures:
        st.warning(f"⚠️ 自检 {len(failures)} 项未通过：{'; '.join(failures)}")

    # ── 6 个 Tab ──
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        [
            "📊 JSON 预览",
            "📝 Markdown 预览",
            "🔍 自检报告",
            "📜 完整输出",
            "📄 人格分析报告",
            "🔍 事实核查",
        ]
    )

    name = st.session_state.person_name.strip() or "unknown"

    # Tab1: JSON
    with tab1:
        st.json(skill)
        st.download_button(
            "⬇️ 下载 JSON",
            data=json.dumps(skill, ensure_ascii=False, indent=2),
            file_name=f"{name}.json",
            mime="application/json",
        )

    # Tab2: Markdown
    with tab2:
        if enable_desensitize:
            md_content = render_markdown(skill)
        else:
            md_content = st.session_state.skill_md
        if md_content and md_content.strip():
            st.markdown(md_content)
        else:
            st.warning(
                "Markdown 预览为空，可能 JSON 缺少必要字段。"
                "请在「JSON 预览」或「完整输出」中查看结果。"
            )
        st.download_button(
            "⬇️ 下载 Markdown",
            data=md_content,
            file_name=f"{name}.md",
            mime="text/markdown",
        )

    # Tab3: 自检
    with tab3:
        if sc:
            st.markdown("### 自检清单")
            for k, v in sc.items():
                if k != "未通过项":
                    st.write(f"- **{k}**：{v}")
            if failures:
                st.markdown("### ❌ 未通过")
                for f in failures:
                    st.warning(f)
            else:
                st.success("✅ 全部通过（自评准确率有限，建议人工复核）")
        else:
            st.info("无自检数据")

    # Tab4: 完整输出
    with tab4:
        st.markdown("### 🤖 AI 原始流式输出")
        st.caption("包含模型推理过程中的所有分析、思考片段以及最终 JSON。")
        full_stream = st.session_state.get("full_stream", "")
        if full_stream:
            st.text_area("完整流式输出", full_stream, height=500)
            st.download_button(
                "⬇️ 下载完整流式输出",
                data=full_stream,
                file_name=f"{name}_full_stream.txt",
                mime="text/plain",
            )
        else:
            st.info("无流式输出记录（可能是旧版本蒸馏的结果，重新蒸馏一次即可）")

    # Tab5: 人格分析报告
    with tab5:
        if enable_report and st.session_state.analysis_report:
            st.markdown(st.session_state.analysis_report)
            st.download_button(
                "⬇️ 下载人格分析报告",
                data=st.session_state.analysis_report,
                file_name=f"{name}_分析报告.md",
                mime="text/markdown",
            )
        elif not enable_report:
            st.info("人格分析报告未启用。请在侧边栏勾选「同时生成人格分析报告」后重新蒸馏。")
        else:
            st.info("无报告数据。")

    # Tab6: 事实核查
    with tab6:
        if enable_checker and st.session_state.checker_result:
            result = st.session_state.checker_result
            if "### 无异常" in result:
                st.success("✅ 未发现明显矛盾")
                st.markdown(result)
            elif "### 发现的问题" in result:
                st.warning("⚠️ 请仔细核对以下问题")
                st.markdown(result)
            else:
                st.markdown(result)
        elif not enable_checker:
            st.info("事实核查未启用。请在侧边栏勾选「蒸馏后自动核查」后重新蒸馏。")
        else:
            st.info("无核查数据。")

    # ── 自动保存 ──
    safe_name = sanitize_filename(name)
    save_dir = os.path.join("saves", safe_name)
    os.makedirs(save_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    try:
        json_path = os.path.join(save_dir, f"personality_{ts}.json")
        md_path = os.path.join(save_dir, f"personality_{ts}.md")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(skill, f, ensure_ascii=False, indent=2)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(
                render_markdown(skill)
                if enable_desensitize
                else st.session_state.skill_md
            )
        st.caption(f"💾 已自动保存到 `{save_dir}/`")
    except Exception as e:
        st.caption(f"⚠️ 保存失败：{e}")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔄 再蒸馏一次", use_container_width=True):
            st.session_state.stage = "distill"
            st.rerun()
    with c2:
        if st.button("⬅️ 蒸馏下一个人", use_container_width=True):
            for key in DEFAULTS:
                st.session_state[key] = DEFAULTS[key]
            st.session_state.file_labels = {}
            st.rerun()

# ==========================================
# 7. 页脚
# ==========================================
st.divider()
st.caption(
    "🌌 女娲 · 人格蒸馏 v1.4 | "
    "基于 [nuwa-skill](https://github.com/dengzi1219-sys/nuwa-skill-web) | "
    "蒸馏不编造，不确定处标注推测"
)
