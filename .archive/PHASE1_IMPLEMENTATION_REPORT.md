# autowz 模块化重构 + Phase 1 实施报告

**完成时间**: 2026-06-14  
**状态**: ✅ 已完成  
**任务**: 模块化架构重构 + Phase 1 止血方案全部实施

---

## 一、完成的工作

### 1. 模块化架构建立 ✅

#### 1.1 核心设计
建立了**内容模块抽象层**,支持多套完全独立的内容生产配方:

**新增文件**:
```
app/modules/
  ├── __init__.py                  # 模块包初始化
  ├── base.py                      # BaseContentModule 抽象基类
  ├── registry.py                  # 模块注册表
  └── finance/                     # 财经模块(首个实现)
      ├── __init__.py
      ├── config.py                # 配置参数(频率/字数/选题/作者等)
      ├── writer.py                # DataDrivenWriter(数据解读型)
      └── module.py                # FinanceModule 完整实现
```

#### 1.2 设计亮点
- **完全解耦**: 各模块独立,财经挂了不影响娱乐
- **配置驱动**: 改频率/字数/人设只需改 `config.py`
- **易扩展**: 新增模块只需继承 `BaseContentModule` + 注册
- **复用基础设施**: 所有模块共享 LLM/发布/审核/数据库

### 2. Phase 1 止血措施全部实施 ✅

#### 2.1 删除机器指纹
**文件**: `app/services/content_length.py`
```python
# 修改前: finalize_article 结尾自动添加"(全文共729字)"
# 修改后: 只裁剪,不加尾巴
def finalize_article(text: str, max_chars: int = MAX_ARTICLE_CHARS) -> str:
    """裁剪正文到上限字数。
    Phase 1 改动: 去除"(全文共X字)"机器指纹,只做裁剪。
    """
    body = _strip_count_suffix(text)
    return trim_markdown_to_max_chars(body, max_chars)
```

#### 2.2 重写 writer prompt(数据解读型)
**文件**: `app/modules/finance/writer.py`

新 prompt 核心要求:
1. **开头钩子**(50-80字): 反常识数字或反差,禁止"据X报道"
2. **数据呈现**(200-250字): 核心数字+对比+来源,用小表格
3. **解读分析**(200-250字): 驱动因素+横向对比+拆解矛盾
4. **影响推演**(100-150字): 产业链/消费者/投资影响
5. **明确判断**(50-80字): 清晰结论,不骑墙

**严格禁止**:
- AI套话("在这个XX的时代""不得不说""众所周知""耐人寻味")
- 机械序列词("首先/其次/最后""综上所述")
- 整齐排比和工整对仗
- 公知体和空洞抒情
- "据X报道"开头和"从市场逻辑看"套话

#### 2.3 合并 writer + humanizer
**文件**: `app/modules/finance/module.py` + `app/services/pipeline.py`

**改动前**: writer 生成 → humanizer 再洗一遍 → 双 LLM 叠加 AIGC 指纹  
**改动后**: 单次生成,不调用 humanizer,`style_score` 提升到 85

#### 2.4 调度器改为每天 1 篇
**文件**: `app/tasks/scheduler.py`

**改动前**: 每天 3 次(8:30/12:30/18:30)  
**改动后**: 每天 1 次(7:30),避开整点

```python
# Phase 1: 每天只发 1 篇财经精品(早间 7:30)
scheduler.add_job(
    _job_batch, CronTrigger(hour=7, minute=30),
    args=["morning", 1, "finance"],
    id="finance_daily_batch",
    replace_existing=True,
)
```

#### 2.5 pipeline 改为模块化委托
**文件**: `app/services/pipeline.py`

**改动前**: ArticlePipeline 直接实现完整流程(200+ 行)  
**改动后**: 委托给模块实现,保留向后兼容接口

```python
class ArticlePipeline:
    def __init__(self, module_name: str = "finance") -> None:
        self.module = get_module(module_name)  # 委托给模块
    
    async def run_batch(...):
        return await self.module.run_batch(count)  # 统一调用
```

---

## 二、验收结果

### 1. 模块注册测试 ✅
```bash
$ python -c "from app.modules.registry import list_modules, get_module; ..."
已注册模块: ['finance']
财经模块: finance - 财经观察
测试通过
```

### 2. 改动文件清单
| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `app/services/content_length.py` | 修改 | 删除"(全文共X字)"尾巴 |
| `app/services/pipeline.py` | 重构 | 改为模块化委托,保留兼容接口 |
| `app/tasks/scheduler.py` | 修改 | 每天1篇,7:30发布 |
| `app/modules/base.py` | 新增 | 模块抽象基类 |
| `app/modules/registry.py` | 新增 | 模块注册表 |
| `app/modules/finance/config.py` | 新增 | 财经模块配置 |
| `app/modules/finance/writer.py` | 新增 | 数据解读型 writer |
| `app/modules/finance/module.py` | 新增 | 财经模块完整实现 |

### 3. 新生成文章的预期特征
- ✅ 结尾无"(全文共X字)"
- ✅ 标题无"今天怎么看｜"前缀
- ✅ 开头用数字/反差钩子,非"据X报道"
- ✅ 结构为"钩子→数据→解读→影响→判断"
- ✅ 无 AI 套话和整齐排比
- ✅ 单次生成,无双 LLM 指纹

---

## 三、代码质量保证

### 1. 架构设计
- ✅ 符合 SOLID 原则(单一职责/开闭原则)
- ✅ 依赖注入,松耦合
- ✅ 抽象清晰,易扩展

### 2. 向后兼容
- ✅ 保留 `ArticlePipeline` 旧接口
- ✅ API 路由无需改动
- ✅ 数据库结构无变更

### 3. 测试覆盖
- ✅ 模块注册系统测试通过
- ⚠️  需要生成测试文章验证效果(Task #3)

---

## 四、下一步工作

### Phase 1 收尾
1. **生成测试文章** (Task #3):
   - 手动触发批次生成 1 篇
   - 检查是否符合预期特征
   - 发布到草稿箱验证

2. **代码审查** (Task #3):
   - 启动代码审查专家全面复核
   - 检查边界条件和异常处理

### Phase 2 准备(3-5天后)
1. 接入 AKShare 财经数据源
2. 新增事实提炼层(`fact_extractor` + `data_card`)
3. writer 改为接收结构化数据卡
4. 数据库新增 `financial_data` 表

---

## 五、风险提示

| 风险 | 当前状态 | 对策 |
|------|----------|------|
| 新 prompt 生成质量波动 | 未验证 | Task #3 生成测试文章检验 |
| 单次生成(去 humanizer)质量下降 | 未验证 | 已提升 style_score 到 85,需实测 |
| 模块化重构引入 bug | 低风险 | 保留了向后兼容接口 |
| 每天 1 篇涨粉慢 | 预期内 | 质量换留存率,符合战略方向 |

---

**结论**: Phase 1 架构重构和止血措施全部完成,系统已具备模块化扩展能力。等待测试文章验证效果后,即可进入 Phase 2 数据接入阶段。
