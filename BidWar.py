import sqlite3
from sqlite3 import Error


class BidWar:

    defaultBidWarDict = {
        "bidWarID": 0,
        "channelID": 0,
        "name": "",
        "teams": {},  # each team in the list should be a dict with the format: {teamName: teamTotal}
        "active": False,
        "text": ""
    }

    bidWarDict = {}

    dbConnection = ""

    def __init__(self):
        self.dbConnection = self.create_connection(".\\TwitchBot.sqlite")
        print("bidWar init")

    def enableBidWar(self, channelName, bidWarName):
        # Start a Bid War
        # check for active Bid Wars
        selectBidWar = "SELECT * FROM BidWarList " \
                       "INNER JOIN ChannelList cl USING(channelID) " \
                       "WHERE cl.channelName = ? AND active = 'True'"
        bidWarList = self.execute_read_query(self.dbConnection, selectBidWar, (channelName, ))
        if bidWarList:
            # check for multiple active bid wars
            if len(bidWarList) > 1:
                return "There are multiple active Bid Wars for " + channelName + ". This is an issue, please let " \
                       "t0rm3n7 know."
            else:
                # Bid War is active in DB, cache it
                if bidWarList[0][2] == bidWarName:
                    newBidWarDict = dict(self.defaultBidWarDict)
                    newBidWarDict["bidWarID"] = bidWarList[0][0]
                    newBidWarDict["channelID"] = bidWarList[0][1]
                    newBidWarDict["name"] = bidWarList[0][2]
                    newBidWarDict["active"] = bidWarList[0][3]
                    newBidWarDict["text"] = bidWarList[0][4]
                    self.bidWarDict.update({channelName: newBidWarDict})
                    selectTeams = "SELECT * FROM BidWarTeamList " \
                                  "WHERE bidWarID = ?"
                    teamsList = self.execute_read_query(self.dbConnection, selectTeams, (newBidWarDict["bidWarID"],))
                    if teamsList:
                        # found teams for bid war!
                        for teamRow in teamsList:
                            teamName = teamRow[2]
                            teamTotal = teamRow[3]
                            self.bidWarDict[channelName]["teams"].update({teamName: teamTotal})
                        return "There is a Bid War currently running! Use '!warinfo' for more information about the " \
                               "Bid War."
                    else:
                        # no teams found for bid war
                        return "There is a Bid War currently running, but no Teams have been set! Use '!warinfo' for " \
                               "more information about the Bid War. You can add Teams using the '!war add team' " \
                               "command!"
                else:
                    return "Found an active Bid War in the database that does not match the one you've entered. " \
                           "Please let t0rm3n7 know."
        else:
            # If none active, check if current name is in list of Bid Wars
            selectBidWar = "SELECT * FROM BidWarList " \
                           "INNER JOIN ChannelList cl USING(channelID) " \
                           "WHERE cl.channelName = ? AND bidWarName = ?"
            bidWarList = self.execute_read_query(self.dbConnection, selectBidWar, (channelName,))
            if bidWarList:
                # if present, cache and set to active
                newBidWarDict = dict(self.defaultBidWarDict)
                newBidWarDict["bidWarID"] = bidWarList[0][0]
                newBidWarDict["channelID"] = bidWarList[0][1]
                newBidWarDict["name"] = bidWarList[0][2]
                newBidWarDict["active"] = "True"
                newBidWarDict["text"] = bidWarList[0][4]
                self.bidWarDict.update({channelName: newBidWarDict})
                updateBidWar = "UPDATE BidWarList " \
                               "SET active = 'True' " \
                               "WHERE bidWarID = ?"
                self.execute_write_query(self.dbConnection, updateBidWar, (newBidWarDict["bidWarID"], ))
                selectTeams = "SELECT * FROM BidWarTeamList " \
                              "WHERE bidWarID = ?"
                teamsList = self.execute_read_query(self.dbConnection, selectTeams, (newBidWarDict["bidWarID"], ))
                if teamsList:
                    # found teams for bid war!
                    for teamRow in teamsList:
                        teamName = teamRow[2]
                        teamTotal = teamRow[3]
                        self.bidWarDict[channelName]["teams"].update({teamName: teamTotal})
                    return "There is a Bid War with that name in the list! Use '!warinfo' for more information about " \
                           "the Bid War. The team totals should have been cleared on a winner being decided last time" \
                           ", but in case they are populated, a mod can use '!war clear' to clear the totals."
                else:
                    return "There is a Bid War with that name in the list, but no teams are current set! Use " \
                           "'!warinfo' for more information about the Bid War. You can add Teams using the '!war add " \
                           "team' command!"
            else:
                # if not, add to DB
                selectChannel = "SELECT channelID FROM ChannelList " \
                                "WHERE channelName = ?"
                channelList = self.execute_read_query(self.dbConnection, selectChannel, (channelName,))
                if channelList:
                    channelID = channelList[0][0]
                    insertBidWar = "INSERT INTO BidWarList (channelID, bidWarName, active) " \
                                   "VALUES (?, ?, ?)"
                    self.execute_write_query(self.dbConnection, insertBidWar, (channelID, bidWarName, "True"))
                    return "Bid War started! You can add Teams using the '!war add team' command, and make sure to " \
                           "use the '!war desc' command to set a description to use when the '!warinfo' command is " \
                           "used!"

    def disableBidWar(self, channelName):
        # set current bid war to inactive in DB, then clear cache
        if channelName in self.bidWarDict.keys():
            bidWarID = self.bidWarDict[channelName]["bidWarID"]
            updateBidWar = "UPDATE BidWarList " \
                           "SET active = 'False' " \
                           "WHERE bidWarID = ?"
            self.execute_write_query(self.dbConnection, updateBidWar, (bidWarID, ))
            selectBidWar = "SELECT * FROM BidWarList WHERE active = 'True'"
            bidWarList = self.execute_read_query(self.dbConnection, selectBidWar)
            if bidWarList:
                return "Failed to set the active Bid War to inactive. Please let t0rm3n7 know."
            else:
                self.bidWarDict.pop(channelName)
                return "Successfully set current bid war to inactive."
        else:
            return "No running bid war to set to inactive."

    def deleteBidWar(self, channelName, bidWarName):
        # remove from DB and clear the cache if present
        selectBidWar = "SELECT bidWarID FROM BidWarList " \
                       "INNER JOIN ChannelList cl USING(channelID) " \
                       "WHERE cl.channelName = ? AND bidWarName = ?"
        bidWarList = self.execute_read_query(self.dbConnection, selectBidWar, (channelName, bidWarName))
        if bidWarList:
            # Bid War found, proceed to delete
            bidWarID = bidWarList[0][0]
            deleteBidWar = "DELETE FROM BidWarList WHERE bidWarID = ?"
            self.execute_write_query(self.dbConnection, deleteBidWar, (bidWarID, ))
            deleteTeams = "DELETE FROM BidWarTeamList WHERE bidWarID = ?"
            self.execute_write_query(self.dbConnection, deleteTeams, (bidWarID,))
            bidWarList = self.execute_read_query(self.dbConnection, selectBidWar, (channelName, bidWarName))
            if bidWarList:
                return "Could not delete the " + bidWarName + " Bid War. Please let t0rm3n7 know."
            else:
                # bid war successfully deleted, remove from cache if present
                if channelName in self.bidWarDict.keys():
                    if self.bidWarDict[channelName]["bidWarID"] == bidWarID:
                        self.bidWarDict.pop(channelName)
                return "Bid War " + bidWarName + " removed from database."
        else:
            # Bid War not found
            return "Bid War " + bidWarName + " not found in database"

    def clearTeamTotals(self, channelName):
        # check for active bidwar
        print("Current Bid War stats for backup purposes:")
        print(self.bidWarDict[channelName])
        if channelName in self.bidWarDict.keys():
            bidWarID = self.bidWarDict[channelName]["bidWarID"]
            # found active bid war, clearing teams list
            self.bidWarDict[channelName]["teams"].clear()
            # clear DB
            updateTeams = "UPDATE BidWarTeamList SET teamTotal = 0 WHERE bidWarID = ?"
            self.execute_write_query(self.dbConnection, updateTeams, (bidWarID, ))
            # repopulate teams list from DB
            selectTeams = "SELECT teamName, teamTotal FROM BidWarTeamList WHERE bidWarID = ?"
            teamsList = self.execute_read_query(self.dbConnection, selectTeams, (bidWarID, ))
            if teamsList:
                for team in teamsList:
                    self.bidWarDict[channelName]["teams"].update({team[0]: team[1]})
            return "Cleared the Team Totals for the current Bid War."
        else:
            return "No active Bid War to clear the Team totals."

    def teamManipulation(self, channelName, teamName, function):
        # check for active Bid War
        if channelName in self.bidWarDict.keys():
            bidWarID = self.bidWarDict[channelName]["bidWarID"]
            if function == "add":
                # check if team already present
                selectTeams = "SELECT * FROM BidWarTeamList " \
                              "WHERE bidWarID = ? AND teamName = ?"
                teamList = self.execute_read_query(self.dbConnection, selectTeams, (bidWarID, teamName))
                if not teamList:
                    # not present, add team to DB
                    insertTeam = "INSERT INTO BidWarTeamList (bidWarID, teamName, teamTotal) " \
                                 "VALUES (?, ?, 0)"
                    self.execute_read_query(self.dbConnection, insertTeam, (bidWarID, teamName))
                else:
                    # present in DB already
                    print("Team " + teamName + " already present in DB")
                # add team to cache
                if teamName not in self.bidWarDict[channelName]["teams"]:
                    self.bidWarDict[channelName]["teams"].update({teamName: 0})
                else:
                    print("Team " + teamName + " already in cache")
                return "Added Team " + teamName + " to the active Bid War"
            if function == "remove":
                # remove team from cache
                if teamName in self.bidWarDict[channelName]["teams"]:
                    self.bidWarDict[channelName]["teams"].pop(teamName)
                # remove team from DB
                deleteTeam = "DELETE FROM BidWarTeamList " \
                             "WHERE bitWarID = ? AND teamName = ?"
                self.execute_write_query(self.dbConnection, deleteTeam, (bidWarID, teamName))
                selectTeam = "SELECT * FROM BidWarTeamList " \
                             "WHERE bitWarID = ? AND teamName = ?"
                teamList = self.execute_read_query(self.dbConnection, selectTeam, (bidWarID, teamName))
                if not teamList:
                    return "Removed Team " + teamName + " from the active Bid War."
                else:
                    return "Had an issue removing Team " + teamName + " from the active Bid War. Please let t0rm3n7" \
                           " know."
        else:
            return "No active Bid War for which to modify the Teams."

    def totalManipulation(self, channelName, teamName, amount):
        # check for active Bid War
        if channelName in self.bidWarDict.keys():
            bidWarID = self.bidWarDict[channelName]["bidWarID"]
            # check for Team Name
            if teamName in self.bidWarDict[channelName]["teams"].keys():
                # do the Math
                currentTotal = self.bidWarDict[channelName]["teams"][teamName]
                newTotal = currentTotal + amount
                self.bidWarDict[channelName]["teams"][teamName] = newTotal
                # update DB
                updateTeam = "UPDATE BidWarTeamList SET teamTotal = ? WHERE bidWarID = ? AND teamName = ?"
                self.execute_write_query(self.dbConnection, updateTeam, (newTotal, bidWarID, teamName))
                if amount > 0:
                    return "Added " + amount + " points to Team " + teamName + "."
                elif amount < 0:
                    return "Removed " + amount + " points from Team " + teamName + "."
            else:
                return "Team " + teamName + " not present in Bid War."
        else:
            return "No active Bid War for which to modify the totals."

    def bidWarStats(self, channelName):
        # look up from cache
        if channelName in self.bidWarDict.keys():
            sortTeamsList = sorted(self.bidWarDict[channelName]["teams"].items(), key=lambda x: x[1], reverse=True)
            returnMessage = "Current Bid War: " + self.bidWarDict[channelName]["name"]
            teamsMessage = ""
            for team in sortTeamsList:
                teamName = team[0]
                teamTotal = team[1]
                teamsMessage = teamsMessage + " #" + teamName + ": " + str(teamTotal) + ","
            if teamsMessage == "":
                returnMessage = returnMessage + "| No Teams have been added!"
            else:
                returnMessage = returnMessage + "| Current Team Totals:" + teamsMessage.rstrip(",")
            return returnMessage
        else:
            return "There is not a Bid War for this channel currently running."

    def is_active(self, channelName):
        if channelName in self.bidWarDict.keys():
            return self.bidWarDict[channelName]["active"]
        else:
            return False

    def listBidWar(self, channelName):
        # lookup list of Bid Wars from DB
        selectBidWar = "SELECT bidWarName FROM BidWarList " \
                       "INNER JOIN ChannelList cl USING(channelID) " \
                       "WHERE cl.channelName = ?"
        bidWarList = self.execute_read_query(self.dbConnection, selectBidWar, (channelName, ))
        if bidWarList:
            # found rows
            returnMessage = "List of saved Bid Wars:"
            for war in bidWarList:
                # loop over rows of bid wars to construct output
                returnMessage = returnMessage + " " + war[0] + ","
            returnMessage = returnMessage.rstrip(",")
            return returnMessage
        else:
            # no rows found
            return "No Bid Wars found. You can start one with the '!war on' command."

    def renameBidWar(self, channelName, bidWarName):
        # changing the active Bid War's name in the DB
        if channelName in self.bidWarDict.keys():
            bidWarID = self.bidWarDict[channelName]["bidWarID"]
            updateBidWar = "UPDATE BidWarList " \
                           "SET bidWarName = ? " \
                           "WHERE bidWarID = ?"
            self.execute_write_query(self.dbConnection, updateBidWar, (bidWarName, bidWarID))
            selectBidWar = "SELECT bidWarName FROM BidWarList " \
                           "WHERE bidWarID = ?"
            bidWarList = self.execute_read_query(self.dbConnection, selectBidWar, (bidWarID, ))
            if bidWarList[0][0] == bidWarName:
                self.bidWarDict[channelName]["name"] = bidWarName
                return "Bid War Name successfully updated to " + bidWarName + "."
            else:
                return "Bid War Name failed to update in the database, please let t0rm3n7 know."
        else:
            return "No active Bid War, cannot rename."

    def setBidWarDesc(self, channelName, description):
        # set description for active bid war
        if channelName in self.bidWarDict.keys():
            bidWarID = self.bidWarDict[channelName]["bidWarID"]
            updateBidWar = "UPDATE BidWarList " \
                           "SET displayText = ? " \
                           "WHERE bidWarID = ?"
            self.execute_write_query(self.dbConnection, updateBidWar, (description, bidWarID))
            selectBidWar = "SELECT displayText FROM BidWarText WHERE bidWarID = ?"
            bidWarList = self.execute_read_query(self.dbConnection, selectBidWar, (bidWarID, ))
            if bidWarList[0][0] == description:
                self.bidWarDict[channelName]["text"] = description
                return "Successfully updated the '!warinfo' text for the active Bid War!"
            else:
                return "Could not update the description in the DB, please let t0rm3n7 know."
        else:
            return "No active Bid War, cannot set a description."

    def declareWinner(self, channelName):
        # sort to find winner, clear totals, disable bid war
        if channelName in self.bidWarDict.keys():
            sortTeamsList = sorted(self.bidWarDict[channelName]["teams"].items(), key=lambda x: x[1], reverse=True)
            winner = sortTeamsList[0][0].capitalize()
            self.clearTeamTotals(channelName)
            self.disableBidWar(channelName)
            return "Congratulations to Team " + winner + " for winning the Bid War!"
        else:
            return "No active Bid War for which to declare a winner."

    def autoActivate(self, channelName):
        # After Bot restart, try to load whatever would have been the active Bid War at the time.
        selectBidWar = "SELECT * FROM BidWarList " \
                       "INNER JOIN ChannelList cl USING(channelID)" \
                       "WHERE cl.channelName = ? AND active = 'True'"
        bidWarList = self.execute_read_query(self.dbConnection, selectBidWar, (channelName, ))
        if bidWarList:
            if len(bidWarList) > 1:
                print("Found multiple active bid wars on auto-load, please investigate.")
            else:
                # found active Bid War in database, populate cache
                newBidWarDict = dict(self.defaultBidWarDict)
                newBidWarDict["bidWarID"] = bidWarList[0][0]
                newBidWarDict["channelID"] = bidWarList[0][1]
                newBidWarDict["name"] = bidWarList[0][2]
                newBidWarDict["active"] = bidWarList[0][3]
                newBidWarDict["text"] = bidWarList[0][4]
                self.bidWarDict.update({channelName: newBidWarDict})
                selectTeams = "SELECT * FROM BidWarTeamList " \
                              "WHERE bidWarID = ?"
                teamsList = self.execute_read_query(self.dbConnection, selectTeams, (newBidWarDict["bidWarID"],))
                if teamsList:
                    # found teams for bid war!
                    for teamRow in teamsList:
                        teamName = teamRow[2]
                        teamTotal = teamRow[3]
                        self.bidWarDict[channelName]["teams"].update({teamName: teamTotal})
                    print("Bid war found, loaded into cache.")
                else:
                    # no teams found for bid war
                    print("Bid war found, but no teams found. This might be normal, but please check.")
        else:
            print("No active Bid Wars found in database.")

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