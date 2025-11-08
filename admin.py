# admin.py
import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import time

blocked_channels = {}  # {channel_id: unblock_timestamp}
BLOCK_DURATION = 24*60*60  # 24 часа

def setup(bot: commands.Bot, channels_data):
    @bot.command()
    @commands.is_owner()
    async def admin(ctx):
        if not channels_data:
            await ctx.send("❌ Нет каналов для управления")
            return

        class AdminView(View):
            def __init__(self):
                super().__init__(timeout=None)
                # кнопка блокировки
                block_btn = Button(label="⛔ Заблокировать канал", style=discord.ButtonStyle.danger)
                block_btn.callback = self.block_callback
                self.add_item(block_btn)

                # кнопка разблокировки
                unblock_btn = Button(label="✅ Разблокировать канал", style=discord.ButtonStyle.success)
                unblock_btn.callback = self.unblock_callback
                self.add_item(unblock_btn)

            async def block_callback(self, interaction: discord.Interaction):
                await self.show_modal(interaction, block=True)

            async def unblock_callback(self, interaction: discord.Interaction):
                await self.show_modal(interaction, block=False)

            async def show_modal(self, interaction: discord.Interaction, block: bool):
                class ChannelModal(Modal, title="Выбор канала"):
                    channel_number = TextInput(label=f"Введите номер канала (1-{len(channels_data)})", placeholder="Например: 2", required=True)

                    async def on_submit(self, modal_interaction: discord.Interaction):
                        try:
                            num = int(self.channel_number.value)
                            if num < 1 or num > len(channels_data):
                                await modal_interaction.response.send_message("❌ Неверный номер канала", ephemeral=True)
                                return
                        except:
                            await modal_interaction.response.send_message("❌ Неверный ввод", ephemeral=True)
                            return

                        ch_id = channels_data[num-1]
                        if block:
                            blocked_channels[str(ch_id)] = time.time() + BLOCK_DURATION
                            await modal_interaction.response.send_message(f"⛔ Канал <#{ch_id}> заблокирован на 24 часа", ephemeral=True)
                        else:
                            if str(ch_id) in blocked_channels:
                                blocked_channels.pop(str(ch_id))
                                await modal_interaction.response.send_message(f"✅ Канал <#{ch_id}> разблокирован", ephemeral=True)
                            else:
                                await modal_interaction.response.send_message("❌ Канал не был заблокирован", ephemeral=True)

                await interaction.response.send_modal(ChannelModal())

        # выводим список каналов с их статусом
        desc = ""
        for i, ch_id in enumerate(channels_data, start=1):
            status = "🔒 Заблокирован" if str(ch_id) in blocked_channels and time.time() < blocked_channels[str(ch_id)] else "✅ Доступен"
            desc += f"{i}. <#{ch_id}> — {status}\n"

        embed = discord.Embed(title="Админ-панель", description=desc, color=discord.Color.blurple())
        await ctx.send(embed=embed, view=AdminView())
