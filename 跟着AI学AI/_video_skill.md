# 口播视频制作 Skill

## 概览

将图文文章转化为口播视频的完整流程，产出带字幕的 1080p MP4。

```
文章 → 口播脚本 → 素材生成 → 录音 → 合成视频 → 字幕
```

---

## 依赖安装

```bash
pip3 install moviepy pillow openai-whisper opencc-python-reimplemented
```

- **moviepy** — 视频合成
- **pillow** — 图片处理 / 字幕渲染
- **openai-whisper** — 语音转字幕（首次运行下载 ~150MB base 模型）
- **opencc-python-reimplemented** — 繁体转简体

---

## 完整流程

### Step 1：写口播脚本

在文章目录创建 `NNN_video_script.md`，格式：

```markdown
## [0:00-0:20] 开场（20s）
[动图] gif_price.gif
2023年，调用 GPT-4 的 API，每处理100万个Token，要花 60 美元……

## [0:20-0:40] 第二段（20s）
[静图] s1_not_discount.png
你可能觉得……
```

同时导出纯旁白文本 `NNN_video/narration.txt`（无 Markdown，供录音参考）。

**分段建议：**
- 每段 15-40s，与一个核心画面对应
- 动图（GIF）用于展示变化过程；静图用于稳定讲解
- 总时长控制在 3-4 分钟

---

### Step 2：生成素材

**静图**（16:9 白底信息图）：
```python
from gen_image import generate_image
generate_image(prompt, 'NNN_video/s1_xxx.png', style='long', background='white')
```

**动图**（多帧 PNG → GIF）：
```python
from PIL import Image
frames = [Image.open(p).convert('RGB') for p in frame_paths]
frames[0].save('gif_xxx.gif', save_all=True, append_images=frames[1:],
               loop=0, duration=900)   # duration 单位毫秒/帧
```

---

### Step 3：录音（TTS 自动生成）

用 `tts.py` 调用 MiniMax speech-2.8-turbo 自动生成 MP3：

```bash
# 从 narration.txt 生成录音
python3 tts.py NNN_video/narration.txt NNN_video/narration.mp3

# 指定音色和语速
python3 tts.py NNN_video/narration.txt NNN_video/narration.mp3 male-qn-jingying 1.0
```

**可选音色：**
- `male-qn-jingying`（精英青年，默认，科普内容推荐）
- `male-qn-qingse`（清涩青年，偏年轻）
- `Chinese (Mandarin)_Gentle_Youth`（温润青年，柔和）

脚本位置：`tts.py`（项目根目录）。文本超过 5000 字时自动分段合并（需 ffmpeg）。

---

### Step 4：合成视频 `make_video.py`

**关键参数：**

```python
SEGMENTS = [
    # (素材文件, 实际开始秒, 实际结束秒)
    # 时间戳来自 Whisper 转录，不是脚本估算
    ('gif_price.gif',      0.0,  13.4),
    ('s1_xxx.png',        13.4,  25.9),
    ...
]
FADE = 0.4   # 段落间淡入淡出时长（秒）
```

**GIF 处理策略：**

| 场景 | 策略 |
|------|------|
| 开场/重点动画（帧少、需要慢看） | 幻灯片模式：每帧等时展示 |
| 过程演示动画（帧多、节奏快） | 播放2遍后定格最后一帧 |

```python
# 幻灯片模式（开场 gif 推荐）
def gif_to_slideshow(gif_path, duration):
    pil = PILImage.open(gif_path)
    frames = []
    try:
        while True:
            frames.append(np.array(pil.copy().convert('RGB')))
            pil.seek(pil.tell() + 1)
    except EOFError:
        pass
    frame_dur = duration / len(frames)
    return concatenate_videoclips([ImageClip(f).with_duration(frame_dur) for f in frames])

# 播放2遍后定格（其他 gif）
play_dur = raw.duration * 2
last_frame = raw.get_frame(raw.duration - 0.05)
freeze = ImageClip(last_frame).with_duration(duration - play_dur)
clip = concatenate_videoclips([raw, raw, freeze])
```

**淡入淡出：**
```python
from moviepy import vfx
clip = clip.with_effects([vfx.FadeIn(FADE), vfx.FadeOut(FADE)])
```

**视频封面（标题卡）：**

在内容开始前加 3s 白底黑字封面，用 PIL 直接生成，不调图片 API。

```python
from PIL import ImageFont, ImageDraw, Image
import numpy as np
from moviepy import AudioArrayClip, concatenate_audioclips

COVER_DUR = 3.0   # 封面时长（秒），add_subtitles.py 中保持一致

def make_cover_image(title, subtitle, W=1920, H=1080):
    img = Image.new('RGB', (W, H), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    font_t = ImageFont.truetype('/System/Library/Fonts/STHeiti Medium.ttc', 110)
    font_s = ImageFont.truetype('/System/Library/Fonts/STHeiti Medium.ttc', 52)
    bbox = draw.textbbox((0, 0), title, font=font_t)
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    tx, ty = (W-tw)//2, H//2 - th - 30
    draw.text((tx, ty), title, font=font_t, fill=(20, 20, 20))
    bbox2 = draw.textbbox((0, 0), subtitle, font=font_s)
    sw = bbox2[2]-bbox2[0]
    draw.text(((W-sw)//2, ty+th+40), subtitle, font=font_s, fill=(140, 140, 140))
    return np.array(img)

cover_clip = ImageClip(make_cover_image(TITLE, SUBTITLE)).with_duration(COVER_DUR)

# 封面期间音频补静音
fps_a = 44100
silence = AudioArrayClip(np.zeros((int(COVER_DUR*fps_a), 2), dtype=np.float32), fps=fps_a)
full_audio = concatenate_audioclips([silence, audio])

# 合并：封面 + 内容片段
video = concatenate_videoclips([cover_clip] + faded, method='compose')
video = video.with_audio(full_audio)
```

> **注意**：`add_subtitles.py` 中的 `COVER_DUR` 必须与 `make_video.py` 一致，字幕时间戳需 `+COVER_DUR` 偏移。

输出：`NNN_output.mp4`（1920×1080）

---

### Step 5：字幕 `add_subtitles.py`

**Whisper 转录：**
```python
import whisper
model = whisper.load_model('base')   # 中文够用；精度要求高用 medium
result = model.transcribe(AUDIO, language='zh')
# 结果缓存到 NNN_transcript.json，避免重复跑
```

**繁转简：**
```python
import opencc
t2s = opencc.OpenCC('t2s')
for s in segments:
    s['text'] = t2s.convert(s['text'])
```

**字幕渲染（PIL，避免中文乱码）：**
```python
font = ImageFont.truetype('/System/Library/Fonts/STHeiti Medium.ttc', 46)
```

**画布布局：**
- 原视频 1920×1080 放顶部
- 底部扩展 160px 深色字幕区
- 输出 1920×1240

```python
COVER_DUR = 3.0   # 与 make_video.py 保持一致
BAR_H = 160
bar_bg = ColorClip((W, BAR_H), color=(20, 20, 20)).with_position((0, H))

# 字幕时间戳偏移封面时长
sub_clip = ImageClip(sub_arr).with_start(start + COVER_DUR).with_duration(dur)

final = CompositeVideoClip([video, bar_bg] + subtitle_clips, size=(W, H + BAR_H))
```

---

### Step 6：手动校对字幕

Whisper base 常见错误类型：
- "生成" → 识别为"声称"
- "KV Cache" → "KVCatch"
- "投机采样" → "头机彩样"
- "草稿" → "曹稿"
- 专有名词（ChatGPT、API）易出错

**校对流程：**
1. 运行脚本打印全部字幕时间戳
2. 对比原文逐条检查
3. 直接修改 `NNN_transcript.json` 对应条目
4. 重新运行 `add_subtitles.py`（无需重跑 Whisper）

---

## 时间戳对齐注意事项

> **核心原则：用 Whisper 转录确定实际时间点，不要用脚本估算时间线性缩放。**

录音节奏不均匀（前慢后快），线性缩放会导致后段画面滞后 10-15s。
正确做法：先跑一遍 Whisper，找每个话题的实际开始秒数，填入 `SEGMENTS`。

---

## 脚本文件位置

```
/tmp/make_video.py       # 视频合成
/tmp/add_subtitles.py    # 字幕烧录
```

复用时修改：
- `os.chdir(...)` 路径
- `AUDIO` / `VIDEO` / `OUTPUT` 文件名
- `SEGMENTS` 时间段

---

## 产出文件

| 文件 | 说明 |
|------|------|
| `NNN_output.mp4` | 无字幕版，1920×1080 |
| `NNN_subtitled.mp4` | 有字幕版，1920×1240 |
| `NNN_transcript.json` | Whisper 转录缓存，可手动编辑 |
