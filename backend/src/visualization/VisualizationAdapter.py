# 文件: backend/src/visualization/VisualizationAdapter.py (重构为纯渲染器)

import time 
from typing import List
# 确保正确导入了 Planner 和数据模型
from backend.src.agent.Planner import DynamicExecutionGraph
from backend.src.data_models.decision_engine.decision_models import ExecutionNodeStatus, ExecutionNode

class VisualizationAdapter:
    """
    负责将 DynamicExecutionGraph 转换为 Mermaid 格式的 HTML 字符串。
    此模块不再执行文件I/O或打印日志，只专注于数据格式转换。
    """
    
    # 基础 HTML 模板
    HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <title>Agent Execution Graph: {title}</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <style>
        body {{ font-family: sans-serif; padding: 20px; }}
        h1 {{ border-bottom: 2px solid #ccc; padding-bottom: 10px; }}
        .mermaid {{ width: 100%; height: auto; border: 1px solid #ddd; padding: 10px; box-sizing: border-box; }}
        
        /* 自定义 Mermaid 样式 */
        .node.success rect {{ fill: #90EE90; stroke: #3C3; stroke-width: 2px; }}
        .node.running rect {{ fill: yellow; stroke: #FF0; stroke-width: 2px; }}
        .node.failed rect {{ fill: #FA8072; stroke: #F00; stroke-width: 2px; }}
        .node.pending rect {{ fill: lightblue; stroke: #39F; stroke-width: 2px; }}
        .node.pruned rect {{ fill: grey; stroke: #666; stroke-width: 2px; }}
        
        .edgeLabel {{ background-color: white; padding: 0 5px; border-radius: 3px; }}
    </style>
</head>
<body>
    <h1>Agent Execution Graph Snapshot: {title}</h1>
    <p>Timestamp: {timestamp}</p>
    <pre class="mermaid">
{mermaid_code}
    </pre>
    <script>
        mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
    </script>
</body>
</html>
"""
    
    @staticmethod
    def _get_mermaid_style_class(status: ExecutionNodeStatus) -> str:
        """根据节点状态返回 Mermaid CSS 类名。"""
        return status.name.lower()

    @staticmethod
    def render_graph_to_html_string(
        graph: DynamicExecutionGraph, 
        output_filename: str = "execution_plan", 
    ) -> str:
        """
        将图结构转换为完整的 HTML 字符串并返回。
        """
        
        mermaid_code = "graph TD\n"
        styles: List[str] = []
        
        # 1. 遍历节点并生成 Mermaid 定义
        for node_id, node in graph.nodes.items():
            
            label = (
                f"ID: {node_id}<br/>"
                f"P: {node.execution_order_priority}<br/>"
                f"Tool: {node.action.tool_name}<br/>"
                f"Status: {node.current_status.name}"
            )
            
            mermaid_code += f'    {node_id}["{label}"]\n'
            
            class_name = VisualizationAdapter._get_mermaid_style_class(node.current_status)
            styles.append(f'    class {node_id} {class_name};')

        # 2. 遍历边
        for node_id, node in graph.nodes.items():
            if node.parent_id and node.parent_id in graph.nodes:
                edge_label = f"P{node.execution_order_priority}"
                mermaid_code += f'    {node.parent_id} -->|{edge_label}| {node_id}\n'
                
        # 3. 嵌入样式和 Mermaid 源码到 HTML 模板
        mermaid_code += "\n" + "\n".join(styles)

        current_timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        html_content = VisualizationAdapter.HTML_TEMPLATE.format(
            title=output_filename,
            timestamp=current_timestamp,
            mermaid_code=mermaid_code.strip()
        )
        
        return html_content