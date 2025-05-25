import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
from pymongo import MongoClient
from flask import Flask
import threading

# ENVIRONMENT VARIABLES
MONGODB_URI = os.environ.get("MONGODB_URI")
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")

# MongoDB Setup
mongo_client = MongoClient(MONGODB_URI)
db = mongo_client["currency_bot"]
users = db["users"]

# Discord Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

# Bot Setup
class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.synced = False

    async def on_ready(self):
        if not self.synced:
            await self.tree.sync()
            self.synced = True
        await self.change_presence(activity=discord.Game(name="Flexing My Authority"))
        print(f"Logged in as {self.user} (ID: {self.user.id})")

bot = MyBot()

# Flask Web Server
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    app.run(host='0.0.0.0', port=5000)

threading.Thread(target=run_flask).start()

# /give Command
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

# /remove Command
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

# /fx Command
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

bot.run(DISCORD_TOKEN)
