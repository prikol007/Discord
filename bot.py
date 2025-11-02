import os
import discord
from flask import Flask
import threading
from discord.ext import commands, tasks
from discord.ui import Button, View, Select, Modal, TextInput
from dotenv import load_dotenv
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import asyncio

# ---------------------------- Настройки ----------------------------
load_dotenv()
TOKEN = os.getenv("TOKEN")
if TOKEN is None:
    raise ValueError("Токен Discord не задан!")

ADMIN_ID = 1030933788005502996  # ID администратора

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------------------- Слоты ----------------------------
current_slots = {}
last_embed_message = None
header_text = ""

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

class RoleButton(Button):
    def __init__(self, slot_number, slot_name):
        super().__init__(label=add_emoji(slot_name), style=discord.ButtonStyle.primary)
        self.slot_number = slot_number
        self.slot_name = slot_name

    async def callback(self, interaction: discord.Interaction):
        for info in current_slots.values():
            if info["user"] == interaction.user:
                await interaction.response.send_message(
                    f"❌ Вы уже записаны на слот {info['name']}", ephemeral=True)
                return
        if current_slots[self.slot_number]["user"] is not None:
            await interaction.response.send_message(
                f"❌ Слот {self.slot_name} уже занят: {current_slots[self.slot_number]['user'].mention}",
                ephemeral=True)
            return
        current_slots[self.slot_number]["user"] = interaction.user
        await update_message()
        await interaction.response.send_message(
            f"✅ Вы записаны на слот {self.slot_name}", ephemeral=True)

class LeaveButton(Button):
    def __init__(self, slot_number, slot_name):
        super().__init__(label="Отписаться", style=discord.ButtonStyle.danger)
        self.slot_number = slot_number
        self.slot_name = slot_name

    async def callback(self, interaction: discord.Interaction):
        if current_slots[self.slot_number]["user"] != interaction.user:
            await interaction.response.send_message(
                "❌ Вы не записаны на этот слот.", ephemeral=True)
            return
        current_slots[self.slot_number]["user"] = None
        await update_message()
        await interaction.response.send_message(
            f"✅ Вы отписались от слота {self.slot_name}", ephemeral=True)

class SignupView(View):
    def __init__(self):
        super().__init__(timeout=None)
        for slot_id, info in current_slots.items():
            self.add_item(RoleButton(slot_id, info["name"]))
            if info["user"]:
                self.add_item(LeaveButton(slot_id, info["name"]))

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
    embed = discord.Embed(title=title, description=desc, color=0x00ff99)
    await last_embed_message.edit(embed=embed, view=view)

# ---------------------------- Команда !create ----------------------------
@bot.command()
async def create(ctx, *, text):
    if ctx.author.id != ADMIN_ID:
        await ctx.send("❌ У вас нет прав на создание слотов.", delete_after=5)
        return
    global current_slots, last_embed_message, header_text
    current_slots = {}
    lines = text.split("\n")
    if not lines:
        await ctx.send("❌ Нужно хотя бы указать заголовок и один слот.", delete_after=5)
        return
    header_text = lines[0].strip()
    slot_lines = lines[1:]
    for idx, line in enumerate(slot_lines, start=1):
        line = line.strip()
        if line:
            current_slots[idx] = {"name": line, "user": None}
    moscow_time = datetime.now(ZoneInfo("Europe/Moscow"))
    title = f"{header_text} — {moscow_time.strftime('%H:%M %d.%m')}"
    desc = ""
    for slot_id, info in current_slots.items():
        desc += f"{slot_id}. ⬜ {add_emoji(info['name'])} — свободно\n"
    embed = discord.Embed(title=title, description=desc, color=0x00ff99)
    last_embed_message = await ctx.send(embed=embed, view=SignupView())
    try:
        await ctx.message.delete()
    except:
        pass

# ---------------------------- Серверы и промокоды ----------------------------
servers = {}  # guild_id: {name, access_level, expiry, blocked_since, promo_used_by}
promocodes = {}  # code: {days, creator, used_by}

async def notify_server(guild_id, msg):
    guild = bot.get_guild(guild_id)
    if guild:
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                await channel.send(msg)
                break

@bot.event
async def on_guild_join(guild):
    now = datetime.now()
    servers[guild.id] = {
        "name": guild.name,
        "access_level": "free",
        "expiry": now + timedelta(days=1),
        "blocked_since": None,
        "promo_used_by": None
    }
    await notify_server(guild.id, "Бесплатный доступ активирован на 1 день.")

# ---------------------------- Авто-проверка серверов ----------------------------
@tasks.loop(minutes=5)
async def check_server_access():
    now = datetime.now()
    for guild in list(bot.guilds):
        info = servers.get(guild.id)
        if not info:
            servers[guild.id] = {
                "name": guild.name,
                "access_level": "free",
                "expiry": now + timedelta(days=1),
                "blocked_since": None,
                "promo_used_by": None
            }
            await notify_server(guild.id, "Бесплатный доступ активирован на 1 день.")
            continue
        expiry = info.get("expiry")
        blocked_since = info.get("blocked_since")
        if expiry and now > expiry:
            if not blocked_since:
                servers[guild.id]["blocked_since"] = now
                await notify_server(guild.id, "⚠️ Доступ к функциям бота заблокирован. Оплата не подтверждена.")
            elif (now - blocked_since) > timedelta(days=1):
                await guild.leave()
                print(f"Бот покинул сервер {guild.name} — оплата не подтверждена")
                del servers[guild.id]

@bot.event
async def on_ready():
    print(f"Бот запущен как {bot.user}")
    check_server_access.start()

# ---------------------------- Админ-панель ----------------------------
class AdminPanel(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(BlockServerButton())
        self.add_item(UnblockServerButton())
        self.add_item(LeaveServerSelect())
        self.add_item(CreatePromoButton())
        self.add_item(PromoReportButton())

class BlockServerButton(Button):
    def __init__(self):
        super().__init__(label="🚫 Заблокировать сервер", style=discord.ButtonStyle.danger)
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != ADMIN_ID:
            return await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
        servers[interaction.guild.id]["blocked_since"] = datetime.now()
        await notify_server(interaction.guild.id, "⚠️ Сервер заблокирован администратором.")
        await interaction.response.send_message("Сервер заблокирован.", ephemeral=True)

class UnblockServerButton(Button):
    def __init__(self):
        super().__init__(label="🟢 Разблокировать сервер", style=discord.ButtonStyle.success)
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != ADMIN_ID:
            return await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
        await interaction.response.send_message("Выберите срок разблокировки:", view=UnblockDurationSelect(), ephemeral=True)

class UnblockDurationSelect(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(UnblockDurationSelectMenu())

class UnblockDurationSelectMenu(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="1 день", value="1"),
            discord.SelectOption(label="3 дня", value="3"),
            discord.SelectOption(label="7 дней", value="7"),
            discord.SelectOption(label="30 дней", value="30"),
            discord.SelectOption(label="Навсегда", value="forever")
        ]
        super().__init__(placeholder="Выберите срок доступа", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != ADMIN_ID:
            return await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
        guild_id = interaction.guild.id
        now = datetime.now()
        value = self.values[0]
        if value == "forever":
            servers[guild_id]["expiry"] = None
            servers[guild_id]["blocked_since"] = None
            msg = "✅ Сервер разблокирован навсегда."
        else:
            days = int(value)
            servers[guild_id]["expiry"] = now + timedelta(days=days)
            servers[guild_id]["blocked_since"] = None
            msg = f"✅ Сервер разблокирован на {days} дней (до {servers[guild_id]['expiry'].strftime('%d.%m %H:%M')})."
        await notify_server(guild_id, msg)
        await interaction.response.send_message(msg, ephemeral=True)

class LeaveServerSelect(Select):
    def __init__(self):
        options = [discord.SelectOption(label=g.name, value=str(g.id)) for g in bot.guilds]
        super().__init__(placeholder="Выберите сервер для выхода", options=options)
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != ADMIN_ID:
            return await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
        guild_id = int(self.values[0])
        guild = bot.get_guild(guild_id)
        if guild:
            await interaction.response.send_message(f"Бот покидает сервер {guild.name} через 5 секунд...", ephemeral=True)
            await asyncio.sleep(5)
            await guild.leave()
            await interaction.followup.send(f"✅ Бот покинул сервер {guild.name}.", ephemeral=True)

class CreatePromoButton(Button):
    def __init__(self):
        super().__init__(label="🎁 Создать промокод на 3 дня", style=discord.ButtonStyle.primary)
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != ADMIN_ID:
            return await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
        code = f"PROMO{len(promocodes)+1}"
        promocodes[code] = {"days": 3, "creator": ADMIN_ID, "used_by": []}
        await interaction.response.send_message(f"✅ Промокод `{code}` создан на 3 дня.", ephemeral=True)

class PromoReportButton(Button):
    def __init__(self):
        super().__init__(label="📋 Отчёт по промокодам", style=discord.ButtonStyle.secondary)
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != ADMIN_ID:
            return await interaction.response.send_message("❌ Нет прав.", ephemeral=True)
        lines = []
        for code, info in promocodes.items():
            used_servers = [servers[g]["name"] for g in info["used_by"] if g in servers]
            lines.append(f"{code} — использован на: {', '.join(used_servers) if used_servers else 'нет'}")
        msg = "\n".join(lines) or "Промокоды ещё не использовались."
        await interaction.response.send_message(msg, ephemeral=True)

@bot.command()
async def admin_panel(ctx):
    if ctx.author.id != ADMIN_ID:
        return await ctx.send("❌ У вас нет доступа к панели.", delete_after=5)
    await ctx.send("🔧 Панель администратора", view=AdminPanel())

# ---------------------------- Промокоды и доступ ----------------------------
class PromoModal(Modal, title="🎟️ Ввести промокод"):
    code_input = TextInput(label="Введите промокод", placeholder="например, PROMO1")

    async def on_submit(self, interaction: discord.Interaction):
        code = self.code_input.value.strip().upper()
        guild_id = interaction.guild.id
        now = datetime.now()
        if code not in promocodes:
            return await interaction.response.send_message("❌ Неверный промокод.", ephemeral=True)
        promo = promocodes[code]
        if guild_id in promo["used_by"]:
            return await interaction.response.send_message("⚠️ Этот промокод уже использован на вашем сервере.", ephemeral=True)
        servers[guild_id]["expiry"] = now + timedelta(days=promo["days"])
        servers[guild_id]["blocked_since"] = None
        promo["used_by"].append(guild_id)
        await notify_server(guild_id, f"🎉 Промокод `{code}` активирован! Доступ продлён на {promo['days']} дней.")
        await interaction.response.send_message(f"✅ Промокод активирован на {promo['days']} дней!", ephemeral=True)

@bot.command()
async def promo(ctx):
    await ctx.send_modal(PromoModal())

@bot.command()
async def access(ctx):
    info = servers.get(ctx.guild.id)
    if not info:
        return await ctx.send("⚠️ Сервер не зарегистрирован.")
    expiry = info.get("expiry")
    if expiry is None:
        return await ctx.send("♾️ У вашего сервера безлимитный доступ.")
    now = datetime.now()
    remaining = expiry - now
    if remaining.total_seconds() <= 0:
        return await ctx.send("⛔ Срок доступа истёк.")
    days = remaining.days
    hours = remaining.seconds // 3600
    await ctx.send(f"⏱️ Доступ активен ещё **{days} дн. {hours} ч.**")

# ---------------------------- Flask для Render ----------------------------
app = Flask("")

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask).start()

# ---------------------------- Запуск бота ----------------------------
bot.run(TOKEN)




