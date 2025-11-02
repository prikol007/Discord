import os
import discord
from discord.ext import commands
from discord.ui import Button, View
from dotenv import load_dotenv

# ==============================
# Загрузка токена из .env
# ==============================
load_dotenv()
TOKEN = os.getenv("TOKEN")

if TOKEN is None:
    raise ValueError("Токен Discord не задан! Проверьте переменные окружения.")

# ==============================
# Настройки Discord-бота
# ==============================
intents = discord.Intents.default()
intents.message_content = True

# ==============================
# Хранилище слотов и сообщений
# ==============================
current_slots = {}
last_embed_message = None

# ==============================
# Кнопки для записи и удаления
# ==============================
class RoleButton(Button):
    def __init__(self, slot_number, slot_name):
        super().__init__(label=slot_name, style=discord.ButtonStyle.primary)
        self.slot_number = slot_number
        self.slot_name = slot_name

    async def callback(self, interaction: discord.Interaction):
        global current_slots, last_embed_message

        # Проверяем, не записан ли уже пользователь
        for slot_id, info in cuimport os
import discord
from discord.ext import commands
from discord.ui import Button, View
from dotenv import load_dotenv

# ==============================
# Загрузка токена из .env
# ==============================
load_dotenv()
TOKEN = os.getenv("TOKEN")

if TOKEN is None:
    raise ValueError("Токен Discord не задан! Проверьте переменные окружения.")

# ==============================
# Настройки Discord-бота
# ==============================
intents = discord.Intents.default()
intents.message_content = True

# ==============================
# Хранилище слотов и сообщений
# ==============================
current_slots = {}
last_embed_message = None

# ==============================
# Кнопки для записи и удаления
# ==============================
class RoleButton(Button):
    def __init__(self, slot_number, slot_name):
        super().__init__(label=slot_name, style=discord.ButtonStyle.primary)
        self.slot_number = slot_number
        self.slot_name = slot_name

    async def callback(self, interaction: discord.Interaction):
        global current_slots, last_embed_message

        # Проверяем, не записан ли уже пользователь
        for slot_id, info in current_slots.items():
            if info["user"] == interaction.user:
                await interaction.response.send_message(
                    f"❌ Вы уже записаны на слот {info['name']}. Сначала отпишитесь.",
                    ephemeral=True
                )
                return

        # Проверяем, не занят ли слот
        if current_slots[self.slot_number]["user"] is not None:
            await interaction.response.send_message(
                f"❌ Слот {self.slot_name} уже занят: {current_slots[self.slot_number]['user'].mention}",
                ephemeral=True
            )
            return

        # Записываем пользователя
        current_slots[self.slot_number]["user"] = interaction.user
        await update_message(last_embed_message, current_user=interaction.user)
        await interaction.response.send_message(
            f"✅ Вы записаны на слот {self.slot_name}", ephemeral=True
        )


class LeaveButton(Button):
    def __init__(self, slot_number, slot_name):
        super().__init__(label="Отписаться", style=discord.ButtonStyle.danger)
        self.slot_number = slot_number
        self.slot_name = slot_name

    async def callback(self, interaction: discord.Interaction):
        global current_slots, last_embed_message

        if current_slots[self.slot_number]["user"] != interaction.user:
            await interaction.response.send_message(
                "❌ Вы не записаны на этот слот.", ephemeral=True
            )
            return

        current_slots[self.slot_number]["user"] = None
        await update_message(last_embed_message, current_user=interaction.user)
        await interaction.response.send_message(
            f"✅ Вы отписались от слота {self.slot_name}", ephemeral=True
        )


# ==============================
# Генерация кнопок и обновлений
# ==============================
class SignupView(View):
    def __init__(self, user=None):
        super().__init__(timeout=None)
        added_leave = set()
        for slot_id, info in current_slots.items():
            # Кнопка "Записаться"
            self.add_item(RoleButton(slot_id, info["name"]))
            # Кнопка "Отписаться" только один раз для пользователя
            if user and info["user"] == user and slot_id not in added_leave:
                self.add_item(LeaveButton(slot_id, info["name"]))
                added_leave.add(slot_id)


async def update_message(message, current_user=None):
    if not message:
        return
    embed = discord.Embed(title="Запись на поход", color=0x00ff99)
    desc = ""
    for slot_id, info in current_slots.items():
        if info["user"]:
            desc += f"{slot_id}. ✅ {info['name']} — {info['user'].mention}\n"
        else:
            desc += f"{slot_id}. ⬜ {info['name']} — свободно\n"
    embed.description = desc
    try:
        await message.edit(embed=embed, view=SignupView(user=current_user))
    except discord.NotFound:
        # Сообщение уже удалено, обнуляем ссылку
        global last_embed_message
        last_embed_message = None


# ==============================
# Команды бота
# ==============================
def setup_commands(bot):
    @bot.command()
    async def create(ctx, *, text):
        """Создаёт запись с кнопками для выбора слотов."""
        global current_slots, last_embed_message
        current_slots = {}

        lines = text.split("\n")
        header_lines = []
        slot_lines = []

        # Разделяем текст на заголовок и слоты
        for line in lines:
            if line.strip().startswith(tuple(str(i) for i in range(1, 10))):
                slot_lines.append(line.strip())
            else:
                header_lines.append(line.strip())

        # Заполняем слоты
        for idx, line in enumerate(slot_lines, start=1):
            slot_name = line.split(".", 1)[-1].strip()
            current_slots[idx] = {"name": slot_name, "user": None}

        # Создаём embed
        embed = discord.Embed(
            title="Запись на поход",
            description="\n".join(header_lines),
            color=0x00ff99
        )

        # Добавляем состояние слотов
        slot_status = "\n".join([f"{i}. ⬜ {info['name']} — свободно" for i, info in current_slots.items()])
        embed.add_field(name="Слоты", value=slot_status, inline=False)

        # Отправляем сообщение с кнопками
        view = SignupView()
        last_embed_message = await ctx.send(embed=embed, view=view)

        # Попытка удалить команду пользователя (обрабатываем NotFound)
        try:
            await ctx.message.delete()
        except discord.NotFound:
            pass


# ==============================
# Запуск бота
# ==============================
if __name__ == "__main__":
    bot = commands.Bot(command_prefix="!", intents=intents)
    setup_commands(bot)
    bot.run(TOKEN)

