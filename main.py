import os
import discord
from discord.ext import commands
from discord import app_commands
from pymongo import MongoClient
from flask import Flask
import threading
import matplotlib.pyplot as plt
from datetime import datetime
import io

# Load environment variables
MONGODB_URI = os.environ.get("MONGODB_URI")
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")

# MongoDB Setup
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client["currency_bot"]
users = db["users"]
history = db["fx_history"]
settings = db["settings"]  # For storing log channel

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

# Helper: Check if member has the required role
def has_role(member, role_id):
    return any(role.id == role_id for role in getattr(member, "roles", []))

# Helper: Send log message to logs channel
async def send_log(guild, message):
    config = settings.find_one({"_id": "log_channel"})
    if config:
        channel_id = config.get("channel_id")
        if channel_id:
            channel = guild.get_channel(channel_id)
            if channel:
                await channel.send(message)

# FX Historical Rate Tracker (for internal use)
def update_fx_history():
    total_fx = sum(user.get("fx", 0) for user in users.find())
    total_invites = users.count_documents({"fx": {"$gt": 0}})
    value_per_invite = round(total_fx / total_invites, 2) if total_invites > 0 else 0
    history.insert_one({
        "timestamp": datetime.utcnow(),
        "value_per_invite": value_per_invite
    })

# /give command
@bot.tree.command(name="give", description="Give FX to a user (Admin only)")
@app_commands.describe(user="User to give FX to", amount="Amount of FX to give")
async def give(interaction: discord.Interaction, user: discord.Member, amount: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("🚫 You need admin permissions to use this command.", ephemeral=True)
        return
    users.update_one({"_id": user.id}, {"$inc": {"fx": amount}}, upsert=True)
    update_fx_history()
    # Log in fx_history
    history.insert_one({
        "timestamp": datetime.utcnow(),
        "user_id": user.id,
        "amount": amount,
        "reason": "give",
        "from_user": interaction.user.id,
    })
    await interaction.response.send_message(embed=discord.Embed(
        title="✅ FX Given",
        description=f"{user.mention} received **{amount} FX**.",
        color=0x00ff00
    ))
    await send_log(interaction.guild, f"🟢 {interaction.user.mention} gave {amount} FX to {user.mention}")

# /remove command
@bot.tree.command(name="remove", description="Remove FX from a user (Admin only)")
@app_commands.describe(user="User to remove FX from", amount="Amount of FX to remove")
async def remove(interaction: discord.Interaction, user: discord.Member, amount: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("🚫 You need admin permissions to use this command.", ephemeral=True)
        return
    users.update_one({"_id": user.id}, {"$inc": {"fx": -amount}}, upsert=True)
    update_fx_history()
    # Log in fx_history
    history.insert_one({
        "timestamp": datetime.utcnow(),
        "user_id": user.id,
        "amount": -amount,
        "reason": "remove",
        "from_user": interaction.user.id,
    })
    await interaction.response.send_message(embed=discord.Embed(
        title="❌ FX Removed",
        description=f"{user.mention} lost **{amount} FX**.",
        color=0xff0000
    ))
    await send_log(interaction.guild, f"🔴 {interaction.user.mention} removed {amount} FX from {user.mention}")

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
    top_users = list(users.find().sort("fx", -1).limit(15))
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

# /reset command
@bot.tree.command(name="reset", description="Reset a user's FX to 0 (Admin only)")
@app_commands.describe(user="User whose FX will be reset to 0")
async def reset(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("🚫 You need admin permissions to use this command.", ephemeral=True)
        return
    users.update_one({"_id": user.id}, {"$set": {"fx": 0}}, upsert=True)
    update_fx_history()
    # Log in fx_history
    history.insert_one({
        "timestamp": datetime.utcnow(),
        "user_id": user.id,
        "amount": 0,
        "reason": "reset",
        "from_user": interaction.user.id,
    })
    await interaction.response.send_message(embed=discord.Embed(
        title="🔄 FX Reset",
        description=f"{user.mention}'s FX has been reset to **0**.",
        color=0x95a5a6
    ))
    await send_log(interaction.guild, f"🔄 {interaction.user.mention} reset {user.mention}'s FX to 0")

# /redeem command
@bot.tree.command(name="redeem", description="Redeem FX for services from Flex Harder (min 100 FX)")
@app_commands.describe(service="Service you want", platform="Platform", link="Link to your profile/post")
async def redeem(interaction: discord.Interaction, service: str, platform: str, link: str):
    user_id = interaction.user.id
    user_data = users.find_one({"_id": user_id}) or {"fx": 0}
    if user_data["fx"] < 100:
        await interaction.response.send_message("🚫 You need at least 100 FX to redeem a service.", ephemeral=True)
        return
    category_id = 1376138636445225081
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
    update_fx_history()
    # Log in fx_history
    history.insert_one({
        "timestamp": datetime.utcnow(),
        "user_id": user_id,
        "amount": -100,
        "reason": "redeem",
        "service": service,
        "platform": platform,
        "link": link,
        "from_user": interaction.user.id,
    })
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
    await send_log(interaction.guild, f"🎟️ {interaction.user.mention} redeemed 100 FX for {service} ({platform}) - {link}")

# /currency_rate command
@bot.tree.command(name="currency_rate", description="View FX value per invite over time as a graph")
async def currency_rate(interaction: discord.Interaction):
    await interaction.response.defer()
    records = list(history.find().sort("timestamp", 1))
    if not records:
        await interaction.followup.send("📉 No FX history available yet.")
        return

    timestamps = [rec["timestamp"] for rec in records if "value_per_invite" in rec]
    values = [rec["value_per_invite"] for rec in records if "value_per_invite" in rec]

    if not timestamps or not values:
        await interaction.followup.send("📉 No FX history available yet.")
        return

    plt.figure(figsize=(10, 5))
    plt.plot(timestamps, values, marker="o", linestyle="-", color="blue")
    plt.title("FX Value Per Invite Over Time")
    plt.xlabel("Date")
    plt.ylabel("Value per Invite (FX)")
    plt.xticks(rotation=45)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    plt.close()

    file = discord.File(fp=buf, filename="fx_currency_rate.png")
    await interaction.followup.send(content="📈 Historical FX Currency Rate:", file=file)

# /history command (role restricted)
@bot.tree.command(name="history", description="Show a user's FX transaction history (allowed roles only)")
@app_commands.describe(user="User whose FX transaction history to show")
async def history_cmd(interaction: discord.Interaction, user: discord.Member):
    # Allow users with either of the two specific role IDs
    allowed_roles = [1376114172181483582, 1376114369842253884]
    if not any(has_role(interaction.user, role_id) for role_id in allowed_roles):
        await interaction.response.send_message("🚫 You don't have permission to use this command.", ephemeral=True)
        return

    # Get the user's transaction history (last 20)
    records = list(history.find({"user_id": user.id}).sort("timestamp", -1).limit(20))
    if not records:
        await interaction.response.send_message(f"No FX transaction history found for {user.mention}.", ephemeral=True)
        return

    lines = []
    for rec in records:
        date = rec.get("timestamp")
        if isinstance(date, datetime):
            date = date.strftime('%Y-%m-%d %H:%M')
        amount = rec.get("amount", 0)
        reason = rec.get("reason", "Unknown")
        from_user = rec.get("from_user", None)
        service = rec.get("service", "")
        platform = rec.get("platform", "")
        link = rec.get("link", "")
        # Compose message
        base = f"{date}: `{amount:+} FX` via `{reason}`"
        if reason == "redeem":
            base += f" for `{service}` on `{platform}` (<{link}>)"
        if from_user:
            base += f" (by <@{from_user}>)"
        lines.append(base)

    await interaction.response.send_message(
        embed=discord.Embed(
            title=f"📜 FX History for {user.display_name}",
            description="\n".join(lines),
            color=0x7289da
        ),
        ephemeral=True
    )

# /logs set #channel command (role restricted)
@bot.tree.command(name="logs", description="Configure log channel (1376114172181483582 only)")
@app_commands.describe(channel="Channel to set as logs channel")
async def logs(interaction: discord.Interaction, channel: discord.TextChannel):
    if not has_role(interaction.user, 1376114172181483582):
        await interaction.response.send_message("🚫 You don't have permission to use this command.", ephemeral=True)
        return
    # Save the logs channel ID in settings
    settings.update_one({"_id": "log_channel"}, {"$set": {"channel_id": channel.id}}, upsert=True)
    await interaction.response.send_message(f"✅ Logs channel set to {channel.mention}", ephemeral=True)

# Run the bot
bot.run(DISCORD_TOKEN)
