import discord
from discord.ext import commands
from pymongo import MongoClient
from flask import Flask
import os
import threading

# Environment Variables
mongodb_uri = os.environ["MONGODB_URI"]
discord_token = os.environ["DISCORD_TOKEN"]

# MongoDB Setup
client = MongoClient(mongodb_uri)
db = client['currency_db']
collection = db['fx_balances']

# Flask App (for uptime pings or dashboard)
app = Flask(__name__)

@app.route('/')
def home():
    return 'Bot is running!', 200

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# Start Flask on another thread
flask_thread = threading.Thread(target=run_flask)
flask_thread.start()

# Discord Bot Setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Set Bot Status
@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Game(name="Flexing My Authority"))
    print(f'Bot is ready! Logged in as {bot.user}')

# Helper functions
def get_balance(user_id):
    user = collection.find_one({"user_id": user_id})
    if user:
        return user['balance']
    else:
        collection.insert_one({"user_id": user_id, "balance": 0})
        return 0

def set_balance(user_id, amount):
    collection.update_one({"user_id": user_id}, {"$set": {"balance": amount}}, upsert=True)

# Admin-only Commands
@bot.command()
@commands.has_permissions(administrator=True)
async def give(ctx, currency: str, amount: int, member: discord.Member):
    if currency.upper() != "FX":
        await ctx.send("❌ Invalid currency.")
        return

    current = get_balance(member.id)
    new_balance = current + amount
    set_balance(member.id, new_balance)

    embed = discord.Embed(title="💸 FX Given!", color=discord.Color.green())
    embed.add_field(name="User", value=member.mention, inline=True)
    embed.add_field(name="Amount", value=f"{amount} FX", inline=True)
    embed.add_field(name="New Balance", value=f"{new_balance} FX", inline=False)
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def remove(ctx, currency: str, amount: int, member: discord.Member):
    if currency.upper() != "FX":
        await ctx.send("❌ Invalid currency.")
        return

    current = get_balance(member.id)
    new_balance = max(0, current - amount)
    set_balance(member.id, new_balance)

    embed = discord.Embed(title="❌ FX Removed", color=discord.Color.red())
    embed.add_field(name="User", value=member.mention, inline=True)
    embed.add_field(name="Amount Removed", value=f"{amount} FX", inline=True)
    embed.add_field(name="New Balance", value=f"{new_balance} FX", inline=False)
    await ctx.send(embed=embed)

# Command to Check FX (Available to all)
@bot.command(name="FX")
async def fx(ctx, member: discord.Member = None):
    target = member or ctx.author
    balance = get_balance(target.id)

    embed = discord.Embed(title="💼 FX Balance", color=discord.Color.blue())
    embed.add_field(name="User", value=target.mention, inline=True)
    embed.add_field(name="Balance", value=f"{balance} FX", inline=True)
    await ctx.send(embed=embed)

# Handle permission errors
@give.error
@remove.error
async def permission_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("🚫 You need Administrator permissions to use this command.")

# Run the bot
bot.run(discord_token)
