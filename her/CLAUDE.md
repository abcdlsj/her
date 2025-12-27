# her/ - 核心模块

## 模块职责

| 文件 | 职责 |
|------|------|
| `agent.py` | Her Agent 主类，协调对话和探索 |
| `cli.py` | 终端交互入口 |
| `llm.py` | LLM 抽象层，支持多提供商 |
| `memory.py` | 记忆系统，SQLite 存储 |
| `prompts.py` | 所有 Prompt 模板集中管理 |

## Agent 设计

```python
class Her:
    """Her Agent - 有主动性的 AI 伙伴"""

    def __init__(
        self,
        sources: list[Source],      # 信息源列表
        memory: Memory,             # 记忆系统
        llm: LLM,                   # 语言模型
        event_bus: EventBus,        # 事件总线
    ): ...

    async def chat(self, message: str) -> str:
        """响应用户消息"""

    async def start_exploring(self):
        """启动后台探索循环"""

    async def maybe_share(self) -> str | None:
        """检查是否有值得分享的发现"""
```

## LLM 抽象

支持多个提供商，通过环境变量或配置切换：

```python
# 环境变量
OPENAI_API_KEY / OPENAI_BASE_URL
ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL

# 使用
config = LLMConfig(provider=Provider.OPENAI, model="gpt-4o")
llm = create_llm(config)
```

## Memory 设计

```
~/.her/
├── memory.db       # SQLite 数据库
├── history         # 命令历史
└── config.toml     # 配置文件（TODO）

Tables:
- conversations     # 对话历史
- explored_items    # 探索到的内容
- daily_digest      # 每日摘要
```

## 命名规范

- 类名: PascalCase
- 函数/变量: snake_case
- 常量: UPPER_SNAKE_CASE
- 私有成员: _leading_underscore
