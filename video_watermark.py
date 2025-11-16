#!/usr/bin/env python3
"""
Накладывает повернутый/масштабированный вотермарк на все видео в папке,
приводя видео к соотношению 9:16 (добавляя чёрные полосы сверху/снизу при необходимости).

Требования:
- ffmpeg и ffprobe в PATH
- Pillow: pip install pillow
"""

import os
import math
import random
import subprocess
import tempfile
import shutil
from PIL import Image
from tqdm import tqdm

# ====== Параметры (из твоего задания) ======
videos_folder = "videos"
output_folder = "output"
watermark_path = "watermark/white.jpg"

# Параметры водяного знака / позиционирования
WM_REL_WIDTH = 0.25        # ширина водяного знака относительно ширины видео
WM_OPACITY = 0.1           # непрозрачность (0..1) — реализовано через альфу в Pillow
ROTATE_DEG_RANGE = 8       # случайный поворот в градусах ±
SCALE_VARIATION = 0.15     # ±15% случайного изменения размера
MARGIN_X = 0.05            # отступ от края по ширине (5%)
MARGIN_Y = 0.5             # отступ от низа по высоте (5%)

# Создаём папку вывода
os.makedirs(output_folder, exist_ok=True)

# ====== Утилиты для ffprobe/ffmpeg ======
def probe_size(path):
    """Возвращает (width, height) видео с помощью ffprobe. Бросает Exception при ошибке."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=p=0:s=x",
        path
    ]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0 or not out.stdout.strip():
        raise RuntimeError(f"ffprobe failed for {path}: {out.stderr.strip()}")
    w_h = out.stdout.strip().split("x")
    return int(w_h[0]), int(w_h[1])

def run_ffmpeg(cmd_args):
    """Запускает ffmpeg (список аргументов), печатает stderr при ошибке."""
    proc = subprocess.run(cmd_args, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\ncmd: {' '.join(cmd_args)}\nstdout: {proc.stdout}\nstderr: {proc.stderr}")

# ====== Основная обработка одного видео ======
def process_one_video(input_path, output_path):
    print(f"Processing: {os.path.basename(input_path)}")
    try:
        vw, vh = probe_size(input_path)
    except Exception as e:
        print("  Ошибка чтения размеров видео:", e)
        return

    # Целевая высота для соотношения 9:16, при той же ширине
    target_h = int(math.ceil(vw * 16 / 9))

    # нужно ли добавлять полосы сверху/снизу?
    need_pad = vh < target_h
    pad_top = pad_bottom = 0
    if need_pad:
        # равномерно сверху и снизу
        extra = target_h - vh
        pad_top = extra // 2
        pad_bottom = extra - pad_top

    # Подготовим временный повернутый/масштабированный вотермарк через Pillow
    with tempfile.TemporaryDirectory() as td:
        tmp_wm = os.path.join(td, "wm_processed.png")

        # Загружаем оригинал
        pil = Image.open(watermark_path).convert("RGBA")

        # Вычисляем целевую ширину в пикселях и применяем вариацию
        variation = 1.0 + random.uniform(-SCALE_VARIATION, SCALE_VARIATION)
        target_wm_w = max(8, int(vw * WM_REL_WIDTH * variation))

        # Масштабируем по ширине, сохраняя аспект
        w0, h0 = pil.size
        target_w = target_wm_w
        target_h_wm = max(1, int(h0 * (target_w / w0)))
        pil = pil.resize((target_w, target_h_wm), resample=Image.LANCZOS)

        # Меняем альфу (умножаем на WM_OPACITY)
        if WM_OPACITY < 1.0:
            alpha = pil.split()[3]
            alpha = alpha.point(lambda p: int(p * WM_OPACITY))
            pil.putalpha(alpha)

        # Поворот с expand=True и прозрачным фоном
        angle = random.uniform(-ROTATE_DEG_RANGE, ROTATE_DEG_RANGE)
        pil = pil.rotate(angle, expand=True, resample=Image.BICUBIC, fillcolor=(0, 0, 0, 0))

        # Сохраняем временный PNG с альфой
        pil.save(tmp_wm, format="PNG")

        # Размер итоговой вотермарки (после вращения)
        wm_w, wm_h = pil.size

        # Позиция: левый или правый нижний угол, с отступами
        corner = random.choice(["left", "right"])
        if corner == "left":
            pos_x = int(vw * MARGIN_X)
        else:
            pos_x = int(vw - wm_w - vw * MARGIN_X)
        # Позиция по Y на основе итоговой высоты (если был пад — высота = target_h)
        dest_h = target_h if need_pad else vh
        pos_y = int(dest_h - wm_h - dest_h * MARGIN_Y)
        if pos_y < 0:
            pos_y = 0

        # ====== Формируем filter_complex и запускаем ffmpeg ======
        # Отметка выходного видео как [vout], потом замапим аудио из входа (если есть)
        if need_pad:
            # Сначала сделаем pad, затем overlay
            # pad syntax: pad=width:height:x:y:color
            pad_y = pad_top
            filter_complex = (
                f"[0:v]pad={vw}:{target_h}:0:{pad_y}:color=black[bg];"
                f"[1:v]format=rgba[wm];"
                f"[bg][wm]overlay={pos_x}:{pos_y}:format=auto[vout]"
            )
        else:
            # Без паддинга — просто overlay
            filter_complex = (
                f"[0:v]format=rgba[bg];"
                f"[1:v]format=rgba[wm];"
                f"[bg][wm]overlay={pos_x}:{pos_y}:format=auto[vout]"
            )

        # Собираем команду
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-i", tmp_wm,
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "0:a?",            # попытаться взять аудио, если есть
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            output_path
        ]

        try:
            run_ffmpeg(cmd)
        except Exception as e:
            print("  Ошибка ffmpeg:", e)
            # Для отладки можно распечатать команду (раскомментируй)
            # print("FFMPEG CMD:", " ".join(cmd))
            return

    print("  Done ->", os.path.basename(output_path))


# ====== Поиск видеофайлов в папке ======
def is_video_file(fn):
    ext = os.path.splitext(fn)[1].lower()
    return ext in [".mp4", ".mov", ".mkv", ".avi", ".webm", ".mpeg", ".mpg", ".flv"]

def main():
    files = [f for f in sorted(os.listdir(videos_folder)) if is_video_file(f)]
    if not files:
        print("Не найдено видео в папке", videos_folder)
        return

    for fname in tqdm(files):
        in_path = os.path.join(videos_folder, fname)
        out_fname = os.path.splitext(fname)[0] + "_wm.mp4"
        out_path = os.path.join(output_folder, out_fname)
        try:
            process_one_video(in_path, out_path)
        except Exception as e:
            print(f"Error processing {fname}:", e)

if __name__ == "__main__":
    main()
