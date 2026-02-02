import discord
from discord import app_commands
from discord.ui import Button, View
import os
from datetime import datetime
import asyncio
from aiohttp import web
import threading

# Intents の設定
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# 環境変数から設定を取得
TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_A_ID = int(os.getenv('CHANNEL_A_ID'))  # 最初の投稿先チャンネル
CHANNEL_B_ID = int(os.getenv('CHANNEL_B_ID'))  # 確認後の投稿先チャンネル

# 提出データを保存する辞書
submission_data = {}

class ConfirmButton(View):
    def __init__(self, user_id, username, timestamp, image_url, message_id):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.username = username
        self.timestamp = timestamp
        self.image_url = image_url
        self.message_id = message_id
    
    @discord.ui.button(label="確認済み", style=discord.ButtonStyle.green, custom_id="confirm_button")
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # ボタンを無効化
        button.disabled = True
        button.label = "確認完了"
        await interaction.response.edit_message(view=self)
        
        # チャンネルBに投稿
        channel_b = client.get_channel(CHANNEL_B_ID)
        if channel_b:
            embed = discord.Embed(
                title="提出が受理されました",
                color=discord.Color.green(),
                timestamp=self.timestamp
            )
            embed.add_field(name="提出者", value=self.username, inline=False)
            embed.add_field(name="提出時刻", value=self.timestamp.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
            embed.set_image(url=self.image_url)
            
            await channel_b.send(embed=embed)
        
        # ユーザーにDMを送信
        try:
            user = await client.fetch_user(self.user_id)
            await user.send("✅ 提出が受理されました。")
        except:
            pass
        
        # 提出データから削除
        if self.message_id in submission_data:
            del submission_data[self.message_id]

@client.event
async def on_ready():
    await tree.sync()
    print(f'{client.user} としてログインしました')
    print(f'チャンネルA ID: {CHANNEL_A_ID}')
    print(f'チャンネルB ID: {CHANNEL_B_ID}')

@tree.command(name="up", description="画像を提出します")
@app_commands.describe(画像="提出する画像")
async def up_command(interaction: discord.Interaction, 画像: discord.Attachment):
    # 画像かどうかを確認
    if not 画像.content_type or not 画像.content_type.startswith('image/'):
        await interaction.response.send_message("❌ 画像ファイルを指定してください。", ephemeral=True)
        return
    
    # チャンネルAを取得
    channel_a = client.get_channel(CHANNEL_A_ID)
    if not channel_a:
        await interaction.response.send_message("❌ 投稿先チャンネルが見つかりません。", ephemeral=True)
        return
    
    # 提出情報
    user = interaction.user
    timestamp = datetime.now()
    
    # Embed を作成
    embed = discord.Embed(
        title="新しい提出",
        color=discord.Color.blue(),
        timestamp=timestamp
    )
    embed.add_field(name="提出者", value=user.mention, inline=False)
    embed.add_field(name="提出時刻", value=timestamp.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
    embed.set_image(url=画像.url)
    
    # ボタン付きでチャンネルAに投稿（シークレットメッセージ）
    view = ConfirmButton(user.id, user.name, timestamp, 画像.url, None)
    message = await channel_a.send(embed=embed, view=view)
    
    # メッセージIDを保存
    view.message_id = message.id
    submission_data[message.id] = {
        'user_id': user.id,
        'username': user.name,
        'timestamp': timestamp,
        'image_url': 画像.url
    }
    
    # コマンドの応答
    await interaction.response.send_message("✅ 提出が送信されました。", ephemeral=True)

@client.event
async def on_message(message):
    # Botのメッセージは無視
    if message.author.bot:
        return
    
    # リプライかどうかを確認
    if message.reference and message.reference.message_id in submission_data:
        ref_message_id = message.reference.message_id
        data = submission_data[ref_message_id]
        
        # 元のメッセージを取得して削除
        try:
            channel_a = client.get_channel(CHANNEL_A_ID)
            original_message = await channel_a.fetch_message(ref_message_id)
            await original_message.delete()
        except:
            pass
        
        # ユーザーにDMを送信
        try:
            user = await client.fetch_user(data['user_id'])
            await user.send(f"❌ 提出が受理されませんでした。\n理由: {message.content}")
        except:
            pass
        
        # リプライメッセージを削除
        try:
            await message.delete()
        except:
            pass
        
        # 提出データから削除
        del submission_data[ref_message_id]

# 簡易 HTTP サーバー (Render の要件を満たすため)
async def handle_health(request):
    return web.Response(text="Bot is running")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_health)
    app.router.add_get('/health', handle_health)
    
    port = int(os.getenv('PORT', 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f'HTTP サーバーがポート {port} で起動しました')

async def main():
    # HTTP サーバーを起動
    asyncio.create_task(start_web_server())
    # Bot を起動
    await client.start(TOKEN)

# Bot を起動
if __name__ == "__main__":
    asyncio.run(main())
