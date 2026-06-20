# 多渠道发布方案(2026-06-19)

> 配合 `GUIDE.md` §8.4(多平台矩阵)/ §8.5(工程改造)。本方案的前提同样是 [项目第一纲领](../CLAUDE.md):**质量第一,质量低不如不做**——多渠道只是把"一篇好内容"分发到更多算法平台起量,绝不是把低质内容铺满全网。

## 0. 目标

让 autowz 的「生成」与「发布」彻底解耦:一篇文章生成后,可自由组合发布到 **微信公众号 / 头条号 / 百家号 / 大鱼号**(后续可扩展知乎、视频号等)。核心诉求:复用现有系统、尽量零成本、尽量自动。

## 1. 开源选型调研(GitHub,2026-06-19)

| 项目 | Star | 技术栈 | 覆盖平台 | 对 autowz 的价值 |
|---|---|---|---|---|
| **wechatsync/Wechatsync** | 5786★ | TS / Chrome 扩展 | **头条/百家/大鱼**+知乎/掘金/CSDN/微博/小红书等 **29+** | ⭐ 首选参考。逆向了各平台 Web 编辑器官方接口,社区活跃维护(2026-05),原生支持 MCP |
| crawlab-team/artipub | 3198★ | TS / 平台 | 掘金/知乎/头条/SegmentFault 等 | 架构参考,但偏博客技术平台,维护时紧时松 |
| aiseall/SmartMediaHub | 117★ | TS | 头条/公众号/抖音/小红书/B站 | 形态最像 autowz(发布+定时+阅读状态+LLM),可参考整体设计 |
| veeicwgy/ip-publisher | 25★ | **Python** | 微信/小红书等 7 平台 | 同语言,含"事实审计"(质量向),可读其发布代码 |
| zhuixin8/meiti-ai | 2★ | - | 抖音/小红书/头条/百家/公众号等 20+ | ⚠️ 宣称"去 AI 味",理念与本项目纲领相悖,仅参考其分发面,**不采纳其规避思路** |

**结论**:不存在能直接 `pip install` 接进 autowz、覆盖头条+百家+大鱼的成熟 Python 库。**Wechatsync 是最佳参考源**——它把"各平台发布接口怎么调"这件最脏最易过时的事做好了且在维护。

## 2. 关键发现:技术路线可升级(Cookie + Web API,而非脆弱 RPA)

原先判断多平台只能靠 Playwright 模拟点击(脆弱、易被页面改版打断)。Wechatsync 证明有更稳的路:

> **持有浏览器登录态 Cookie → 直接 HTTP 调用各平台 Web 编辑器的官方接口**(与手动网页发布等价),默认存草稿。

优点:不依赖页面 DOM(比模拟点击稳)、不经第三方服务器、开源接口可参考。代价:需要**各平台登录 Cookie**,且 Cookie 会过期(见 §6 最小人工)。

**复用方式(诚实说明)**:Wechatsync 是 TypeScript Chrome 扩展,**不能被 Python 后端直接调用**。可行的是:
- (a) **参考移植**——读其源码里各平台的接口地址 / 字段映射,在 Python(httpx)里重新实现对应 Channel。**这是主路径。**
- (b) 其 MCP 能力适合"交互式 Claude Code 里手动发",但 autowz 是后台 systemd 无人值守服务,MCP 需会话驱动,**不适合自动发布主链路**。

## 3. autowz 解耦发布层架构

```
modules/*(生成层)──产出──▶ ArticleProduct(标准产物,与渠道无关)
                                   │
                          PublishRouter(按配置路由到 N 个渠道)
                                   │
        ┌──────────────┬───────────┼───────────┬──────────────┐
   WechatChannel   ToutiaoChannel  Baijiahao   DayuChannel   (知乎/视频号…)
   (现有官方API)   (Cookie+WebAPI)    …             …
```

### 3.1 标准产物(生成层只管产出它)

```python
@dataclass
class ArticleProduct:
    title: str
    digest: str
    content_html: str
    content_md: str
    cover_path: str | None
    inline_images: list[str]
    tags: list[str]
    ai_disclosure: bool = True      # 合规:是否注入"AI 辅助生成"声明(走质量+合规路线)
    quality_score: float | None = None   # 质量门:低于阈值的产物 Router 直接拒发(落实纲领)
```

### 3.2 渠道抽象

```python
class Channel(ABC):
    name: str
    @abstractmethod
    async def is_ready(self) -> bool: ...                 # 登录态/Cookie 是否有效
    @abstractmethod
    async def publish(self, product: ArticleProduct, *, as_draft: bool = True) -> PublishResult: ...
    async def fetch_stats(self, ref: str) -> ChannelStats | None:   # 数据回收(P2)
        return None
```

### 3.3 路由器(落实"质量门 + 草稿优先")

```python
class PublishRouter:
    def __init__(self, channels: dict[str, Channel], min_quality: float): ...
    async def publish(self, product, targets: list[str], as_draft=True) -> dict[str, PublishResult]:
        # 1) 质量门:product.quality_score < min_quality → 全部拒发(纲领:质量低不如不做)
        # 2) 对每个 target:is_ready() 通过才发,默认 as_draft=True
        # 3) 汇总各渠道结果,落库(为数据闭环铺路)
```

### 3.4 目录结构(新增,不破坏现有)

```
app/services/publish/
  product.py     # ArticleProduct / PublishResult / ChannelStats
  base.py        # Channel 抽象
  router.py      # PublishRouter(质量门 + 草稿优先 + 落库)
  channels/
    wechat.py    # WechatChannel —— 包装现有 app/services/wechat/service.py,行为不变
    toutiao.py   # 头条号(Cookie + Web API,参考 Wechatsync)
    baijiahao.py # 百家号
    dayu.py      # 大鱼号
  cookies/       # 各平台登录态(加入 .gitignore,不入库)
```

## 4. 与纲领 / 合规的结合

- **质量门**:`PublishRouter` 在分发前用 `quality_score` 卡线,不达标不发——把"质量低不如不做"写进发布主路径。
- **草稿优先**:借鉴 Wechatsync,各渠道默认发草稿,降低风控与误发风险。
- **AI 标识**:`ai_disclosure` 让各 Channel 按平台要求注入合规声明(《标识办法》),与质量路线同向,不做规避。

## 5. 实施路线

| 阶段 | 内容 | 说明 |
|---|---|---|
| **P0-1** | 建 `publish/` 骨架:`ArticleProduct` + `Channel` + `PublishRouter` + `WechatChannel`(包装现有微信发布) | 纯重构,**不改变现有微信发布行为**,先让"解耦"成立 |
| **P0-2** | 实现 `ToutiaoChannel`(头条号) | 头条是起量主力且 Wechatsync 支持成熟,先打通一个验证架构 |
| **P1** | `BaijiahaoChannel` / `DayuChannel` + Cookie 登录态管理与失效告警 | 复制头条模式 |
| **P1** | pipeline 接 `PublishRouter`,加"发布路由"配置(哪篇→哪些渠道) | 真正实现"自由组合" |
| **P2** | 各渠道 `fetch_stats` 数据回收 → 喂 §8.5 P0 数据闭环 | 多渠道阅读量统一回收 |

## 6. 风险与最小人工

- **Cookie 维护**:头条/百家/大鱼需人工登录一次、导出 Cookie;过期后需重新导出(频率约数周~数月)。系统提供 `is_ready()` 检测 + 失效告警,把人工降到最低。
- **平台风控**:即便走官方 Web 接口,短时间高频发布仍可能触发风控 → 草稿优先 + 发布间隔。
- **接口漂移**:平台改接口时对应 Channel 需跟进 → 跟踪 Wechatsync 更新即可低成本同步。
- **不碰的红线**:不做"去 AI 味/去水印规避检测"(违纲领且违《标识办法》),起量靠内容质量。
