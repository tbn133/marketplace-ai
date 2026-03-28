# AI Voice Cover Plugin — Hướng dẫn sử dụng

## Mục lục

- [Tổng quan](#tổng-quan)
- [Yêu cầu hệ thống](#yêu-cầu-hệ-thống)
- [Cài đặt](#cài-đặt)
- [Chuẩn bị voice model](#chuẩn-bị-voice-model)
- [Sử dụng](#sử-dụng)
- [Style System](#style-system)
- [Cấu hình](#cấu-hình)
- [Kiến trúc](#kiến-trúc)
- [Xử lý sự cố](#xử-lý-sự-cố)

---

## Tổng quan

AI Voice Cover Plugin là công cụ tạo AI voice cover từ YouTube URL:

- **Download** audio từ YouTube (yt-dlp)
- **Tách** vocal và instrumental (audio-separator)
- **Chuyển đổi** giọng bằng AI model (RVC)
- **Blend** giọng gốc + giọng AI ở nhiều tỷ lệ khác nhau (FFmpeg)
- **Mix** vocal đã blend với instrumental (FFmpeg)
- **Đánh giá** tự động và chọn bản tốt nhất (rule-based)

Mỗi lần chạy tạo **ít nhất 3 phiên bản** với blend ratio khác nhau, sau đó tự động chọn bản có chất lượng audio tốt nhất.

---

## Yêu cầu hệ thống

### Bắt buộc

| Yêu cầu | Ghi chú |
|---|---|
| **Python 3.10** | Bắt buộc 3.10 (rvc-python phụ thuộc faiss-cpu==1.7.3, chỉ có wheel cho 3.10) |
| FFmpeg | Phải có trên PATH (`brew install ffmpeg` / `apt install ffmpeg`) |
| RVC voice model (.pth) | Ít nhất 1 model trong thư mục models |

### Cài Python 3.10

```bash
# macOS (Homebrew)
brew install python@3.10

# pyenv (cross-platform)
pyenv install 3.10.14

# Ubuntu/Debian
sudo apt install python3.10 python3.10-venv
```

Plugin sẽ **tự động tìm Python 3.10** khi cài đặt (qua `setup-venv.sh`). Thứ tự tìm:
1. `python3.10` trên PATH
2. pyenv (`~/.pyenv/versions/3.10.*/bin/python`)
3. Homebrew (`/opt/homebrew/opt/python@3.10/bin/python3.10`)
4. System (`/usr/bin/python3.10`)

### Tự động cài qua pip (trong Python 3.10 venv)

| Package | Chức năng |
|---|---|
| `yt-dlp` | Download audio từ YouTube |
| `audio-separator` | Tách vocal/instrumental (thay thế UVR) |
| `rvc-python` | Chuyển đổi giọng (RVC inference) |
| `huggingface_hub` | Download models từ HuggingFace |
| `PyYAML` | Đọc style config |

> **GPU**: `rvc-python` cần PyTorch. Nếu dùng GPU, sau khi setup xong, cài thêm:
> ```bash
> # Kích hoạt venv của plugin trước
> source ~/.claude/plugins/data/ai-voice-cover/venv/bin/activate
> pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118
> ```

---

## Cài đặt

### Từ marketplace

```bash
# Thêm marketplace
claude plugin marketplace add github.com/tabi4/code-intelligence-system

# Cài plugin
claude plugin install ai-voice-cover@code-intelligence-system --scope project
```

### Từ local path (development)

```bash
claude plugin install ./plugins/ai-voice-cover --scope project
```

### Cài đặt thủ công (CLI trực tiếp)

```bash
cd plugins/ai-voice-cover

# Tạo venv Python 3.10 tự động
bash setup-venv.sh .

# Hoặc tạo thủ công
python3.10 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### Kiểm tra cài đặt

```bash
# Qua CLI
python cli.py check-tools

# Qua run.sh (dùng venv của plugin)
bash run.sh check-tools
```

Output khi OK:

```
All tools and packages OK.
```

---

## Chuẩn bị voice model

### 1. Set biến môi trường

```bash
export VOICE_COVER_RVC_MODEL_DIR="$HOME/.ai-voice-cover/models"
```

Thêm vào `.bashrc` / `.zshrc` để không phải set lại mỗi lần.

### 2. Download model (tự động)

Dùng lệnh `download-model` để tải từ HuggingFace hoặc URL trực tiếp:

```bash
# Từ HuggingFace repo
bash run.sh download-model --source "https://huggingface.co/user/model-repo" --name "singer_a"

# Từ direct URL
bash run.sh download-model --source "https://example.com/model.pth" --name "singer_b"
```

Hoặc dùng Claude Code skill:

```
/voice:download-model --source https://huggingface.co/user/model-repo --name singer_a
```

### 3. Xem danh sách models đã tải

```bash
bash run.sh list-models
```

Output:

```
Models in /Users/you/.ai-voice-cover/models (2):

  singer_a                   model.pth, model.index
  singer_b                   model.pth
```

### 4. Download thủ công (nếu cần)

Tải file `.pth` và đặt vào thư mục models:

```
~/.ai-voice-cover/models/
├── singer_a.pth                    # standalone file
├── singer_b/                       # hoặc subdirectory
│   ├── model.pth
│   └── model.index
```

### Nguồn tải model

| Nguồn | URL | Ghi chú |
|---|---|---|
| HuggingFace | `https://huggingface.co/` | Hỗ trợ tự động qua `download-model` |
| voice-models.com | `https://voice-models.com/` | Tìm link HuggingFace hoặc download trực tiếp |
| weights.gg | `https://weights.gg/` | Tải .pth rồi dùng URL trực tiếp |

---

## Sử dụng

### Qua Claude Code skill

```
/voice:cover https://youtube.com/watch?v=xxx --voice singer_a --style vietnamese_soft
```

Claude sẽ tự động:
1. Parse arguments
2. Chạy pipeline
3. Báo cáo kết quả (best audio, tất cả versions, style params)

### Qua CLI trực tiếp

```bash
# Tạo cover với style tự động
bash run.sh cover --url "https://youtube.com/watch?v=xxx" --voice "singer_a" --style auto

# Tạo cover với style cụ thể
bash run.sh cover --url "https://youtube.com/watch?v=xxx" --voice "singer_a" --style vietnamese_soft

# Xem danh sách styles
bash run.sh list-styles

# Kiểm tra tools
bash run.sh check-tools
```

### Output format

```json
{
  "best_audio": "/Users/you/.ai-voice-cover/output/cover_20260328_143000/cover_neutral_0.30.wav",
  "versions": [
    "/Users/you/.ai-voice-cover/output/cover_20260328_143000/cover_neutral_0.20.wav",
    "/Users/you/.ai-voice-cover/output/cover_20260328_143000/cover_neutral_0.30.wav",
    "/Users/you/.ai-voice-cover/output/cover_20260328_143000/cover_neutral_0.40.wav"
  ],
  "meta": {
    "style": "neutral",
    "params": {
      "blend_values": [0.2, 0.3, 0.4],
      "pitch_shift": 0,
      "formant_shift": 0.0
    },
    "title": "Song Title",
    "evaluation": "Best loudness match (score=1.23)"
  }
}
```

### Qua Python API

```python
from plugin import run

result = run({
    "url": "https://youtube.com/watch?v=xxx",
    "voice": "singer_a",
    "style": "auto",
})

print(result["best_audio"])    # Path tới file tốt nhất
print(result["versions"])      # Tất cả phiên bản đã tạo
print(result["meta"]["style"]) # Style đã dùng
```

---

## Style System

### Styles có sẵn

| Style | Blend Ratio | Pitch | Formant | Mô tả |
|---|---|---|---|---|
| `vietnamese_soft` | 0.3 | -1 | -0.08 | Giọng Việt nhẹ nhàng |
| `kpop_bright` | 0.25 | 0 | 0.0 | Giọng K-pop sáng |
| `deep_male` | 0.4 | -3 | -0.15 | Giọng nam trầm |
| `female_high` | 0.35 | +4 | +0.1 | Giọng nữ cao |
| `neutral` | 0.3 | 0 | 0.0 | Trung tính, không điều chỉnh pitch |

### Cách hoạt động

- **`style: auto`** → tự động chọn `neutral`
- **`style: <tên>`** → load preset từ `styles.yaml`
- Mỗi style tạo 3 blend variations: `[base - 0.1, base, base + 0.1]`
  - Ví dụ `vietnamese_soft` (base 0.3): tạo bản 0.2, 0.3, 0.4

### Thêm style mới

Sửa file `styles.yaml`:

```yaml
styles:
  my_custom_style:
    blend_ratio: 0.35
    pitch_shift: 2
    formant_shift: 0.05
    description: "My custom style"
```

### Giải thích parameters

| Parameter | Ý nghĩa | Phạm vi |
|---|---|---|
| `blend_ratio` | Tỷ lệ giọng AI trong mix (0 = 100% gốc, 1 = 100% AI) | 0.05 - 0.95 |
| `pitch_shift` | Điều chỉnh pitch (semitones, + = cao hơn, - = trầm hơn) | -12 đến +12 |
| `formant_shift` | Điều chỉnh formant (đặc tính giọng) | -1.0 đến +1.0 |

---

## Cấu hình

Tất cả cấu hình qua biến môi trường:

### Bắt buộc

| Biến | Mô tả |
|---|---|
| `VOICE_COVER_RVC_MODEL_DIR` | Thư mục chứa file `.pth` voice models |

### Tùy chọn

| Biến | Default | Mô tả |
|---|---|---|
| `VOICE_COVER_RVC_DEVICE` | `cpu` | Device cho RVC (`cpu`, `cuda:0`) |
| `VOICE_COVER_RVC_F0_METHOD` | `rmvpe` | Phương pháp trích pitch (`rmvpe`, `harvest`, `crepe`, `pm`) |
| `VOICE_COVER_FFMPEG_PATH` | `ffmpeg` | Path tới FFmpeg |
| `VOICE_COVER_FFPROBE_PATH` | `ffprobe` | Path tới FFprobe |
| `VOICE_COVER_SEPARATOR_MODEL_DIR` | *(auto)* | Thư mục model cho audio-separator |
| `VOICE_COVER_OUTPUT_DIR` | `~/.ai-voice-cover/output` | Thư mục output |
| `VOICE_COVER_TEMP_DIR` | `~/.ai-voice-cover/tmp` | Thư mục tạm |
| `VOICE_COVER_KEEP_TEMP` | `false` | Giữ file tạm sau khi chạy xong (`true`/`false`) |
| `VOICE_COVER_LOG_LEVEL` | `INFO` | Log level |

### Ví dụ cấu hình đầy đủ

```bash
# Bắt buộc
export VOICE_COVER_RVC_MODEL_DIR="$HOME/.ai-voice-cover/models"

# GPU acceleration
export VOICE_COVER_RVC_DEVICE="cuda:0"

# Pitch extraction method (rmvpe cho chất lượng tốt nhất)
export VOICE_COVER_RVC_F0_METHOD="rmvpe"

# Custom output directory
export VOICE_COVER_OUTPUT_DIR="$HOME/Music/covers"

# Giữ file tạm để debug
export VOICE_COVER_KEEP_TEMP="true"
```

---

## Kiến trúc

### Pipeline flow

```
YouTube URL
    │
    ▼
┌─────────────┐
│  download    │  yt-dlp Python API
│  (yt_dlp)    │  → audio.wav
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  separate    │  audio-separator Python API
│              │  → vocal.wav + instrumental.wav
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  convert     │  rvc-python Python API
│  (RVC)       │  → ai_vocal.wav
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│  blend × 3                          │  FFmpeg
│  ratio=0.2 → blended_0.20.wav      │
│  ratio=0.3 → blended_0.30.wav      │
│  ratio=0.4 → blended_0.40.wav      │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│  mix × 3                            │  FFmpeg
│  blended + instrumental → final     │
│  → cover_style_0.20.wav            │
│  → cover_style_0.30.wav            │
│  → cover_style_0.40.wav            │
└──────┬──────────────────────────────┘
       │
       ▼
┌─────────────┐
│  evaluator   │  ffprobe analysis
│              │  → chọn bản tốt nhất
└─────────────┘
```

### Module structure

```
plugin.py          run(input) → dict         Entry point
    ├── planner.py     plan() → PlanResult       Chọn style + params
    ├── executor.py    execute() → ExecutionResult    Chạy pipeline
    │   ├── steps/download.py    yt-dlp API
    │   ├── steps/separate.py    audio-separator API
    │   ├── steps/convert.py     rvc-python API
    │   ├── steps/blend.py       FFmpeg subprocess
    │   └── steps/mix.py         FFmpeg subprocess
    └── evaluator.py   evaluate() → EvaluationResult  Chọn best
```

### Evaluator rules

1. **Reject** nếu peak > -0.5 dBFS (clipping)
2. **Reject** nếu mean volume < -30 dBFS (quá nhỏ) hoặc > -5 dBFS (quá to)
3. **Chọn** bản gần -14 dBFS nhất (broadcast standard)
4. Nếu tất cả bị reject → chọn bản ít tệ nhất kèm warning

---

## Xử lý sự cố

### "Python 3.10 is required but not found"

Plugin cần Python 3.10 (do rvc-python phụ thuộc faiss-cpu==1.7.3). Cài đặt:

```bash
# macOS
brew install python@3.10

# pyenv
pyenv install 3.10.14

# Ubuntu
sudo apt install python3.10 python3.10-venv
```

Sau đó chạy lại setup:

```bash
bash setup-venv.sh .
```

### "faiss-cpu" / "rvc-python" conflict

Nếu gặp lỗi dependency conflict khi cài, nguyên nhân là Python không phải 3.10. Kiểm tra:

```bash
# Xem Python version trong venv
.venv/bin/python --version
# Phải là Python 3.10.x
```

Nếu sai version, xóa venv và tạo lại:

```bash
rm -rf .venv
bash setup-venv.sh .
```

### "FFmpeg not found"

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Kiểm tra
ffmpeg -version
```

### "RVC model directory not set"

```bash
export VOICE_COVER_RVC_MODEL_DIR="$HOME/.ai-voice-cover/models"
```

### "Voice model 'xxx' not found"

Kiểm tra file model tồn tại:

```bash
ls $VOICE_COVER_RVC_MODEL_DIR
# Phải có file: xxx.pth hoặc xxx/
```

### "Python package 'xxx' not installed"

```bash
# Cài lại dependencies
cd plugins/ai-voice-cover
pip install -r requirements.txt
```

### GPU không nhận

```bash
# Kiểm tra PyTorch có CUDA
python -c "import torch; print(torch.cuda.is_available())"

# Nếu False, cài lại PyTorch với CUDA
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118

# Set device
export VOICE_COVER_RVC_DEVICE="cuda:0"
```

### Download YouTube bị lỗi

```bash
# Cập nhật yt-dlp (YouTube thường thay đổi API)
pip install -U yt-dlp
```

### Muốn giữ file tạm để debug

```bash
export VOICE_COVER_KEEP_TEMP="true"
# File tạm sẽ ở: ~/.ai-voice-cover/tmp/run_YYYYMMDD_HHMMSS/
```

### Output tất cả bị reject bởi evaluator

Evaluator vẫn chọn bản tốt nhất nhưng kèm warning. Nguyên nhân thường gặp:
- Audio gốc chất lượng thấp
- Voice model không phù hợp với bài hát
- Thử style khác hoặc điều chỉnh `blend_ratio` trong `styles.yaml`
