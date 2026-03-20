import os
import sys
import asyncio
import logging
import uuid
import shutil
import threading
import re
from pathlib import Path

from keep_alive import keep_alive
from flask import Flask
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import anthropic

BOT_TOKEN = "8788961014:AAFXDB9bNxLJv6NtokMW01BbHi4yBV-weis"
CLAUDE_API_KEY = os.getenv(“CLAUDE_API_KEY”, “”)
CHANNEL_ID = os.getenv(“CHANNEL_ID”, “YOUR_CHANNEL_ID”)
OWNER_ID = int(os.getenv(“OWNER_ID”, “0”))
BOT_FILE = Path(**file**).resolve()
DOWNLOADS_DIR = Path(“downloads”)
OUTPUT_DIR = Path(“output”)
DOWNLOADS_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(**name**)

app_flask = Flask(**name**)

@app_flask.route(’/’)
def home():
return ‘Bot is running!’

@app_flask.route(’/health’)
def health():
return ‘OK’, 200

def run_flask():
port = int(os.environ.get(“PORT”, 8000))
app_flask.run(host=‘0.0.0.0’, port=port)

class EditStates(StatesGroup):
waiting_url = State()
waiting_music_url = State()
choosing_duration = State()
choosing_content_type = State()
choosing_moment = State()
choosing_transitions = State()
choosing_speed = State()
choosing_ratio = State()
processing = State()

class AIStates(StatesGroup):
waiting_description = State()

user_sessions: dict[int, dict] = {}
ai_conversations: dict[int, list] = {}

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

def kb(*buttons_rows):
keyboard = []
for row in buttons_rows:
keyboard.append([InlineKeyboardButton(text=btn[0], callback_data=btn[1]) for btn in row])
return InlineKeyboardMarkup(inline_keyboard=keyboard)

def is_owner(user_id: int) -> bool:
if OWNER_ID == 0:
return True
return user_id == OWNER_ID

def get_claude_client():
if CLAUDE_API_KEY:
return anthropic.Anthropic(api_key=CLAUDE_API_KEY)
return None

CLAUDE_SYSTEM_PROMPT = “”“Ты — профессиональный видеомонтажёр и режиссёр, специализирующийся на:

- TikTok и Reels эдитах (быстрый динамичный монтаж)
- Спортивных хайлайтах и клипах
- Музыкальных эдитах под бит
- Cinematic роликах

Ты помогаешь пользователю создать видео. Когда пользователь описывает что хочет — ты:

1. Уточняешь детали если нужно (ссылка на видео, музыка, стиль)
1. Определяешь параметры монтажа:
- duration: длина в секундах (15/30/60/90)
- content_type: “edit” (быстрый) или “reels” (плавный) или “cinematic”
- moment: “start”/“middle”/“end”/“best”
- transitions: true/false
- speed: “slow”/“medium”/“fast”/“vfast”
- ratio: “9:16”/“16:9”/“1:1”
- style: описание стиля монтажа

Когда у тебя есть ВСЯ нужная информация (ссылка на видео обязательна),
верни JSON в конце ответа в таком формате:
<PARAMS>
{
“ready”: true,
“video_url”: “https://youtube.com/…”,
“duration”: 30,
“content_type”: “edit”,
“moment”: “best”,
“transitions”: true,
“speed”: “fast”,
“ratio”: “9:16”,
“style”: “dynamic sport edit”
}
</PARAMS>

Общайся дружелюбно, как настоящий профессиональный монтажёр.
Если нет ссылки на видео — обязательно попроси её.
Отвечай на языке пользователя.”””

async def ask_claude(user_id: int, user_message: str) -> tuple[str, dict | None]:
client = get_claude_client()
if not client:
return “❌ Claude AI не настроен. Добавьте CLAUDE_API_KEY в переменные Railway.”, None

```
if user_id not in ai_conversations:
    ai_conversations[user_id] = []

ai_conversations[user_id].append({
    "role": "user",
    "content": user_message
})

if len(ai_conversations[user_id]) > 20:
    ai_conversations[user_id] = ai_conversations[user_id][-20:]

loop = asyncio.get_event_loop()
response = await loop.run_in_executor(
    None,
    lambda: client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        system=CLAUDE_SYSTEM_PROMPT,
        messages=ai_conversations[user_id]
    )
)

reply = response.content[0].text
ai_conversations[user_id].append({
    "role": "assistant",
    "content": reply
})

params = None
if "<PARAMS>" in reply and "</PARAMS>" in reply:
    try:
        import json
        params_str = reply.split("<PARAMS>")[1].split("</PARAMS>")[0].strip()
        params = json.loads(params_str)
        reply = reply.split("<PARAMS>")[0].strip()
    except Exception as e:
        logger.error(f"Params parse error: {e}")

return reply, params
```

@dp.message(Command(“start”))
async def cmd_start(message: Message):
claude_status = “✅ Claude AI агент активен” if CLAUDE_API_KEY else “⚠️ Claude AI не настроен (нужен CLAUDE_API_KEY)”
await message.answer(
“👋 Привет! Я профессиональный монтажёр видео с AI.\n\n”
“🎬 Создаю эдиты, Reels, TikTok ролики из YouTube видео.\n\n”
f”🧠 {claude_status}\n\n”
“📋 Команды:\n”
“/ai — описать что хочешь, Claude сделает сам\n”
“/edit — создать видео через кнопки\n”
“/setmusic — установить фоновую музыку\n”
“/help — помощь\n\n”
“💡 Просто напиши /ai и опиши что хочешь!”
)

@dp.message(Command(“help”))
async def cmd_help(message: Message):
await message.answer(
“🎬 <b>Как пользоваться ботом</b>\n\n”
“🤖 <b>/ai</b> — умный режим с Claude\n”
“   Опишите что хотите словами:\n”
“   ‘Сделай эдит Роналдо 30 секунд под музыку’\n”
“   Claude сам спросит ссылку и настроит всё\n\n”
“🎬 <b>/edit</b> — ручной режим через кнопки\n\n”
“🎵 <b>/setmusic</b> — фоновая музыка (YouTube)\n\n”
“📐 <b>Форматы:</b>\n”
“   • 9:16 — TikTok / Reels\n”
“   • 16:9 — YouTube\n”
“   • 1:1 — Instagram квадрат\n\n”
“⚡ Монтаж через ffmpeg — 100% бесплатно!”,
parse_mode=“HTML”
)

@dp.message(Command(“ai”))
async def cmd_ai(message: Message, state: FSMContext):
await state.clear()
user_id = message.from_user.id
ai_conversations.pop(user_id, None)

```
args = message.text.strip().split(maxsplit=1)

if not CLAUDE_API_KEY:
    await message.answer(
        "❌ <b>Claude AI не настроен</b>\n\n"
        "Добавьте переменную <code>CLAUDE_API_KEY</code> в Railway:\n"
        "Settings → Variables → Add Variable\n\n"
        "Получить ключ: console.anthropic.com",
        parse_mode="HTML"
    )
    return

await state.set_state(AIStates.waiting_description)

if len(args) > 1 and args[1].strip():
    await process_ai_message(message, state, args[1].strip())
else:
    await message.answer(
        "🎬 <b>Claude AI Монтажёр</b>\n\n"
        "Опишите что хотите создать:\n\n"
        "Примеры:\n"
        "• <i>Сделай эдит Роналдо 30 секунд для TikTok</i>\n"
        "• <i>Хочу cinematic клип 60 секунд в формате 9:16</i>\n"
        "• <i>Нарежь лучшие моменты: [ссылка]</i>\n\n"
        "Отправьте ваш запрос:",
        parse_mode="HTML"
    )
```

@dp.message(AIStates.waiting_description)
async def handle_ai_message(message: Message, state: FSMContext):
await process_ai_message(message, state, message.text.strip())

async def process_ai_message(message: Message, state: FSMContext, text: str):
user_id = message.from_user.id
thinking_msg = await message.answer(“🧠 Claude думает…”)

```
try:
    reply, params = await ask_claude(user_id, text)
    await thinking_msg.delete()

    if params and params.get("ready") and params.get("video_url"):
        confirm_text = (
            f"✅ <b>Claude готов к монтажу!</b>\n\n"
            f"{reply}\n\n"
            f"📋 <b>Параметры:</b>\n"
            f"⏱ Длина: {params.get('duration', 30)} сек\n"
            f"🎭 Тип: {params.get('content_type', 'edit')}\n"
            f"📐 Формат: {params.get('ratio', '9:16')}\n"
            f"⚡ Скорость: {params.get('speed', 'fast')}\n"
            f"✨ Переходы: {'Да' if params.get('transitions') else 'Нет'}"
        )
        confirm_kb = kb(
            [("🎬 Начать монтаж!", "ai_start_edit")],
            [("✏️ Изменить параметры", "ai_change_params")],
            [("❌ Отмена", "ai_cancel_edit")]
        )
        await state.update_data(ai_params=params)
        await message.answer(confirm_text, reply_markup=confirm_kb, parse_mode="HTML")
    else:
        await message.answer(
            f"🎬 <b>Claude:</b>\n\n{reply}",
            parse_mode="HTML"
        )
except Exception as e:
    logger.error(f"Claude AI error: {e}")
    await thinking_msg.delete()
    await state.clear()
    await message.answer(
        f"❌ Ошибка Claude AI:\n{str(e)[:200]}\n\n"
        "Попробуйте /ai снова или используйте /edit"
    )
```

@dp.callback_query(F.data == “ai_start_edit”)
async def ai_start_edit(callback: CallbackQuery, state: FSMContext):
data = await state.get_data()
params = data.get(“ai_params”, {})
await state.clear()
await callback.message.edit_text(
“⏳ <b>Начинаю монтаж по указаниям Claude…</b>\n\nЭто займёт 2-5 минут 🎬”,
parse_mode=“HTML”
)
asyncio.create_task(
process_video(callback.from_user.id, callback.message.chat.id, params, bot)
)
await callback.answer()

@dp.callback_query(F.data == “ai_change_params”)
async def ai_change_params(callback: CallbackQuery, state: FSMContext):
await callback.message.edit_text(
“✏️ Опишите что изменить:\n”
“Например: ‘сделай длиннее, 60 секунд’ или ‘формат 16:9’”
)
await callback.answer()

@dp.callback_query(F.data == “ai_cancel_edit”)
async def ai_cancel_edit(callback: CallbackQuery, state: FSMContext):
await state.clear()
ai_conversations.pop(callback.from_user.id, None)
await callback.message.edit_text(“❌ Отменено. Напишите /ai чтобы начать заново.”)
await callback.answer()

@dp.message(Command(“setmusic”))
async def cmd_setmusic(message: Message, state: FSMContext):
await state.set_state(EditStates.waiting_music_url)
await message.answer(
“🎵 Отправьте ссылку на YouTube для музыки:\n”
“Например: https://www.youtube.com/watch?v=…\n\n”
“Музыка будет добавляться ко всем видео.”
)

@dp.message(EditStates.waiting_music_url)
async def process_music_url(message: Message, state: FSMContext):
user_id = message.from_user.id
url = message.text.strip()
if “youtube.com” not in url and “youtu.be” not in url:
await message.answer(“❌ Это не YouTube ссылка.”)
return
await message.answer(“⏳ Скачиваю музыку…”)
music_path = DOWNLOADS_DIR / f”music_{user_id}.mp3”
try:
cmd = [
“yt-dlp”, “-x”, “–audio-format”, “mp3”,
“-o”, str(music_path.with_suffix(””)),
“–no-playlist”, url
]
proc = await asyncio.create_subprocess_exec(
*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
)
_, stderr = await proc.communicate()
if proc.returncode != 0:
raise Exception(stderr.decode())
user_sessions.setdefault(user_id, {})[“music_path”] = str(music_path)
await state.clear()
await message.answer(“✅ Музыка сохранена! Используйте /ai или /edit для создания видео.”)
except Exception as e:
logger.error(f”Music download error: {e}”)
await state.clear()
await message.answer(“❌ Не удалось скачать музыку. Проверьте ссылку.”)

@dp.message(Command(“edit”))
async def cmd_edit(message: Message, state: FSMContext):
await state.set_state(EditStates.waiting_url)
await message.answer(
“🎬 <b>Создание видео (ручной режим)</b>\n\n”
“💡 Совет: попробуйте /ai для умного режима с Claude!\n\n”
“Шаг 1/7: Отправьте ссылку на YouTube видео:”,
parse_mode=“HTML”
)

@dp.message(EditStates.waiting_url)
async def process_video_url(message: Message, state: FSMContext):
url = message.text.strip()
if “youtube.com” not in url and “youtu.be” not in url:
await message.answer(“❌ Это не YouTube ссылка.”)
return
await state.update_data(video_url=url)
await state.set_state(EditStates.choosing_duration)
await message.answer(
“✅ Ссылка принята!\n\nШаг 2/7: <b>Длина видео:</b>”,
reply_markup=kb(
[(“⏱ 15 сек”, “dur_15”), (“⏱ 30 сек”, “dur_30”)],
[(“⏱ 60 сек”, “dur_60”), (“⏱ 90 сек”, “dur_90”)]
),
parse_mode=“HTML”
)

@dp.callback_query(F.data.startswith(“dur_”))
async def choose_duration(callback: CallbackQuery, state: FSMContext):
dur_map = {“dur_15”: 15, “dur_30”: 30, “dur_60”: 60, “dur_90”: 90}
await state.update_data(duration=dur_map.get(callback.data, 30))
await callback.answer()
await callback.message.edit_text(
“Шаг 3/7: <b>Тип контента:</b>”,
reply_markup=kb(
[(“⚡ Эдит (быстрый)”, “type_edit”)],
[(“🌊 Рилс/ТикТок (плавный)”, “type_reels”)],
[(“🎬 Cinematic”, “type_cinematic”)]
),
parse_mode=“HTML”
)

@dp.callback_query(F.data.startswith(“type_”))
async def choose_content_type(callback: CallbackQuery, state: FSMContext):
type_map = {“type_edit”: “edit”, “type_reels”: “reels”, “type_cinematic”: “cinematic”}
await state.update_data(content_type=type_map.get(callback.data, “edit”))
await callback.answer()
await callback.message.edit_text(
“Шаг 4/7: <b>Момент для нарезки:</b>”,
reply_markup=kb(
[(“⬅️ Начало”, “moment_start”), (“🎯 Середина”, “moment_middle”)],
[(“➡️ Конец”, “moment_end”), (“🔥 Лучший момент”, “moment_best”)]
),
parse_mode=“HTML”
)

@dp.callback_query(F.data.startswith(“moment_”))
async def choose_moment(callback: CallbackQuery, state: FSMContext):
moment_map = {“moment_start”: “start”, “moment_middle”: “middle”, “moment_end”: “end”, “moment_best”: “best”}
await state.update_data(moment=moment_map.get(callback.data, “middle”))
await callback.answer()
await callback.message.edit_text(
“Шаг 5/7: <b>Переходы между клипами?</b>”,
reply_markup=kb(
[(“✅ Да”, “trans_yes”), (“❌ Нет”, “trans_no”)]
),
parse_mode=“HTML”
)

@dp.callback_query(F.data.startswith(“trans_”))
async def choose_transitions(callback: CallbackQuery, state: FSMContext):
await state.update_data(transitions=(callback.data == “trans_yes”))
await callback.answer()
await callback.message.edit_text(
“Шаг 6/7: <b>Скорость монтажа:</b>”,
reply_markup=kb(
[(“🐢 Медленная”, “speed_slow”), (“🚶 Средняя”, “speed_medium”)],
[(“🏃 Быстрая”, “speed_fast”), (“⚡ Очень быстрая”, “speed_vfast”)]
),
parse_mode=“HTML”
)

@dp.callback_query(F.data.startswith(“speed_”))
async def choose_speed(callback: CallbackQuery, state: FSMContext):
speed_map = {“speed_slow”: “slow”, “speed_medium”: “medium”, “speed_fast”: “fast”, “speed_vfast”: “vfast”}
await state.update_data(speed=speed_map.get(callback.data, “medium”))
await callback.answer()
await callback.message.edit_text(
“Шаг 7/7: <b>Формат видео:</b>”,
reply_markup=kb(
[(“📱 9:16 (TikTok/Reels)”, “ratio_916”)],
[(“🖥 16:9 (YouTube)”, “ratio_169”)],
[(“⬛ 1:1 (Instagram)”, “ratio_11”)]
),
parse_mode=“HTML”
)

@dp.callback_query(F.data.startswith(“ratio_”))
async def choose_ratio(callback: CallbackQuery, state: FSMContext):
ratio_map = {“ratio_916”: “9:16”, “ratio_169”: “16:9”, “ratio_11”: “1:1”}
ratio = ratio_map.get(callback.data, “9:16”)
await state.update_data(ratio=ratio)
await callback.answer()
data = await state.get_data()
await state.clear()
await callback.message.edit_text(
“⏳ <b>Начинаю монтаж…</b> Это займёт 2-5 минут 🎬”,
parse_mode=“HTML”
)
asyncio.create_task(
process_video(callback.from_user.id, callback.message.chat.id, data, bot)
)

async def process_video(user_id: int, chat_id: int, data: dict, bot_instance: Bot):
session_id = str(uuid.uuid4())[:8]
work_dir = DOWNLOADS_DIR / session_id
work_dir.mkdir(exist_ok=True)
final_output = None

```
try:
    video_url = data.get("video_url")
    duration = data.get("duration") or 30
    content_type = data.get("content_type", "edit")
    moment = data.get("moment", "best")
    transitions = data.get("transitions", True)
    speed_key = data.get("speed", "fast")
    ratio = data.get("ratio", "9:16")

    speed_values = {"slow": 0.9, "medium": 1.2, "fast": 1.6, "vfast": 2.0}
    speed = speed_values.get(speed_key, 1.3)
    if content_type in ("reels", "cinematic"):
        speed = min(speed, 1.2)

    await bot_instance.send_message(chat_id, "📥 Скачиваю видео с YouTube...")
    raw_video = work_dir / "raw.mp4"
    dl_cmd = [
        "yt-dlp",
        "-f", "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]/best",
        "--merge-output-format", "mp4",
        "-o", str(raw_video),
        "--no-playlist", video_url
    ]
    proc = await asyncio.create_subprocess_exec(
        *dl_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0 or not raw_video.exists():
        raise Exception(f"Ошибка скачивания: {stderr.decode()[:200]}")

    probe_cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "ini",
        "-show_format", str(raw_video)
    ]
    proc2 = await asyncio.create_subprocess_exec(
        *probe_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    probe_out, _ = await proc2.communicate()
    total_duration = 60.0
    for line in probe_out.decode().splitlines():
        if line.startswith("duration="):
            try:
                total_duration = float(line.split("=")[1])
            except Exception:
                pass

    segment_duration = duration / speed
    if moment == "start":
        start_time = 5.0
    elif moment == "end":
        start_time = max(0.0, total_duration - segment_duration - 5)
    elif moment == "best":
        start_time = max(0.0, total_duration * 0.25)
    else:
        start_time = max(0.0, (total_duration / 2) - (segment_duration / 2))
    start_time = max(0.0, min(start_time, total_duration - segment_duration - 1))

    await bot_instance.send_message(chat_id, "🎬 Монтирую видео...")

    ratio_filters = {
        "9:16": "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
        "16:9": "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080",
        "1:1": "scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080"
    }
    scale_filter = ratio_filters.get(ratio, ratio_filters["9:16"])

    if content_type == "edit":
        color_filter = "eq=contrast=1.15:saturation=1.2:brightness=0.02"
        fade_in = "fade=t=in:st=0:d=0.1"
        fade_out = f"fade=t=out:st={max(0, duration - 0.2)}:d=0.2"
    elif content_type == "cinematic":
        color_filter = "eq=contrast=1.05:saturation=0.9:brightness=-0.02,colorchannelmixer=rr=1.1:gg=0.95:bb=0.9"
        fade_in = "fade=t=in:st=0:d=1.0"
        fade_out = f"fade=t=out:st={max(0, duration - 1.5)}:d=1.5"
    else:
        color_filter = "eq=contrast=1.08:saturation=1.12:brightness=0.01"
        fade_in = "fade=t=in:st=0:d=0.5"
        fade_out = f"fade=t=out:st={max(0, duration - 0.8)}:d=0.8"

    vf_parts = [scale_filter, color_filter, f"setpts={1/speed}*PTS"]
    if transitions:
        vf_parts += [fade_in, fade_out]
    vf_chain = ",".join(vf_parts)

    af_chain = f"atempo={min(speed, 2.0)},afade=t=in:st=0:d=0.5,afade=t=out:st={max(0, duration-1.0)}:d=1.0,volume=0.9"

    trimmed = work_dir / "trimmed.mp4"
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_time), "-i", str(raw_video),
        "-t", str(segment_duration),
        "-vf", vf_chain, "-af", af_chain,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
        str(trimmed)
    ]
    proc3 = await asyncio.create_subprocess_exec(
        *ffmpeg_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, stderr3 = await proc3.communicate()
    if proc3.returncode != 0 or not trimmed.exists():
        raise Exception(f"FFmpeg ошибка: {stderr3.decode()[-300:]}")

    music_path = user_sessions.get(user_id, {}).get("music_path")
    final_output = OUTPUT_DIR / f"result_{session_id}.mp4"

    if music_path and Path(music_path).exists():
        await bot_instance.send_message(chat_id, "🎵 Накладываю музыку...")
        music_cmd = [
            "ffmpeg", "-y", "-i", str(trimmed), "-i", str(music_path),
            "-filter_complex",
            f"[0:a]volume=0.25[orig];[1:a]atempo=1.0,volume=0.75,afade=t=out:st={max(0, duration-1.5)}:d=1.5[music];[orig][music]amix=inputs=2:duration=first[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest",
            str(final_output)
        ]
        proc4 = await asyncio.create_subprocess_exec(
            *music_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr4 = await proc4.communicate()
        if proc4.returncode != 0:
            shutil.copy(str(trimmed), str(final_output))
    else:
        shutil.copy(str(trimmed), str(final_output))

    if not final_output.exists() or final_output.stat().st_size == 0:
        raise Exception("Файл не создан")

    file_size_mb = final_output.stat().st_size / (1024 * 1024)
    if file_size_mb > 50:
        await bot_instance.send_message(chat_id, f"⚠️ Сжимаю файл ({file_size_mb:.1f} МБ)...")
        compressed = OUTPUT_DIR / f"compressed_{session_id}.mp4"
        compress_cmd = [
            "ffmpeg", "-y", "-i", str(final_output),
            "-c:v", "libx264", "-crf", "30", "-preset", "fast",
            "-c:a", "aac", "-b:a", "96k", str(compressed)
        ]
        proc5 = await asyncio.create_subprocess_exec(
            *compress_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await proc5.communicate()
        if compressed.exists():
            final_output = compressed

    await bot_instance.send_message(chat_id, "📤 Отправляю готовое видео...")

    type_labels = {"edit": "⚡ Эдит", "reels": "🌊 Рилс/ТикТок", "cinematic": "🎬 Cinematic"}
    speed_labels = {"slow": "Медленная", "medium": "Средняя", "fast": "Быстрая", "vfast": "Очень быстрая"}
    caption = (
        f"🎬 <b>Готово!</b>\n\n"
        f"🎭 Тип: {type_labels.get(content_type, content_type)}\n"
        f"📐 Формат: {ratio}\n"
        f"⏱ Длина: ~{duration} сек\n"
        f"🏃 Скорость: {speed_labels.get(speed_key, speed_key)}\n"
        f"✨ Переходы: {'Да' if transitions else 'Нет'}\n"
        f"📦 Размер: {final_output.stat().st_size / (1024*1024):.1f} МБ\n\n"
        f"🤖 Хочешь ещё? /ai"
    )

    with open(final_output, "rb") as f:
        await bot_instance.send_video(
            chat_id, video=f, caption=caption,
            parse_mode="HTML", supports_streaming=True
        )

except Exception as e:
    logger.error(f"Processing error for user {user_id}: {e}")
    await bot_instance.send_message(
        chat_id,
        f"❌ Ошибка при обработке:\n{str(e)[:200]}\n\nПопробуйте /ai или /edit снова"
    )
finally:
    shutil.rmtree(work_dir, ignore_errors=True)
    if final_output and final_output.exists():
        try:
            final_output.unlink(missing_ok=True)
        except Exception:
            pass
```

async def main():
keep_alive()
threading.Thread(target=run_flask, daemon=True).start()
logger.info(“Bot started!”)
await dp.start_polling(bot)

if **name** == “**main**”:
asyncio.run(main())
