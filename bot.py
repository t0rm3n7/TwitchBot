import os
from abc import ABC
from twitchio.ext import commands
import asyncio
import random
import time
import sqlite3
from sqlite3 import Error
import LiveCheck
import functools
import re
from Raffle import Raffle
import pickle
from NootVsDoot import NootVsDoot


timer = 0
notmemes = [
    "Milli Vanilli is not a meme!",
    "Blame it on the Rain is not a meme!",
    "Pizza Time is not a meme!",
    "It's not a murder basement!",
    "The gnomes are just sleeping!"
    ]

timeList = [
    "Planck time unit", "yoctosecond", "zeptosecond", "attosecond", "femtosecond", "picosecond", "nanosecond",
    "microsecond", "millisecond", "second", "minute", "hour", "day", "week", "fortnight", "month", "year",
    "olympiad", "decade", "gigasecond", "century", "millenium", "aeon"
    ]

# botloop = asyncio.new_event_loop()


class Bot(commands.Bot, ABC):  # set up the bot
    def __init__(self):
        super().__init__(
            irc_token=os.environ['TMI_TOKEN'],
            client_id=os.environ['CLIENT_ID'],
            client_secret=os.environ['CLIENT_SECRET'],
            api_token=os.environ['API_TOKEN'],
            scopes=[os.environ['SCOPES']],
            nick=os.environ['BOT_NICK'],
            prefix=os.environ['BOT_PREFIX'],
            initial_channels=[os.environ['CHANNEL']]
        )

    async def OAuthListener(self, reader, writer):
        response = await reader.readuntil(b'\n')
        responseList = re.split(r"\\r\\n", response.decode())
        responseHeader = responseList[0]
        code = re.search(r"\w{10,}", responseHeader)
        if code:
            print(code.group())
        response = b"HTTP/1.1 200 OK"
        writer.write(response)
        await writer.drain()
        writer.close()

    async def event_ready(self):
        """Called once when the bot goes online."""
        print(f"{os.environ['BOT_NICK']} is online!")
        ws = self._ws  # this is only needed to send messages within event_ready
        await ws.send_privmsg(os.environ['CHANNEL'], f"/me is now online! MrDestructoid ")
        """await self.pubsub_subscribe(os.environ['API_TOKEN'],
                                    "channel-bits-events-v1.40208771",
                                    "channel-bits-events-v2.40208771",
                                    "channel-points-channel-v1.40208771")"""
        if self.botStarted == 0:
            # runs on Bot startup, but will only be reset if the bot actually goes down.
            # prevents the points accumulation from running multiple times if the bot gets disconnected from chat
            # add any loop-based timer starts here
            self.loop.call_later(30, self.list_chatters)  # used to get list of current viewers in chat, every minute
            self.loop.call_later(86400, self.reauthorize)  # should reauthorize the oauth token to prevent expiration
            await asyncio.start_server(
                self.OAuthListener, host="localhost", port=28888, start_serving=True)
            self.NVD.autoActivate(os.environ['CHANNEL'])
            if self.NVD.active:
                self.loop.call_later(600, self.NvDTimer)
            self.botStarted = 1

    def reauthorize(self):
        print("attempting to reauthorize")
        LiveCheck.reauthorize()
        self.loop.call_later(86400, self.reauthorize)

    def list_chatters(self, points=0):
        isLive = LiveCheck.liveCheck(os.environ['CHANNEL'])
        if isLive is True:
            viewerlist = asyncio.gather(self.get_chatters(os.environ['CHANNEL']))  # gathers list from twitch
            viewerlist.add_done_callback(functools.partial(self.accumulate_points, points))
            # when list is complete, passes viewerlist to acc_points
        elif isLive is False:
            print(os.environ['CHANNEL'] + " is not live. " + str(time.time()))
            self.loop.call_later(30, self.list_chatters)
        else:
            print("Unable to reach Twitch API at " + str(time.time()) + ". " + str(isLive))
            if re.search(r"HTTP Error 4\d{2}", str(isLive)):
                print("Fatal Error with LiveCheck, please check credentials.")
            else:
                self.loop.call_later(1, self.list_chatters)

    def accumulate_points(self, pointsToAdd, viewerlist):
        accFlag = 0
        if pointsToAdd == 0:
            print("accumulating " + str(time.time()))
            pointsToAdd = self.pointsPerMinute
            accFlag = 1
        else:
            print("BONUS! " + str(pointsToAdd))
        if accFlag == 1:
            self.loop.call_later(60, self.list_chatters)
        pointsConnection = self.create_connection(".\\points.sqlite")
        viewerTuple = ["", ]
        try:
            viewerTuple = viewerlist.result()[0]
        except Exception:
            if accFlag != 1:
                print("Couldn't return viewer(s) for bonus")
                return 1
        # print(viewerTuple.all)
        for viewerName in viewerTuple.all:
            select_points = "SELECT id, points from PointsTracking where name = ?"
            viewers = self.execute_pointsDB_read_query(pointsConnection, select_points, (viewerName,))
            if viewers:
                # updating
                for viewerRow in viewers:
                    newPoints = int(viewerRow[1]) + pointsToAdd
                    update_points = "UPDATE PointsTracking SET points = ? WHERE id = " + str(viewerRow[0])
                    self.execute_pointsDB_write_query(pointsConnection, update_points,
                                                      (newPoints,))
            else:
                # insert
                insert_points = "INSERT into PointsTracking (channel, name, points) VALUES (?, ?, ?)"
                self.execute_pointsDB_write_query(pointsConnection, insert_points,
                                                  (os.environ['CHANNEL'], viewerName, pointsToAdd))

    """async def event_raw_data(self, data):
        # Prints every chat event.
        print(data)"""

    async def event_raw_pubsub(self, data):
        print(data)

    async def event_message(self, ctx):
        """Runs every time a message is sent in chat."""

        # make sure the bot ignores itself and the streamer
        if ctx.author.name.lower() == os.environ['BOT_NICK'].lower():
            return

        await self.handle_commands(ctx)

        # await ctx.channel.send(ctx.content)

        if 'pizza time' in ctx.content.lower():
            pizzaCoolDown = time.time() - self.pizzaLastTime
            if pizzaCoolDown > 120:
                await ctx.channel.send("Pizza Time is not a meme!")
                self.pizzaLastTime = time.time()

        if 'MrDestructoid' in ctx.content:
            botCoolDown = time.time() - self.botLastTime
            if botCoolDown > 120:
                await ctx.channel.send("MrDestructoid 01000010 01010010 01001111 01010100"
                                       " 01001000 01000101 01010010 MrDestructoid ")
                self.botLastTime = time.time()

        if 'rooBot' in ctx.content:
            botCoolDown = time.time() - self.botLastTime
            if botCoolDown > 120:
                await ctx.channel.send("MrDestructoid 01000010 01010111 01010101 01010100"
                                       " 01001000 01000101 01010010 MrDestructoid ")
                self.botLastTime = time.time()

    """@commands.command(name='test')
    async def test(ctx):
        await ctx.send('test passed!')"""

    @commands.command(name='close')
    async def quit(self, ctx):
        await ctx.channel.send("W-will I dream? :(")
        self._ws.teardown()

    @commands.command(name='meme')
    async def meme(self, ctx):
        print(len(notmemes))
        memeindex = random.randrange(0, len(notmemes))
        memestring = notmemes[memeindex]
        await ctx.send(memestring)

    @commands.command(name='awuwu')
    async def awuwu(self, ctx):
        await ctx.channel.send("grtAWUWU <3")

    @commands.command(name='early')
    async def early(self, ctx):
        await ctx.channel.send("It's now too early to be early?")

    @commands.command(name='time')
    async def time(self, ctx):
        timeCooldown = time.time() - self.timeLastTime
        if timeCooldown > 45:
            numSpaces = re.findall(" ", ctx.content)
            if len(numSpaces) < 1:
                num1 = random.randrange(1, 200, 1)
                if num1 > 1:
                    unit1 = str(random.choice(timeList))
                    if unit1 == "century":
                        unit1 = "centuries"
                    elif unit1 == "millenium":
                        unit1 = "millenia"
                    else:
                        unit1 = unit1 + "s"
                else:
                    unit1 = str(random.choice(timeList))
                num2 = random.randrange(1, 200, 1)
                if num2 > 1:
                    unit2 = str(random.choice(timeList))
                    if unit2 == "century":
                        unit2 = "centuries"
                    elif unit2 == "millenium":
                        unit2 = "millenia"
                    else:
                        unit2 = unit2 + "s"
                else:
                    unit2 = str(random.choice(timeList))

                await ctx.channel.send(str(num1) + " " + unit1 + "? That's almost " + str(num2) + " " + unit2 + "!")
            else:
                commandList = re.split(" ", ctx.content, 2)
                timeValue = commandList[1]
                if timeValue.isnumeric():
                    timeUnits = commandList[2]
                    num2 = random.randrange(1, 200, 1)
                    if num2 > 1:
                        unit2 = str(random.choice(timeList))
                        if unit2 == "century":
                            unit2 = "centuries"
                        elif unit2 == "millenium":
                            unit2 = "millenia"
                        else:
                            unit2 = unit2 + "s"
                    else:
                        unit2 = str(random.choice(timeList))

                    await ctx.channel.send(
                        timeValue + " " + timeUnits + "? That's almost " + str(num2) + " " + unit2 + "!")
                else:
                    await ctx.channel.send(
                        "To use !time beyond the basic call, use the following format: !time <number> <units> "
                        "Ex: !time 5 months to get a result like 5 months? That's almost 337 millenia!")
            self.timeLastTime = time.time()

    @commands.command(name='negacassie')
    async def negacassie(self, ctx):
        await ctx.channel.send(
            "Ì̴̧̧̘͚̠͑͐̇̓̋t̴̨͈̳̝͇͐͗̍̚͞ "
            "m̧̨̜͙̳̻̣̫͈̋͊̿̄̚͠͡ḁ̴̡̡̲̻͇̈͛̃̔̚͜k̶̨̘̼̝̺̽̎̃̓͊̒͑͘̚̚e̛͈͉͚͈̳̯̻̥̿̍̔̿̃̀͑͟͡͡s"
            "̴̰͔͔͎̼͉̫͕̗̿͆̐̉̐͒̏͌̾ y̵̧͈̯̻̠̔͆͗̾̽̾̇̿͝o̢̜̞̹̪̽͌͌͑̂̏̒͢ư̷̢̱͖̮̔͊̚̕͟͜͠ "
            "N̷̥̺͕̘̦̞̼̰̗͗̓͌̅̅̓̕͟͠͡ỏ̵͉͕̹̭̆̀̇́͝͞ͅt̷̡̧̛̟͔̣̥̪̩͉̻́͗̿͝͞͝ḫ̤̞̂́̔̊͟͠"
            "̮i̵͉̻̭͍̾́͛̉͆̉͐̃̍͜ǹ͙͇̠̞͈̭̳̆͐͛̎̓͒̚͜͠͠ͅg̵̰͇̠̗͔̅͋̔̐̂͢")

    @commands.command(name='king')
    async def king(self, ctx):
        dbConnection = self.create_connection(".\\points.sqlite")
        selectNoun = "SELECT noun FROM Nouns ORDER BY RANDOM() LIMIT 1;"
        nounRaw = self.execute_read_query(dbConnection, selectNoun)
        await ctx.channel.send(nounRaw[0][0].rstrip().title() + " of the King!")

    @commands.command(name='bodies')
    async def bodies(self, ctx):
        # HonorableJay's tip reward 10/29/2020
        await ctx.channel.send("ACTUAL CANNIBAL SHIA LABEOUF!!")

    # BIT WAR section ==================================================================================================
    @commands.command(name='war')
    async def war(self, ctx):
        if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name == "t0rm3n7" or ctx.author.is_mod:
            numSpaces = re.findall(" ", ctx.content)
            if len(numSpaces) < 1:
                await ctx.channel.send("Example usage: '!war start', '!war on', '!war off', '!war delete', "
                                       "'!war team', and '!war bits'. Please use the commands as listed to see more "
                                       "info on how to use them.")
            else:
                warList = re.split(" ", ctx.content, 2)
                warCommand = warList[1].lower()
                if warCommand == "start":
                    if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name == "t0rm3n7":
                        if len(numSpaces) < 2:
                            await ctx.channel.send("Example usage: '!war start Waifu in Portia' will setup a bit "
                                                   "war for 'Waifu in Portia'.")
                        else:
                            if self.bitWarActive is True:
                                await ctx.channel.send(
                                    "There is an active bit war already in progress. Please turn off "
                                    "the current bit war to start a new one.")
                            else:
                                warSubCommand = warList[2]
                                # add to DB if warSubCommand (bit war name) isn't already present
                                dbConnection = sqlite3.connect(".\\points.sqlite")
                                selectBitWar = "SELECT * from BitWars where channelName = ? AND bitWarName = ?"
                                bitWarLookup = self.execute_pointsDB_read_query(
                                    dbConnection, selectBitWar, (ctx.channel.name, warSubCommand))
                                if bitWarLookup:
                                    # Bit War exists
                                    await ctx.channel.send(
                                        ctx.author.name + ", this bit war already exists. "
                                        "Please open it using the command '!war on " + warSubCommand + "'")
                                else:
                                    # Bit war doesn't exist, insert new row into DB
                                    self.bitWarActive = True
                                    self.bitWarName = str(warSubCommand)
                                    self.bitWarTeams = list()
                                    self.bitWarDonations = list()
                                    convertedTeams = pickle.dumps(self.bitWarTeams).hex()
                                    convertedTotals = pickle.dumps(self.bitWarDonations).hex()
                                    dbConnection = sqlite3.connect(".\\points.sqlite")
                                    insertBitWar = "INSERT into BitWars " \
                                                   "(channelName, bitWarName, donationTeams, donationTotals) " \
                                                   "VALUES (?,?,?,?)"
                                    self.execute_pointsDB_write_query(
                                        dbConnection, insertBitWar,
                                        (ctx.channel.name, self.bitWarName, convertedTeams, convertedTotals))
                                    await ctx.channel.send(
                                        ctx.author.name + " has started a bid war for " + str(warSubCommand) + ". "
                                        "This bid war is now open, but will need to have the teams populated with "
                                        "'!war team add'. To check the status, use the command '!bitwar' in chat!")
                elif warCommand == "on":
                    if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name == "t0rm3n7":
                        if len(numSpaces) < 2:
                            await ctx.channel.send("Example usage: '!war on Waifu in Portia' will start up the bit "
                                                   "war for 'Waifu in Portia'.")
                        else:
                            if self.bitWarActive is True:
                                await ctx.channel.send(
                                    "There is an active bit war already in progress. Please turn off "
                                    "the current bit war to start a new one.")
                            else:
                                warSubCommand = warList[2]
                                # lookup values from DB to bring into memory
                                dbConnection = sqlite3.connect(".\\points.sqlite")
                                selectBitWar = "SELECT * from BitWars where channelName = ? AND bitWarName = ?"
                                bitWarLookup = self.execute_pointsDB_read_query(
                                    dbConnection, selectBitWar, (ctx.channel.name, warSubCommand))
                                if bitWarLookup:
                                    # Bit War exists
                                    self.bitWarActive = True
                                    self.bitWarName = str(warSubCommand)
                                    if bitWarLookup[0][3]:
                                        self.bitWarTeams = pickle.loads(bytes.fromhex(bitWarLookup[0][3]))
                                    else:
                                        self.bitWarTeams = list()
                                    if bitWarLookup[0][4]:
                                        self.bitWarDonations = pickle.loads(bytes.fromhex(bitWarLookup[0][4]))
                                    else:
                                        self.bitWarDonations = list()
                                    await ctx.channel.send("Bid War for " + str(warSubCommand) + " is now open. "
                                                           "All bits/tips will now be added to the current bid war, "
                                                           "as long as you use a hashtag for the team you want to win. "
                                                           "To check the status, use the command '!bitwar' in chat!")
                                    await self.bitWarCheck(ctx)
                                else:
                                    # Bit War isn't in database
                                    await ctx.channel.send(ctx.author.name + ", that bit war doesn't exist! Please "
                                                           "create it using the command '!war start " +
                                                           warSubCommand + "'")
                elif warCommand == "off":
                    if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name == "t0rm3n7":
                        if len(numSpaces) != 1:
                            await ctx.channel.send(
                                "Example usage: '!war off' will turn off the currently active bit war.")
                        else:
                            if self.bitWarActive is False:
                                await ctx.channel.send(
                                    "There is no active bit war to turn off! "
                                    "Example usage: '!war off' will turn off the currently active bit war.")
                            else:
                                # make a final write to the DB to ensure saved data before clearing memory
                                dbConnection = sqlite3.connect(".\\points.sqlite")
                                selectBitWar = "SELECT * FROM BitWars " \
                                               "WHERE channelName = ? AND bitWarName = ?"
                                bitWarLookup = self.execute_pointsDB_read_query(
                                    dbConnection, selectBitWar, (ctx.channel.name, self.bitWarName))
                                if bitWarLookup:
                                    # Bit War exists so update it
                                    cachedName = str(self.bitWarName)
                                    convertedTeams = pickle.dumps(self.bitWarTeams).hex()
                                    convertedTotals = pickle.dumps(self.bitWarDonations).hex()
                                    updateBitWar = "UPDATE BitWars " \
                                                   "SET donationTeams = ?, donationTotals = ?" \
                                                   "WHERE channelName = ? AND bitWarName = ? "
                                    self.execute_pointsDB_write_query(
                                        dbConnection, updateBitWar,
                                        (convertedTeams, convertedTotals, ctx.channel.name, self.bitWarName))
                                    self.bitWarActive = False
                                    self.bitWarName = ""
                                    self.bitWarTeams = list()
                                    self.bitWarDonations = list()
                                    await ctx.channel.send("Bid War for " + str(cachedName) + " is now closed.")
                                else:
                                    await ctx.channel.send("I have no idea how you got to this point, but something "
                                                           "probably broke. No SQL row was found for the current bit "
                                                           "war. Please let t0rm3n7 know. :|")
                elif warCommand == "delete":
                    if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name == "t0rm3n7":
                        if len(numSpaces) < 2:
                            await ctx.channel.send("Example usage: '!war delete Waifu in Portia' will delete the "
                                                   "bit war 'Waifu in Portia' and remove it from the database.")
                        else:
                            warSubCommand = warList[2]
                            # delete the bit war from DB
                            dbConnection = sqlite3.connect(".\\points.sqlite")
                            selectBitWar = "SELECT * FROM BitWars " \
                                           "WHERE channelName = ? AND bitWarName = ?"
                            bitWarLookup = self.execute_pointsDB_read_query(
                                dbConnection, selectBitWar, (ctx.channel.name, warSubCommand))
                            if bitWarLookup:
                                # Bit War exists so delete it
                                deleteBitWar = "DELETE FROM BitWars " \
                                               "WHERE channelName = ? AND bitWarName = ?"
                                self.execute_pointsDB_write_query(
                                    dbConnection, deleteBitWar, (ctx.channel.name, warSubCommand))
                                if self.bitWarActive and self.bitWarName == warSubCommand:
                                    self.bitWarActive = False
                                    self.bitWarName = ""
                                    self.bitWarTeams = list()
                                    self.bitWarDonations = list()
                                    await ctx.channel.send(
                                        "Bid War for " + str(warSubCommand) +
                                        " has been turned off and removed from the database.")
                                else:
                                    await ctx.channel.send(
                                        "Bid War for " + str(warSubCommand) + " has been removed from the database.")
                            else:
                                # Bit War doesn't exist in database
                                await ctx.channel.send(
                                    "Bid War for " + str(warSubCommand) + " doesn't exist in database to delete.")
                elif warCommand == "team":
                    if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name == "t0rm3n7" \
                            or ctx.author.is_mod:
                        if len(numSpaces) < 3:
                            await ctx.channel.send("Example usage: '!war team add Emily' will add Emily to the "
                                                   "currently active bit war. '!war team remove Emily' will remove "
                                                   "Emily from the currently active bit war.")
                        else:
                            if self.bitWarActive is False:
                                await ctx.channel.send("There is no active bit war for which to modify the teams!")
                            else:
                                warList = re.split(" ", ctx.content, 3)
                                warSubCommand = warList[2]
                                warString = warList[3]
                                if warSubCommand == "add":
                                    # update the team info in memory, then update the DB
                                    self.bitWarTeams.append(warString)
                                    self.bitWarDonations.append(0)
                                    convertedTeams = pickle.dumps(self.bitWarTeams).hex()
                                    convertedTotals = pickle.dumps(self.bitWarDonations).hex()
                                    dbConnection = sqlite3.connect(".\\points.sqlite")
                                    selectBitWar = "SELECT * FROM BitWars " \
                                                   "WHERE channelName = ? AND bitWarName = ?"
                                    bitWarLookup = self.execute_pointsDB_read_query(
                                        dbConnection, selectBitWar, (ctx.channel.name, self.bitWarName))
                                    if bitWarLookup:
                                        # Bit War exists so update it
                                        updateBitWar = "UPDATE BitWars " \
                                                       "SET donationTeams = ?, donationTotals = ?" \
                                                       "WHERE channelName = ? AND bitWarName = ? "
                                        self.execute_pointsDB_write_query(
                                            dbConnection, updateBitWar,
                                            (convertedTeams, convertedTotals, ctx.channel.name, self.bitWarName))
                                        await ctx.channel.send("Added the #" + str(warString) + " team to the " +
                                                               str(self.bitWarName) + " bid war.")
                                    else:
                                        # Bit War doesn't exist in database
                                        await ctx.channel.send(
                                            "Bid War for " + str(self.bitWarName) +
                                            " doesn't exist in database to update.")
                                elif warSubCommand == "remove":
                                    # update the team info in memory, then update the DB
                                    index = self.bitWarTeams.index(warString)
                                    self.bitWarTeams.pop(index)
                                    self.bitWarDonations.pop(index)
                                    convertedTeams = pickle.dumps(self.bitWarTeams).hex()
                                    convertedTotals = pickle.dumps(self.bitWarDonations).hex()
                                    dbConnection = sqlite3.connect(".\\points.sqlite")
                                    selectBitWar = "SELECT * FROM BitWars " \
                                                   "WHERE channelName = ? AND bitWarName = ?"
                                    bitWarLookup = self.execute_pointsDB_read_query(
                                        dbConnection, selectBitWar, (ctx.channel.name, self.bitWarName))
                                    if bitWarLookup:
                                        # Bit War exists so update it
                                        updateBitWar = "UPDATE BitWars " \
                                                       "SET donationTeams = ?, donationTotals = ?" \
                                                       "WHERE channelName = ? AND bitWarName = ? "
                                        self.execute_pointsDB_write_query(
                                            dbConnection, updateBitWar,
                                            (convertedTeams, convertedTotals, ctx.channel.name, self.bitWarName))
                                        await ctx.channel.send("Removed the #" + str(warString) + " team from the " +
                                                               str(self.bitWarName) + " bid war.")
                                    else:
                                        # Bit War doesn't exist in database
                                        await ctx.channel.send(
                                            "Bid War for " + str(self.bitWarName) +
                                            " doesn't exist in database to update.")
                elif warCommand == "bits":
                    if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name == "t0rm3n7" \
                            or ctx.author.is_mod:
                        if len(numSpaces) < 3:
                            await ctx.channel.send("Example usage: '!war bits add Emily 667' will add $6.67 or "
                                                   "667 bits to the total amount for Team Emily. '!war bits "
                                                   "subtract Emily 420' will remove $4.20 or 420 bits from the "
                                                   "total amount for Team Emily.")
                        else:
                            if self.bitWarActive is False:
                                await ctx.channel.send("There is no active bit war for which to adjust the donation "
                                                       "totals!")
                            else:
                                warList = re.split(" ", ctx.content, 4)
                                warSubCommand = warList[2]
                                warName = warList[3]
                                warAmount = warList[4]
                                print(warSubCommand + ", " + warName + ", " + warAmount)
                                if warAmount.isnumeric():
                                    if warSubCommand == "add":
                                        # update the team info in memory, then update the DB
                                        index = self.bitWarTeams.index(warName)
                                        self.bitWarDonations[index] += abs(int(warAmount))
                                        convertedTeams = pickle.dumps(self.bitWarTeams).hex()
                                        convertedTotals = pickle.dumps(self.bitWarDonations).hex()
                                        dbConnection = sqlite3.connect(".\\points.sqlite")
                                        selectBitWar = "SELECT * FROM BitWars " \
                                                       "WHERE channelName = ? AND bitWarName = ?"
                                        bitWarLookup = self.execute_pointsDB_read_query(
                                            dbConnection, selectBitWar, (ctx.channel.name, self.bitWarName))
                                        if bitWarLookup:
                                            # Bit War exists so update it
                                            updateBitWar = "UPDATE BitWars " \
                                                           "SET donationTeams = ?, donationTotals = ?" \
                                                           "WHERE channelName = ? AND bitWarName = ? "
                                            self.execute_pointsDB_write_query(
                                                dbConnection, updateBitWar,
                                                (convertedTeams, convertedTotals, ctx.channel.name, self.bitWarName))
                                            await ctx.channel.send("Added " + str(warAmount) + " to the " +
                                                                   str(warName) + " Team.")
                                        else:
                                            # Bit War doesn't exist in database
                                            await ctx.channel.send(
                                                "Bid War for " + str(self.bitWarName) +
                                                " doesn't exist in database to update.")
                                    elif warSubCommand == "subtract":
                                        # update the team info in memory, then update the DB
                                        index = self.bitWarTeams.index(warName)
                                        self.bitWarDonations[index] -= abs(int(warAmount))
                                        convertedTeams = pickle.dumps(self.bitWarTeams).hex()
                                        convertedTotals = pickle.dumps(self.bitWarDonations).hex()
                                        dbConnection = sqlite3.connect(".\\points.sqlite")
                                        selectBitWar = "SELECT * FROM BitWars " \
                                                       "WHERE channelName = ? AND bitWarName = ?"
                                        bitWarLookup = self.execute_pointsDB_read_query(
                                            dbConnection, selectBitWar, (ctx.channel.name, self.bitWarName))
                                        if bitWarLookup:
                                            # Bit War exists so update it
                                            updateBitWar = "UPDATE BitWars " \
                                                           "SET donationTeams = ?, donationTotals = ?" \
                                                           "WHERE channelName = ? AND bitWarName = ? "
                                            self.execute_pointsDB_write_query(
                                                dbConnection, updateBitWar,
                                                (convertedTeams, convertedTotals, ctx.channel.name, self.bitWarName))
                                            await ctx.channel.send("Subtracted " + str(warAmount) + " from the " +
                                                                   str(warName) + " Team.")
                                        else:
                                            # Bit War doesn't exist in database
                                            await ctx.channel.send(
                                                "Bid War for " + str(self.bitWarName) +
                                                " doesn't exist in database to update.")
                                else:
                                    await ctx.channel.send("Example usage: '!war bits add Emily 667' will add $6.67 or "
                                                           "667 bits to the total amount for Team Emily. '!war bits "
                                                           "subtract Emily 420' will remove $4.20 or 420 bits from the "
                                                           "total amount for Team Emily.")
                else:
                    await ctx.channel.send("Example usage: '!war start', '!war on', '!war off', '!war delete', "
                                           "'!war team', and '!war bits'. Please use the commands as listed to see "
                                           "more info on how to use them.")

    @commands.command(name="bitwar")
    async def bitwar(self, ctx):
        await self.bitWarCheck(ctx)

    async def bitWarCheck(self, ctx):
        if self.bitWarActive is True:
            teamTotalsList = "Current Bit War: " + self.bitWarName
            if self.bitWarTeams:
                teamTotalsList = teamTotalsList + ", Current Totals:"
                for team in self.bitWarTeams:
                    index = self.bitWarTeams.index(team)
                    total = self.bitWarDonations[index]
                    teamTotalsList = teamTotalsList + " #" + team + ": " + str(total) + ","
                teamTotalsList = teamTotalsList.rstrip(",")
            else:
                teamTotalsList = teamTotalsList + ", but there are no teams for which to list totals!"
            await ctx.channel.send(teamTotalsList)
        else:
            await ctx.channel.send("There is no active bit war at this time.")

    # NOOT vs DOOT section =============================================================================================
    @commands.command(name='noot')
    async def noot(self, ctx):
        # add a noot to the tally, can list viewer and donation amount,
        # or just listing the number of noots to force add/remove
        channelName = ctx.channel.name.lower()
        if ctx.author.name.lower() == channelName or ctx.author.name == "t0rm3n7" or ctx.author.is_mod:
            if self.NVD.isActive(channelName):
                await self.NvDAddRemoveTeamPoints(ctx, "noot")
            else:
                await ctx.channel.send("Noot vs Doot is currently disabled.")

    @commands.command(name='doot')
    async def doot(self, ctx):
        # add a doot to the tally, can list viewer and donation amount,
        # or just listing the number of doots to force add/remove
        channelName = ctx.channel.name.lower()
        if ctx.author.name.lower() == channelName or ctx.author.name == "t0rm3n7" or ctx.author.is_mod:
            if self.NVD.isActive(channelName):
                await self.NvDAddRemoveTeamPoints(ctx, "doot")
            else:
                await ctx.channel.send("Noot vs Doot is currently disabled.")

    @commands.command(name='third')
    async def third(self, ctx):
        # add a third team point to the tally, can list viewer and donation amount,
        # or just listing the number of third team points to force add/remove
        channelName = ctx.channel.name.lower()
        if ctx.author.name.lower() == channelName or ctx.author.name == "t0rm3n7" or ctx.author.is_mod:
            if self.NVD.isActive(channelName):
                await self.NvDAddRemoveTeamPoints(ctx, "third")
            else:
                await ctx.channel.send("Noot vs Doot is currently disabled.")

    @commands.command(name='nootvsdoot')
    async def nootVsDoot(self, ctx):
        # main command for info and enabling/disabling
        channelName = ctx.channel.name.lower()
        if ctx.author.name.lower() == channelName or ctx.author.name == "t0rm3n7":
            # Gilder and t0rm3n7 (debug-access for t0rm3n7)
            numSpaces = re.findall(" ", ctx.content)
            if len(numSpaces) < 1:
                if self.NVD.active:
                    await self.NvDInfo(ctx)
                else:
                    await ctx.channel.send("Noot vs Doot is currently disabled. For more info, use '!nootvsdoot help'.")
            else:
                nootList = re.split(" ", ctx.content, 2)
                if nootList[1] == "start":
                    if not self.NVD.active:
                        # NVD is not active
                        self.NVD.enableNootVsDoot(channelName)
                    else:
                        # NVD is active
                        await ctx.channel.send("Noot vs Doot is already enabled.")
                elif nootList[1] == "end":
                    if self.NVD.active:
                        # NVD is active
                        self.NVD.disableNootVsDoot(channelName)
                    else:
                        # NVD is not active
                        await ctx.channel.send("Noot vs Doot is already disabled.")
                elif nootList[1] == "commands":
                    await ctx.channel.send(
                        "List of commands related to Noot vs Doot: '!nootvsdoot', '!noot', '!doot', '!third', "
                        "'!nvdstats', '!nvdcaptainpoints', and '!nvdteamchange'")
                elif nootList[1] == "third":
                    if len(numSpaces) < 3:
                        await ctx.channel.send("Example usage: '!nootvsdoot third 1226 shrook' to set the third team "
                                               "as Team Shrook with a bit value of 1226 to track points for that team.")
                    else:
                        thirdList = re.split(" ", ctx.content, 4)
                        teamBits = thirdList[2]
                        teamName = thirdList[3]
                        status = self.NVD.enableExtraTeam(channelName, teamName, teamBits)
                        await ctx.channel.send(status)
                else:
                    await ctx.channel.send("Example Usage: '!nootvsdoot' to display information about Noot vs Doot. "
                                           "'!nootvsdoot start' to enable Noot vs Doot and will enable the various "
                                           "team commands: '!noot', '!doot', and '!third' for adding/removing points. "
                                           "'!nootvsdoot end' will disable Noot vs Doot and clear the loyalty points "
                                           "for all viewers as well as the grand totals. '!nootvsdoot third' for help "
                                           "on how to add the third team to the roster. '!nootvsdoot commands' will "
                                           "display the current command list for Noot vs Doot.")
                    await ctx.channel.send("If a bot crash were to occur, on startup, the bot will check if "
                                           "Noot vs Doot was active last session.")
        elif ctx.author.is_mod:
            #mods cannot start or stop Noot vs Doot, but they have all the other commands listed
            numSpaces = re.findall(" ", ctx.content)
            if len(numSpaces) < 1:
                if self.NVD.active:
                    await self.NvDInfo(ctx)
                else:
                    await ctx.channel.send("Noot vs Doot is currently disabled. For more info, use '!nootvsdoot help'.")
            else:
                nootList = re.split(" ", ctx.content, 2)
                if nootList[1] == "commands":
                    await ctx.channel.send(
                        "List of commands related to Noot vs Doot: '!nootvsdoot', '!noot', '!doot', '!third', "
                        "'!nvdstats', '!nvdcaptainpoints', and '!nvdteamchange'")
                else:
                    await ctx.channel.send("Example Usage: '!nootvsdoot' to display information about Noot vs Doot. "
                                           "'!nootvsdoot commands' will display the current command list for "
                                           "Noot vs Doot.")
                    await ctx.channel.send("If a bot crash were to occur, on startup, the bot will check if "
                                           "Noot vs Doot was active last session.")
        else:
            # normal viewers
            if self.NVD.active:
                await self.NvDInfo(ctx)

    @commands.command(name='nvdstats')
    async def nvdstats(self, ctx):
        # looks up stats of the teams, or for the author
        channelName = ctx.channel.name.lower()
        if self.NVD.isActive(channelName):
            numSpaces = re.findall(" ", ctx.content)
            if len(numSpaces) < 1:
                await self.NvDCurrentStats(ctx)
            else:
                ctxList = re.split(" ", ctx.content, 2)
                if ctxList[1] == "me":
                    viewerName = ctx.author.name.lower()
                    statsList = self.NVD.viewerStatsLookup(channelName, viewerName)
                    if statsList:
                        currentTeam = statsList[0][3].capitalize()
                        currentNoots = statsList[0][4]
                        currentDoots = statsList[0][5]
                        currentThird = statsList[0][6]
                        if self.NVD.teams[2]:
                            # third team
                            thirdName = self.NVD.teams[2]
                            await ctx.channel.send(
                                viewerName + ", you are on Team " + currentTeam + ". Noots: " + currentNoots + ", "
                                "Doots: " + currentDoots + ", " + thirdName + ": " + currentThird)
                        else:
                            # no third team
                            await ctx.channel.send(
                                viewerName + ", you are on Team " + currentTeam + ". Noots: " + currentNoots + ", "
                                "Doots: " + currentDoots)
                    else:
                        await ctx.channel.send(
                            viewerName + ", you have not yet declared your allegiance in the War for Christmas!")
                        await self.NvDTeamsReminder(ctx)
                else:
                    await ctx.channel.send(
                        "Example usage: '!nvdstats' for overall standings of the teams. "
                        "'!nvdstats me' to see which team you're allied with, and your standings with the other teams.")
        else:
            await ctx.channel.send("Noot vs Doot is not currently running.")

    @commands.command(name='nvdcaptainpoints')
    async def nvdcaptainpoints(self, ctx):
        # used to adjust captain points for a specified viewer
        channelName = ctx.channel.name.lower()
        if ctx.author.name.lower() == channelName or ctx.author.name == "t0rm3n7" or ctx.author.is_mod:
            if self.NVD.isActive(channelName):
                numSpaces = re.findall(" ", ctx.content)
                if len(numSpaces) < 2:
                    await ctx.channel.send(
                        "Example usage: '!nvdcaptainpoints t0rm3n7 5' to add 5 captain points for t0rm3n7. "
                        "This will accept negative values to remove points.")
                else:
                    captainList = re.split(" ", ctx.content, 3)
                    if not captainList[2].isnumeric():
                        await ctx.channel.send(
                            "Example usage: '!nvdcaptainpoints t0rm3n7 5' to add 5 captain points for t0rm3n7. "
                            "This will accept negative values to remove points.")
                    else:
                        viewerName = captainList[1]
                        points = int(captainList[2])
                        status = self.NVD.forceCaptainPoints(channelName, viewerName, points)
                        await ctx.channel.send(status)
            else:
                await ctx.channel.send("Noot vs Doot is currently disabled.")

    @commands.command(name='nvdteamchange')
    async def nvdteamchange(self, ctx):
        # used to manually change the specified viewer's team
        channelName = ctx.channel.name.lower()
        if ctx.author.name.lower() == channelName or ctx.author.name == "t0rm3n7" or ctx.author.is_mod:
            if self.NVD.isActive(channelName):
                numSpaces = re.findall(" ", ctx.content)
                if len(numSpaces) < 2:
                    await ctx.channel.send(
                        "Example usage: '!nvdteamchange t0rm3n7 doot' to move t0rm3n7 to Team Doot.")
                else:
                    ctxList = re.split(" ", ctx.content, 3)
                    if ctxList[2].lower() in self.NVD.teams:
                        # specified team is in the list of recognized teams
                        viewerName = ctxList[1]
                        teamName = ctxList[2]
                        status = self.NVD.forceTeamChange(channelName, viewerName, teamName)
                        await ctx.channel.send(status)
                    else:
                        await ctx.channel.send(
                            "Example usage: '!nvdteamchange t0rm3n7 noot' to move t0rm3n7 to Team Noot.")
            else:
                await ctx.channel.send("Noot vs Doot is currently disabled.")

    async def NvDAddRemoveTeamPoints(self, ctx, teamName):
        channelName = ctx.channel.name.lower()
        numSpaces = re.findall(" ", ctx.content)
        if len(numSpaces) < 1:
            # add one point via force adding
            if teamName == "third":
                teamName = self.NVD.teams[2]
            self.NVD.forceAddRemove(channelName, teamName, 1)
        elif len(numSpaces) < 2:
            # add/remove multiple points via force adding or listing help topic
            nootList = re.split(" ", ctx.content, 2)
            if nootList[1] == "help":
                await ctx.channel.send(ctx.author.name + " Example usage: '!" + teamName + "' to add one point for that"
                                       " team. '!" + teamName + " 4' to add four points for that team. "
                                       "If needing to add a donation amount from a viewer, use '!" + teamName + " "
                                       "1225 t0rm3n7' to add the bit value and let the bot handle the math! "
                                       "If you make the value negative for any of the numerical commands, "
                                       "then the value would be removed from the totals.")
            elif nootList[1].isnumeric():
                if teamName == "third":
                    teamName = self.NVD.teams[2]
                self.NVD.forceAddRemove(channelName, teamName, int(nootList[1]))
        elif len(numSpaces) < 3:
            # add/remove multiple points for a viewer via bit amount
            nootList = re.split(" ", ctx.content, 3)
            donation = int(nootList[1])
            viewerName = nootList[2]
            if teamName == "third":
                teamName = self.NVD.teams[2]
            if donation < 0:
                absDonation = abs(donation)
                self.NVD.removeDonation(channelName, teamName, viewerName, absDonation)
            else:
                self.NVD.addDonation(channelName, teamName, viewerName, donation)

    async def enableNootDoot(self, ctx):
        channelName = ctx.channel.name.lower()
        self.NVD.enableNootVsDoot(channelName)
        await ctx.channel.send("Noot vs Doot is live! The War for Christmas has begun!")
        await self.NvDTeamsReminder(ctx)
        self.loop.call_later(600, self.NvDTimer)

    async def disableNootDoot(self, ctx):
        channelName = ctx.channel.name.lower()
        winningTeam = self.NVD.determineWinner(channelName)
        self.NVD.disableNootVsDoot(channelName)
        await ctx.channel.send("Noot vs Doot is over! Team " + winningTeam + " has won Christmas!")

    async def NvDTeamsReminder(self, ctx):
        # function is mainly called by others, no reason to call this one manually
        channelName = ctx.channel.name.lower()
        await ctx.channel.send("To join Team Noot, cheer 1225 bits or donate $12.25 through StreamLabs!")
        await ctx.channel.send("To join Team Doot, cheer 1224 bits or donate $12.24 through StreamLabs!")
        thirdTeam = self.NVD.isThird(channelName)
        if thirdTeam[0]:
            thirdName = thirdTeam[0].capitalize()
            thirdBits = thirdTeam[1]
            thirdDollar = thirdBits / 100
            await ctx.channel.send("To join Team " + thirdName + ", cheer " + thirdBits + " bits or donate "
                                   "$" + thirdDollar + " through StreamLabs!")

    async def NvDInfo(self, ctx):
        # function only sends info on how to join teams, is suitable for a timer
        channelName = ctx.channel.name.lower()
        thirdTeam = self.NVD.isThird(channelName)
        if thirdTeam[0]:
            thirdName = thirdTeam[0].capitalize()
            await ctx.channel.send("Noot vs Doot is Happening! Penguins are fighting against the Skeleton Army in the "
                                   "War for Christmas! Join Team Noot or Team Doot help decide the victor. In addition,"
                                   " we have Team " + thirdName + " rolling in to lay claim to Christmas! "
                                   "Use !nvdstats to check on the current standings for the teams.")
        else:
            await ctx.channel.send("Noot vs Doot is Happening! Penguins are fighting against the Skeleton Army in the "
                                   "War for Christmas! Join Team Noot or Team Doot help decide the victor. "
                                   "Use !nvdstats to check on the current standings for the teams.")
        await self.NvDTeamsReminder(ctx)

    async def NvDCurrentStats(self, ctx):
        channelName = ctx.channel.name.lower()
        NVDList = self.NVD.currentStats(channelName)
        nootTotal = NVDList[0][3]
        dootTotal = NVDList[0][4]
        thirdTotal = NVDList[0][5]
        thirdName = NVDList[0][6].capitalize()
        if thirdName:
            await ctx.channel.send(
                "Current standings: Team Noot with " + nootTotal + " points. Team Doot with " + dootTotal + " points. "
                "Team " + thirdName + " with " + thirdTotal + " points.")
        else:
            await ctx.channel.send(
                "Current standings: Team Noot with " + nootTotal + " points. Team Doot with " + dootTotal + " points.")

    async def NvDTimer(self):
        isLive = LiveCheck.liveCheck(os.environ['CHANNEL'])
        if isLive:
            if self.NVD.active:
                ws = self._ws
                channelName = os.environ['CHANNEL'][0]
                thirdTeam = self.NVD.isThird(channelName.lower())
                if thirdTeam[0]:
                    thirdName = thirdTeam[0].capitalize()
                    message = str(
                        "Noot vs Doot is Happening! Penguins are fighting against the Skeleton Army in the "
                        "War for Christmas! Join Team Noot or Team Doot help decide the victor. In addition,"
                        " we have Team " + thirdName + " rolling in to lay claim to Christmas! "
                        "Use !nvdstats to check on the current standings for the teams.")
                else:
                    message = str(
                        "Noot vs Doot is Happening! Penguins are fighting against the Skeleton Army in the "
                        "War for Christmas! Join Team Noot or Team Doot help decide the victor. "
                        "Use !nvdstats to check on the current standings for the teams.")
                await ws.send_privmsg(channelName, message)
        self.loop.call_later(600, self.NvDTimer)

    # QUOTE section ====================================================================================================

    @commands.command(name='quote')
    async def quote(self, ctx):
        quoteCooldown = time.time() - self.quoteLastTime
        if quoteCooldown > 60:
            numSpaces = re.findall(" ", ctx.content)
            if len(numSpaces) < 1:
                pointsConnection = self.create_connection(".\\points.sqlite")
                selectQuote = "SELECT id, quote FROM Quotes where channelName = ? ORDER BY RANDOM() LIMIT 1;"
                quoteLookup = self.execute_pointsDB_read_query(pointsConnection, selectQuote, (ctx.channel.name,))
                if quoteLookup:
                    quoteID = int(quoteLookup[0][0])
                    quote = quoteLookup[0][1]
                    await ctx.channel.send("#" + str(quoteID) + ": \"" + quote + "\" - Gilder, 2017")
                    self.quoteLastTime = time.time()
                else:
                    await ctx.channel.send("For some reason, I couldn't lookup a random quote. Please let a mod know.")
            else:
                quoteList = re.split(" ", ctx.content, 1)
                quoteID = quoteList[1]
                if quoteID.isnumeric():
                    pointsConnection = self.create_connection(".\\points.sqlite")
                    selectQuote = "SELECT quote from Quotes where id = ? and channelName = ?"
                    quoteLookup = self.execute_pointsDB_read_query(pointsConnection, selectQuote,
                                                                   (quoteID, ctx.channel.name, ))
                    if quoteLookup:
                        quote = quoteLookup[0][0]
                        await ctx.channel.send("#" + str(quoteID) + ": \"" + quote + "\" - Gilder, 2017")
                        self.quoteLastTime = time.time()
                    else:
                        await ctx.channel.send(ctx.author.name + ", there was no quote with that ID.")
                else:
                    await ctx.channel.send("Example command usage: '!quote' to get a random quote. '!quote 25' to get"
                                           " quote #25")

    @commands.command(name='addquote')
    async def addquote(self, ctx):
        if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name == "t0rm3n7" or ctx.author.is_mod:
            numSpaces = re.findall(" ", ctx.content)
            if len(numSpaces) < 1:
                await ctx.channel.send("Example command usage: '!addquote <quote>' to add a quote to the bot!")
            else:
                quoteList = re.split(" ", ctx.content, 1)
                quote = quoteList[1]
                pointsConnection = self.create_connection(".\\points.sqlite")
                insertQuote = "INSERT into Quotes (channelName, quote) VALUES (?, ?)"
                self.execute_pointsDB_write_query(pointsConnection, insertQuote, (ctx.channel.name, quote))
                selectQuote = "SELECT id from Quotes where quote = ?"
                quoteLookup = self.execute_pointsDB_read_query(pointsConnection, selectQuote, (quote,))
                if quoteLookup:
                    quoteID = quoteLookup[0][0]
                    await ctx.channel.send(ctx.author.name + ", the quote was added as quote #" + str(quoteID))
                else:
                    await ctx.channel.send(ctx.author.name + ", something went wrong with the ID lookup. "
                                                             "Please let t0rm3n7 know!")

    @commands.command(name='deletequote')
    async def deletequote(self, ctx):
        if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name == "t0rm3n7" or ctx.author.is_mod:
            numSpaces = re.findall(" ", ctx.content)
            if len(numSpaces) < 1:
                await ctx.channel.send("Example command usage: '!deletequote 25' to remove quote #25.")
            else:
                quoteList = re.split(" ", ctx.content, 1)
                quoteID = quoteList[1]
                pointsConnection = self.create_connection(".\\points.sqlite")
                deleteQuote = "DELETE from Quotes where id = ?"
                self.execute_pointsDB_write_query(pointsConnection, deleteQuote, (quoteID,))
                selectQuote = "SELECT * from Quotes where id = ?"
                quoteLookup = self.execute_pointsDB_read_query(pointsConnection, selectQuote, (quoteID,))
                if quoteLookup:
                    await ctx.channel.send(ctx.author.name + ", the quote was unable to be deleted. Please let "
                                           "t0rm3n7 know.")
                else:
                    await ctx.channel.send(ctx.author.name + ", quote #" + quoteID + " was deleted successfully!")

    @commands.command(name='editquote')
    async def editquote(self, ctx):
        if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name == "t0rm3n7" or ctx.author.is_mod:
            numSpaces = re.findall(" ", ctx.content)
            if len(numSpaces) < 2:
                await ctx.channel.send("Example command usage: '!editquote 13 B i G S H R i M P i N' to change quote "
                                       "#13 to 'B i G S H R i M P i N'.")
            else:
                quoteList = re.split(" ", ctx.content, 2)
                quoteID = quoteList[1]
                newQuote = quoteList[2]
                pointsConnection = self.create_connection(".\\points.sqlite")
                deleteQuote = "UPDATE Quotes " \
                              "SET quote = ? " \
                              "WHERE id = ?"
                self.execute_pointsDB_write_query(pointsConnection, deleteQuote, (newQuote, quoteID,))
                selectQuote = "SELECT * from Quotes where id = ?"
                quoteLookup = self.execute_pointsDB_read_query(pointsConnection, selectQuote, (quoteID,))
                if quoteLookup[2] == newQuote:
                    await ctx.channel.send(ctx.author.name + ", quote #" + quoteID + " was updated successfully!")
                else:
                    await ctx.channel.send(ctx.author.name + ", quote #" + quoteID + " was unable to be updated, "
                                           "please let t0rm3n7 know!")

    # POINTS section ===================================================================================================

    @commands.command(name='bonusall')  # !bonus 5000
    async def bonusall(self, ctx):
        if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name == "t0rm3n7":
            numSpaces = re.findall(" ", ctx.content)
            if len(numSpaces) != 1:
                await ctx.channel.send("Example command usage: '!bonusall 5000' to give everyone 5000 grtOne !")
            else:
                bonusList = re.split(" ", ctx.content)
                self.list_chatters(points=int(bonusList[1]))
                await ctx.channel.send(ctx.author.name + " is making it rain! " +
                                       str(bonusList[1]) + " grtOne for everyone!")

    @commands.command(name='bonus')  # !bonus t0rm3n7 5000
    async def bonus(self, ctx):
        if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name == "t0rm3n7" or ctx.author.is_mod:
            numSpaces = re.findall(" ", ctx.content)
            if len(numSpaces) != 2:
                await ctx.channel.send("Example command usage: '!bonus Rufus 5000' to give Rufus 5000 grtOne ")
            else:
                bonusList = re.split(" ", ctx.content)
                viewerName = str(bonusList[1]).lower()
                try:
                    pointsToAdd = int(bonusList[2])
                except ValueError as bonusError:
                    await ctx.channel.send("Cannot update points. Please format in !bonus <username> <points>. "
                                           "Ex: !bonus t0rm3n7 5000")
                    return bonusError
                atSymbol = re.match("@", viewerName)
                if atSymbol:
                    viewerName = re.sub("@", "", viewerName)
                pointsConnection = self.create_connection(".\\points.sqlite")
                select_points = "SELECT id, points from PointsTracking where name = ?"
                viewers = self.execute_pointsDB_read_query(pointsConnection, select_points, (viewerName,))
                if viewers:
                    # updating
                    for viewerRow in viewers:
                        newPoints = int(viewerRow[1]) + pointsToAdd
                        update_points = "UPDATE PointsTracking SET points = ? WHERE id = " + str(viewerRow[0])
                        self.execute_pointsDB_write_query(pointsConnection, update_points,
                                                          (newPoints,))
                else:
                    # insert
                    insert_points = "INSERT into PointsTracking (channel, name, points) VALUES (?, ?, ?)"
                    self.execute_pointsDB_write_query(pointsConnection, insert_points,
                                                      (ctx.channel.name, viewerName, pointsToAdd))
                await ctx.channel.send(str(pointsToAdd) + " grtOne added for " + viewerName)

    @commands.command(name='points')  # checks for current points
    async def points(self, ctx):
        await self.pointcheckcall(ctx)

    @commands.command(name='pints')  # checks for current points
    async def pints(self, ctx):
        await self.pointcheckcall(ctx)

    @commands.command(name='b1rs')  # checks for current points
    async def b1rs(self, ctx):
        await self.pointcheckcall(ctx)

    async def pointcheckcall(self, ctx):
        viewerName = ctx.author.name
        pointsConnection = self.create_connection(".\\points.sqlite")
        select_users = "SELECT points from PointsTracking where name = ?"
        viewers = self.execute_pointsDB_read_query(pointsConnection, select_users, (viewerName,))
        if viewers:
            for viewerRow in viewers:
                await ctx.channel.send(str(viewerName) + ", you have " + str(viewerRow[0]) + " grtOne ")
        else:
            await ctx.channel.send(str(viewerName) + ", you have 0 grtOne ")

    @commands.command(name='gamble')  # checks for current points
    async def gamble(self, ctx):
        allFlag = False
        numSpaces = re.findall(" ", ctx.content)
        if len(numSpaces) != 1:
            await ctx.channel.send("Example command usage: '!gamble 69' to bet 69 grtOne on a roll of the 'dice'. "
                                   "A 61 or higher is a win, and pays double your bet. "
                                   "A roll of 99 or 100 is a MAXIMOPTIMAL win and pays TRIPLE your bet! "
                                   "There might even be special points rewards for certain rolls with certain bets!"
                                   "If you want to join the high rollers club (fyi: not actually a thing), "
                                   "you can also bet all your points with '!gamble all'!")
        else:
            points = re.split(" ", ctx.content)
            try:
                pointsToGamble = int(points[1])
            except Exception:
                pointsToGamble = points[1]
                if pointsToGamble == "all":
                    allFlag = True
                else:
                    await ctx.channel.send("Cannot update points. Please format in '!gamble #' to bet your points. "
                                           "If you're trying to bet all your points try '!gamble all'.")
            viewerName = ctx.author.name
            currentTime = time.time()
            cooldownExpired = True
            sixtyNine = False
            gambleDiff = 0

            pointsConnection = self.create_connection(".\\points.sqlite")

            select_gamble = "SELECT * from GambleCooldown where user = ?"
            gamble = self.execute_pointsDB_read_query(pointsConnection, select_gamble, (viewerName,))
            if not gamble:
                # insert
                insert_gamble = "INSERT into GambleCooldown (channel, user, lastGamble, sixtynineflag) " \
                                "VALUES (?, ?, ?, ?)"
                self.execute_pointsDB_write_query(pointsConnection, insert_gamble,
                                                  (ctx.channel.name, viewerName, 0, sixtyNine))
            else:
                for gambleRow in gamble:
                    lastGamble = gambleRow[3]
                    sixtyNine = gambleRow[4]
                    gambleDiff = (float(currentTime) - float(lastGamble))
                    if gambleDiff < 1800:
                        cooldownExpired = False
            if cooldownExpired is True:
                select_users = "SELECT id, points from PointsTracking where name = ?"
                viewers = self.execute_pointsDB_read_query(pointsConnection, select_users, (viewerName,))
                if viewers:
                    for viewerRow in viewers:
                        viewerID = viewerRow[0]
                        currentpoints = viewerRow[1]
                        if allFlag:
                            pointsToGamble = currentpoints
                        if pointsToGamble > currentpoints:
                            await ctx.channel.send(str(viewerName) + ", you cannot back your bet! You only have " +
                                                   str(currentpoints) + " grtOne available.")
                        else:
                            currentpoints -= pointsToGamble
                            gambleroll = random.randrange(1, 101)
                            if gambleroll == 69 and pointsToGamble == 69 and sixtyNine is False:
                                # print("6969")
                                currentpoints += (pointsToGamble*2)
                                update_points = "UPDATE PointsTracking SET points = ? WHERE id = " + str(viewerID)
                                self.execute_pointsDB_write_query(pointsConnection, update_points,
                                                                  (currentpoints,))
                                update_gamble = "UPDATE GambleCooldown " \
                                                "SET lastGamble = ?, sixtynineflag = ? " \
                                                "WHERE user = '" + str(viewerName) + "'"
                                self.execute_pointsDB_write_query(pointsConnection, update_gamble,
                                                                  (currentTime, True))
                                await ctx.channel.send("Hell Yeah! " + ctx.author.name +
                                                       ", you rolled " + str(gambleroll) +
                                                       ". You have won 6969 grtOne ! "
                                                       "You now have " + str(currentpoints) + " grtOne .")
                            elif gambleroll < 61:
                                # print("lose")
                                update_points = "UPDATE PointsTracking SET points = ? WHERE id = " + str(viewerID)
                                self.execute_pointsDB_write_query(pointsConnection, update_points,
                                                                  (currentpoints,))
                                update_gamble = "UPDATE GambleCooldown " \
                                                "SET lastGamble = ? " \
                                                "WHERE user = '" + str(viewerName) + "'"
                                self.execute_pointsDB_write_query(pointsConnection, update_gamble,
                                                                  (currentTime,))
                                await ctx.channel.send(
                                    ctx.author.name + ", you rolled " + str(gambleroll) +
                                    ". You lost your bet. :( You now have " + str(currentpoints) + " grtOne .")
                            elif gambleroll < 99:
                                # print("win")
                                currentpoints += (pointsToGamble*2)
                                update_points = "UPDATE PointsTracking SET points = ? WHERE id = " + str(viewerID)
                                self.execute_pointsDB_write_query(pointsConnection, update_points,
                                                                  (currentpoints,))
                                update_gamble = "UPDATE GambleCooldown " \
                                                "SET lastGamble = ? " \
                                                "WHERE user = '" + str(viewerName) + "'"
                                self.execute_pointsDB_write_query(pointsConnection, update_gamble,
                                                                  (currentTime,))
                                await ctx.channel.send(
                                    ctx.author.name + ", you rolled " + str(gambleroll) +
                                    ". You have won " + str(pointsToGamble*2) + " grtOne . "
                                    "You now have " + str(currentpoints) + " grtOne .")
                            else:
                                # print("superwin")
                                currentpoints += (pointsToGamble*3)
                                update_points = "UPDATE PointsTracking SET points = ? WHERE id = " + str(viewerID)
                                self.execute_pointsDB_write_query(pointsConnection, update_points,
                                                                  (currentpoints,))
                                update_gamble = "UPDATE GambleCooldown " \
                                                "SET lastGamble = ? " \
                                                "WHERE user = '" + str(viewerName) + "'"
                                self.execute_pointsDB_write_query(pointsConnection, update_gamble,
                                                                  (currentTime,))
                                await ctx.channel.send(
                                    ctx.author.name + " hit the BIG SHOT! You rolled " + str(gambleroll) +
                                    "! You have won " + str(pointsToGamble*3) + " grtOne ."
                                    " You now have " + str(currentpoints) + " grtOne .")
                else:
                    await ctx.channel.send(str(viewerName) + ", you have no grtOne to gamble!")
            else:
                timeDiff = 1800 - gambleDiff
                timeDiffSplit = re.split(r"\.", str(timeDiff))
                await ctx.channel.send(str(viewerName) + ", you have to wait another " +
                                       str(int(timeDiffSplit[0]) + 1) + " seconds to gamble again!")

    # RAFFLE Section ===================================================================================================

    @commands.command(name='raffle')
    async def raffle(self, ctx):
        if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name.lower() == "t0rm3n7":
            raffleActive = self.raffleObject.is_active()
            if raffleActive:
                await ctx.channel.send("There is already an active raffle!")
            else:
                numSpaces = re.findall(" ", ctx.content)
                if len(numSpaces) < 1:
                    await ctx.channel.send("Example command usage: '!raffle $25 steam gift card' "
                                           "to start a raffle for a '$25 steam gift card'")
                else:
                    raffleList = re.split(" ", ctx.content, 1)
                    rafflePrize = raffleList[1]
                    channelName = ctx.channel.name
                    self.raffleObject.open_raffle(channelName, rafflePrize)
                    self.loop.call_later(600, asyncio.create_task, self.raffle_timer(ctx))
                    await ctx.channel.send("Started a WAFFLE for the following prize: " + rafflePrize +
                                           ". Get your tickets using the !buytickets command! Everyone gets one free "
                                           "entry, but you can keep watching the stream to get points ( grtOne ) "
                                           "to buy tickets! Each ticket is " + str(self.raffleTicketCost) + " grtOne "
                                           "so spend wisely, or use !gamble to get more points!")

    @commands.command(name='loadraffle')
    async def loadraffle(self, ctx):
        if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name.lower() == "t0rm3n7":
            active = self.raffleObject.is_active()
            if active:
                ctx.channel.send("There is already an active raffle.")
            else:
                channelName = ctx.channel.name
                loadedPrize = self.raffleObject.load_raffle(channelName)
                if loadedPrize is not None:
                    self.loop.call_later(600, asyncio.create_task, self.raffle_timer(ctx))
                    await ctx.channel.send("Loaded saved raffle info. The raffle for " + str(loadedPrize) +
                                           " has started, again! All your tickets from before whatever killed the bot "
                                           "should have been saved! Use !ticketcount to confirm your tickets are in "
                                           "the pot!")
                else:
                    await ctx.channel.send("Failed to load raffle info. :(")

    @commands.command(name='raffleinfo')
    async def raffleinfo(self, ctx):
        raffleActive = self.raffleObject.is_active()
        if not raffleActive:
            await ctx.channel.send("There is no active raffle at the moment.")
        else:
            rafflePrize = self.raffleObject.what_prize()
            raffleTickets = self.raffleObject.get_total_tickets()
            await ctx.channel.send("Gilder is currently raffling off: " + rafflePrize +
                                   ". There are " + str(raffleTickets) + " tickets currently in the pool. "
                                   "Get your tickets using the !buytickets command! Everyone gets one free entry, but "
                                   "you can keep watching the stream to get points ( grtOne ) to buy tickets! Each "
                                   "ticket is " + str(self.raffleTicketCost) + " grtOne so spend wisely, or use !gamble"
                                   " to get more points!")

    @commands.command(name='buyticket')
    async def buyticket(self, ctx):
        await self.buyticketcall(ctx)

    @commands.command(name='buytickets')
    async def buytickets(self, ctx):
        await self.buyticketcall(ctx)

    async def buyticketcall(self, ctx):
        active = self.raffleObject.is_active()
        overHundred = False
        if not active:
            await ctx.channel.send("There is no active raffle for which to buy tickets! "
                                   "When there is a raffle, use '!buyticket #' to buy # number of tickets.")
        else:
            numSpaces = re.findall(" ", ctx.content)
            if len(numSpaces) != 1:
                await ctx.channel.send("Example command usage: '!buytickets 5' to buy 5 tickets in an active raffle.")
            else:
                raffleList = re.split(" ", ctx.content, 1)
                if re.match(r"^\d+$", raffleList[1]):
                    numTickets = int(raffleList[1])
                    if numTickets <= 0:
                        await ctx.channel.send("You have to buy a positive number of tickets! Use !buytickets with a "
                                               "positive number to add tickets into the pool.")
                    else:
                        viewerName = ctx.author.name
                        channelName = ctx.channel.name
                        currentTickets = self.raffleObject.list_tickets(viewerName)  # lists number of tickets in raffle
                        maxTickets = 100 - currentTickets  # set max number of tickets available for purchase out of 100
                        estimatedTicketTotal = numTickets + currentTickets
                        if currentTickets >= 100:
                            await ctx.channel.send(viewerName + ", you already have the max number of tickets per "
                                                   "raffle! You can only have up to 100 tickets in the raffle.")
                        else:
                            if numTickets > 100 or estimatedTicketTotal > 100:
                                overHundred = True
                                numTickets = maxTickets  # set number of tickets to purchase to the maximum allowed
                            cost = int(self.raffleTicketCost) * int(numTickets)
                            print(cost)
                            pointsConnection = self.create_connection(".\\points.sqlite")
                            select_points = "SELECT id, points from PointsTracking where name = ?"
                            viewers = self.execute_pointsDB_read_query(pointsConnection, select_points, (viewerName,))
                            if viewers:
                                for viewerRow in viewers:
                                    viewerID = viewerRow[0]
                                    currentPoints = viewerRow[1]
                                    inList = self.raffleObject.in_list(viewerName)
                                    if inList is False:
                                        cost -= int(self.raffleTicketCost)
                                        # print(cost)
                                    if int(cost) > int(currentPoints):
                                        if inList is False:
                                            self.raffleObject.add_tickets(channelName, viewerName, 1)
                                            await ctx.channel.send(str(viewerName) + ", you cannot buy that many "
                                                                   "tickets! You only have " + str(currentPoints) +
                                                                   " grtOne available. However, everyone gets one free "
                                                                   "entry, so you now have 1 ticket in the raffle! Keep"
                                                                   " watching the stream, and you'll earn more points "
                                                                   "to spend on tickets! Tickets are 500 grtOne each, "
                                                                   "so you can purchase up to " +
                                                                   str(int(currentPoints/self.raffleTicketCost)) +
                                                                   " tickets right now.")
                                        else:
                                            await ctx.channel.send(str(viewerName) + ", you cannot buy that many "
                                                                   "tickets! You only have " + str(currentPoints) +
                                                                   " grtOne available, and your free ticket has already"
                                                                   " been claimed. Tickets are 500 grtOne each, so you "
                                                                   "can purchase up to " +
                                                                   str(int(currentPoints/self.raffleTicketCost))
                                                                   + " tickets right now.")
                                    else:
                                        self.raffleObject.add_tickets(channelName, viewerName, int(numTickets))
                                        currentPoints -= cost
                                        totalTickets = self.raffleObject.list_tickets(viewerName)
                                        update_points = "UPDATE PointsTracking SET points = ? WHERE id = "\
                                                        + str(viewerID)
                                        self.execute_pointsDB_write_query(pointsConnection, update_points,
                                                                          (currentPoints,))
                                        if inList is False:
                                            if int(numTickets) == 1:
                                                await ctx.channel.send(str(viewerName) + ", you have claimed your free "
                                                                       "ticket. You now have a total of " +
                                                                       str(totalTickets) + " tickets in this raffle.")
                                            else:
                                                await ctx.channel.send(str(viewerName) + ", you have purchased " +
                                                                       str(int(numTickets) - 1) + " tickets for the "
                                                                       "current raffle, and claimed your free ticket. "
                                                                       "You now have a total of " + str(totalTickets) +
                                                                       " tickets in this raffle.")
                                        else:
                                            await ctx.channel.send(
                                                str(viewerName) + ", you have purchased " + str(numTickets) +
                                                " tickets for the current raffle. You now have a total of " +
                                                str(totalTickets) + " tickets in this raffle.")
                            else:
                                await ctx.channel.send("You have no grtOne to spend on tickets! "
                                                       "However, everyone gets one free entry! Keep watching the stream"
                                                       ", and you'll earn more points to spend on tickets! Tickets are "
                                                       "500 grtOne each, so look out for bonuses or try gambling for "
                                                       "extra points!")
                                self.raffleObject.add_tickets(channelName, viewerName, 1)
                else:
                    await ctx.channel.send("Example command usage: "
                                           "'!buytickets 5' to buy 5 tickets in an active raffle.")

    @commands.command(name='addtickets')
    async def addtickets(self, ctx):
        if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name == "t0rm3n7":
            active = self.raffleObject.is_active()
            channelName = ctx.channel.name
            if not active:
                await ctx.channel.send("There is no active raffle for which to add tickets! "
                                       "When there is a raffle, use '!addticket t0rm3n7 5' to give t0rm3n7 5 tickets.")
            else:
                numSpaces = re.findall(" ", ctx.content)
                if len(numSpaces) != 2:
                    await ctx.channel.send("Example command usage: '!addticket t0rm3n7 5'"
                                           " to give t0rm3n7 5 tickets in an active raffle")
                else:
                    raffleList = re.split(" ", ctx.content)
                    viewerName = str(raffleList[1])
                    try:
                        numTickets = int(raffleList[2])
                    except ValueError as bonusError:
                        await ctx.channel.send("Cannot update points. "
                                               "Please format in !addticket <username> <tickets>. "
                                               "Ex: !bonus t0rm3n7 5000")
                        return bonusError
                    self.raffleObject.add_tickets(channelName, viewerName, int(numTickets))
                    totalTickets = self.raffleObject.list_tickets(viewerName)
                    await ctx.channel.send("You have added " + str(numTickets) +
                                           " tickets into the raffle for " + viewerName + ", free of charge. "
                                           "They now have a total of " + str(totalTickets) + " tickets in the raffle.")

    @commands.command(name='draw')
    async def draw(self, ctx):
        if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name.lower() == "t0rm3n7":
            active = self.raffleObject.is_active()
            if not active:
                await ctx.channel.send("There is no active raffle for which to draw a winner! "
                                       "When there is a raffle, use '!draw' to pick the winning ticket.")
            else:
                winner = self.raffleObject.draw_winner(ctx.channel.name)
                if winner:
                    await ctx.channel.send("Raffle is Closed!")
                    await ctx.channel.send(str(winner) + " has won the raffle!")
                else:
                    await ctx.channel.send("There were no tickets in the raffle. Nobody wins... :(")

    @commands.command(name='ticketcount')
    async def ticketcount(self, ctx):
        await self.ticketcountcall(ctx)

    @commands.command(name='tickets')
    async def tickets(self, ctx):
        await self.ticketcountcall(ctx)

    async def ticketcountcall(self, ctx):
        active = self.raffleObject.is_active()
        viewerName = ctx.author.name
        if not active:
            await ctx.channel.send("There is no active raffle for which to check your number of purchased tickets! "
                                   "When there is a raffle, use '!ticketcount' to see your ticket total.")
        else:
            totalTickets = self.raffleObject.list_tickets(viewerName)
            await ctx.channel.send(
                viewerName + ", you have " + str(totalTickets) + " tickets in the current raffle.")

    @commands.command(name='raffleupdate')
    async def raffleupdate(self, ctx):
        if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name.lower() == "t0rm3n7":
            raffleActive = self.raffleObject.is_active()
            if not raffleActive:
                await ctx.channel.send("There isn't an active raffle! You can start a raffle with !raffle")
            else:
                numSpaces = re.findall(" ", ctx.content)
                if len(numSpaces) < 1:
                    await ctx.channel.send("Example command usage: '!raffleupdate $50 steam gift card' "
                                           "to update the raffle prize to '$50 steam gift card'")
                else:
                    raffleList = re.split(" ", ctx.content, 1)
                    rafflePrize = raffleList[1]
                    self.raffleObject.update_prize(ctx.channel.name, rafflePrize)
                    await ctx.channel.send("Prize updated to: " + rafflePrize +
                                           ". Get your tickets using the !buytickets command!")

    @commands.command(name='closeraffle')
    async def closeraffle(self, ctx):
        if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name.lower() == "t0rm3n7":
            self.raffleObject.close_raffle(ctx.channel.name.lower())
            await ctx.channel.send("Winner has claimed their prize! Raffle is officially closed!")

    async def raffle_timer(self, ctx):
        if self.raffleObject.is_active():
            currentPrize = self.raffleObject.prize
            await ctx.channel.send("There is a raffle currently going for the following prize: '" + str(currentPrize) +
                                   "'. Get your tickets in by using the !buytickets command. Everyone gets one free"
                                   " entry! Keep watching the stream, and you'll earn more points to spend on tickets!")
            self.loop.call_later(600, asyncio.create_task, self.raffle_timer(ctx))

    # DATABASE section =================================================================================================

    def create_connection(self, path):
        connection = None
        try:
            connection = sqlite3.connect(path)
            # print("Connection to SQLite DB successful")
        except Error as e:
            print(f"The error '{e}' occurred")
        return connection

    def execute_query(self, connection, query, *args):
        cursor = connection.cursor()
        try:
            cursor.execute(query, args)
            connection.commit()
            # print("Query executed successfully")
        except Error as e:
            print(f"The error '{e}' occurred")

    def execute_read_query(self, connection, query, *args):
        cursor = connection.cursor()
        result = None
        try:
            cursor.execute(query, args)
            result = cursor.fetchall()
            return result
        except Error as e:
            print(f"The error '{e}' occurred")

    def execute_pointsDB_read_query(self, connection, query, viewerName):
        cursor = connection.cursor()
        result = None
        try:
            cursor.execute(query, viewerName)
            result = cursor.fetchall()
            return result
        except Error as e:
            print(f"The error '{e}' occurred")

    def execute_pointsDB_write_query(self, connection, query, values):
        cursor = connection.cursor()
        try:
            cursor.execute(query, values)
            connection.commit()
            # print("Query executed successfully")
        except Error as e:
            print(f"The error '{e}' occurred")

    # VARIABLES Section ================================================================================================

    botStarted = 0
    pizzaLastTime = 0
    botLastTime = 0
    timeLastTime = 0
    quoteLastTime = 0

    bitWarActive = False
    bitWarName = ""
    bitWarTeams = ["", ]
    bitWarDonations = ["", ]

    raffleObject = Raffle()
    pointsPerMinute = 10
    raffleTicketCost = 500
    pointsConnection = sqlite3.connect(".\\points.sqlite")
    select_constants = "SELECT * from Constants"
    cursor = pointsConnection.cursor()
    cursor.execute(select_constants)
    constants = cursor.fetchall()
    if constants:
        # updating
        for constantsRow in constants:
            pointsPerMinute = constantsRow[2]
            print("PPM: " + str(pointsPerMinute))
            raffleTicketCost = constantsRow[3]
            print("tickets: " + str(raffleTicketCost))

    NVD = NootVsDoot()


if __name__ == "__main__":
    bot = Bot()
    bot.run()
