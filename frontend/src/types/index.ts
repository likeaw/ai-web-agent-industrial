export enum ExecutionNodeStatus {
  PENDING = 'PENDING',
  RUNNING = 'RUNNING',
  SUCCESS = 'SUCCESS',
  FAILED = 'FAILED',
  PRUNED = 'PRUNED',
  SKIPPED = 'SKIPPED',
}

export interface ExecutionNode {
  node_id: string
  parent_id?: string
  child_ids: string[]
  execution_order_priority: number
  action: DecisionAction
  current_status: ExecutionNodeStatus
  failure_reason?: string
  required_precondition: string
  expected_cost_units: number
  last_observation?: WebObservation
  resolved_output?: string
}

export interface DecisionAction {
  tool_name: string
  tool_args: Record<string, any>
  max_attempts: number
  execution_timeout_seconds: number
  wait_for_condition_after?: string
  reasoning: string
  confidence_score: number
  expected_outcome: string
  on_failure_action: string
}

export interface WebObservation {
  observation_timestamp_utc: string
  current_url: string
  http_status_code: number
  page_load_time_ms: number
  is_authenticated: boolean
  key_elements: KeyElement[]
  screenshot_available: boolean
  last_action_feedback?: ActionFeedback
  memory_context: string
  browser_health_status: string
}

export interface KeyElement {
  element_id: string
  tag_name: string
  xpath: string
  inner_text: string
  is_visible: boolean
  is_clickable: boolean
  bbox: BoundingBox
  purpose_hint?: string
}

export interface BoundingBox {
  x_min: number
  y_min: number
  x_max: number
  y_max: number
}

export interface ActionFeedback {
  status: string
  error_code: string
  message: string
}

export interface TaskGoal {
  task_uuid: string
  step_id: string
  target_description: string
  task_deadline_utc?: string
  max_execution_time_seconds: number
  required_data?: Record<string, any>
  current_agent_persona: string
  execution_environment: string
  allowed_actions: string[]
  priority_level: number
}

export interface TaskExecution {
  task_uuid: string
  goal: TaskGoal
  nodes: Record<string, ExecutionNode>
  root_node_id?: string
  status: 'idle' | 'running' | 'completed' | 'failed'
  start_time?: string
  end_time?: string
}

export interface LogEntry {
  id: string
  timestamp: string
  level: 'info' | 'warning' | 'error' | 'success'
  message: string
  node_id?: string
}

