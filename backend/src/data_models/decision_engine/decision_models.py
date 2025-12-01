from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

# --- 辅助类型定义 ---
DynamicData = Dict[str, Any]

class BoundingBox(BaseModel):
    """元素边界框信息。"""
    x_min: float
    y_min: float
    x_max: float
    y_max: float

# --- 3. 决策输出结构体 (DecisionAction) ---

class DecisionAction(BaseModel):
    """决策引擎返回的、将被执行的操作指令。"""
    
    tool_name: str = Field(..., description="对应 ActionExecutor 中封装的函数名，例如：'click_element'。")
    tool_args: DynamicData = Field(..., description="调用 tool_name 所需的参数。")
    
    # 执行控制
    max_attempts: int = Field(1, description="如果操作失败，ActionExecutor 应该重试的次数。")
    execution_timeout_seconds: int = Field(10, description="此操作允许执行的最长时间（秒）。")
    wait_for_condition_after: Optional[str] = Field(None, description="操作执行后等待的条件。")
    
    # 决策元数据
    reasoning: str = Field(..., description="LLM 解释其做出此操作选择的逻辑。")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="LLM 对此决策正确性的信心评分 (0.0 - 1.0)。")
    expected_outcome: str = Field(..., description="执行此操作后，Agent 预期的下一页状态或结果。")
    
    # 错误处理
    on_failure_action: str = Field("RE_EVALUATE", description="如果操作失败，Agent 下一步应该做什么（RE_EVALUATE, STOP_TASK, TRY_ALTERNATE）。")


# --- 1. 任务目标结构体 (TaskGoal) ---

class TaskGoal(BaseModel):
    """当前 Agent 想要达成的目标和上下文。"""
    
    task_uuid: str = Field(..., description="任务的全局唯一标识符。")
    step_id: str = Field(..., description="Planner 生成的当前执行步骤ID。")
    
    target_description: str = Field(..., description="当前步骤的自然语言描述。")
    task_deadline_utc: Optional[str] = Field(None, description="整个任务的截止时间 (ISO 8601)。")
    max_execution_time_seconds: int = Field(60, description="允许 Agent 在此步骤花费的最大时间。")
    
    required_data: Optional[DynamicData] = Field(None, description="步骤执行所需的关键数据。")
    current_agent_persona: str = Field("standard_user", description="Agent 当前模拟的用户角色。")
    execution_environment: str = Field("desktop_chrome", description="执行操作的浏览器环境。")
    
    allowed_actions: List[str] = Field(["click", "type", "scroll", "extract", "wait"], description="限制 LLM 工具。")
    priority_level: int = Field(5, description="任务的业务优先级 (1-10)。")


# --- 2. 网页状态观测结构体 (WebObservation) ---

class KeyElement(BaseModel):
    """可操作元素信息。"""
    element_id: str
    tag_name: str
    xpath: str
    inner_text: str
    is_visible: bool = False
    is_clickable: bool = False
    bbox: BoundingBox
    purpose_hint: Optional[str] = None # LLM/视觉模型对该元素功能的推断。

class ActionFeedback(BaseModel):
    """上一步操作的详细反馈。"""
    status: str
    error_code: str
    message: str

class WebObservation(BaseModel):
    """当前网页环境的结构化观测结果。"""
    
    observation_timestamp_utc: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="本次观测的时间戳。")
    current_url: str
    http_status_code: int
    page_load_time_ms: int
    is_authenticated: bool = False
    
    key_elements: List[KeyElement]
    screenshot_available: bool = False
    
    last_action_feedback: Optional[ActionFeedback] = None
    memory_context: str
    
    browser_health_status: str = "healthy"


# --- 4. 动态执行图节点结构体 (ExecutionNode) ---

class ExecutionNodeStatus(str, Enum):
    """节点在执行图中的状态。"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PRUNED = "PRUNED"
    SKIPPED = "SKIPPED"

class ExecutionNode(BaseModel):
    """
    定义动态执行图中的一个决策或操作步骤。
    """
    
    node_id: str
    parent_id: Optional[str] = None
    child_ids: List[str] = Field(default_factory=list)
    execution_order_priority: int = Field(1, description="在同一级别上，节点的执行顺序 (1最高)。")

    action: DecisionAction # 节点中封装的实际操作 (Tool Call)
    
    current_status: ExecutionNodeStatus = ExecutionNodeStatus.PENDING
    failure_reason: Optional[str] = None

    required_precondition: str = Field("True", description="执行此节点前，网页必须达到的状态。")
    expected_cost_units: int = 1 # 预估的资源消耗或时间
    
    # === [新增字段] 运行时状态/结果 ===
    last_observation: Optional[WebObservation] = Field(None, description="此节点执行完毕后的网页观测结果。")
    resolved_output: Optional[str] = Field(None, description="从WebObservation中提取的关键结果，供后续节点使用。")