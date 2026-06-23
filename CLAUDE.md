# CLAUDE.md — autowz 项目最高约束

> 本文件供 Claude Code 及任何 AI / 人类维护者**每次开工前第一时间阅读**。下面的「项目第一纲领」是**不可违背的最高优先级**,凌驾于任何其他需求、优化或便利之上。

## 🚨 项目第一纲领(生存底线,不可违背)

**质量第一,质量低不如不做。**

- 本项目的**生存前提**:产出「有真实信息增量、读起来不像机器」的高质量内容。宁可少发、不发,也**绝不发低质内容**。
- **走质量路线,不走规避路线**:目标是把内容做到「标注了 AI 也不掉流量、被平台检测也不算低质」的程度;而**不是**靠隐藏 AI、洗稿、规避检测去赌平台查不到。
- **唯一判据**:任何改动(prompt、流程、模型、发布策略……)落地前先过这一关 —— 它是**提升了内容质量**,还是为了数量 / 效率 / 规避而**牺牲了质量**?后者一律不做。
- **实证依据**:平台(微信 / 头条 / 百家)降权的真正触发器是「AI 痕迹 + 低质 / 同质」,而非「是否声明 AI」。靠质量过审是唯一可持续路径。详见 `GUIDE.md` §8.1 / §8.3。

> 这条纲领同样写入了 `README.md` 顶部,以及 `app/services/pipeline.py` / `app/modules/base.py` / 各 `writer.py` 的文件头。无论从哪里进入代码,都应第一时间看到它。

## 项目一句话

「现象观察」—— 全自动 AI 内容运营系统:采集热点 → AI 选题 → 生成 → 风控 → 多渠道发布。完整战略与可行性分析见 `GUIDE.md` 第 8 章。

## 维护入口

- 最近生产链路、三渠道草稿、头条 `save=0` 坑位、定时配置等维护记录见：`docs/maintenance_notes.md`。

## 关键约束(摘要,详见 GUIDE §8)

- **平台**:多平台矩阵分发(头条 / 百家等算法平台起量),微信为长期目标号。
- **内容**:走「实用工具型知识」,放弃纯财经 / 娱乐资讯搬运。
- **AIGC 合规**:《人工智能生成合成内容标识办法》(2025-09-01 施行)要求显式 + 隐式标识;走质量路线本就与合规同向。
- **成本**:尽量零成本(不投流)。

## 提示词架构(2026-06-23 重构)

**项目级 vs 模块级分离:**

| 层级 | 文件 | 职责 |
|------|------|------|
| 项目级 | `app/services/prompts/base.py` | 所有文章必须遵守的规则:禁第一人称、禁具体媒体名、反AI指纹、字数/格式 |
| 娱乐 | `app/modules/entertainment/writer.py` `ENTERTAINMENT_PROMPT` | 娱乐观察定位、结构、网感要求 |
| 财经 | `app/modules/finance/writer.py` `FINANCE_PROMPT` | 数据驱动解读、五段式结构、来源标注 |

组合方式:`self.system_prompt = BASE_SYSTEM_PROMPT.format(min_chars=, max_chars=) + MODULE_PROMPT`

**修改规则:**
- 跨模块通用规则(禁词、媒体名列表、AI套话、字数、格式) → 只改 `base.py`
- 某个模块专属的定位/结构/风格 → 改对应模块的 `MODULE_PROMPT`
- 不要在两个模块的 prompt 之间复制粘贴规则

**当前项目级关键规则:**
- **禁第一人称**:我的看法/我的态度/我认为/在我看来/我个人觉得
- **禁具体媒体名**:新华社/央视/人民日报/CCTV/中新网/澎湃新闻/新京报/新华网/人民网/光明日报/经济日报/中国新闻网/环球时报/第一财经/每日经济新闻/21世纪经济报道/财新/界面新闻/南方周末
- **禁 AI 套话**:值得深思/引发广泛关注/在这个时代/不得不说/众所周知/耐人寻味/这背后折射出
- **禁模板化开头**:不要每篇都以"公开信息显示"开头,开头方式不拘一格(场景/数据/反差/提问)
- **技术约束**:单句≤80字、段1-3句、末段完整收尾、禁超长句堆叠

## 质量防线(2026-06-23)

### 规则质量闸 — `app/services/quality/checker.py`

在文章入库/发布前，用纯规则拦截退化/断头/重复/注水:

| 检测项 | 阈值 | 扣分 | 硬否决 |
|--------|------|------|--------|
| 退化超长句 | 单句>80字 | -35 | ✅ |
| 断头结尾 | 末字非句末标点 | -30 | ✅ |
| 字数严重不足 | 差>10% | -25 | ✅ |
| 字数略少 | 差≤10% | -10 | ❌(不否决) |
| 超长段落 | 单段>320字 | -20 | ❌ |
| 片段重复 | 6gram重复>3次 | -25 | ❌ |
| 分段过少 | <2段 | -15 | ❌ |

passed = score≥80 且无硬否决项。

### 生产链路接入

`app/modules/finance/module.py:_process_single_article`:
- `_generate_quality_checked_article()`:生成→质量闸→不合格重生成1次→仍不合格 status="quality_rejected" 弃稿不发布
- `_check_draft_quality()`:用真实质量分覆盖硬编码 style_score

### 风控(GuardService)增强

`app/services/guard/service.py`:
- 新增"语义质量"维度(信息增量/是否像机器/可读性)
- 规则质量分兜底:LLM 审核失败不再无条件放行,规则不合格则拦截
- 质量分<60→升high风险,<80→升medium风险

## LLM 模型链与定时(2026-06-23)

### 模型优先级

本机通过 8317(CLIProxyAPI)统一对外提供模型:

```
首选: sharedchat/gpt-5.5 (codex-api-key 静态key → sharedchat公益站)
 ↓ 失败
fallback1: gpt-5.5 (OAuth 29个codex token → 稳定)
 ↓ 失败
fallback2: claude-opus-4-6 → kimi-k2.6 → deepseek-v4-pro → kimi-k2p5
 → gpt-oss-120b → google/gemma-4-31b-it
```

配置在 `.env`(不入git):`OPENAI_MODEL=sharedchat/gpt-5.5` 和 `LLM_FALLBACK_MODELS=...`
8317 配置在 `/root/cc/CLIProxyAPI/config.yaml`(另一仓库)。
8317 的 auth-dir:`/root/.cli-proxy-api`(OAuth token文件的存放位置)。

### 定时发文

`entertainment/config.py` SCHEDULE_SLOTS:
- 北京 12:05 / 15:05 / 18:05 各一篇
- batch_type 分别为 noon/afternoon/evening(避免 job_id 冲突)

`scheduler.py`:CronTrigger 已显式传 `timezone=SCHEDULE_TZ="Asia/Shanghai"`(机器本地是 JST,不显式传会差1小时)。

### 头条号发布

`app/services/publish/channels/toutiao.py`:
- Playwright RPA 方式,登录态文件:`app/services/publish/cookies/toutiao_state.json`(.gitignore排除)
- `save=0` 保存草稿(详见 maintenance_notes.md §头条号重要坑位)
- 发布 API 失败自动重试 1 次(超时/异常不重试,由 PlaywrightChannel 基类兜底)
- 登录态过期表现:page.goto 超时或跳转到登录页;用 `scripts/login_helper.py` 重新获取
