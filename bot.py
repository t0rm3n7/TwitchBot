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
from NootVsDoot import NootVsDoot
from BidWar import BidWar

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
    "olympiad", "decade", "gigasecond", "century", "millenium", "aeon", "pizza"
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
        print("OAuth Port")
        response = await reader.readuntil(b'\n')
        responseList = re.split(r"\\r\\n", response.decode())
        responseHeader = responseList[0]
        code = re.search(r"\w{10,}", responseHeader)
        if code:
            print(code.group())
        else:
            print(response.decode())
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
            self.constantsLookup()
            self.loop.call_later(30, self.list_chatters)  # used to get list of current viewers in chat, every minute
            self.loop.call_later(86400, self.reauthorize)  # should reauthorize the oauth token to prevent expiration
            await asyncio.start_server(
                self.OAuthListener, host="localhost", port=28888, start_serving=True)
            self.NVD.autoActivate(os.environ['CHANNEL'])
            self.BidWarObject.autoActivate(os.environ['CHANNEL'])
            if self.NVD.active:
                self.loop.call_later(600, asyncio.create_task, self.NvDTimer())
            self.botStarted = 1

    def reauthorize(self):
        print("attempting to reauthorize")
        LiveCheck.reauthorize()
        self.loop.call_later(86400, self.reauthorize)

    def list_chatters(self, points=0):
        isLive = LiveCheck.liveCheck(os.environ['CHANNEL'])
        if isLive is True:
            viewerlist = asyncio.gather(self.get_chatters(os.environ['CHANNEL']))  # gathers list from twitch
            viewerlist.add_done_callback(functools.partial(self.accumulate_points, points, os.environ['CHANNEL']))
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

    def accumulate_points(self, pointsToAdd, channelName, viewerList):
        accFlag = 0  # flag for seeing if the bonus is auto-accumulation
        if pointsToAdd == 0:
            print("accumulating " + str(time.time()))
            pointsToAdd = self.constantsDict[channelName]["pointsPerMinute"]
            accFlag = 1
        else:
            print("BONUS! " + str(pointsToAdd))
        if accFlag == 1:
            self.loop.call_later(60, self.list_chatters)
        dbConnection = self.create_connection(".\\TwitchBot.sqlite")
        # check if Noot vs Doot is active for bonus points
        if self.NVD.active:
            teamsDict = self.NVD.currentPlaces(channelName)
            winningTeamDict = teamsDict[0]
            secondTeamDict = teamsDict[1]
            thirdTeamDict = teamsDict[2]
        viewerTuple = ["", ]
        try:
            viewerTuple = viewerList.result()[0]
        except Exception:
            if accFlag != 1:
                print("Couldn't return viewer(s) for bonus")
                return 1
        # print(viewerTuple.all)
        for viewerName in viewerTuple.all:
            if accFlag == 1:
                pointsToAdd = self.constantsDict[channelName]["pointsPerMinute"]
            select_points = "SELECT pointsID, points, nv.currentTeam FROM PointsList " \
                            "INNER JOIN ViewerList vl USING(viewerID) " \
                            "LEFT JOIN NootVsDootViewers nv USING(viewerID) " \
                            "WHERE vl.viewerName = ?"
            viewers = self.execute_read_query(dbConnection, select_points, (viewerName,))
            if viewers:
                # updating
                for viewerRow in viewers:
                    if self.NVD.active and accFlag == 1:
                        if viewerRow[2] == winningTeamDict["name"]:
                            # print(f"original {pointsToAdd} for {viewerName}")
                            pointsToAdd *= 3
                        elif viewerRow[2] == secondTeamDict["name"]:
                            # print(f"original {pointsToAdd} for {viewerName}")
                            pointsToAdd *= 2
                        elif viewerRow[2] == thirdTeamDict["name"] and self.NVD.isThird(channelName)[0]:
                            # print(f"original {pointsToAdd} for {viewerName}")
                            pointsToAdd *= 1.5
                        # print(f"pointsToAdd: {pointsToAdd} for {viewerName}")

                    newPoints = int(viewerRow[1]) + pointsToAdd
                    update_points = "UPDATE PointsList " \
                                    "SET points = ? " \
                                    "WHERE pointsID = ?"
                    self.execute_write_query(dbConnection, update_points, (newPoints, viewerRow[0]))
            else:
                # insert
                channelID = self.constantsDict[channelName]["channelID"]
                selectViewer = "SELECT viewerID FROM ViewerList WHERE viewerName = ?"
                viewerList = self.execute_read_query(dbConnection, selectViewer, (viewerName,))
                if viewerList:
                    viewerID = viewerList[0][0]
                else:
                    print(f"inserting {viewerName} into ViewerList")
                    insertViewer = "INSERT into ViewerList (viewerName) VALUES (?)"
                    self.execute_write_query(dbConnection, insertViewer, (viewerName, ))
                    selectViewer = "SELECT viewerID FROM ViewerList WHERE viewerName = ?"
                    viewerList = self.execute_read_query(dbConnection, selectViewer, (viewerName,))
                    viewerID = viewerList[0][0]
                print(f"inserting {viewerName} into PointsList")
                insert_points = "INSERT into PointsList (channelID, viewerID, points) VALUES (?, ?, ?)"
                self.execute_write_query(dbConnection, insert_points, (channelID, viewerID, pointsToAdd))

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
        if timeCooldown > 30:
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
                if num1 == 9 and unit1.lower().startswith("month"):
                    num2 = 1
                    unit2 = "baby"
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
                    if timeValue == "9" and timeUnits.lower().startswith("month"):
                        num2 = 1
                        unit2 = "baby"
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

    @commands.command(name='honse', aliases=['horse', 'hoss'])
    async def honse(self, ctx):
        await ctx.channel.send("IT'S HONSE TIME! EVERYBODY ON THE HONSE TRAIN!!!")

    @commands.command(name='king')
    async def king(self, ctx):
        dbConnection = self.create_connection(".\\TwitchBot.sqlite")
        selectNoun = "SELECT noun " \
                     "FROM Nouns " \
                     "ORDER BY RANDOM() LIMIT 1;"
        nounRaw = self.execute_read_query(dbConnection, selectNoun)
        await ctx.channel.send(nounRaw[0][0].rstrip().title() + " of the King!")

    @commands.command(name='bury')
    async def bury(self, ctx):
        dbConnection = self.create_connection(".\\TwitchBot.sqlite")
        selectNoun = "SELECT noun " \
                     "FROM Nouns " \
                     "ORDER BY RANDOM() LIMIT 1;"
        nounRaw = self.execute_read_query(dbConnection, selectNoun)
        await ctx.channel.send("Bury me with my " + nounRaw[0][0].rstrip() + "!")

    @commands.command(name='bodies')
    async def bodies(self, ctx):
        # HonorableJay's tip reward 10/29/2020
        await ctx.channel.send("ACTUAL CANNIBAL SHIA LABEOUF!!")

    @commands.command(name='notthatbad')
    async def notthatbad(self, ctx):
        await ctx.channel.send("I dOn'T kNoW gIlDeR. iT dOeSn'T lOoK tHaT bAd. grtSHROOK ")

    @commands.command(name='raidmessage')
    async def raidmessage(self, ctx):
        numSpaces = re.findall(" ", ctx.content)
        if len(numSpaces) < 1:
            await ctx.channel.send(
                "Example usage: '!raidmessage list' to list potential raid messages from the stream. "
                "'!raidmessage add <message>' to add a raid message to the list. "
                "'!raidmessage clear' to remove all entries from this list.")
        else:
            ctxList = re.split(" ", ctx.content, 2)
            if ctxList[1] == "list":
                if len(self.raidList) > 0:
                    message = 'Potential Raid Messages: "'
                    for raidMessage in self.raidList:
                        if len(message + '", "' + raidMessage) > 500:
                            message = message.rstrip(', "')
                            await ctx.channel.send(message)
                            message = 'Potential Raid Messages: "'
                        message = message + raidMessage + '", "'
                    match = re.search(r'(.*), "$', message)
                    await ctx.channel.send(match.group(1))
                else:
                    await ctx.channel.send(
                        "There are no potential Raid Messages yet. "
                        "Use '!raidmessage add <message>' to add a potential raid message to the list!")
            elif ctxList[1] == "add":
                channelName = ctx.channel.name.lower()
                if ctx.author.name.lower() == channelName or ctx.author.name == "t0rm3n7" or ctx.author.is_mod:
                    newRaidMessage = ctxList[2]
                    messagePresent = False
                    for raidMessage in self.raidList:
                        if newRaidMessage.lower() == raidMessage.lower():
                            messagePresent = True
                    if messagePresent is True:
                        await ctx.channel.send("This message is already in the list!")
                    else:
                        self.raidList.append(newRaidMessage)
                        await ctx.channel.send("Added a new potential raid message to the list!")
            elif ctxList[1] == "clear":
                channelName = ctx.channel.name.lower()
                if ctx.author.name.lower() == channelName or ctx.author.name == "t0rm3n7" or ctx.author.is_mod:
                    self.raidList.clear()
                    await ctx.channel.send("Cleared the Raid Message list!")
            else:
                await ctx.channel.send(
                    "Example usage: '!raidmessage list' to list potential raid messages from the stream. "
                    "'!raidmessage add <message>' to add a raid message to the list. "
                    "'!raidmessage clear' to remove all entries from this list.")

    """@commands.command(name='roulette', aliases=['faq', ])
    async def roulette(self, ctx):
        await ctx.channel.send(
            "Gilder is running a 24-hour roguelite marathon! Every new run gets a spin on the main roulette wheel, "
            "but if you donate, you can shift the results to a game more to your liking. Higher donations have other "
            "effects, like choosing a specific game and/or challenge. For full information on the event, go to "
            "https://tinyurl.com/RouletteFAQ")"""

    @commands.command(name='nexus', aliases=['store', ])
    async def nexus(self, ctx):
        await ctx.channel.send(
            "Gilder has a Nexus.gg store, where you can buy games and a bit goes back to Gilder! Visit "
            "https://www.nexus.gg/Gildersneeze to view his promoted games and buy if you like!")

    """@commands.command(name='wastenauts')
    async def wastenauts(self, ctx):
        await ctx.channel.send(
            "Wastenauts is a Co-op Deckbuilder game currently in development! Visit "
            "https://www.kickstarter.com/projects/razburygames/wastenauts for more information on Wastenauts!")"""

    # BIT WAR section ==================================================================================================
    @commands.command(name='war')
    async def war(self, ctx):
        if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name == "t0rm3n7" or ctx.author.is_mod:
            numSpaces = re.findall(" ", ctx.content)
            channelName = ctx.channel.name.lower()
            if len(numSpaces) < 1:
                await ctx.channel.send(
                    "Example usage: '!war start', '!war stop', '!war decision', '!war delete', '!war team', '!war bits'"
                    "/'!war tips', '!war list', '!war rename', and '!war text'. Please use the commands as listed to "
                    "see more info on how to use them.")
            else:
                warList = re.split(" ", ctx.content, 2)
                warCommand = warList[1].lower()
                if warCommand == "start":
                    if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name == "t0rm3n7":
                        if len(numSpaces) < 2:
                            await ctx.channel.send(
                                "Example usage: '!war start Waifu in Portia' will setup a bid war for 'Waifu in "
                                "Portia' or turn it on if it's already been created previously.")
                        else:
                            bidWarName = warList[2]
                            chatMessage = self.BidWarObject.enableBidWar(channelName, bidWarName)
                            await ctx.channel.send(chatMessage)
                            await self.bidWarCheck(ctx)
                elif warCommand == "stop":
                    if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name == "t0rm3n7":
                        if len(numSpaces) != 1:
                            await ctx.channel.send(
                                "Example usage: '!war stop' will turn off the currently active bid war.")
                        else:
                            chatMessage = self.BidWarObject.disableBidWar(channelName)
                            await ctx.channel.send(chatMessage)
                elif warCommand == "decision":
                    if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name == "t0rm3n7":
                        if len(numSpaces) != 1:
                            await ctx.channel.send(
                                "Example usage: '!war decision' will decide the victor and close the current bid war. "
                                "This will wipe the totals from the database, so only use it when you're ready to "
                                "decide the winner!")
                        else:
                            chatMessage = self.BidWarObject.declareWinner(channelName)
                            await ctx.channel.send(chatMessage)
                elif warCommand == "delete":
                    if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name == "t0rm3n7":
                        if len(numSpaces) < 2:
                            await ctx.channel.send("Example usage: '!war delete Waifu in Portia' will delete the "
                                                   "bid war 'Waifu in Portia' and remove it from the database.")
                        else:
                            bidWarName = warList[2]
                            chatMessage = self.BidWarObject.deleteBidWar(channelName, bidWarName)
                            await ctx.channel.send(chatMessage)
                elif warCommand == "team" or warCommand == "teams":
                    if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name == "t0rm3n7" \
                            or ctx.author.is_mod:
                        if len(numSpaces) < 3:
                            await ctx.channel.send("Example usage: '!war team add Emily' will add Emily to the "
                                                   "currently active bid war. '!war team remove Emily' will remove "
                                                   "Emily from the currently active bid war.")
                        else:
                            warList = re.split(" ", ctx.content, 3)
                            warSubCommand = warList[2]
                            warString = warList[3]
                            if warSubCommand == "add" or warSubCommand == "remove":
                                chatMessage = self.BidWarObject.teamManipulation(channelName, warString, warSubCommand)
                                await ctx.channel.send(chatMessage)
                            else:
                                await ctx.channel.send("Example usage: '!war team add Emily' will add Emily to the "
                                                       "currently active bid war. '!war team remove Emily' will remove "
                                                       "Emily from the currently active bid war.")
                elif warCommand == "bits" or warCommand == "tip" or warCommand == "bit" or warCommand == "tips":
                    if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name == "t0rm3n7" \
                            or ctx.author.is_mod:
                        if len(numSpaces) < 3:
                            await ctx.channel.send(
                                "Example usage: '!war " + warCommand + " Emily 667' will add $6.67 or 667 bits to "
                                "the total amount for Team Emily. '!war " + warCommand + " Emily -420' will "
                                "remove $4.20 or 420 bits from the total amount for Team Emily.")
                        else:
                            warList = re.split(" ", ctx.content, 3)
                            warName = warList[2]
                            print(warName + ", " + warList[3])
                            try:
                                warAmount = int(warList[3])
                                chatMessage = self.BidWarObject.totalManipulation(channelName, warName, warAmount)
                                await ctx.channel.send(chatMessage)
                            except ValueError:
                                await ctx.channel.send(
                                    "Example usage: '!war " + warCommand + " Emily 667' will add $6.67 or 667 bits to "
                                    "the total amount for Team Emily. '!war " + warCommand + " Emily -420' will "
                                    "remove $4.20 or 420 bits from the total amount for Team Emily.")
                elif warCommand == "list":
                    if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name == "t0rm3n7":
                        chatMessage = self.BidWarObject.listBidWar(channelName)
                        await ctx.channel.send(chatMessage)
                elif warCommand == "rename":
                    if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name == "t0rm3n7":
                        if len(numSpaces) < 2:
                            await ctx.channel.send(
                                "Example usage: '!war rename Stardew Waifu' will rename the current Bid War to "
                                "'Stardew Waifu'")
                        else:
                            bidWarName = warList[2]
                            chatMessage = self.BidWarObject.renameBidWar(channelName, bidWarName)
                            await ctx.channel.send(chatMessage)
                elif warCommand == "text":
                    if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name == "t0rm3n7":
                        if len(numSpaces) < 2:
                            await ctx.channel.send(
                                "Example usage: '!war text <insert description here>' will give the bot a blurb to say"
                                " about the active Bid War when someone enters in '!warinfo'")
                        else:
                            bidWarText = warList[2]
                            chatMessage = self.BidWarObject.setBidWarDesc(channelName, bidWarText)
                            await ctx.channel.send(chatMessage)
                else:
                    await ctx.channel.send(
                        "Example usage: '!war start', '!war on', '!war off', '!war delete', '!war team', and '!war "
                        "bits'/'!war tips'. Please use the commands as listed to see more info on how to use them.")

    @commands.command(name="bidwar")
    async def bidwar(self, ctx):
        await self.bidWarCheck(ctx)

    async def bidWarCheck(self, ctx):
        chatMessage = self.BidWarObject.bidWarStats(ctx.channel.name)
        await ctx.channel.send(chatMessage)

    @commands.command(name='warinfo')
    async def warinfo(self, ctx):
        if self.BidWarObject.is_active(ctx.channel.name):
            chatMessage = self.BidWarObject.bidWarDict[ctx.channel.name]["text"]
            await ctx.channel.send(chatMessage)
            await self.bidWarCheck(ctx)
        else:
            await ctx.channel.send("There is no Bid War currently running.")

    # NOOT vs DOOT section =============================================================================================
    @commands.command(name='noot')
    async def noot(self, ctx):
        # add a noot to the tally, can list viewer and donation amount,
        # or just listing the number of noots to force add/remove
        channelName = ctx.channel.name.lower()
        if ctx.author.name.lower() == channelName or ctx.author.name == "t0rm3n7" or ctx.author.is_mod:
            if self.NVD.isActive(channelName):
                await self.NvDAddRemoveTeamPoints(ctx, "noot")
                await self.NvDCurrentStats(ctx)
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
                await self.NvDCurrentStats(ctx)
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
                await self.NvDCurrentStats(ctx)
            else:
                await ctx.channel.send("Noot vs Doot is currently disabled.")

    @commands.command(name='nootvsdoot', aliases=["NootVsDoot", "NootvsDoot"])
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
                        await self.enableNootDoot(ctx)
                    else:
                        # NVD is active
                        await ctx.channel.send("Noot vs Doot is already enabled.")
                elif nootList[1] == "end":
                    if self.NVD.active:
                        # NVD is active
                        await self.disableNootDoot(ctx)
                        print(self.NVD.active)
                    else:
                        # NVD is not active
                        await ctx.channel.send("Noot vs Doot is already disabled.")
                elif nootList[1] == "commands":
                    await ctx.channel.send(
                        "List of commands related to Noot vs Doot: '!nootvsdoot', '!noot', '!doot', '!third', "
                        "'!nvdstats', '!nvdcaptainpoints', and '!nvdteamchange'")
                elif nootList[1] == "third":
                    if len(numSpaces) < 3:
                        await ctx.channel.send(
                            "Example usage: '!nootvsdoot third 1226 shrook' to set the third team as Team Shrook with "
                            "a bit value of 1226 to track points for that team. If you ask nicely, t0rm3n7 might even "
                            "put in a command for the third team name too!")
                    else:
                        thirdList = re.split(" ", ctx.content, 4)
                        teamBits = thirdList[2]
                        teamName = thirdList[3]
                        status = self.NVD.enableExtraTeam(channelName, teamName, teamBits)
                        await ctx.channel.send(status)
                else:
                    await ctx.channel.send(
                        "Example Usage: '!nootvsdoot' to display information about Noot vs Doot. '!nootvsdoot start' "
                        "to enable Noot vs Doot and will enable the various team commands: '!noot', '!doot', and "
                        "'!third' for adding/removing points. '!nootvsdoot end' will disable Noot vs Doot and clear "
                        "the loyalty points for all viewers as well as the grand totals. '!nootvsdoot third' for help "
                        "on how to add the third team to the roster. '!nootvsdoot commands' will display the current "
                        "command list for Noot vs Doot.")

                    await ctx.channel.send(
                        "If a bot crash were to occur, on startup, the bot will check if Noot vs Doot was active last "
                        "session.")
        elif ctx.author.is_mod:
            # mods cannot start or stop Noot vs Doot, but they have all the other commands listed
            numSpaces = re.findall(" ", ctx.content)
            if len(numSpaces) < 1:
                if self.NVD.active:
                    await self.NvDInfo(ctx)
                else:
                    await ctx.channel.send(
                        "Noot vs Doot is currently disabled. For more info, use '!nootvsdoot help'.")
            else:
                nootList = re.split(" ", ctx.content, 2)
                if nootList[1] == "commands":
                    await ctx.channel.send(
                        "List of commands related to Noot vs Doot: '!nootvsdoot', '!noot', '!doot', '!third', "
                        "'!nvdstats', '!nvdcaptainpoints', and '!nvdteamchange'")
                else:
                    await ctx.channel.send(
                        "Example Usage: '!nootvsdoot' to display information about Noot vs Doot. '!nootvsdoot commands'"
                        " will display the current command list for Noot vs Doot.")
                    await ctx.channel.send(
                        "If a bot crash were to occur, on startup, the bot will check if Noot vs Doot was active last "
                        "session.")
        else:
            # normal viewers
            if self.NVD.active:
                await self.NvDInfo(ctx)

    @commands.command(name='nvdstats')
    async def nvdstats(self, ctx):
        # looks up stats of the teams, or for the author
        channelName = ctx.channel.name.lower()
        if self.NVD.isActive(channelName) is False:
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
                        currentNoots = str(statsList[0][4])
                        currentDoots = str(statsList[0][5])
                        currentThird = str(statsList[0][6])
                        if self.NVD.teamsDict[channelName]["third"]["name"]:
                            # third team
                            thirdName = self.NVD.teamsDict[channelName]["third"]["name"]
                            if currentTeam == "third":
                                currentTeam = thirdName.capitalize()
                            await ctx.channel.send(
                                viewerName + ", you are on Team " + currentTeam + ". Noots: " + currentNoots + ", "
                                "Doots: " + currentDoots + ", " + thirdName + "s: " + currentThird)
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
                        "Example usage: '!nvdstats' for overall standings of the teams. '!nvdstats me' to see which "
                        "team you're allied with, and your standings with the other teams.")
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
                    if not captainList[2].isnumeric() and not re.match(r"-\d+", captainList[2]):
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
                    if ctxList[2].lower() in [record['name'] for record in self.NVD.teamsDict[channelName].values()]:
                        # specified team is in the list of recognized teams
                        viewerName = ctxList[1]
                        teamName = ctxList[2].lower
                        if teamName not in ["noot", "doot"]:
                            teamName = "third"
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
            self.NVD.forceAddRemove(channelName, teamName, 1)
            if teamName == "third":
                teamName = self.NVD.teamsDict[channelName]["third"]["name"]
            await ctx.channel.send("Adding one point for Team " + teamName.capitalize())
        elif len(numSpaces) < 2:
            # add/remove multiple points via force adding or listing help topic
            nootList = re.split(" ", ctx.content, 2)
            if nootList[1] == "help":
                await ctx.channel.send(
                    ctx.author.name + " Example usage: '!" + teamName + "' to add one point for that team. '!" +
                    teamName + " 4' to add four points for that team. If you need to add a bit amount from a viewer, "
                    "use '!" + teamName + " 1225 t0rm3n7' to add the bit value and let the bot handle the math! Just "
                    "remember to make the value in the bit format instead of a flat dollar amount. If you make the "
                    "value negative for any of the numerical commands, then the value would be removed from the totals.")
            elif nootList[1].isnumeric() or re.match(r"-\d+", nootList[1]):
                self.NVD.forceAddRemove(channelName, teamName, int(nootList[1]))
                if int(nootList[1]) < 0:
                    if teamName == "third":
                        teamName = self.NVD.teamsDict[channelName]["third"]["name"]
                    await ctx.channel.send(
                        "Removing " + str(abs(int(nootList[1]))) + " point(s) for Team " + teamName.capitalize())
                else:
                    if teamName == "third":
                        teamName = self.NVD.teamsDict[channelName]["third"]["name"]
                    await ctx.channel.send("Adding " + nootList[1] + " point(s) for Team " + teamName.capitalize())
        elif len(numSpaces) < 3:
            # add/remove multiple points for a viewer via bit amount
            nootList = re.split(" ", ctx.content, 3)
            if re.match(r"\d+\.\d*", nootList[1]):
                await ctx.channel.send(ctx.author.name + ", please format the donation in the form of bits.")
            else:
                donation = int(nootList[1])
                viewerName = nootList[2].lower()
                if viewerName.startswith("@"):
                    viewerName = viewerName.lstrip("@")
                if donation < 0:
                    absDonation = abs(donation)
                    status = self.NVD.removeDonation(channelName, teamName, viewerName, absDonation)
                    await ctx.channel.send(status)
                else:
                    status = self.NVD.addDonation(channelName, teamName, viewerName, donation)
                    await ctx.channel.send(status)

    async def enableNootDoot(self, ctx):
        channelName = ctx.channel.name.lower()
        self.NVD.enableNootVsDoot(channelName)
        await ctx.channel.send("Noot vs Doot is live! The War for Christmas has begun!")
        await self.NvDTeamsReminder(ctx)
        self.loop.call_later(600, asyncio.create_task, self.NvDTimer)

    async def disableNootDoot(self, ctx):
        channelName = ctx.channel.name.lower()
        winningTeamString = self.NVD.determineWinner(channelName)
        self.NVD.disableNootVsDoot(channelName)
        await ctx.channel.send(winningTeamString)

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
            await ctx.channel.send(
                "To join Team " + thirdName + ", cheer " + thirdBits + " bits or donate $" + thirdDollar +
                " through StreamLabs!")

    async def NvDInfo(self, ctx):
        # function only sends info on how to join teams, is suitable for a timer
        channelName = ctx.channel.name.lower()
        thirdTeam = self.NVD.isThird(channelName)
        if thirdTeam[0]:
            thirdName = thirdTeam[0].capitalize()
            await ctx.channel.send(
                "Noot vs Doot is Happening! Penguins are fighting against the Skeleton Army in the War for Christmas! "
                "Join Team Noot or Team Doot help decide the victor. In addition, we have Team " + thirdName +
                " rolling in to lay claim to Christmas! Use !nvdstats to check on the current standings for the teams.")
        else:
            await ctx.channel.send(
                "Noot vs Doot is Happening! Penguins are fighting against the Skeleton Army in the War for Christmas! "
                "Join Team Noot or Team Doot help decide the victor. Use !nvdstats to check on the current standings "
                "for the teams.")
        await self.NvDTeamsReminder(ctx)

    async def NvDCurrentStats(self, ctx):
        channelName = ctx.channel.name.lower()
        NVDList = self.NVD.currentStats(channelName)
        nootTotal = NVDList[0][3]
        dootTotal = NVDList[0][4]
        thirdTotal = NVDList[0][5]
        thirdName = NVDList[0][6]
        if thirdName:
            thirdName = NVDList[0][6].capitalize()
            await ctx.channel.send(
                "Current standings: Team Noot with " + str(nootTotal) + " points. Team Doot with " +
                str(dootTotal) + " points. Team " + thirdName + " with " + str(thirdTotal) + " points.")
        else:
            await ctx.channel.send(
                "Current standings: Team Noot with " + str(nootTotal) + " points. Team Doot with " +
                str(dootTotal) + " points.")

    async def NvDTimer(self):
        print("NVDtimer")
        if self.NVD.active:
            isLive = LiveCheck.liveCheck(os.environ['CHANNEL'])
            if isLive:
                ws = self._ws
                channelName = os.environ['CHANNEL'][0]
                thirdTeam = self.NVD.teamsDict[channelName]["third"]["name"]
                if thirdTeam:
                    thirdName = thirdTeam.capitalize()
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
            self.loop.call_later(600, asyncio.create_task, self.NvDTimer())

    # QUOTE section ====================================================================================================

    @commands.command(name='quote')
    async def quote(self, ctx):
        dbConnection = self.create_connection(".\\TwitchBot.sqlite")
        quoteCooldown = time.time() - self.quoteLastTime
        if quoteCooldown > 10:
            numSpaces = re.findall(" ", ctx.content)
            if len(numSpaces) < 1:
                selectQuote = "SELECT quoteID, quoteText " \
                              "FROM Quotes " \
                              "INNER JOIN ChannelList cl " \
                              "USING(channelID) " \
                              "WHERE cl.channelName = ? " \
                              "ORDER BY RANDOM() LIMIT 1;"
                quoteLookup = self.execute_read_query(dbConnection, selectQuote, (ctx.channel.name,))
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
                    selectQuote = "SELECT quoteText " \
                                  "FROM Quotes q1 " \
                                  "INNER JOIN ChannelList cl " \
                                  "USING(channelID) " \
                                  "WHERE q1.quoteID = ? and cl.channelName = ?"
                    quoteLookup = self.execute_read_query(dbConnection, selectQuote, (quoteID, ctx.channel.name,))
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
        if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name == "t0rm3n7" \
                or ctx.author.is_mod or ctx.author.is_subscriber:
            dbConnection = self.create_connection(".\\TwitchBot.sqlite")
            numSpaces = re.findall(" ", ctx.content)
            if len(numSpaces) < 1:
                await ctx.channel.send("Example command usage: '!addquote <quote>' to add a quote to the bot!")
            else:
                quoteList = re.split(" ", ctx.content, 1)
                quote = quoteList[1]
                selectChannel = "SELECT channelID " \
                                "FROM ChannelList " \
                                "WHERE channelName = ?"
                channelLookup = self.execute_read_query(dbConnection, selectChannel, (ctx.channel.name,))
                if channelLookup:
                    channelID = channelLookup[0][0]
                    insertQuote = "INSERT INTO Quotes (channelID, quoteText) " \
                                  "VALUES (?, ?)"
                    self.execute_write_query(dbConnection, insertQuote, (channelID, quote))
                    selectQuote = "SELECT quoteID FROM Quotes " \
                                  "WHERE quoteText = ?"
                    quoteLookup = self.execute_read_query(dbConnection, selectQuote, (quote,))
                    if quoteLookup:
                        quoteID = quoteLookup[0][0]
                        await ctx.channel.send(ctx.author.name + ", the quote was added as quote #" + str(quoteID))
                    else:
                        await ctx.channel.send(
                            ctx.author.name + ", something went wrong with the quoteID lookup. Please let t0rm3n7 know!")
                else:
                    await ctx.channel.send(
                        ctx.author.name + ", something went wrong with the channelID lookup. Please let t0rm3n7 know!")

    @commands.command(name='deletequote')
    async def deletequote(self, ctx):
        if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name == "t0rm3n7" or ctx.author.is_mod:
            dbConnection = self.create_connection(".\\TwitchBot.sqlite")
            numSpaces = re.findall(" ", ctx.content)
            if len(numSpaces) < 1:
                await ctx.channel.send("Example command usage: '!deletequote 25' to remove quote #25.")
            else:
                quoteList = re.split(" ", ctx.content, 1)
                quoteID = quoteList[1]
                deleteQuote = "DELETE FROM Quotes " \
                              "WHERE quoteID = ?"
                self.execute_write_query(dbConnection, deleteQuote, (quoteID,))
                selectQuote = "SELECT * FROM Quotes " \
                              "WHERE quoteID = ?"
                quoteLookup = self.execute_read_query(dbConnection, selectQuote, (quoteID,))
                if quoteLookup:
                    await ctx.channel.send(ctx.author.name + ", the quote was unable to be deleted. Please let "
                                                             "t0rm3n7 know.")
                else:
                    await ctx.channel.send(ctx.author.name + ", quote #" + quoteID + " was deleted successfully!")

    @commands.command(name='editquote')
    async def editquote(self, ctx):
        if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name == "t0rm3n7" or ctx.author.is_mod:
            dbConnection = self.create_connection(".\\TwitchBot.sqlite")
            numSpaces = re.findall(" ", ctx.content)
            if len(numSpaces) < 2:
                await ctx.channel.send("Example command usage: '!editquote 13 B i G S H R i M P i N' to change quote "
                                       "#13 to 'B i G S H R i M P i N'.")
            else:
                quoteList = re.split(" ", ctx.content, 2)
                quoteID = quoteList[1]
                newQuote = quoteList[2]
                updateQuote = "UPDATE Quotes " \
                              "SET quoteText = ? " \
                              "WHERE quoteID = ?"
                self.execute_write_query(dbConnection, updateQuote, (newQuote, quoteID,))
                selectQuote = "SELECT quoteText FROM Quotes " \
                              "WHERE quoteID = ?"
                quoteLookup = self.execute_read_query(dbConnection, selectQuote, (quoteID,))
                if quoteLookup[0][0] == newQuote:
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
            channelID = self.constantsDict[ctx.channel.name.lower()]["channelID"]
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
                dbConnection = self.create_connection(".\\TwitchBot.sqlite")
                select_points = "SELECT pointsID, points " \
                                "FROM PointsList pl " \
                                "INNER JOIN ViewerList vl USING(viewerID) " \
                                "WHERE vl.viewerName = ?"
                viewers = self.execute_read_query(dbConnection, select_points, (viewerName,))
                if viewers:
                    # updating
                    for viewerRow in viewers:
                        newPoints = int(viewerRow[1]) + pointsToAdd
                        pointsID = str(viewerRow[0])
                        update_points = "UPDATE PointsList SET points = ? WHERE pointsID = ?"
                        self.execute_write_query(dbConnection, update_points,
                                                 (newPoints, pointsID))
                        await ctx.channel.send(str(pointsToAdd) + " grtOne added for " + viewerName)
                else:
                    # find viewer in viewer list
                    viewerID = 0
                    select_viewer = "SELECT * FROM ViewerList" \
                                    "WHERE viewerName = ?"
                    viewerList = self.execute_read_query(dbConnection, select_viewer, (viewerName,))
                    if viewerList:
                        print("found viewer in ViewerList table")
                        viewerID = viewerList[0][0]
                    else:
                        insert_viewer = "INSERT INTO ViewerList (viewerName) VALUES (?)"
                        self.execute_write_query(dbConnection, insert_viewer, viewerName)
                        select_viewer = "SELECT * FROM ViewerList" \
                                        "WHERE viewerName = ?"
                        viewerList = self.execute_read_query(dbConnection, select_viewer, (viewerName,))
                        if viewerList:
                            print("Insert into ViewerList table succeeded")
                            viewerID = viewerList[0][0]
                        else:
                            print(f"couldn't find {viewerName} in ViewerList table, it should have been added...")
                            await ctx.channel.send("Problem adding points. Tell t0rm3n7 pls.")
                    if viewerID != 0:
                        insert_points = "INSERT INTO PointsList (channelID, viewerID, points) VALUES (?, ?, ?)"
                        self.execute_write_query(dbConnection, insert_points, (channelID, viewerID, pointsToAdd))
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
        dbConnection = self.create_connection(".\\TwitchBot.sqlite")
        selectPoints = "SELECT points FROM PointsList " \
                       "INNER JOIN ViewerList vl USING(viewerID) " \
                       "WHERE vl.viewerName = ?"
        viewers = self.execute_read_query(dbConnection, selectPoints, (viewerName,))
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
            await ctx.channel.send(
                "Example command usage: '!gamble 69' to bet 69 grtOne on a roll of the 'dice'. A 61 or higher is a win,"
                " and pays double your bet. A roll of 99 or 100 is a MAXIMOPTIMAL win and pays TRIPLE your bet! There "
                "might even be a special points reward for rolls with a certain bet! You can also bet all your points "
                "with '!gamble all'!")
        else:
            points = re.split(" ", ctx.content)
            try:
                pointsToGamble = abs(int(points[1]))
            except Exception:
                pointsToGamble = 0
                if points[1] == "all":
                    allFlag = True
                else:
                    await ctx.channel.send(
                        "Please format in '!gamble #' to bet your points. If you're trying to bet all your points try "
                        "'!gamble all'.")
            viewerName = ctx.author.name
            channelName = ctx.channel.name
            currentTime = time.time()
            cooldownExpired = True
            sixtyNine = False
            gambleDiff = 0

            dbConnection = self.create_connection(".\\TwitchBot.sqlite")

            selectGamble = "SELECT * FROM GambleCooldown " \
                           "INNER JOIN ViewerList vl USING(viewerID) " \
                           "INNER JOIN ChannelList cl USING(channelID) " \
                           "WHERE vl.viewerName = ? and cl.channelName = ?"
            gambleList = self.execute_read_query(dbConnection, selectGamble, (viewerName, channelName))
            if not gambleList:
                # getting viewerID and channelID
                selectViewer = "SELECT * FROM ViewerList WHERE viewerName = ?"
                viewerList = self.execute_read_query(dbConnection, selectViewer, (viewerName, ))
                if viewerList:
                    viewerID = viewerList[0][0]
                else:
                    ctx.channel.send("No entry in viewer list for " + viewerName + ".")
                    return 0
                selectChannel = "SELECT * FROM ChannelList WHERE channelName = ?"
                channelList = self.execute_read_query(dbConnection, selectChannel, (channelName,))
                if channelList:
                    channelID = channelList[0][0]
                else:
                    ctx.channel.send("No entry in viewer list for " + viewerName + ".")
                    return 0
                # insert
                insert_gamble = "INSERT into GambleCooldown (channelID, viewerID, lastGamble, sixtynineflag) " \
                                "VALUES (?, ?, ?, ?)"
                self.execute_write_query(dbConnection, insert_gamble, (channelID, viewerID, 0, sixtyNine))
                selectGamble = "SELECT * FROM GambleCooldown " \
                               "INNER JOIN ViewerList vl USING(viewerID) " \
                               "INNER JOIN ChannelList cl USING(channelID) " \
                               "WHERE vl.viewerName = ? and cl.channelName = ?"
                gambleList = self.execute_read_query(dbConnection, selectGamble, (viewerName, channelName))
                if gambleList:
                    gambleID = gambleList[0][0]
                    channelID = gambleList[0][1]
                    viewerID = gambleList[0][2]
                    lastGamble = gambleList[0][3]
                    sixtyNine = gambleList[0][4]
            else:
                for gambleRow in gambleList:
                    gambleID = gambleRow[0]
                    channelID = gambleRow[1]
                    viewerID = gambleRow[2]
                    lastGamble = gambleRow[3]
                    sixtyNine = gambleRow[4]
                    gambleDiff = (float(currentTime) - float(lastGamble))
                    if gambleDiff < 1800:
                        cooldownExpired = False
            if cooldownExpired is True:
                selectPoints = "SELECT pointsID, points, viewerID, channelID FROM PointsList " \
                               "INNER JOIN ViewerList vl USING(viewerID) " \
                               "INNER JOIN ChannelList cl USING(channelID) " \
                               "WHERE vl.viewerName = ? AND cl.channelName = ?"
                viewers = self.execute_read_query(dbConnection, selectPoints, (viewerName, channelName))
                if viewers:
                    for viewerRow in viewers:
                        pointsID = viewerRow[0]
                        currentPoints = viewerRow[1]
                        viewerID = viewerRow[2]
                        channelID = viewerRow[3]
                        if allFlag:
                            pointsToGamble = currentPoints
                        if pointsToGamble > currentPoints:
                            await ctx.channel.send(str(viewerName) + ", you cannot back your bet! You only have " +
                                                   str(currentPoints) + " grtOne available.")
                        else:
                            currentPoints -= pointsToGamble
                            gambleroll = random.randrange(1, 101)
                            if gambleroll == 69 and pointsToGamble == 69 and sixtyNine is False:
                                # print("6969")
                                currentPoints += (pointsToGamble * 2)
                                update_points = "UPDATE PointsList SET points = ? WHERE PointsID = ?"
                                self.execute_write_query(dbConnection, update_points, (currentPoints, pointsID))
                                update_gamble = "UPDATE GambleCooldown " \
                                                "SET lastGamble = ?, sixtynineflag = ? " \
                                                "WHERE viewerID = ? AND channelID = ?"
                                self.execute_write_query(dbConnection, update_gamble,
                                                         (currentTime, True, viewerID, channelID))
                                await ctx.channel.send(
                                    "Hell Yeah! " + ctx.author.name + ", you rolled " + str(gambleroll) + ". You have "
                                    "won 6969 grtOne ! You now have " + str(currentPoints) + " grtOne .")
                            elif gambleroll < 61:
                                # print("lose")
                                update_points = "UPDATE PointsList SET points = ? WHERE pointsID = ?"
                                self.execute_write_query(dbConnection, update_points, (currentPoints, pointsID))
                                update_gamble = "UPDATE GambleCooldown " \
                                                "SET lastGamble = ?" \
                                                "WHERE viewerID = ? AND channelID = ?"
                                self.execute_write_query(dbConnection, update_gamble,
                                                         (currentTime, viewerID, channelID))
                                await ctx.channel.send(
                                    ctx.author.name + ", you rolled " + str(gambleroll) +
                                    ". You lost your bet. :( You now have " + str(currentPoints) + " grtOne .")
                            elif gambleroll < 99:
                                # print("win")
                                currentPoints += (pointsToGamble * 2)
                                update_points = "UPDATE PointsList SET points = ? WHERE pointsID = ?"
                                self.execute_write_query(dbConnection, update_points, (currentPoints, pointsID))
                                update_gamble = "UPDATE GambleCooldown " \
                                                "SET lastGamble = ?" \
                                                "WHERE viewerID = ? AND channelID = ?"
                                self.execute_write_query(dbConnection, update_gamble,
                                                         (currentTime, viewerID, channelID))
                                await ctx.channel.send(
                                    ctx.author.name + ", you rolled " + str(gambleroll) +
                                    ". You have won " + str(pointsToGamble * 2) + " grtOne . "
                                                                                  "You now have " + str(
                                        currentPoints) + " grtOne .")
                            else:
                                # print("superwin")
                                currentPoints += (pointsToGamble * 3)
                                update_points = "UPDATE PointsList SET points = ? WHERE pointsID = ?"
                                self.execute_write_query(dbConnection, update_points, (currentPoints, pointsID))
                                update_gamble = "UPDATE GambleCooldown " \
                                                "SET lastGamble = ?" \
                                                "WHERE viewerID = ? AND channelID = ?"
                                self.execute_write_query(dbConnection, update_gamble,
                                                         (currentTime, viewerID, channelID))
                                await ctx.channel.send(
                                    ctx.author.name + " hit the BIG SHOT! You rolled " + str(gambleroll) + "! You have "
                                    "won " + str(pointsToGamble * 3) + " grtOne . You now have " + str(currentPoints) +
                                    " grtOne .")
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
            raffleActive = self.raffleObject.is_active(ctx.channel.name)
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
                    raffleTicketCost = self.constantsDict[channelName]["raffleTicketCost"]
                    self.raffleObject.open_raffle(channelName, rafflePrize)
                    self.loop.call_later(600, asyncio.create_task, self.raffle_timer(ctx))
                    await ctx.channel.send(
                        "Started a WAFFLE for the following prize: " + rafflePrize + ". Get your tickets using the "
                        "!buytickets command! Everyone gets one free entry, but you can keep watching the stream to "
                        "get points ( grtOne ) to buy tickets! Each ticket is " +
                        str(raffleTicketCost) + " grtOne so spend wisely, or use !gamble to get "
                        "more points!")

    @commands.command(name='loadraffle')
    async def loadraffle(self, ctx):
        if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name.lower() == "t0rm3n7":
            active = self.raffleObject.is_active(ctx.channel.name)
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
        channelName = ctx.channel.name
        raffleActive = self.raffleObject.is_active(ctx.channel.name)
        if not raffleActive:
            await ctx.channel.send("There is no active raffle at the moment.")
        else:
            rafflePrize = self.raffleObject.what_prize(ctx.channel.name)
            raffleTickets = self.raffleObject.get_total_tickets(ctx.channel.name)
            raffleTicketCost = self.constantsDict[channelName]["raffleTicketCost"]
            await ctx.channel.send(
                "Gilder is currently raffling off: " + rafflePrize + ". There are " + str(raffleTickets) + " tickets "
                "currently in the pool. Get your tickets using the !buytickets command! Everyone gets one free entry, "
                "but you can keep watching the stream to get points ( grtOne ) to buy tickets! Each ticket is " +
                str(raffleTicketCost) + " grtOne so spend wisely, or use !gamble to get more "
                "points!")

    @commands.command(name='buyticket', aliases=['BuyTicket', 'Buyticket', 'buyTicket'])
    async def buyticket(self, ctx):
        await self.buyticketcall(ctx)

    @commands.command(name='buytickets', aliases=['BuyTickets', 'Buytickets', 'buyTickets'])
    async def buytickets(self, ctx):
        await self.buyticketcall(ctx)

    async def buyticketcall(self, ctx):
        active = self.raffleObject.is_active(ctx.channel.name)
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
                        raffleMaxTickets = int(self.constantsDict[channelName]["raffleMaxTickets"])
                        raffleTicketCost = int(self.constantsDict[channelName]["raffleTicketCost"])
                        # listing number of tickets in raffle for viewer
                        currentTickets = self.raffleObject.list_tickets(channelName, viewerName)
                        # set max number of tickets available for purchase out of overall max (default 100)
                        maxTickets = raffleMaxTickets - currentTickets
                        estimatedTicketTotal = numTickets + currentTickets
                        if currentTickets >= raffleMaxTickets:
                            await ctx.channel.send(viewerName + ", you already have the max number of tickets per "
                                                   "raffle! You can only have up to " + str(raffleMaxTickets) +
                                                   " tickets in the raffle.")
                        else:
                            if numTickets > int(raffleMaxTickets) or estimatedTicketTotal > raffleMaxTickets:
                                overHundred = True
                                numTickets = maxTickets  # set number of tickets to purchase to the maximum allowed
                            cost = raffleTicketCost * int(numTickets)
                            print(cost)
                            dbConnection = self.create_connection(".\\TwitchBot.sqlite")
                            select_points = "SELECT pointsID, points " \
                                            "FROM PointsList pl " \
                                            "INNER JOIN ViewerList vl USING (viewerID) " \
                                            "WHERE vl.viewerName = ?"
                            viewers = self.execute_read_query(dbConnection, select_points, (viewerName,))
                            if viewers:
                                for viewerRow in viewers:
                                    pointsID = viewerRow[0]
                                    currentPoints = viewerRow[1]
                                    inList = self.raffleObject.in_list(channelName, viewerName)
                                    if inList is False:
                                        cost -= int(raffleTicketCost)
                                        # print(cost)
                                    if int(cost) > int(currentPoints):
                                        if inList is False:
                                            self.raffleObject.add_tickets(channelName, viewerName, 1)
                                            await ctx.channel.send(
                                                str(viewerName) + ", you cannot buy that many tickets! You only have "
                                                + str(currentPoints) + " grtOne available. However, everyone gets one "
                                                "free entry, so you now have 1 ticket in the raffle! Keep watching the "
                                                "stream, and you'll earn more points to spend on tickets! Tickets are "
                                                "500 grtOne each, so you can purchase up to " +
                                                str(int(currentPoints / raffleTicketCost)) + " tickets right now.")
                                        else:
                                            await ctx.channel.send(
                                                str(viewerName) + ", you cannot buy that many tickets! You only have "
                                                + str(currentPoints) + " grtOne available, and your free ticket has "
                                                "already been claimed. Tickets are 500 grtOne each, so you can purchase"
                                                " up to " + str(int(currentPoints / raffleTicketCost)) + " tickets "
                                                "right now.")
                                    else:
                                        self.raffleObject.add_tickets(channelName, viewerName, int(numTickets))
                                        currentPoints -= cost
                                        totalTickets = self.raffleObject.list_tickets(channelName, viewerName)
                                        update_points = "UPDATE PointsList SET points = ? WHERE pointsID = ?"
                                        self.execute_write_query(dbConnection, update_points, (currentPoints, pointsID))
                                        if inList is False:
                                            if int(numTickets) == 1:
                                                await ctx.channel.send(
                                                    str(viewerName) + ", you have claimed your free ticket. You now "
                                                    "have a total of " + str(totalTickets) + " tickets in this raffle.")
                                            else:
                                                await ctx.channel.send(
                                                    str(viewerName) + ", you have purchased " + str(int(numTickets) - 1)
                                                    + " tickets for the current raffle, and claimed your free ticket. "
                                                    "You now have a total of " + str(totalTickets) + " tickets in this "
                                                    "raffle.")
                                        else:
                                            await ctx.channel.send(
                                                str(viewerName) + ", you have purchased " + str(numTickets) +
                                                " tickets for the current raffle. You now have a total of " +
                                                str(totalTickets) + " tickets in this raffle.")
                            else:
                                await ctx.channel.send(
                                    "You have no grtOne to spend on tickets! However, everyone gets one free entry! "
                                    "Keep watching the stream, and you'll earn more points to spend on tickets! "
                                    "Tickets are " + str(raffleTicketCost) + " grtOne each, so look out for bonuses or "
                                    "try gambling for extra points!")
                                self.raffleObject.add_tickets(channelName, viewerName, 1)
                else:
                    await ctx.channel.send(
                        "Example command usage: '!buytickets 5' to buy 5 tickets in an active raffle.")

    @commands.command(name='addtickets')
    async def addtickets(self, ctx):
        if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name == "t0rm3n7":
            channelName = ctx.channel.name
            active = self.raffleObject.is_active(channelName)
            if not active:
                await ctx.channel.send(
                    "There is no active raffle for which to add tickets! When there is a raffle, use '!addticket "
                    "t0rm3n7 5' to give t0rm3n7 5 tickets.")
            else:
                numSpaces = re.findall(" ", ctx.content)
                if len(numSpaces) != 2:
                    await ctx.channel.send(
                        "Example command usage: '!addticket t0rm3n7 5' to give t0rm3n7 5 tickets in an active raffle")
                else:
                    raffleList = re.split(" ", ctx.content)
                    viewerName = str(raffleList[1])
                    try:
                        numTickets = int(raffleList[2])
                    except ValueError as bonusError:
                        await ctx.channel.send("Cannot add tickets for " + viewerName)
                        return bonusError
                    self.raffleObject.add_tickets(channelName, viewerName, int(numTickets))
                    totalTickets = self.raffleObject.list_tickets(channelName, viewerName)
                    await ctx.channel.send(
                        "You have added " + str(numTickets) + " tickets into the raffle for " + viewerName + ". They "
                        "now have a total of " + str(totalTickets) + " tickets in the raffle.")

    @commands.command(name='draw')
    async def draw(self, ctx):
        if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name.lower() == "t0rm3n7":
            active = self.raffleObject.is_active(ctx.channel.name)
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
        active = self.raffleObject.is_active(ctx.channel.name)
        viewerName = ctx.author.name
        if not active:
            await ctx.channel.send("There is no active raffle for which to check your number of purchased tickets! "
                                   "When there is a raffle, use '!ticketcount' to see your ticket total.")
        else:
            totalTickets = self.raffleObject.list_tickets(ctx.channel.name, viewerName)
            await ctx.channel.send(
                viewerName + ", you have " + str(totalTickets) + " tickets in the current raffle.")

    @commands.command(name='raffleupdate')
    async def raffleupdate(self, ctx):
        if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name.lower() == "t0rm3n7":
            raffleActive = self.raffleObject.is_active(ctx.channel.name)
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
        if self.raffleObject.is_active(ctx.channel.name.lower()):
            currentPrize = self.raffleObject.what_prize(ctx.channel.name.lower())
            await ctx.channel.send("There is a raffle currently going for the following prize: '" + str(currentPrize) +
                                   "'. Get your tickets in by using the !buytickets command. Everyone gets one free"
                                   " entry! Keep watching the stream, and you'll earn more points to spend on tickets!")
            self.loop.call_later(600, asyncio.create_task, self.raffle_timer(ctx))

    @commands.command(name='setmaxtickets')
    async def setMaxTickets(self, ctx):
        if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name.lower() == "t0rm3n7":
            channelName = ctx.channel.name.lower()
            numSpaces = re.findall(" ", ctx.content)
            if len(numSpaces) != 1:
                await ctx.channel.send(
                    "Example command usage: '!setMaxTickets 5' to set the max number of tickets for any raffle to 5. "
                    "You can also use the 'default' argument to set the number of tickets to the default of 100.")
            else:
                raffleList = re.split(" ", ctx.content)
                if raffleList[1] == "default":
                    maxTickets = 100
                    await self.callMaxTickets(channelName, maxTickets)
                    await ctx.channel.send(
                        "Max Tickets set to " + str(maxTickets))
                else:
                    if not raffleList[1].isnumeric():
                        await ctx.channel.send(
                            "Example command usage: '!setMaxTickets 5' to set the max number of tickets for any raffle "
                            "to 5. You can also use the 'default' argument to set the number of tickets to the default "
                            "of 100.")
                    else:
                        maxTickets = int(raffleList[1])
                        await self.callMaxTickets(channelName, maxTickets)
                        await ctx.channel.send(
                            "Max Tickets set to " + str(maxTickets))

    async def callMaxTickets(self, channelName, maxTickets):
        # update cache
        self.constantsDict[channelName]["raffleMaxTickets"] = maxTickets
        # update DB
        dbConnection = sqlite3.connect(".\\TwitchBot.sqlite")
        update_constants = "UPDATE Constants " \
                           "SET maxTickets = ? " \
                           "WHERE channelID = ?"
        self.execute_write_query(dbConnection, update_constants,
                                 (maxTickets, self.constantsDict[channelName]["channelID"]))

    # DATABASE section =================================================================================================

    def create_connection(self, path):
        connection = None
        try:
            connection = sqlite3.connect(path)
            # print("Connection to SQLite DB successful")
        except Error as e:
            print(f"The error '{e}' occurred")
        return connection

    def execute_write_query(self, connection, query, *args):
        cursor = connection.cursor()
        try:
            cursor.execute(query, *args)
            connection.commit()
            # print("Query executed successfully")
        except Error as e:
            print(f"The error '{e}' occurred")

    def execute_read_query(self, connection, query, *args):
        cursor = connection.cursor()
        result = None
        try:
            cursor.execute(query, *args)
            result = cursor.fetchall()
            return result
        except Error as e:
            print(f"The error '{e}' occurred")

    # VARIABLES Section ================================================================================================

    def constantsLookup(self):
        defaultConstantsDict = {
            "channelID": "0",
            "pointsPerMinute": 10,
            "raffleTicketCost": 500,
            "raffleMaxTickets": 100
        }
        dbConnection = sqlite3.connect(".\\TwitchBot.sqlite")
        selectConstants = "SELECT * from Constants " \
                          "INNER JOIN ChannelList cl USING(channelID)"
        constants = self.execute_read_query(dbConnection, selectConstants)
        if constants:
            # updating
            for constantsRow in constants:
                newConstantsDict = dict(defaultConstantsDict)
                newConstantsDict["channelID"] = constantsRow[1]
                newConstantsDict["pointsPerMinute"] = constantsRow[2]
                newConstantsDict["raffleTicketCost"] = constantsRow[3]
                newConstantsDict["raffleMaxTickets"] = constantsRow[4]
                self.constantsDict.update({constantsRow[5]: newConstantsDict})
            print(self.constantsDict)

    botStarted = 0
    pizzaLastTime = 0
    botLastTime = 0
    timeLastTime = 0
    quoteLastTime = 0

    raffleObject = Raffle()

    constantsDict = {}

    NVD = NootVsDoot()

    BidWarObject = BidWar()

    raidList = []


if __name__ == "__main__":
    bot = Bot()
    bot.run()
