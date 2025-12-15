import discord
from discord.ext import commands, tasks
from discord.ui import Button, View, Modal, TextInput
import json, os, time, asyncio, shutil
from dotenv import load_dotenv
import traceback
from admin import setup as setup_admin, blocked_channels  # импортируем блокировки

# ================== НАСТРОЙКИ ==================
load_dotenv()
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("❌ TOKEN не найден")
    exit(1)

ADMIN_ID = 1030933788005502996
RL_ROLE_NAME = "РЛ"
DATA_FILE = "raids.json"
CHANNEL_FILE = "channel.json"

UPDATE_INTERVAL = 600   # обновление панели каждые 10 минут
RAID_EXPIRE = 43200     # 12 часов

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ================== JSON УТИЛИТЫ ==================
def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# ================== ЗАГРУЗКА ДАННЫХ ==================
raids = load_json(DATA_FILE, {})
channels_data = load_json(CHANNEL_FILE, [])
if not isinstance(channels_data, list):
    channels_data = []

# ================== ФУНКЦИЯ ПРОВЕРКИ БЛОКИРОВКИ ==================
def is_channel_blocked(channel_id):
    return str(channel_id) in blocked_channels and time.time() < blocked_channels[str(channel_id)]

# ================== UI ==================
class CreateRaidPanel(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="➕ Создать слот", style=discord.ButtonStyle.green, custom_id="create_raid"))

class RaidSignupView(View):
    def __init__(self, msg_id):
        super().__init__(timeout=None)
        self.add_item(Button(label="✅ Записаться", style=discord.ButtonStyle.primary, custom_id=f"signup_{msg_id}"))
        self.add_item(Button(label="❌ Отписаться", style=discord.ButtonStyle.danger, custom_id=f"leave_{msg_id}"))

# ================== EMBED ==================
def generate_embed(raid):
    desc = f"**Описание:** {raid['desc']}\n**Время:** {raid['time']}\n\n**Участники:**\n"
    for i, slot in enumerate(raid['slots'], start=1):
        user_text = slot['user'] if slot['user'] else "—"
        desc += f"{i} {slot['role']}: {user_text}\n"
    embed = discord.Embed(
        title=f"⚔️ {raid['name']}",
        description=desc,
        color=discord.Color.orange()
    )
    embed.set_footer(text=f"Создано: {raid['author_name']}")
    return embed

# ================== ГЛОБАЛЬНЫЙ ФЛАГ ДЛЯ ЗАЩИТЫ ОТ ЦИКЛА ==================
deleting_panel = False

# ================== ПАНЕЛЬ ==================
async def send_create_panel(channel):
    global deleting_panel
    if is_channel_blocked(channel.id):
        return

    deleting_panel = True  # бот сам удаляет панели
    async for msg in channel.history(limit=50):
        if msg.author == bot.user and msg.embeds and msg.embeds[0].title == "🎯 Создание рейда":
            try:
                await msg.delete()
                await asyncio.sleep(0.5)
            except:
                continue
    deleting_panel = False  # закончили удаление

    embed = discord.Embed(
        title="🎯 Создание рейда",
        description="Нажми кнопку ниже, чтобы создать новый слот рейда.",
        color=discord.Color.blue()
    )
    view = CreateRaidPanel()
    msg = await channel.send(embed=embed, view=view)

    if channel.id not in channels_data:
        channels_data.append(channel.id)
        save_json(CHANNEL_FILE, channels_data)
    return msg

# ================== ОБНОВЛЕНИЕ ПАНЕЛЕЙ ==================
@tasks.loop(seconds=UPDATE_INTERVAL)
async def refresh_panels_loop():
    for ch_id in channels_data:
        channel = bot.get_channel(ch_id)
        if not channel or is_channel_blocked(ch_id):
            continue

        found = False
        async for msg in channel.history(limit=50):
            if msg.author == bot.user and msg.embeds and msg.embeds[0].title == "🎯 Создание рейда":
                found = True
                break

        if not found:
            print(f"🔄 Панель в {channel.name} отсутствует — создаем новую")
            await send_create_panel(channel)

# ================== ВОССТАНОВЛЕНИЕ УДАЛЕННОЙ ПАНЕЛИ ==================
@bot.event
async def on_message_delete(message):
    global deleting_panel
    if deleting_panel:  # бот сам удалял — игнорируем
        return
    if not message.guild or message.author != bot.user:
        return

    if message.embeds and message.embeds[0].title == "🎯 Создание рейда":
        channel_id = message.channel.id
        if channel_id in channels_data and not is_channel_blocked(channel_id):
            await asyncio.sleep(2)
            print(f"♻️ Панель в {message.channel.name} была удалена — восстанавливаем...")
            await send_create_panel(message.channel)

# ================== КОМАНДА ДЛЯ АДМИНА ==================
@bot.command()
@commands.has_permissions(administrator=True)
async def createpanel(ctx):
    if is_channel_blocked(ctx.channel.id):
        await ctx.send("❌ Этот канал заблокирован для работы бота", delete_after=5)
        return
    await send_create_panel(ctx.channel)
    await ctx.send("✅ Панель создания рейда добавлена!", delete_after=5)

# ================== ВЗАИМОДЕЙСТВИЯ ==================
@bot.event
async def on_interaction(interaction: discord.Interaction):
    try:
        if not interaction.data:
            return
        cid = interaction.data.get("custom_id")

        if is_channel_blocked(interaction.channel.id):
            await interaction.response.send_message("❌ Действия в этом канале временно заблокированы", ephemeral=True)
            return

        # -------- Создать рейд --------
        if cid == "create_raid":
            member_roles = [r.name for r in interaction.user.roles]
            if not (interaction.user.id == ADMIN_ID or RL_ROLE_NAME in member_roles):
                await interaction.response.send_message("❌ Только админ или РЛ могут создавать рейд!", ephemeral=True)
                return

            class RaidModal(Modal, title="Создание рейда"):
                raid_name = TextInput(label="Название рейда", placeholder="Например: Рейд в Мартлок", required=True)
                raid_desc = TextInput(label="Описание", style=discord.TextStyle.long, placeholder="УРОВЕНЬ БРОНИ\n \n...", required=True)
                raid_time = TextInput(label="Время рейда", placeholder="20:00 МСК", required=True)
                raid_slots = TextInput(label="Слоты (по одной роли в строке)", style=discord.TextStyle.long, placeholder="Танк\nПорезка\nДД\nДД\n...", required=True)

                async def on_submit(self, inter_sub: discord.Interaction):
                    slots = [{"role": line.strip(), "user": None} for line in self.raid_slots.value.split("\n") if line.strip()]
                    raid = {
                        "name": self.raid_name.value,
                        "desc": self.raid_desc.value,
                        "time": self.raid_time.value,
                        "author_id": inter_sub.user.id,
                        "author_name": inter_sub.user.display_name,
                        "slots": slots,
                        "created_at": time.time(),
                        "channel_id": inter_sub.channel.id
                    }
                    msg = await inter_sub.channel.send(f"@everyone", embed=generate_embed(raid))
                    raids[str(msg.id)] = raid
                    save_json(DATA_FILE, raids)
                    await msg.edit(view=RaidSignupView(msg.id))
                    await inter_sub.response.send_message("✅ Рейд успешно создан!", ephemeral=True)
                    await asyncio.sleep(1)
                    await send_create_panel(inter_sub.channel)  # обновляем панель после создания рейда

            await interaction.response.send_modal(RaidModal())

        # -------- Записаться --------
        elif cid.startswith("signup_"):
            msg_id = cid.split("_")[1]
            raid = raids.get(msg_id)
            if not raid:
                return await interaction.response.send_message("❌ Рейд не найден", ephemeral=True)

            if any(slot['user'] == interaction.user.display_name for slot in raid['slots']):
                return await interaction.response.send_message("❌ Ты уже записан", ephemeral=True)

            class SlotModal(Modal, title="Выбор слота"):
                slot_number = TextInput(label=f"Выбери номер слота (1-{len(raid['slots'])})", placeholder="Например: 2", required=True)

                async def on_submit(self, modal_inter: discord.Interaction):
                    try:
                        num = int(self.slot_number.value)
                        if num < 1 or num > len(raid['slots']):
                            await modal_inter.response.send_message("❌ Неверный номер слота", ephemeral=True)
                            return
                    except:
                        await modal_inter.response.send_message("❌ Неверный номер слота", ephemeral=True)
                        return

                    slot = raid['slots'][num-1]
                    if slot['user']:
                        await modal_inter.response.send_message("❌ Слот занят", ephemeral=True)
                        return

                    slot['user'] = modal_inter.user.display_name
                    save_json(DATA_FILE, raids)
                    await modal_inter.message.edit(embed=generate_embed(raid), view=RaidSignupView(msg_id))
                    await modal_inter.response.send_message(f"✅ Ты записался в слот {num} ({slot['role']})", ephemeral=True)

            await interaction.response.send_modal(SlotModal())

        # -------- Отписка --------
        elif cid.startswith("leave_"):
            msg_id = cid.split("_")[1]
            raid = raids.get(msg_id)
            if not raid:
                return await interaction.response.send_message("❌ Рейд не найден", ephemeral=True)

            if not (interaction.user.id == ADMIN_ID or interaction.user.id == raid['author_id']):
                return await interaction.response.send_message("❌ Ты не можешь отписывать участников", ephemeral=True)

            class RemoveModal(Modal, title="Отписка участника"):
                slot_number = TextInput(label=f"Введите номер слота для очистки (1-{len(raid['slots'])})", required=True)

                async def on_submit(self, modal_inter: discord.Interaction):
                    try:
                        num = int(self.slot_number.value)
                        if num < 1 or num > len(raid['slots']):
                            await modal_inter.response.send_message("❌ Неверный номер слота", ephemeral=True)
                            return
                    except:
                        await modal_inter.response.send_message("❌ Неверный номер слота", ephemeral=True)
                        return

                    raid['slots'][num-1]['user'] = None
                    save_json(DATA_FILE, raids)
                    await modal_inter.message.edit(embed=generate_embed(raid), view=RaidSignupView(msg_id))
                    await modal_inter.response.send_message(f"✅ Слот {num} очищен", ephemeral=True)

            await interaction.response.send_modal(RemoveModal())

    except Exception as e:
        print(f"❌ Ошибка взаимодействия: {e}")
        traceback.print_exc()

# ================== ОЧИСТКА СТАРЫХ РЕЙДОВ ==================
@tasks.loop(minutes=30)
async def cleanup_old_raids():
    now = time.time()
    expired = [k for k,v in raids.items() if now - v.get("created_at", now) > RAID_EXPIRE]
    for k in expired:
        raid = raids[k]
        channel = bot.get_channel(raid.get("channel_id"))
        if channel:
            try:
                msg = await channel.fetch_message(int(k))
                embed = generate_embed(raid)
                embed.color = discord.Color.light_grey()
                embed.title += " [Завершён]"
                embed.description += "\n⚠️ Рейд завершён"
                await msg.edit(embed=embed, view=None)
            except:
                pass
        raids.pop(k)
    if expired:
        save_json(DATA_FILE, raids)

# ================== АВТОМАТИЧЕСКАЯ ОЧИСТКА ЛОГОВ И ФАЙЛОВ ==================
LOG_FILES = ["bot.log", "bot_output.log"]
MAX_LOG_SIZE_MB = 5
MAX_RAIDS_FILE_AGE_HOURS = 12

@tasks.loop(minutes=60)
async def cleanup_files_loop():
    now = time.time()

    # Очистка логов
    for log in LOG_FILES:
        if os.path.exists(log):
            size_mb = os.path.getsize(log) / (1024 * 1024)
            if size_mb > MAX_LOG_SIZE_MB:
                with open(log, "w", encoding="utf-8") as f:
                    f.write("")
                print(f"🧹 Очищен лог {log} ({size_mb:.1f} МБ)")

    # Очистка raids.json если нет активных рейдов
    if os.path.exists(DATA_FILE):
        raids_data = load_json(DATA_FILE, {})
        active_raids = sum(1 for r in raids_data.values() if now - r.get("created_at", now) < RAID_EXPIRE)
        if active_raids == 0:
            mtime = os.path.getmtime(DATA_FILE)
            if now - mtime > MAX_RAIDS_FILE_AGE_HOURS * 3600:
                save_json(DATA_FILE, {})
                print(f"🗑️ Очищен файл {DATA_FILE} — старых рейдов нет")

    # Очистка channel.json, если старше недели
    if os.path.exists(CHANNEL_FILE):
        mtime = os.path.getmtime(CHANNEL_FILE)
        if now - mtime > 7 * 24 * 3600:
            shutil.copy(CHANNEL_FILE, f"{CHANNEL_FILE}.bak")
            save_json(CHANNEL_FILE, [])
            print("🧾 channel.json очищен (создан бэкап .bak)")

# ================== Инициализация admin.py ==================
setup_admin(bot, channels_data)

# ================== Глобальная проверка команд ==================
@bot.check
async def global_block_check(ctx):
    return not is_channel_blocked(ctx.channel.id)

# ================== СТАРТ ==================
@bot.event
async def on_ready():
    print(f"✅ Бот запущен как {bot.user}")
    if not refresh_panels_loop.is_running():
        refresh_panels_loop.start()
    if not cleanup_old_raids.is_running():
        cleanup_old_raids.start()
    if not cleanup_files_loop.is_running():
        cleanup_files_loop.start()
    for raid_id in raids:
        bot.add_view(RaidSignupView(raid_id))

bot.run(TOKEN)
