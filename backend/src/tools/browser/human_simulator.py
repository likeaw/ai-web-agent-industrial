"""
人类操作模拟器。

模拟真实的人类浏览器操作，包括：
- 随机延迟
- 鼠标移动轨迹
- 自然的滚动行为
- 检测并展开折叠内容
"""

import random
import time
from typing import Optional, List, Tuple

from playwright.sync_api import Page


def random_delay(min_seconds: float = 0.5, max_seconds: float = 2.0):
    """随机延迟，模拟人类反应时间。"""
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)


def human_like_scroll(
    page: Page,
    direction: str = "down",
    amount: Optional[int] = None,
    smooth: bool = True,
):
    """
    模拟人类自然的滚动行为。
    
    :param page: Playwright Page 对象
    :param direction: 滚动方向 "down" 或 "up"
    :param amount: 滚动像素数，None 表示随机
    :param smooth: 是否平滑滚动
    """
    if amount is None:
        # 人类通常不会一次滚动太多
        amount = random.randint(300, 800)
    
    if direction == "down":
        scroll_amount = amount
    else:
        scroll_amount = -amount
    
    # 平滑滚动：分多小步完成
    if smooth:
        steps = random.randint(3, 6)
        step_size = scroll_amount / steps
        
        for _ in range(steps):
            page.mouse.wheel(0, step_size)
            time.sleep(random.uniform(0.05, 0.15))
    else:
        page.mouse.wheel(0, scroll_amount)
    
    # 滚动后随机等待
    random_delay(0.3, 0.8)


def simulate_mouse_movement(page: Page, start_pos: Tuple[int, int], end_pos: Tuple[int, int]):
    """
    模拟鼠标移动轨迹（贝塞尔曲线近似）。
    
    :param page: Playwright Page 对象
    :param start_pos: 起始位置 (x, y)
    :param end_pos: 结束位置 (x, y)
    """
    steps = random.randint(10, 20)
    
    for i in range(steps + 1):
        t = i / steps
        # 简单的线性插值 + 随机偏移
        x = start_pos[0] + (end_pos[0] - start_pos[0]) * t + random.randint(-5, 5)
        y = start_pos[1] + (end_pos[1] - start_pos[1]) * t + random.randint(-5, 5)
        
        page.mouse.move(x, y)
        time.sleep(random.uniform(0.01, 0.03))


def detect_and_expand_collapsible_content(page: Page) -> int:
    """
    检测并展开页面中的折叠内容（如"查看更多"、折叠菜单等）。
    
    :param page: Playwright Page 对象
    :return: 展开的元素数量
    """
    expanded_count = 0
    
    # 常见的折叠内容选择器
    expand_selectors = [
        # 通用展开按钮
        "button:has-text('更多')",
        "button:has-text('展开')",
        "button:has-text('显示更多')",
        "button:has-text('查看更多')",
        "button:has-text('展开全部')",
        "a:has-text('更多')",
        "a:has-text('展开')",
        "a:has-text('显示更多')",
        "a:has-text('查看更多')",
        
        # 英文
        "button:has-text('more')",
        "button:has-text('More')",
        "button:has-text('show more')",
        "button:has-text('Show More')",
        "button:has-text('expand')",
        "button:has-text('Expand')",
        
        # 常见 class/id 模式
        "[class*='expand']",
        "[class*='more']",
        "[class*='toggle']",
        "[id*='expand']",
        "[id*='more']",
        
        # 详情/折叠面板
        "details",
        "[class*='collapsible']",
        "[class*='accordion']",
    ]
    
    for selector in expand_selectors:
        try:
            elements = page.locator(selector)
            count = min(elements.count(), 5)  # 最多展开5个
            
            for idx in range(count):
                try:
                    element = elements.nth(idx)
                    
                    # 检查是否可见且可点击
                    if not element.is_visible(timeout=1000):
                        continue
                    
                    # 检查是否已经是展开状态（对于 details 元素）
                    if selector == "details":
                        is_open = element.evaluate("el => el.open")
                        if is_open:
                            continue
                    
                    # 点击展开
                    element.click(timeout=2000)
                    expanded_count += 1
                    
                    # 展开后等待内容加载
                    random_delay(0.5, 1.0)
                    
                except Exception:
                    continue
        except Exception:
            continue
    
    return expanded_count


def detect_and_trigger_lazy_load(page: Page, max_scrolls: int = 5) -> int:
    """
    检测并触发懒加载内容（通过滚动触发）。
    
    :param page: Playwright Page 对象
    :param max_scrolls: 最大滚动次数
    :return: 触发的懒加载次数
    """
    triggered_count = 0
    last_content_height = 0
    
    for _ in range(max_scrolls):
        # 获取当前页面高度
        current_height = page.evaluate("document.body.scrollHeight")
        
        # 如果高度没有变化，可能已经加载完所有内容
        if current_height == last_content_height:
            break
        
        last_content_height = current_height
        
        # 滚动到页面底部触发懒加载
        human_like_scroll(page, direction="down", amount=800)
        
        # 等待新内容加载
        random_delay(1.0, 2.0)
        
        # 检查是否有新内容加载
        new_height = page.evaluate("document.body.scrollHeight")
        if new_height > current_height:
            triggered_count += 1
    
    return triggered_count


def prepare_page_for_extraction(page: Page, max_expand_attempts: int = 3):
    """
    全面准备页面以便提取内容：
    - 展开折叠内容
    - 触发懒加载
    - 等待内容稳定
    
    :param page: Playwright Page 对象
    :param max_expand_attempts: 最大展开尝试次数
    """
    print("[human_simulator] Preparing page for extraction...")
    
    # 1. 等待初始页面加载
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass
    
    random_delay(1.0, 2.0)
    
    # 2. 展开折叠内容（多次尝试，因为展开后可能还有更多折叠内容）
    for attempt in range(max_expand_attempts):
        expanded = detect_and_expand_collapsible_content(page)
        if expanded > 0:
            print(f"[human_simulator] Expanded {expanded} collapsible elements (attempt {attempt + 1})")
            random_delay(1.0, 1.5)
        else:
            break
    
    # 3. 触发懒加载内容
    lazy_loaded = detect_and_trigger_lazy_load(page, max_scrolls=3)
    if lazy_loaded > 0:
        print(f"[human_simulator] Triggered {lazy_loaded} lazy load events")
    
    # 4. 滚动回顶部（可选）
    # page.evaluate("window.scrollTo(0, 0)")
    # random_delay(0.5, 1.0)
    
    print("[human_simulator] Page preparation completed")


def human_like_click(page: Page, selector: str, timeout: int = 10000):
    """
    模拟人类点击操作：先移动鼠标，再点击。
    
    :param page: Playwright Page 对象
    :param selector: 元素选择器
    :param timeout: 超时时间
    """
    try:
        element = page.locator(selector).first
        element.wait_for(state="visible", timeout=timeout)
        
        # 获取元素位置
        box = element.bounding_box()
        if box:
            center_x = box['x'] + box['width'] / 2
            center_y = box['y'] + box['height'] / 2
            
            # 随机偏移，不完全点击中心
            offset_x = random.randint(-5, 5)
            offset_y = random.randint(-5, 5)
            
            # 移动鼠标到元素附近
            page.mouse.move(center_x + offset_x, center_y + offset_y)
            random_delay(0.1, 0.3)
            
            # 点击
            page.mouse.click(center_x + offset_x, center_y + offset_y)
            random_delay(0.3, 0.7)
        else:
            # 如果无法获取位置，使用普通点击
            element.click(timeout=timeout)
            random_delay(0.3, 0.7)
    except Exception as e:
        print(f"[human_simulator] Human-like click failed: {e}")
        raise

