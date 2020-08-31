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


timer = 0
notmemes = [
    "Milli Vanilli is not a meme!",
    "Blame it on the Rain is not a meme!",
    "Pizza Time is not a meme!",
    "It's not a murder basement!",
    "The gnomes are just sleeping!"
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
            self.loop.call_later(30, self.list_chatters)  # used to get list of current viewers in chat, every minute
            self.botStarted = 1

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

    @commands.command(name='early')
    async def early(self, ctx):
        await ctx.channel.send("It's now too early to be early?")

    # POINTS section ====================================================================================

    @commands.command(name='bonusall')  # !bonus 5000
    async def bonusall(self, ctx):
        if ctx.author.name.lower() == ctx.channel.name.lower() or ctx.author.name == "t0rm3n7":
            numSpaces = re.findall(" ", ctx.content)
            if len(numSpaces) != 1:
                await ctx.channel.send("Example command usage: '!bonusall 5000' to give everyone 5000 grtOne ")
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
                                                      (os.environ['CHANNEL'], viewerName, pointsToAdd))
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
                                                  (os.environ['CHANNEL'], viewerName, 0, sixtyNine))
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

    # RAFFLE Section ====================================================================================

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
                        currentTickets = self.raffleObject.list_tickets(viewerName)
                        maxTickets = 100 - currentTickets
                        if currentTickets == 100:
                            await ctx.channel.send(viewerName + ", you already have the max number of tickets per "
                                                   "raffle! You can only have up to 100 tickets in the raffle.")
                        else:
                            if numTickets > 100:
                                overHundred = True
                                numTickets = maxTickets
                            cost = int(self.raffleTicketCost) * int(numTickets)
                            # print(cost)
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
                    await ctx.channel.send("Raffle is Closed! " + winner + " has won the raffle!")
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
        self.raffleObject.close_raffle(ctx.channel.name.lower())

    async def raffle_timer(self, ctx):
        if self.raffleObject.is_active():
            currentPrize = self.raffleObject.prize
            await ctx.channel.send("There is a raffle currently going for the following prize: '" + str(currentPrize) +
                                   "'. Get your tickets in by using the !buytickets command. Everyone gets one free"
                                   " entry! Keep watching the stream, and you'll earn more points to spend on tickets!")
            self.loop.call_later(600, asyncio.create_task, self.raffle_timer(ctx))

    # DATABASE section ====================================================================================

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

    botStarted = 0
    pizzaLastTime = 0
    botLastTime = 0
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


if __name__ == "__main__":
    bot = Bot()
    bot.run()
