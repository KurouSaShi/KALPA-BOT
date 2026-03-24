import discord
from discord import app_commands
from discord.ui import Button, View
import os
import json
from datetime import datetime
import asyncio
from aiohttp import web

# Intents の設定
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# 環境変数から設定を取得
TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_A_ID = int(os.getenv('CHANNEL_A_ID'))
CHANNEL_B_ID = int(os.getenv('CHANNEL_B_ID'))

# 提出データの永続化ファイル
SUBMISSION_FILE = "submissions.json"

# --- submission_data の永続化ヘルパー ---

def load_submissions() -> dict:
    if os.path.exists(SUBMISSION_FILE):
        with open(SUBMISSION_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        # キーを int に戻す、timestamp を datetime に戻す
        return {
            int(k): {**v, "timestamp": datetime.fromisoformat(v["timestamp"])}
            for k, v in raw.items()
        }
    return {}

def save_submissions(data: dict):
    serializable = {
        str(k): {**v, "timestamp": v["timestamp"].isoformat()}
        for k, v in data.items()
    }
    with open(SUBMISSION_FILE, "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)

submission_data: dict = {}


# --- Persistent View ---

class ConfirmButton(View):
    """
    timeout=None かつ custom_id を固定にすることで Persistent View になる。
    再起動後も on_ready で add_view() すれば動く。
    コールバック内では submission_data には頼らず、
    Embed から直接データを復元する。
    """

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="確認済み",
        style=discord.ButtonStyle.green,
        custom_id="confirm_button_v1",   # ★ 固定の custom_id
    )
    async def confirm_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        # --- Embed からデータを復元 ---
        embed = interaction.message.embeds[0]
        image_url = embed.image.url if embed.image else None
        timestamp = embed.timestamp  # discord.py が datetime として返す

        # フィールド[0] は "提出者" → mention 文字列 (<@USER_ID>)
        mention_value = embed.fields[0].value  # 例: "<@123456789>"
        try:
            user_id = int(mention_value.strip("<@!>"))
        except ValueError:
            user_id = None

        # ボタンを無効化して即レスポンス
        button.disabled = True
        button.label = "確認完了"
        await interaction.response.edit_message(view=self)

        # チャンネル B に投稿
        try:
            channel_b = await client.fetch_channel(CHANNEL_B_ID)
        except Exception:
            channel_b = None
        if channel_b and image_url:
            b_embed = discord.Embed(
                title="提出が受理されました",
                color=discord.Color.green(),
                timestamp=timestamp,
            )
            b_embed.add_field(name="提出者", value=mention_value, inline=False)
            if timestamp:
                b_embed.add_field(
                    name="提出時刻",
                    value=timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    inline=False,
                )
            b_embed.set_image(url=image_url)
            await channel_b.send(embed=b_embed)

        # チャンネル A の元メッセージを削除
        try:
            await interaction.message.delete()
        except Exception:
            pass

        # ユーザーに DM
        if user_id:
            try:
                user = await client.fetch_user(user_id)
                dm_embed = discord.Embed(
                    title="✅ 提出が受理されました",
                    color=discord.Color.green(),
                    timestamp=timestamp,
                )
                if timestamp:
                    dm_embed.add_field(
                        name="提出時刻",
                        value=timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                        inline=False,
                    )
                if image_url:
                    dm_embed.set_image(url=image_url)
                await user.send(embed=dm_embed)
            except Exception:
                pass

        # submission_data からも削除（存在すれば）
        msg_id = interaction.message.id
        if msg_id in submission_data:
            del submission_data[msg_id]
            save_submissions(submission_data)


# --- イベント ---

@client.event
async def on_ready():
    # ★ 起動時に Persistent View を再登録する
    client.add_view(ConfirmButton())

    # 永続化ファイルから submission_data を復元
    global submission_data
    submission_data = load_submissions()

    await tree.sync()
    print(f"{client.user} としてログインしました")
    print(f"チャンネルA ID: {CHANNEL_A_ID}")
    print(f"チャンネルB ID: {CHANNEL_B_ID}")
    print(f"未処理の提出数: {len(submission_data)}")


@tree.command(name="up", description="リザルトを提出します")
@app_commands.describe(画像="提出する画像")
async def up_command(interaction: discord.Interaction, 画像: discord.Attachment):
    if not 画像.content_type or not 画像.content_type.startswith("image/"):
        await interaction.response.send_message(
            "❌ 画像ファイルを指定してください。", ephemeral=True
        )
        return

    try:
        channel_a = await client.fetch_channel(CHANNEL_A_ID)
    except Exception:
        await interaction.response.send_message(
            "❌ 投稿先チャンネルが見つかりません。", ephemeral=True
        )
        return

    user = interaction.user
    timestamp = datetime.now()

    embed = discord.Embed(
        title="新しい提出",
        color=discord.Color.blue(),
        timestamp=timestamp,
    )
    embed.add_field(name="提出者", value=user.mention, inline=False)
    embed.add_field(
        name="提出時刻", value=timestamp.strftime("%Y-%m-%d %H:%M:%S"), inline=False
    )
    embed.set_image(url=画像.url)

    # ★ ConfirmButton() は引数なし
    message = await channel_a.send(embed=embed, view=ConfirmButton())

    # submission_data に保存（リプライ却下用）して永続化
    submission_data[message.id] = {
        "user_id": user.id,
        "username": user.name,
        "timestamp": timestamp,
        "image_url": 画像.url,
    }
    save_submissions(submission_data)

    await interaction.response.send_message(
        "✅ リザルトが送信されました。", ephemeral=True
    )


@client.event
async def on_message(message):
    if message.author.bot:
        return

    if (
        message.reference
        and message.reference.message_id in submission_data
    ):
        ref_id = message.reference.message_id
        data = submission_data[ref_id]

        # チャンネル B に却下通知
        try:
            channel_b = await client.fetch_channel(CHANNEL_B_ID)
        except Exception:
            channel_b = None
        if channel_b:
            embed = discord.Embed(
                title="提出が却下されました",
                color=discord.Color.red(),
                timestamp=data["timestamp"],
            )
            embed.add_field(name="提出者", value=data["username"], inline=False)
            embed.add_field(
                name="提出時刻",
                value=data["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                inline=False,
            )
            embed.add_field(name="却下理由", value=message.content, inline=False)
            embed.set_image(url=data["image_url"])
            await channel_b.send(embed=embed)

        # チャンネル A の元メッセージを削除
        try:
            channel_a = await client.fetch_channel(CHANNEL_A_ID)
            original = await channel_a.fetch_message(ref_id)
            await original.delete()
        except Exception:
            pass

        # ユーザーに DM
        try:
            user = await client.fetch_user(data["user_id"])
            dm_embed = discord.Embed(
                title="❌ リザルトが受理されませんでした",
                color=discord.Color.red(),
                timestamp=data["timestamp"],
            )
            dm_embed.add_field(
                name="提出時刻",
                value=data["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                inline=False,
            )
            dm_embed.add_field(name="理由", value=message.content, inline=False)
            dm_embed.set_image(url=data["image_url"])
            await user.send(embed=dm_embed)
        except Exception:
            pass

        # リプライ自体を削除
        try:
            await message.delete()
        except Exception:
            pass

        del submission_data[ref_id]
        save_submissions(submission_data)


# --- HTTP サーバー (Render 用) ---

async def handle_health(request):
    return web.Response(text="Bot is running")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_health)
    app.router.add_get("/health", handle_health)
    port = int(os.getenv("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()
    print(f"HTTP サーバーがポート {port} で起動しました")

async def main():
    asyncio.create_task(start_web_server())
    await client.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
