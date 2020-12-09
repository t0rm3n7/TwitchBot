import sqlite3
from sqlite3 import Error


class NootVsDoot:
    # teams should follow format [noot, doot, etc]
    teams = ["Noot", "Doot", None]
    teamTotals = [0, 0, 0]
    nootBitValue = 1225
    dootBitValue = 1224
    thirdBitValue = 1226
    teamCaptains = []
    active = False
    dbConnection = ""

    def __init__(self):
        self.dbConnection = dbConnection = self.create_connection(".\\points.sqlite")
        print("noot init")

    def isActive(self, channelName):
        return self.active

    def enableNootVsDoot(self, channelName):
        # set Noot and Doot to active in object and database
        selectNVD = "SELECT * FROM NootVsDootMain " \
                    "WHERE channelName = ?"
        activeDB = self.execute_read_query(self.dbConnection, selectNVD, (channelName,))
        if activeDB:
            print(activeDB[0])
            if activeDB[0][2] == 'True':
                # is active already so update from table (load if active already)
                self.teamTotals = [activeDB[0][3], activeDB[0][4], activeDB[0][5]]
                self.teams[2] = activeDB[0][6]
                self.thirdBitValue = activeDB[0][7]
                print("Noot vs Doot is still active, loading values!")
            else:
                # is not currently active so clear out values in the DB and activate
                updateNVD = "UPDATE NootVsDootMain " \
                            "SET active = 'True', nootTotal = 0, dootTotal = 0, " \
                            "thirdTotal = NULL, thirdName = NULL, thirdBitAmount = NULL "\
                            "WHERE channelName = ?"
                self.execute_write_query(self.dbConnection, updateNVD, (channelName,))
                print("Noot vs Doot is not active, resetting any values and enabling!")
        else:
            # is not in DB yet, add to DB
            insertNVD = "INSERT INTO NootVsDootMain " \
                        "(channelName, active, nootTotal, dootTotal, thirdTotal, thirdName, thirdBitAmount) " \
                        "VALUES (?, 'True', 0, 0, NULL, NULL, NULL)"
            self.execute_write_query(self.dbConnection, insertNVD, (channelName,))
            print("Noot vs Doot is not present, creating entry in DB!")
        self.active = True
        print("Noot vs Doot is live!")

    def disableNootVsDoot(self, channelName):
        # set Noot and Doot to inactive in object and database
        selectNVD = "SELECT * FROM NootVsDootMain " \
                    "WHERE channelName = ?"
        activeDB = self.execute_read_query(self.dbConnection, selectNVD, (channelName,))
        if activeDB:
            print(activeDB[0])
            updateNVD = "UPDATE NootVsDootMain " \
                        "SET active = 'False', nootTotal = 0, dootTotal = 0, " \
                        "thirdTotal = NULL, thirdName = NULL, thirdBitAmount = NULL "\
                        "WHERE channelName = ?"
            self.execute_write_query(self.dbConnection, updateNVD, (channelName,))
            self.teams = ["Noot", "Doot", None]
            self.teamTotals = [0, 0, 0]
            self.active = False
            print("The War for Christmas has come to a close.")
        else:
            print("No row found in DB for " + channelName)

    def enableExtraTeam(self, channelName, thirdTeamName, thirdTeamBit):
        # set thirdTeamName as active and set bit value as thirdTeamBit
        selectNVD = "SELECT * FROM NootVsDootMain " \
                    "WHERE channelName = ?"
        activeDB = self.execute_read_query(self.dbConnection, selectNVD, (channelName,))
        if activeDB:
            print(activeDB[0])
            updateNVD = "UPDATE NootVsDootMain " \
                        "SET thirdName = ?, thirdBitAmount = ? " \
                        "WHERE channelName = ?"
            self.execute_write_query(self.dbConnection, updateNVD, (thirdTeamName, thirdTeamBit, channelName))
            self.teams[2] = thirdTeamName
            self.thirdBitValue = thirdTeamBit
            print("Team " + self.teams[2] + " joins the battle! "
                  "Cheer " + str(self.thirdBitValue) + " bits or donate " +
                  str(float(self.thirdBitValue/10)) + " to join Team " + self.teams[2] + "!")
        else:
            print("No row found in DB for " + channelName)

    def addDonation(self, channelName, teamName, viewerName, donation=0):
        # add donation to teamName, donation is broken down into noots/doots if present
        # if no donation present, counts as 1 noot/doot
        if donation > 0:
            print()
        updateNVD = "UPDATE NootVsDootMain " \
                    "SET " \
                    "WHERE channelName = ?"
        self.execute_write_query(self.dbConnection, updateNVD, ())
        updateNVDViewers = "UPDATE NootVsDootViewers" \
                           "SET " \
                           "WHERE channelName = ? AND viewerName = ?"
        self.execute_write_query(self.dbConnection, updateNVDViewers, ())
        print("adding " + str(donation) + " for team " + teamName)

    def removeDonation(self, channelName, teamName, viewerName, donation=0):
        # remove a donation from teamName, donation is broken down into noots/doots if present
        # if no donation present, counts as 1 noot/doot
        print("removing " + str(donation) + " from team " + teamName)

    def teamChange(self, channelName, viewerName, teamName):
        # change viewerName's team affiliation to teamName
        print(viewerName + " is now on team " + teamName)

    def create_connection(self, path):
        connection = None
        try:
            connection = sqlite3.connect(path)
            # print("Connection to SQLite DB successful")
        except Error as e:
            print(f"The error '{e}' occurred")
        return connection

    def execute_write_query(self, connection, query, args):
        cursor = connection.cursor()
        try:
            cursor.execute(query, args)
            connection.commit()
            # print("Query executed successfully")
        except Error as e:
            print(f"The error '{e}' occurred")

    def execute_read_query(self, connection, query, args):
        cursor = connection.cursor()
        result = None
        try:
            cursor.execute(query, args)
            result = cursor.fetchall()
            return result
        except Error as e:
            print(f"The error '{e}' occurred")
