import os
import asyncio
import logging
import uuid
import shutil
import threading
from pathlib import Path
from flask import Flask
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import anthropic

# ── Настройки (всё через переменные окружения) ──────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "8788961014:AAFXDB9bNxLJv6NtokMW01BbHi4yBV-weis")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "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")
CHANNEL_ID = os.getenv("CHANNEL_ID", "")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

DOWNLOADS_DIR = Path("downloads")
OUTPUT_DIR = Path("output")
DOWNLOADS_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Flask (единственный веб-сервер) ─────────────────────────────────
app_flask = Flask(__name__)


@app_flask.route('/')
def home():
    return 'Bot is running!'


@app_flask.route('/health')
def health():
    return 'OK', 200


def run_flask():
    port = int(os.environ.get("PORT", 8000))
    app_flask.run(host='0.0.0.0', port=port)


# ── FSM-состояния ───────────────────────────────────────────────────
class EditStates(StatesGroup):
    waiting_url = State()
    waiting_music_url = State()
    choosing_duration = State()
    choosing_content_type = State()
    choosing_moment = State()
    choosing_transitions = State()
    choosing_speed = State()
    choosing_ratio = State()


class AIStates(StatesGroup):
    waiting_description = State()


# ── Глобальные объекты ──────────────────────────────────────────────
user_sessions = {}
ai_conversations = {}

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# ── Утилиты ─────────────────────────────────────────────────────────
def kb(*buttons_rows):
    keyboard = []
    for row in buttons_rows:
        keyboard.append(
            [InlineKeyboardButton(text=btn[0], callback_data=btn[1]) for btn in row]
        )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_claude_client():
    if CLAUDE_API_KEY:
        return anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    return None


# ── Claude AI ───────────────────────────────────────────────────────
CLAUDE_SYSTEM_PROMPT = """Ty — professionalnyy videomontazhor i rezhissor, specializiruyushchiysya na:
- TikTok i Reels editakh (bystryy dinamichnyy montazh)
- Sportivnykh khaylaitakh i klipakh
- Muzykalnykh editakh pod bit
- Cinematic rolikakh

Ty pomogayesh polzovatelyu sozdat video. Kogda polzovatel opisyvaet chto khochet:
1. Utochnyayesh detali esli nuzhno (ssylka na video, muzyka, stil)
2. Opredelyayesh parametry montazha:
   - duration: dlina v sekundakh (15/30/60/90)
   - content_type: edit ili reels ili cinematic
   - moment: start/middle/end/best
   - transitions: true/false
   - speed: slow/medium/fast/vfast
   - ratio: 9:16 ili 16:9 ili 1:1

Kogda u tebya est VSYA nuzhna informatsiya (ssylka na video obyazatelna),
verni JSON v kontse otveta v takom formate:
<PARAMS>
{
  "ready": true,
  "video_url": "https://youtube.com/...",
  "duration": 30,
  "content_type": "edit",
  "moment": "best",
  "transitions": true,
  "speed": "fast",
  "ratio": "9:16",
  "style": "dynamic sport edit"
}
</PARAMS>

Obshchaysya druzhelyubno kak nastoyashchiy professionalnyy montazhor.
Esli net ssylki na video — obyazatelno poprosi ee.
Otvechay na yazyke polzovatelya."""


async def ask_claude(user_id, user_message):
    client = get_claude_client()
    if not client:
        return "Claude AI ne nastroyen. Dobavte CLAUDE_API_KEY v peremennye Railway.", None

    if user_id not in ai_conversations:
        ai_conversations[user_id] = []

    ai_conversations[user_id].append({
        "role": "user",
        "content": user_message
    })

    if len(ai_conversations[user_id]) > 20:
        ai_conversations[user_id] = ai_conversations[user_id][-20:]

    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(
        None,
        lambda: client.messages.create(
            model="claude-sonnet-4-20250514",
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
            logger.error("Params parse error: %s", e)

    return reply, params


# ── Команды ─────────────────────────────────────────────────────────
@dp.message(Command("start"))
async def cmd_start(message: Message):
    claude_status = "Claude AI agent aktiven" if CLAUDE_API_KEY else "Claude AI ne nastroyen"
    await message.answer(
        "Privet! Ya professionalnyy montazhor video s AI.\n\n"
        "Sozdayu edity, Reels, TikTok roliki iz YouTube video.\n\n"
        "Status: " + claude_status + "\n\n"
        "Komandy:\n"
        "/ai — opisat chto khochesh, Claude sdelaet sam\n"
        "/edit — sozdat video cherez knopki\n"
        "/setmusic — ustanovit fonovuyu muzyku\n"
        "/help — pomoshch"
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Kak polzovatsya botom\n\n"
        "/ai — umnyy rezhim s Claude\n"
        "Opishite chto khotite slovami\n"
        "Naprimer: Sdelay edit Ronaldo 30 sekund dlya TikTok\n\n"
        "/edit — ruchnoy rezhim cherez knopki\n\n"
        "/setmusic — fonovaya muzyka YouTube\n\n"
        "Formaty:\n"
        "9:16 — TikTok / Reels\n"
        "16:9 — YouTube\n"
        "1:1 — Instagram kvadrat\n\n"
        "Montazh cherez ffmpeg — 100% besplatno!"
    )


@dp.message(Command("ai"))
async def cmd_ai(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    ai_conversations.pop(user_id, None)

    args = message.text.strip().split(maxsplit=1)

    if not CLAUDE_API_KEY:
        await message.answer(
            "Claude AI ne nastroyen\n\n"
            "Dobavte peremennuyu CLAUDE_API_KEY v Railway:\n"
            "Settings - Variables - Add Variable"
        )
        return

    await state.set_state(AIStates.waiting_description)

    if len(args) > 1 and args[1].strip():
        await process_ai_message(message, state, args[1].strip())
    else:
        await message.answer(
            "Claude AI Montazhor\n\n"
            "Opishite chto khotite sozdat:\n\n"
            "Primery:\n"
            "Sdelay edit Ronaldo 30 sekund dlya TikTok\n"
            "Khochu cinematic klip 60 sekund v formate 9:16\n"
            "Narezh luchshie momenty: [ssylka]\n\n"
            "Otpravte vash zapros:"
        )


@dp.message(AIStates.waiting_description)
async def handle_ai_message(message: Message, state: FSMContext):
    await process_ai_message(message, state, message.text.strip())


async def process_ai_message(message: Message, state: FSMContext, text: str):
    user_id = message.from_user.id
    thinking_msg = await message.answer("Claude dumayet...")

    try:
        reply, params = await ask_claude(user_id, text)
        await thinking_msg.delete()

        if params and params.get("ready") and params.get("video_url"):
            confirm_text = (
                "Claude gotov k montazhu!\n\n" +
                reply + "\n\n"
                "Parametry:\n"
                "Dlina: " + str(params.get("duration", 30)) + " sek\n"
                "Tip: " + str(params.get("content_type", "edit")) + "\n"
                "Format: " + str(params.get("ratio", "9:16")) + "\n"
                "Skorost: " + str(params.get("speed", "fast")) + "\n"
                "Perekhody: " + ("Da" if params.get("transitions") else "Net")
            )

            confirm_kb = kb(
                [("Nachat montazh!", "ai_start_edit")],
                [("Izmenit parametry", "ai_change_params")],
                [("Otmena", "ai_cancel_edit")]
            )

            await state.update_data(ai_params=params)
            await message.answer(confirm_text, reply_markup=confirm_kb)
        else:
            await message.answer("Claude:\n\n" + reply)

    except Exception as e:
        logger.error("Claude AI error: %s", e)
        try:
            await thinking_msg.delete()
        except Exception:
            pass
        await state.clear()
        await message.answer("Oshibka Claude AI:\n" + str(e)[:200] + "\n\nPoprobuy /ai snova")


@dp.callback_query(F.data == "ai_start_edit")
async def ai_start_edit(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    params = data.get("ai_params", {})
    await state.clear()
    await callback.message.edit_text("Nachinayu montazh po ukazaniyam Claude... Eto zaymet 2-5 minut")
    asyncio.create_task(process_video(callback.from_user.id, callback.message.chat.id, params, bot))
    await callback.answer()


@dp.callback_query(F.data == "ai_change_params")
async def ai_change_params(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Opishite chto izmenit:\nNaprimer: sdelay dlinnee 60 sekund")
    await callback.answer()


@dp.callback_query(F.data == "ai_cancel_edit")
async def ai_cancel_edit(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    ai_conversations.pop(callback.from_user.id, None)
    await callback.message.edit_text("Otmeneno. Napishite /ai chtoby nachat zanovo.")
    await callback.answer()


# ── Музыка ──────────────────────────────────────────────────────────
@dp.message(Command("setmusic"))
async def cmd_setmusic(message: Message, state: FSMContext):
    await state.set_state(EditStates.waiting_music_url)
    await message.answer("Otpravte ssylku na YouTube dlya muzyki:\nNaprimer: https://www.youtube.com/watch?v=...")


@dp.message(EditStates.waiting_music_url)
async def process_music_url(message: Message, state: FSMContext):
    user_id = message.from_user.id
    url = message.text.strip()

    if "youtube.com" not in url and "youtu.be" not in url:
        await message.answer("Eto ne YouTube ssylka.")
        return

    await message.answer("Skachivay muzyku...")
    music_path = DOWNLOADS_DIR / ("music_" + str(user_id) + ".mp3")

    try:
        cmd = [
            "yt-dlp", "-x", "--audio-format", "mp3",
            "-o", str(music_path.with_suffix("")) + ".%(ext)s", url
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise Exception(stderr.decode())

        user_sessions.setdefault(user_id, {})["music_path"] = str(music_path)
        await state.clear()
        await message.answer("Muzyka sokhranena! Ispolzuyte /ai ili /edit dlya sozdaniya video.")

    except Exception as e:
        logger.error("Music download error: %s", e)
        await state.clear()
        await message.answer("Ne udalos skachat muzyku. Proverite ssylku.")


# ── Ручной режим /edit ──────────────────────────────────────────────
@dp.message(Command("edit"))
async def cmd_edit(message: Message, state: FSMContext):
    await state.set_state(EditStates.waiting_url)
    await message.answer("Sozdanie video ruchnoy rezhim\n\nShag 1/7: Otpravte ssylku na YouTube video:")


@dp.message(EditStates.waiting_url)
async def process_video_url(message: Message, state: FSMContext):
    url = message.text.strip()
    if "youtube.com" not in url and "youtu.be" not in url:
        await message.answer("Eto ne YouTube ssylka.")
        return

    await state.update_data(video_url=url)
    await state.set_state(EditStates.choosing_duration)
    await message.answer(
        "Ssylka prinyata!\n\nShag 2/7: Dlina video:",
        reply_markup=kb(
            [("15 sek", "dur_15"), ("30 sek", "dur_30")],
            [("60 sek", "dur_60"), ("90 sek", "dur_90")]
        )
    )


@dp.callback_query(F.data.startswith("dur_"))
async def choose_duration(callback: CallbackQuery, state: FSMContext):
    dur_map = {"dur_15": 15, "dur_30": 30, "dur_60": 60, "dur_90": 90}
    await state.update_data(duration=dur_map.get(callback.data, 30))
    await callback.answer()
    await callback.message.edit_text(
        "Shag 3/7: Tip kontenta:",
        reply_markup=kb(
            [("Edit bystryy", "type_edit")],
            [("Reels TikTok plavnyy", "type_reels")],
            [("Cinematic", "type_cinematic")]
        )
    )


@dp.callback_query(F.data.startswith("type_"))
async def choose_content_type(callback: CallbackQuery, state: FSMContext):
    type_map = {"type_edit": "edit", "type_reels": "reels", "type_cinematic": "cinematic"}
    await state.update_data(content_type=type_map.get(callback.data, "edit"))
    await callback.answer()
    await callback.message.edit_text(
        "Shag 4/7: Moment dlya narezki:",
        reply_markup=kb(
            [("Nachalo", "moment_start"), ("Seredina", "moment_middle")],
            [("Konets", "moment_end"), ("Luchshiy moment", "moment_best")]
        )
    )


@dp.callback_query(F.data.startswith("moment_"))
async def choose_moment(callback: CallbackQuery, state: FSMContext):
    moment_map = {
        "moment_start": "start", "moment_middle": "middle",
        "moment_end": "end", "moment_best": "best"
    }
    await state.update_data(moment=moment_map.get(callback.data, "middle"))
    await callback.answer()
    await callback.message.edit_text(
        "Shag 5/7: Perekhody mezhdu klipami?",
        reply_markup=kb(
            [("Da", "trans_yes"), ("Net", "trans_no")]
        )
    )


@dp.callback_query(F.data.startswith("trans_"))
async def choose_transitions(callback: CallbackQuery, state: FSMContext):
    await state.update_data(transitions=(callback.data == "trans_yes"))
    await callback.answer()
    await callback.message.edit_text(
        "Shag 6/7: Skorost montazha:",
        reply_markup=kb(
            [("Medlennaya", "speed_slow"), ("Srednyaya", "speed_medium")],
            [("Bystraya", "speed_fast"), ("Ochen bystraya", "speed_vfast")]
        )
    )


@dp.callback_query(F.data.startswith("speed_"))
async def choose_speed(callback: CallbackQuery, state: FSMContext):
    speed_map = {
        "speed_slow": "slow", "speed_medium": "medium",
        "speed_fast": "fast", "speed_vfast": "vfast"
    }
    await state.update_data(speed=speed_map.get(callback.data, "medium"))
    await callback.answer()
    await callback.message.edit_text(
        "Shag 7/7: Format video:",
        reply_markup=kb(
            [("9:16 TikTok Reels", "ratio_916")],
            [("16:9 YouTube", "ratio_169")],
            [("1:1 Instagram", "ratio_11")]
        )
    )


@dp.callback_query(F.data.startswith("ratio_"))
async def choose_ratio(callback: CallbackQuery, state: FSMContext):
    ratio_map = {"ratio_916": "9:16", "ratio_169": "16:9", "ratio_11": "1:1"}
    ratio = ratio_map.get(callback.data, "9:16")
    await state.update_data(ratio=ratio)
    await callback.answer()

    data = await state.get_data()
    await state.clear()
    await callback.message.edit_text("Nachinayu montazh... Eto zaymet 2-5 minut")
    asyncio.create_task(process_video(callback.from_user.id, callback.message.chat.id, data, bot))


# ── Обработка видео ─────────────────────────────────────────────────
async def process_video(user_id, chat_id, data, bot_instance):
    session_id = str(uuid.uuid4())[:8]
    work_dir = DOWNLOADS_DIR / session_id
    work_dir.mkdir(exist_ok=True)
    final_output = None

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

        await bot_instance.send_message(chat_id, "Skachivay video s YouTube...")

        raw_video = work_dir / "raw.mp4"
        dl_cmd = [
            "yt-dlp",
            "-f", "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]",
            "--merge-output-format", "mp4",
            "-o", str(raw_video),
            "--no-playlist", video_url
        ]

        proc = await asyncio.create_subprocess_exec(
            *dl_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0 or not raw_video.exists():
            raise Exception("Oshibka skachivanya: " + stderr.decode()[:200])

        # Получаем длительность исходного видео
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

        await bot_instance.send_message(chat_id, "Montiruyu video...")

        # Фильтры по соотношению сторон
        ratio_filters = {
            "9:16": "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
            "16:9": "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080",
            "1:1": "scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080"
        }
        scale_filter = ratio_filters.get(ratio, ratio_filters["9:16"])

        # Цветокоррекция и фейды по типу контента
        if content_type == "edit":
            color_filter = "eq=contrast=1.15:saturation=1.2:brightness=0.02"
            fade_in = "fade=t=in:st=0:d=0.1"
            fade_out = "fade=t=out:st=" + str(max(0, duration - 0.2)) + ":d=0.2"
        elif content_type == "cinematic":
            color_filter = "eq=contrast=1.05:saturation=0.9:brightness=-0.02,colorchannelmixer=rr=1.02:gg=0.98:bb=1.05"
            fade_in = "fade=t=in:st=0:d=1.0"
            fade_out = "fade=t=out:st=" + str(max(0, duration - 1.5)) + ":d=1.5"
        else:
            color_filter = "eq=contrast=1.08:saturation=1.12:brightness=0.01"
            fade_in = "fade=t=in:st=0:d=0.5"
            fade_out = "fade=t=out:st=" + str(max(0, duration - 0.8)) + ":d=0.8"

        vf_parts = [scale_filter, color_filter, "setpts=" + str(1 / speed) + "*PTS"]
        if transitions:
            vf_parts += [fade_in, fade_out]
        vf_chain = ",".join(vf_parts)

        af_chain = (
            "atempo=" + str(min(speed, 2.0))
            + ",afade=t=in:st=0:d=0.5"
            + ",afade=t=out:st=" + str(max(0, duration - 1)) + ":d=1"
        )

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
            raise Exception("FFmpeg oshibka: " + stderr3.decode()[-300:])

        # Наложение музыки (если есть)
        music_path = user_sessions.get(user_id, {}).get("music_path")
        final_output = OUTPUT_DIR / ("result_" + session_id + ".mp4")

        if music_path and Path(music_path).exists():
            await bot_instance.send_message(chat_id, "Nakladyvay muzyku...")
            music_cmd = [
                "ffmpeg", "-y", "-i", str(trimmed), "-i", str(music_path),
                "-filter_complex",
                "[0:a]volume=0.25[orig];"
                "[1:a]atempo=1.0,volume=0.75,afade=t=out:st="
                + str(max(0, duration - 2)) + ":d=2[music];"
                "[orig][music]amix=inputs=2:duration=first[aout]",
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
            raise Exception("Fayl ne sozdan")

        # Сжатие если файл > 50 МБ
        file_size_mb = final_output.stat().st_size / (1024 * 1024)
        if file_size_mb > 50:
            await bot_instance.send_message(
                chat_id, "Szhimayu fayl " + str(round(file_size_mb, 1)) + " MB..."
            )
            compressed = OUTPUT_DIR / ("compressed_" + session_id + ".mp4")
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

        # Отправка результата
        await bot_instance.send_message(chat_id, "Otpravlyayu gotovoe video...")

        type_labels = {"edit": "Edit", "reels": "Reels TikTok", "cinematic": "Cinematic"}
        speed_labels = {
            "slow": "Medlennaya", "medium": "Srednyaya",
            "fast": "Bystraya", "vfast": "Ochen bystraya"
        }

        caption = (
            "Gotovo!\n\n"
            "Tip: " + type_labels.get(content_type, content_type) + "\n"
            "Format: " + ratio + "\n"
            "Dlina: " + str(duration) + " sek\n"
            "Skorost: " + speed_labels.get(speed_key, speed_key) + "\n"
            "Perekhody: " + ("Da" if transitions else "Net") + "\n"
            "Razmer: " + str(round(final_output.stat().st_size / (1024 * 1024), 1)) + " MB\n\n"
            "Khochesh eshche? /ai"
        )

        with open(final_output, "rb") as f:
            await bot_instance.send_video(
                chat_id, video=f, caption=caption, supports_streaming=True
            )

    except Exception as e:
        logger.error("Processing error for user %s: %s", user_id, e)
        await bot_instance.send_message(
            chat_id, "Oshibka pri obrabotke:\n" + str(e)[:200] + "\n\nPoprobuy /ai snova"
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        if final_output and final_output.exists():
            try:
                final_output.unlink(missing_ok=True)
            except Exception:
                pass


# ── Запуск ──────────────────────────────────────────────────────────
async def main():
    threading.Thread(target=run_flask, daemon=True).start()
    logger.info("Bot started!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
