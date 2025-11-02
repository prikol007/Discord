import os
import discord
from discord.ext import commands
from discord.ui import Button, View
from dotenv import load_dotenv
from datetime import datetime
from zoneinfo import ZoneInfo  # Для московского времени

# Загрузка токена из .env
load_dotenv()
TOKEN = os.getenv("TOKEN")
if TOKEN is None:
    raise ValueError("Токен Discord не задан!")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

current_slots = {}
last_embed_message = None
header_text = ""  # Заголовок уведомления

EMOJI_MAP = {
    "танк": "🛡️",
    "хил": "💉",
    "ДД": "⚔️",
    "порезка": "🔪",
    "пылайка": "🔥"
}

def add_emoji(name):
    for key, emoji in EMOJI_MAP.items():
        if key.lower() in name.lower():
            return f"{emoji} {name}"
    return name

# Кнопка "Записаться"
class RoleButton(Button):
    def __init__(self, slot_number, slot_name):
        super().__init__(label=add_emoji(slot_name), style=discord.ButtonStyle.primary)
        self.slot_number = slot_number
        self.slot_name = slot_name

    async def callback(self, interaction: discord.Interaction):
        global current_slots

        # Проверка, записан ли пользователь на другой слот
        for info in current_slots.values():
            if info["user"] == interaction.user:
                await interaction.response.send_message(
                    f"❌ Вы уже записаны на слот {info['name']}", ephemeral=True)
                return

        # Проверка, свободен ли слот
        if current_slots[self.slot_number]["user"] is not None:
            await interaction.response.send_message(
                f"❌ Слот {self.slot_name} уже занят: {current_slots[self.slot_number]['user'].mention}",
                ephemeral=True)
            return

        current_slots[self.slot_number]["user"] = interaction.user
        await update_message()
        await interaction.response.send_message(
            f"✅ Вы записаны на слот {self.slot_name}", ephemeral=True)

# Кнопка "Отписаться"
class LeaveButton(Button):
    def __init__(self, slot_number, slot_name):
        super().__init__(label="Отписаться", style=discord.ButtonStyle.danger)
        self.slot_number = slot_number
        self.slot_name = slot_name

    async def callback(self, interaction: discord.Interaction):
        global current_slots
        if current_slots[self.slot_number]["user"] != interaction.user:
            await interaction.response.send_message(
                "❌ Вы не записаны на этот слот.", ephemeral=True)
            return
        current_slots[self.slot_number]["user"] = None
        await update_message()
        await interaction.response.send_message(
            f"✅ Вы отписались от слота {self.slot_name}", ephemeral=True)

# Вью для кнопок: запись и отписка
class SignupView(View):
    def __init__(self):
        super().__init__(timeout=None)
        for slot_id, info in current_slots.items():
            # Кнопка для записи
            self.add_item(RoleButton(slot_id, info["name"]))
            # Кнопка для отписки, если слот уже занят
            if info["user"]:
                self.add_item(LeaveButton(slot_id, info["name"]))

# Обновление embed-сообщения
async def update_message():
    global last_embed_message, header_text
    if not last_embed_message:
        return

    moscow_time = datetime.now(ZoneInfo("Europe/Moscow"))
    title = f"{header_text} — {moscow_time.strftime('%H:%M %d.%m')}"

    desc = ""
    for slot_id, info in current_slots.items():
        slot_display = add_emoji(info["name"])
        if info["user"]:
            desc += f"{slot_id}. ✅ {slot_display} — {info['user'].mention}\n"
        else:
            desc += f"{slot_id}. ⬜ {slot_display} — свободно\n"

    view = SignupView()
    embed = discord.Embed(
        title=title,
        description=desc,
        color=0x00ff99
    )

    await last_embed_message.edit(embed=embed, view=view)

# Команда для создания слотов
@bot.command()
async def create(ctx, *, text):
    global current_slots, last_embed_message, header_text
    current_slots = {}

    lines = text.split("\n")
    if not lines:
        await ctx.send("❌ Нужно хотя бы указать заголовок и один слот.", delete_after=5)
        return

    header_text = lines[0].strip()  # Заголовок
    slot_lines = lines[1:]         # Остальные строки — слоты

    for idx, line in enumerate(slot_lines, start=1):
        line = line.strip()
        if line:
            current_slots[idx] = {"name": line, "user": None}

    moscow_time = datetime.now(ZoneInfo("Europe/Moscow"))
    title = f"{header_text} — {moscow_time.strftime('%H:%M %d.%m')}"

    desc = ""
    for slot_id, info in current_slots.items():
        desc += f"{slot_id}. ⬜ {add_emoji(info['name'])} — свободно\n"

    embed = discord.Embed(
        title=title,
        description=desc,
        color=0x00ff99
    )

    last_embed_message = await ctx.send(embed=embed, view=SignupView())

    # Попытка удалить команду пользователя
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        await ctx.send("❌ У меня нет прав на удаление сообщений!", delete_after=5)
    except discord.HTTPException as e:
        await ctx.send(f"❌ Не удалось удалить сообщение: {e}", delete_after=5)

bot.run(TOKEN)



