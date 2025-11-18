#ifndef AI_AGENT_MODELS_HPP
#define AI_AGENT_MODELS_HPP

#include <string>
#include <vector>
#include <map>
#include <optional>

/**
 * @brief 核心数据模型头文件
 * * 包含了 AI Agent 决策引擎所需的所有输入和输出结构体。
 * 设计为工业级，包含丰富的元数据和控制字段。
 */

namespace AIAgent {

// --- 辅助结构体定义 ---

/**
 * @brief 键值对数据结构，用于存储动态配置或参数。
 */
using DynamicData = std::map<std::string, std::string>;

/**
 * @brief 元素边界框信息。
 */
struct BoundingBox {
    double x_min;
    double y_min;
    double x_max;
    double y_max;
};

// --- 1. 任务目标结构体 (TaskGoal) ---

struct TaskGoal {
    // 核心任务定义
    std::string task_uuid;              // 任务的全局唯一标识符 (UUID)。
    std::string step_id;                // Planner 生成的当前执行步骤ID。
    
    // 目标与约束
    std::string target_description;     // 当前步骤的自然语言描述。
    std::optional<std::string> task_deadline_utc; // 整个任务的截止时间 (ISO 8601)。
    int max_execution_time_seconds = 60; // 允许 Agent 在此步骤花费的最大时间。
    
    // 状态与配置
    std::optional<DynamicData> required_data; // 步骤执行所需的关键数据，如登录凭证。
    std::string current_agent_persona = "standard_user"; // Agent 当前模拟的用户角色。
    std::string execution_environment = "desktop_chrome"; // 执行操作的浏览器环境。
    
    // 策略与工具
    std::vector<std::string> allowed_actions = {"click", "type", "scroll", "extract", "wait"}; // 限制 LLM 只能从这些工具中选择。
    int priority_level = 5;             // 任务的业务优先级 (1-10, 1最高)。
};

// --- 2. 网页状态观测结构体 (WebObservation) ---

/**
 * @brief 可操作元素信息。
 */
struct KeyElement {
    std::string element_id;         // 元素的内部ID或唯一标识。
    std::string tag_name;           // HTML 标签名 (如 div, a, input)。
    std::string xpath;              // 元素的 XPath 定位器。
    std::string inner_text;         // 元素的可见文本内容。
    bool is_visible = false;        // 元素是否在当前视口内可见。
    bool is_clickable = false;      // 元素是否可被点击。
    BoundingBox bbox;               // 元素的边界框信息。
    std::optional<std::string> purpose_hint; // LLM/视觉模型对该元素功能的推断。
};

/**
 * @brief 上一步操作的详细反馈。
 */
struct ActionFeedback {
    std::string status;             // 状态（如：SUCCESS, FAILED, TIMEOUT）。
    std::string error_code;         // 自定义或 HTTP 错误码 (如: E_404_NOT_FOUND, 401)。
    std::string message;            // 详细错误信息。
};

struct WebObservation {
    // 状态和性能元数据
    std::string observation_timestamp_utc; // 本次观测的时间戳 (ISO 8601)。
    std::string current_url;              // 当前浏览器加载的完整 URL。
    int http_status_code;                 // 最近一次导航操作返回的 HTTP 状态码。
    int page_load_time_ms;                // 页面加载完成所需的时间（毫秒）。
    bool is_authenticated = false;        // Agent 是否已登录（基于记忆中的标记）。
    
    // 核心 DOM/元素信息
    std::vector<KeyElement> key_elements; // 经过精简后的可操作元素列表。
    
    // 视觉信息（可选）
    bool screenshot_available = false;    // 是否有最新的截图可供视觉AI辅助判断。
    
    // 历史与反馈
    std::optional<ActionFeedback> last_action_feedback; // 上一步操作的详细反馈。
    std::string memory_context;           // Agent 的简短历史和短期记忆总结。
    
    // 浏览器健康
    std::string browser_health_status = "healthy"; // 浏览器驱动实例的健康状态。
};

// --- 3. 决策输出结构体 (DecisionAction) ---

struct DecisionAction {
    // 核心指令
    std::string tool_name;              // 要调用的工具函数名 (例如：'click_element')。
    DynamicData tool_args;              // 调用 tool_name 所需的参数 (键值对)。
    
    // 执行控制
    int max_attempts = 1;               // 如果操作失败，ActionExecutor 应该重试的次数。
    int execution_timeout_seconds = 10; // 此操作允许执行的最长时间（秒）。
    std::optional<std::string> wait_for_condition_after; // 操作执行后等待的条件。
    
    // 决策元数据
    std::string reasoning;              // LLM 解释其做出此操作选择的逻辑。
    double confidence_score;            // LLM 对此决策正确性的信心评分 (0.0 - 1.0)。
    std::string expected_outcome;       // 执行此操作后，Agent 预期的下一页状态。
    
    // 错误处理
    std::string on_failure_action = "RE_EVALUATE"; // 如果操作失败，Agent 下一步应该做什么。
};

} // namespace AIAgent

#endif // AI_AGENT_MODELS_HPP