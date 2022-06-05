import discord, time, datetime, json
from web3 import Web3
from database import DB

with open("config/config.json", "r+", encoding="utf-8") as configfile:
    config = json.load(configfile)
    
discord_client = discord.Client()

last_transaction = None

# polygon mainnet
RPC = "https://polygon-mainnet.infura.io/v3/dafe7978cb1145039d88ae648aa3278a"
chain_Id = 137

# polygon mumbai
#RPC = "https://polygon-mumbai.infura.io/v3/dafe7978cb1145039d88ae648aa3278a"
#chain_Id = 80001

def log(whatever):
    with open("logs/faucet_log.csv","a+") as f:
        f.write(f"{whatever}\n")

def check_balance(wallet):
    try:
        web3 = Web3(Web3.HTTPProvider(RPC))
        wallet = web3.toChecksumAddress(wallet)
        balance = web3.eth.getBalance(wallet)/1e18
    except Exception as e:
        print(e)
        balance = 0.0
    return balance

@discord_client.event
async def on_ready():
    print("""
               __
             <(o )___
              ( ._> /
               `---'
        """)
    print(f'* Successfully Logged in as: {discord_client.user}')
    await discord_client.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="💧 !faucet"))
    
@discord_client.event
async def on_message(message):

    # ignoring private messages to prevent abuse
    if message.channel.type is discord.ChannelType.private: 
        return

    # ignoring bot's own messages
    author = message.author
    if message.author == discord_client.user:
        return
        
    channel = message.channel

    if message.content.startswith("!balance") or message.content.startswith("!funds") or message.content.startswith("!donate") and message.channel.name in "matic-faucet":
        await message.add_reaction("✅")
        await channel.send(f" **{check_balance(config['faucet_contract'])} MATIC** is left in the faucet\n**{check_balance(config['runner_public_key'])} MATIC** is left in the runner\nConsider donating back: **{config['faucet_contract']}**", reference=message)
        
    if message.content.startswith("!credits") or message.content.startswith("!about") and message.channel.name in "matic-faucet":
        await channel.send(f":v: i was made by **cockroach#1431**, big thanks to **Schuster#0307**, **rimraf.eth#5100** for the support")  

    if message.content.startswith("!faucet") and message.channel.name in "matic-faucet":
        global last_transaction
        #if last_transaction and datetime.datetime.now() < last_transaction + datetime.timedelta(seconds=str(config['faucet_cooldown'])):
        if last_transaction and datetime.datetime.now() < last_transaction + datetime.timedelta(seconds=60):
            await channel.send(f"there's a previous pending transaction, try again in 60 seconds :stopwatch:", reference=message)
            return
    
        requester_wallet = str(message.content).replace("!faucet", "").replace(" ", "").lower()
        
        # checking discord account's age
        if time.time() - author.created_at.timestamp() < 2492000:
            await message.add_reaction("🚫")
            await channel.send(f"{author.mention}, your account must be 30 days or older to use this faucet please ask for manual sending in #support", reference=message)
            return

        # if the provided wallet is valid
        if Web3.isAddress(requester_wallet):
        
            # checking user's wallet for balance
            if check_balance(requester_wallet) > 1:
                await message.add_reaction("🚫")
                await channel.send(f"{author.mention}, you already have enough matic!", reference=message)
                return
                
            # checking address timeout 
            web3 = Web3(Web3.HTTPProvider(RPC))
            with open('faucet_contract_abi.json') as json_file:
                    abi = json.load(json_file)
            requester_wallet = web3.toChecksumAddress(requester_wallet)        
            contract = web3.eth.contract(address=web3.toChecksumAddress(config['faucet_contract']), abi=abi)
            get_wallet_timeout = contract.functions.getAddressTimeout(requester_wallet).call()
            if get_wallet_timeout > 0:
                await message.add_reaction("🚫")
                await channel.send(f"{author.mention}, too early for another faucet drop... try again later", reference=message)
                return
            else:
                pass
                
            # checking if the address has web3 
            web3 = Web3(Web3.HTTPProvider(RPC))
            with open('faucet_contract_abi.json') as json_file:
                    abi = json.load(json_file)
            requester_wallet = web3.toChecksumAddress(requester_wallet)        
            contract = web3.eth.contract(address=web3.toChecksumAddress(config['faucet_contract']), abi=abi)
            has_fweb3 = contract.functions.hasERC20Token(requester_wallet).call()
            if has_fweb3 == False:
                await message.add_reaction("🚫")
                await channel.send(f"{author.mention}, you do not have enough FWEB3 tokens. get some at <#947293158432202772>", reference=message)
                return
            else:
                pass

            # checking faucet balance
            if check_balance(config["faucet_contract"]) < 0.1 or check_balance(config["runner_public_key"]) < 0.05:
                await message.add_reaction("😭")
                await channel.send(f"{author.mention}, the faucet/runner is currently dry, <@697236677382635541> <@231584498058395648> <@899723104211836949> <@636924911390294030> <@730160616815198258> <@541851538445041665> <@698494149627740230>", reference=message)
                return

            # sending fweb3 tokens
            last_transaction = datetime.datetime.now()
            await message.add_reaction("✅")
            web3 = Web3(Web3.HTTPProvider(RPC))
            try:
                with open('faucet_contract_abi.json') as json_file:
                    abi = json.load(json_file)
                receiver = web3.toChecksumAddress(requester_wallet)
                contract = web3.eth.contract(address=web3.toChecksumAddress(config['faucet_contract']), abi=abi)
                nonce = web3.eth.getTransactionCount(config["runner_public_key"])
                function = contract.functions.faucet(receiver).buildTransaction({'chainId':chain_Id, 'gas': 100000,'gasPrice': web3.eth.gas_price, 'nonce':nonce})
                sign_txn = web3.eth.account.signTransaction(function, private_key=config["runner_private_key"])
                raw_tx = web3.eth.sendRawTransaction(sign_txn.rawTransaction)
                tx_hash = web3.toHex(raw_tx)
                if tx_hash:
                    log(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')};{receiver}")
                    # adding the info to our db
                    DB.save(author.name, author.id, requester_wallet, tx_hash)
                    embed=discord.Embed(title=f"**Faucet was sent**", description=f"Hey {author.name}, MATIC has been sent to your wallet!\n\nhttps://polygonscan.com/tx/{tx_hash}")
                    embed.set_footer(text=f"Please consider donating back to the faucet to help other members", icon_url="https://i.imgur.com/QNdjlfV.png")
                    embed.set_thumbnail(url="https://i.imgur.com/PtQbDjd.png")
                    await channel.send(embed=embed, reference=message)
                else:
                    embed=discord.Embed(title=f"**Faucet failed!**", description=f"Hey {author.name}, please try again..")
                    embed.set_footer(text=f"Please consider donating back to the faucet to help other members", icon_url="https://i.imgur.com/QNdjlfV.png")
                    embed.set_thumbnail(url="https://i.imgur.com/OpBmtzX.png")
                    await channel.send(embed=embed, reference=message)
            except Exception as e:
                print(e)
                log(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')};{e}")
                pass
        else:
            await message.add_reaction("🚫")
            await channel.send(f"{author.mention}, invalid wallet was provided. **Usage**: !faucet YOUR_METAMASK_WALLET")

discord_client.run(config["bot_token"])
