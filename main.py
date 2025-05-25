import os
import discord
from discord.ext import commands
from discord import app_commands
from pymongo import MongoClient
from flask import Flask
import threading

# Load environment variables (set manually in deployment env)
MONGODB_URI = os.environ.get("MONGODB_URI")
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")

# MongoDB Setup
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client["currency_bot"]
users = db["users"]

# Flask Setup
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=5000)

threading.Thread(target=run_flask).start()

# Discord Bot Setup
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.synced = False

    async def setup_hook(self):
        if not self.synced:
            await self.tree.sync()
            self.synced = True

    async def on_ready(self):
        await self.change_presence(activity=discord.Game(name="Flexing My Authority"))
        print(f"✅ Logged in as {self.user} (ID: {self.user.id})")

bot = MyBot()

# /give Command (Admin only)
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

# /remove Command (Admin only)
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

# /fx Command (View own or other's FX)
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

# /leaderboard Command (Top FX holders)
@bot.tree.command(name="leaderboard", description="Show the top FX holders in the server")
async def leaderboard(interaction: discord.Interaction):
    await interaction.response.defer()
    guild = interaction.guild
    top_users = list(users.find().sort("fx", -1).limit(10))

    if not top_users:
        await interaction.followup.send("No FX data found.")
        return

    leaderboard_lines = []
    for i, user_data in enumerate(top_users, start=1):
        member = guild.get_member(user_data["_id"])
        if member:
            leaderboard_lines.append(f"**#{i}** {member.mention} - **{user_data.get('fx', 0)} FX**")
        else:
            leaderboard_lines.append(f"**#{i}** Unknown User (`{user_data['_id']}`) - **{user_data.get('fx', 0)} FX**")

    embed = discord.Embed(
        title="🏆 FX Leaderboard",
        description="\n".join(leaderboard_lines),
        color=0xf1c40f
    )
    await interaction.followup.send(embed=embed)

# Start the bot
bot.run(DISCORD_TOKEN)
