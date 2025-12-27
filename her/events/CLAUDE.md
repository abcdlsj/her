# events/ - 事件系统

## 职责

提供事件驱动的通信机制，解耦 Agent 逻辑和 UI 展示。

## 核心概念

```
Producer (Agent/Explorer)
         │
         │ emit(event)
         ▼
    ┌─────────┐
    │ EventBus │ ──────────────────┐
    └─────────┘                    │
         │                         │
         │ subscribe()             │ persist()
         ▼                         ▼
    ┌─────────┐              ┌──────────┐
    │ UI/CLI  │              │ events.db │
    └─────────┘              └──────────┘
```

## 事件类型

```python
# 基础事件
@dataclass
class Event:
    timestamp: datetime
    type: str

# 具体事件
class StatusEvent(Event):       # 状态更新
class ExploreStartEvent(Event): # 开始探索某个源
class ExploreEndEvent(Event):   # 探索完成
class DiscoveryEvent(Event):    # 发现有趣内容，想要分享
class ChatEvent(Event):         # 对话消息
class ErrorEvent(Event):        # 错误发生
```

## EventBus API

```python
class EventBus:
    async def emit(self, event: Event):
        """发送事件"""

    async def subscribe(self) -> AsyncIterator[Event]:
        """订阅事件流"""

    def on(self, event_type: type[Event], handler: Callable):
        """注册特定事件的处理器"""
```

## 使用场景

### 1. 状态通知
```python
# Agent 发送状态
await bus.emit(StatusEvent(message="正在浏览 Hacker News..."))

# UI 接收并显示
async for event in bus.subscribe():
    if isinstance(event, StatusEvent):
        console.print(f"[dim]{event.message}[/dim]")
```

### 2. 主动分享
```python
# Explorer 发现有趣内容
await bus.emit(DiscoveryEvent(
    item=item,
    reason="这个和你之前聊的 AI 话题相关"
))

# UI 在合适时机展示
async for event in bus.subscribe():
    if isinstance(event, DiscoveryEvent):
        # 等用户输入间隙再展示
        await show_discovery(event)
```

### 3. 错误处理
```python
# 某个源获取失败
await bus.emit(ErrorEvent(
    source="Twitter",
    error="API rate limit exceeded"
))
```

## 实现要点

1. **异步队列**: 使用 `asyncio.Queue` 实现
2. **多订阅者**: 支持多个消费者同时订阅
3. **不阻塞**: emit 应该快速返回
4. **可选持久化**: 事件可以写入文件用于回放
