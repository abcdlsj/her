# 自主分享与自主行为实现

## 概述

已成功实现 Her 的自主分享和自主行为功能，使其能够主动与用户交互，而不仅仅是被动响应。

## 实现的功能

### 1. 自主分享发现 (Proactive Sharing)

**工作原理**：
- 后台探索 RSSHub 获取内容
- 使用 `_find_interesting()` 筛选出最有趣的发现（基于 score）
- 将有趣的发现加入 `_pending_discoveries` 队列
- 定期检查队列并主动分享给用户

**时机控制**：
- 用户输入后等待 30 秒再考虑分享
- 每次分享后至少等待 90 秒
- 每 15 秒检查一次是否有分享机会
- 避免在用户打字时打断

**用户体验**：
- 分享消息显示在聊天区域
- 左侧意图面板记录 `proactive_share` 意图
- 状态栏显示 "💡 Her 分享了一个发现"

### 2. 自主行为监控循环

**实现位置**：`ui/app.py` 的 `_autonomous_behavior_loop()`

**核心逻辑**：
```python
async def _autonomous_behavior_loop(self) -> None:
    """后台循环：定期检查 Her 是否需要：
    1. 分享发现（主动分享）
    2. 打断对话（紧急消息）
    """
    # 每 15 秒检查一次
    # 满足条件时调用 _try_autonomous_share()
```

**时间参数**：
- `SHARE_CHECK_INTERVAL = 90` 秒：两次分享之间的最小间隔
- `WAIT_AFTER_USER_INPUT = 30` 秒：用户输入后等待时间
- 检查频率：15 秒一次
- 后台探索初始延迟：10 秒

### 3. 后台探索增强

**改进点**：
- 后台探索启动后 10 秒立即执行第一次探索
- 每次探索后自动查找有趣的发现
- 有趣发现自动加入待分享队列
- 后台探索失败时不影响 UI（静默处理）

**探索配置**：
```python
# 当前使用的 4 个科技信息源
TECH_ROUTES = [
    "/36kr/newsflash",       # 36氪快讯
    "/sspai/matrix",         # 少数派
    "/github/trending/daily", # GitHub 热门
    "/v2ex/topics/hot",     # V2EX 热门
]

# 探索间隔：5 分钟（300 秒）
```

### 4. 自主意图生成（框架已就绪）

**已实现但未启用**：
- `generate_autonomous_intent()`: 基于上下文生成自主意图
- `maybe_interrupt()`: 检查是否需要打断对话
- 支持的意图类型：`INTERRUPT`, `APPEND_TOPIC`, `CURIOSITY`

**未来可扩展**：
- 根据对话上下文主动引入新话题
- 紧急消息打断当前对话
- 表达好奇心并要求探索特定主题

## 文件变更

### `her/core/agent.py`
- 修改 `start_background_explore()`: 初始延迟后立即执行第一次探索
- 无其他功能变更（逻辑已存在）

### `her/ui/app.py`
- 新增 `_autonomous_task`: 后台任务引用
- 新增 `_last_user_input_time`: 最后用户输入时间
- 新增 `_last_share_time`: 最后分享时间
- 新增 `_is_user_typing`: 用户输入状态标志
- 修改 `on_chat_input_submitted()`: 记录用户输入时间
- 修改 `_process_input()`: 重置用户输入状态
- 新增 `_autonomous_behavior_loop()`: 自主行为监控循环
- 新增 `_try_autonomous_share()`: 尝试主动分享
- 修改 `action_quit()`: 取消自主任务并优雅退出

## 工作流程

### 启动流程
```
1. App 启动
2. on_mount() 被调用
3. 显示问候语
4. 启动自主行为监控任务 (_autonomous_behavior_loop)
5. Her.greet() 启动后台探索
   - 等待 10 秒
   - 立即执行第一次探索
   - 每 5 分钟探索一次
```

### 主动分享流程
```
1. 自主行为循环每 15 秒检查一次
2. 检查条件：
   - 用户未打字 (_is_user_typing = False)
   - 距离上次输入 > 30 秒
   - 距离上次分享 > 90 秒
3. 调用 _try_autonomous_share()
4. Agent.maybe_share_discovery() 检查待分享队列
5. 如果有待分享内容：
   - 从队列取出第一个
   - 生成分享消息（LLM）
   - 记录 PROACTIVE_SHARE 意图
   - 返回分享消息
6. UI 显示：
   - 聊天区域显示分享消息
   - 意图面板记录意图
   - 状态栏显示通知
```

### 退出流程
```
1. 用户按 Ctrl+C
2. action_quit() 被调用
3. 取消自主行为任务
4. 关闭 Agent（停止后台探索，关闭数据库）
5. 退出应用
```

## 配置建议

### 调整分享频率

在 `ui/app.py` 中修改：
```python
SHARE_CHECK_INTERVAL = 90  # 改为 120 减少分享频率
WAIT_AFTER_USER_INPUT = 30  # 改为 60 增加等待时间
```

### 调整探索频率

在 `her/core/agent.py` 中调用时修改：
```python
await agent.start_background_explore(interval=300)  # 改为 600 降低频率
```

### 添加更多信息源

在 `ui/app.py` 中修改：
```python
from her.infra.rsshub import create_rsshub, TECH_ROUTES, NEWS_ROUTES

# 合并多个信息源
ALL_ROUTES = TECH_ROUTES + NEWS_ROUTES
self.rsshub = create_rsshub(routes=ALL_ROUTES)
```

## 测试验证

### 已测试功能
- ✅ 探索内容并保存到数据库
- ✅ 查找有趣的发现（基于 score）
- ✅ 主动分享机制（生成分享消息）
- ✅ 意图记录和显示
- ✅ 时机控制（不打扰用户）
- ✅ 优雅退出（取消任务）

### 测试方法
运行完整流程测试（已删除）：
```bash
uv run python test_autonomous_simple.py
```

## 已知限制

1. **自主打断功能未启用**
   - `maybe_interrupt()` 代码已实现
   - 需要在自主行为循环中调用
   - 建议谨慎使用，避免频繁打断用户

2. **自主话题引入功能未启用**
   - `generate_autonomous_intent()` 支持 `APPEND_TOPIC`
   - 需要更复杂的上下文管理
   - 建议基于对话深度判断

3. **分享内容依赖 LLM 生成**
   - 使用 SHARE_PROMPT 模板
   - 需要消耗 LLM API
   - 可以考虑添加缓存

## 未来改进方向

1. **智能分享时机**
   - 基于对话主题相关性决定是否分享
   - 分析用户兴趣图谱
   - 学习用户对分享的反馈

2. **打断策略优化**
   - 仅在真正紧急时打断（重大新闻）
   - 提供用户自定义打断偏好
   - 支持临时静默模式

3. **分享内容个性化**
   - 根据用户兴趣筛选分享内容
   - 支持用户屏蔽某些主题
   - 分享不同长度的内容（简短/详细）

4. **性能优化**
   - LLM 调用缓存
   - 批量处理待分享队列
   - 后台任务优先级管理
