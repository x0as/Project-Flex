import os
import discord
from discord.ext import commands
from discord import app_commands
from pymongo import MongoClient
from flask import Flask
import threading

# Load environment variables
MONGODB_URI = os.environ.get("MONGODB_URI")
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")

# MongoDB Setup
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client["currency_bot"]
users = db["users"]

# Flask for Uptime
app = Flask(__name__)
@app.route("/")
def home():
    return "Bot is running!"
def run_flask():
    app.run(host="0.0.0.0", port=5000)
threading.Thread(target=run_flask).start()

# Discord Intents
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

# Bot Definition
class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.synced = False

    async def setup_hook(self):
        if not self.synced:
            await self.tree.sync()
            self.synced = True

    async def on_ready(self):
        print(f"✅ Logged in as {self.user} (ID: {self.user.id})")
        await self.change_presence(activity=discord.Game(name="Flexing My Authority"))

bot = MyBot()

# /give command
@bot.tree.command(name="give", description="Give FX to a user (Admin only)")
@app_commands.describe(user="User to give FX to", amount="Amount of FX to give")
async def give(interaction: discord.Interaction, user: discord.Member, amount: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("🚫 You need admin permissions to use this command.", ephemeral=True)
        return

    users.update_one({"_id": user.id}, {"$inc": {"fx": amount}}, upsert=True)
    await interaction.response.send_message(embed=discord.Embed(
        title="✅ FX Given",
        description=f"{user.mention} received **{amount} FX**.",
        color=0x00ff00
    ))

# /remove command
@bot.tree.command(name="remove", description="Remove FX from a user (Admin only)")
@app_commands.describe(user="User to remove FX from", amount="Amount of FX to remove")
async def remove(interaction: discord.Interaction, user: discord.Member, amount: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("🚫 You need admin permissions to use this command.", ephemeral=True)
        return

    users.update_one({"_id": user.id}, {"$inc": {"fx": -amount}}, upsert=True)
    await interaction.response.send_message(embed=discord.Embed(
        title="❌ FX Removed",
        description=f"{user.mention} lost **{amount} FX**.",
        color=0xff0000
    ))

# /fx command
@bot.tree.command(name="fx", description="Check FX balance")
@app_commands.describe(user="User to check FX of (optional)")
async def fx(interaction: discord.Interaction, user: discord.Member = None):
    user = user or interaction.user
    data = users.find_one({"_id": user.id}) or {"fx": 0}

    await interaction.response.send_message(embed=discord.Embed(
        title="💰 FX Balance",
        description=f"{user.mention} has **{data['fx']} FX**.",
        color=0x3498db
    ))

# /leaderboard command
@bot.tree.command(name="leaderboard", description="Show the top FX holders")
async def leaderboard(interaction: discord.Interaction):
    top_users = list(users.find().sort("fx", -1).limit(10))
    if not top_users:
        await interaction.response.send_message("No FX data found.")
        return

    lines = []
    for i, user_data in enumerate(top_users, start=1):
        member = interaction.guild.get_member(user_data["_id"])
        fx = user_data.get("fx", 0)
        name = member.mention if member else f"User `{user_data['_id']}`"
        lines.append(f"**#{i}** {name} — **{fx} FX**")

    await interaction.response.send_message(embed=discord.Embed(
        title="🏆 FX Leaderboard",
        description="\n".join(lines),
        color=0xf1c40f
    ))

# /redeem command
@bot.tree.command(name="redeem", description="Redeem FX for services from Flex Harder (min 100 FX)")
@app_commands.describe(
    service="Service you want (e.g. Promotion, Boost, Shoutout)",
    platform="Platform (e.g. Instagram, YouTube, TikTok)",
    link="Link to your profile or post"
)
async def redeem(interaction: discord.Interaction, service: str, platform: str, link: str):
    user_id = interaction.user.id
    user_data = users.find_one({"_id": user_id}) or {"fx": 0}

    if user_data["fx"] < 100:
        await interaction.response.send_message("🚫 You need at least 100 FX to redeem a service.", ephemeral=True)
        return

    category_id = 1376138636445225081  # Replace with your category ID
    guild = interaction.guild
    category = guild.get_channel(category_id)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        guild.owner: discord.PermissionOverwrite(read_messages=True),
        interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }

    channel_name = f"redeem-{interaction.user.name}".replace(" ", "-").lower()
    private_channel = await guild.create_text_channel(channel_name, category=category, overwrites=overwrites)

    users.update_one({"_id": user_id}, {"$inc": {"fx": -100}}, upsert=True)

    await private_channel.send(
        f"🎟️ **New Redemption Request**\n"
        f"👤 User: {interaction.user.mention}\n"
        f"🛠️ Platform: **{platform}**\n"
        f"📌 Service: **{service}**\n"
        f"🔗 Link: {link}\n"
        f"💳 Cost: **100 FX**"
    )

    await interaction.response.send_message(
        f"✅ Redeemed! Check your private channel: {private_channel.mention}",
        ephemeral=True
    )

# Run the bot
bot.run(DISCORD_TOKEN)
