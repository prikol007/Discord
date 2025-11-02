import os
import discord
from discord.ext import commands
from discord.ui import Button, View
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
TOKEN = os.getenv("TOKEN")
if TOKEN is None:
    raise ValueError("Токен Discord не задан!")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

current_slots = {}
last_embed_message = None

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
        global current_slots, last_embed_message

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
        await update_message(current_user=interaction.user)
        await interaction.response.send_message(
            f"✅ Вы записаны на слот {self.slot_name}", ephemeral=True)

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
        await update_message(current_user=interaction.user)
        await interaction.response.send_message(
            f"✅ Вы отписались от слота {self.slot_name}", ephemeral=True)

class SignupView(View):
    def __init__(self, current_user=None):
        super().__init__(timeout=None)
        for slot_id, info in current_slots.items():
            self.add_item(RoleButton(slot_id, info["name"]))
        if current_user:
            for slot_id, info in current_slots.items():
                if info["user"] == current_user:
                    self.add_item(LeaveButton(slot_id, info["name"]))

async def update_message(current_user=None):
    global last_embed_message
    if not last_embed_message:
        return

    now = datetime.now()
    title = f"Запись {now.strftime('%H:%M %d.%m')}"

    embed = discord.Embed(
        title=title,
        description=last_embed_message.embeds[0].description,
        color=0x00ff99
    )

    desc = ""
    for slot_id, info in current_slots.items():
        slot_display = add_emoji(info["name"])
        if info["user"]:
            desc += f"{slot_id}. ✅ {slot_display} — {info['user'].mention}\n"
        else:
            desc += f"{slot_id}. ⬜ {slot_display} — свободно\n"

    embed.add_field(name="Слоты", value=desc, inline=False)

    await last_embed_message.edit(embed=embed, view=SignupView(current_user))

@bot.command()
async def create(ctx, *, text):
    global current_slots, last_embed_message
    current_slots = {}

    lines = text.split("\n")
    header_lines = []
    slot_lines = []

    for line in lines:
        if line.strip() and line.strip()[0].isdigit():
            slot_lines.append(line.strip())
        else:
            header_lines.append(line.strip())

    for idx, line in enumerate(slot_lines, start=1):
        slot_name = line.split(" ", 1)[-1].strip()
        current_slots[idx] = {"name": slot_name, "user": None}

    now = datetime.now()
    title = f"Запись {now.strftime('%H:%M %d.%m')}"

    embed = discord.Embed(
        title=title,
        description="\n".join(header_lines),
        color=0x00ff99
    )

    slot_status = "\n".join([f"{i}. ⬜ {add_emoji(info['name'])} — свободно"
                             for i, info in current_slots.items()])
    embed.add_field(name="Слоты", value=slot_status, inline=False)

    last_embed_message = await ctx.send(content="@everyone", embed=embed, view=SignupView())

    try:
        await ctx.message.delete()
    except:
        pass

bot.run(TOKEN)
