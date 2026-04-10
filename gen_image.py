"""
gen_image.py — 通用图片生成工具
调用 Nano Banana (gemini-3-pro-image) 生成配图

两种风格：
  - "long"  长文内嵌图：16:9，白底或透明，简洁信息图风格
  - "short" 短文封面图：3:4，黑板手绘风格（账号视觉统一）
"""

import requests
import base64
import os

API_URL = "https://llm.baijia.com/v1/chat/completions"
API_KEY = "sk-NQob-VPolCt629g-VHkzvA"

# ── 短文风格：黑板手绘（3:4）──────────────────────────────────────────────────
_BLACKBOARD_BASE = (
    "一张黑板手绘风格的科普信息图。深色黑板背景，具有真实的粉笔笔触和粉笔灰质感。"
    "画面的最底部是木制的黑板槽，没有边框，不要绘制边框，上面放着一块旧黑板擦和几根彩色的粉笔"
    "（粉色、绿色、黄色、蓝色）。图片的比例是 3:4。\n"
    "画面主体：{content}"
)

# ── 长文风格：简洁信息图（16:9）─────────────────────────────────────────────
_INFOGRAPHIC_BASE_WHITE = (
    "一张简洁现代的科普信息图，用于文章内嵌配图。纯白色背景，无任何装饰边框。"
    "使用清晰的线条、几何图形和色块进行信息可视化，配色方案以蓝色、绿色、橙色为主，搭配灰色辅助色。"
    "图形风格扁平化（flat design），文字排版清晰易读，整体专业、现代、克制。"
    "图片比例是 16:9。\n"
    "图表内容：{content}"
)

_INFOGRAPHIC_BASE_TRANSPARENT = (
    "一张简洁现代的科普信息图，用于文章内嵌配图。透明背景（无背景色），无任何装饰边框。"
    "使用清晰的线条、几何图形和色块进行信息可视化，配色方案以蓝色、绿色、橙色为主，搭配灰色辅助色。"
    "图形风格扁平化（flat design），文字排版清晰易读，整体专业、现代、克制。"
    "图片比例是 16:9。\n"
    "图表内容：{content}"
)


def generate_image(
    prompt: str,
    output_path: str,
    style: str = "long",
    background: str = "white",
) -> bool:
    """
    生成图片并保存到本地。

    Args:
        prompt:      图片内容描述（只需描述要画什么，底板样式自动套用）
        output_path: 保存路径，例如 "035_images/cover.png"
        style:       "long"  → 16:9 简洁信息图（内文嵌入用）
                     "short" → 3:4  黑板手绘（短文封面用）
        background:  "white" | "transparent"（仅 long 风格生效）

    Returns:
        True 表示成功，False 表示失败
    """
    if style == "short":
        full_prompt = _BLACKBOARD_BASE.format(content=prompt)
    else:
        base = _INFOGRAPHIC_BASE_WHITE if background == "white" else _INFOGRAPHIC_BASE_TRANSPARENT
        full_prompt = base.format(content=prompt)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }
    payload = {
        "model": "gemini-3-pro-image",
        "messages": [{"role": "user", "content": full_prompt}],
    }

    import time
    for attempt in range(1, 4):
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=120)
            response.raise_for_status()
            result = response.json()
            image_b64 = result["choices"][0]["message"]["images"][0]["image_url"]["url"]
            return _save_image(image_b64, output_path)

        except (KeyError, IndexError):
            print("❌ 响应结构异常，未找到图片字段，请检查 API 返回。")
            return False
        except requests.RequestException as e:
            if attempt < 3:
                print(f"  ⚠️ 第{attempt}次失败，5秒后重试: {e}")
                time.sleep(5)
            else:
                print(f"❌ 请求失败（已重试3次）: {e}")
                return False


def _save_image(base64_str: str, output_path: str) -> bool:
    """将 base64 字符串解码并保存为图片文件。"""
    try:
        if "," in base64_str:
            base64_str = base64_str.split(",")[-1]

        img_data = base64.b64decode(base64_str)

        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        with open(output_path, "wb") as f:
            f.write(img_data)

        print(f"✅ 图片已保存: {output_path}")
        return True

    except Exception as e:
        print(f"❌ 保存失败: {e}")
        return False


if __name__ == "__main__":
    # 长文内嵌图示例（白底，16:9）
    generate_image(
        prompt="左右对比图：左侧标注传统大模型全部1000个参数同时激活，右侧标注DeepSeek MoE只激活370亿/6710亿，中间用箭头指向省钱比例94%。",
        output_path="test_long_white.png",
        style="long",
        background="white",
    )

    # 短文封面图示例（黑板，3:4）
    generate_image(
        prompt="黑板正中央黄色粉笔写大字 MoE 混合专家模型，下方白色粉笔画三个小圆圈代表被激活的专家，整体构图留上方空白。",
        output_path="test_short_blackboard.png",
        style="short",
    )
