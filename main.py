import discord
import mysql.connector
from datetime import datetime
from queue import Queue
from discord.utils import get
from discord.ext import commands, tasks

intents = discord.Intents.all()
client = commands.Bot(command_prefix = '!', intents = intents)
eventDictionary = {} #Empty dictionary where task will be put later
discordBotDB = None 
queryQueue = Queue() #FIFO Queue

'''
Premade function from discord.py that run when bot start.
If connection is successful to discord then it will try to connect to the database
Then it will delete all the events that is remaining in EVENTS table
'''
@client.event
async def on_ready():
    global discordBotDB
    print(f"We have logged in as {client.user}")
    discordBotDB = mysql.connector.connect(user = "discordBot", password = "nexx", host = "127.0.0.0", database = "discordBotDB") #Connect to the discodBotDB using mysql.connector
    cursor = discordBotDB.cursor()
    cursor.execute("DELETE FROM EVENTS")
    cursor.close()
    discordBotDB.commit()

'''
A task loop from discord that will loop this function every second
The function will check if queue is not empty and will get everything in queue and execute it in mysql database query
'''
@tasks.loop(seconds = 1)
async def mySQLQuery():
    global discordBotDB
    while(queryQueue.qsize() > 0): #Will run if query is not empty
        cursor = discordBotDB.cursor()
        queryList = queryQueue.get() #Retrieve from queue and put it in a list
        cursor.execute(queryList[0], queryList[1]) #Execute the query and its values obtained from index 0,1 of queryList
        cursor.close()
        discordBotDB.commit()

'''
Creating event on command using the newTitle, date, time
newTitle: the name of event
date: the date of the event in YYYY-MM-DD format
time: the time of the event in HH:MM format
'''
@client.command()
@commands.has_role("Officer")
async def createEvent(ctx, newTitle, date, time):
    global discordBotDB
    title = newTitle.strip().capitalize() #Capitalize the name and exclude any spaces
    if len(title) > 20: #Check if title length is greater than 20 characters long
        await ctx.channel.send(f"Title {title} is greater than 20 characters long")
    else: #Else check if the date and time is in valid format
        isValidDate = True
        isValidTime = True
        try: #Check whether the input date is in a valid format
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError: #Date is not valid format
            isValidDate = False
        try:#Check whether the input time is in a valid format
            datetime.strptime(time, "%H:%M")
        except: #Time is not valid format
            isValidTime = False
        if isValidDate == False: #If validDate is in incorrect format
            await ctx.channel.send(f"Date {date} is invalid please use MM-DD-YYYY")
        elif isValidTime == False: #If validTime is in incorrect format
            await ctx.channel.send(f"Time {time} is invalid please use HH:MM")
        else: #Else check if event is in Database
            if checkDBForTitle(title) == True: #Check if title is in Database
                await ctx.channel.send(f"Event {title} already exist")
            else: #Else create the role and added the event to Database
                await createRole(ctx, title) #Create the role
                insertIntoEventsTable(title, date, time) #Insert event info to Database
                guildTitleRole = get(ctx.guild.roles, name = title) #Check if guild has the role
                eventMessage = await ctx.channel.send(f"Title: <@&{guildTitleRole.id}>, Date: {date}, Time: {time}") #Display eventMessage in discord
                guildEmoji = await ctx.guild.fetch_emojis() #Get all custom emojis in the server
                damageDealer = get(guildEmoji, name = "DD") #DD emoji class
                support = get(guildEmoji, name = "SUP") #SUP emoji class
                await eventMessage.add_reaction(damageDealer) #Add DD emoji to eventMessage
                await eventMessage.add_reaction(support) #Add SUP emoji to eventMessage
                eventDateTime = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M") #Combine date and time to YYYY-MM-DD HH:MM Format
                eventTime = datetime(eventDateTime.year, eventDateTime.month, eventDateTime.day, eventDateTime.hour, eventDateTime.minute) #Get the event time
                timeLeft = eventTime - datetime.now() #Calculate the remaining time
                countdownMessage = await ctx.channel.send(f"Time remaining: {timeLeft}") #Display the remaining time in discord
                createTask(ctx, countdownMessage, eventTime, title) #Create a task for the event
                mySQLQuery.start() #Start the mySQLQuery loop

'''
Check Database if title exist using SELECT Query
title: the name of event
Will return True if title exist else False
'''
def checkDBForTitle(title):
    cursor = discordBotDB.cursor()
    checkIfTitleExist = ("SELECT * FROM EVENTS WHERE Title = %s") #mySQL Query
    titleTuple = (title,) #Value to be put in query
    cursor.execute(checkIfTitleExist, titleTuple) #Execute the query with value
    checkIfTitleExistResult = cursor.fetchone() #Retrieve the first row of SELECT result
    cursor.close()
    return checkIfTitleExistResult #True or False

'''
Insert event info into Database using INSERT Query
title: the name of event
date: the date of event
time: the time of event
'''
def insertIntoEventsTable(title, date, time):
    cursor = discordBotDB.cursor()
    insertTitleDateTime = ("INSERT INTO EVENTS (Title, Date, Time) VALUES (%s, %s, %s)") #mySQL Query
    titleDateTimeValues = (title, date, time) #Values to be put in query
    cursor.execute(insertTitleDateTime, titleDateTimeValues) #Execute the query with value
    cursor.close()
    discordBotDB.commit()

'''
Delete event from Database using DELETE Query
title: the name of event
'''
def deleteEventFromTable(title):
    cursor = discordBotDB.cursor()
    deleteEvent = ("DELETE FROM EVENTS WHERE Title = %s") #mySQL Query
    titleTuple = (title,) #Values to be put in query
    cursor.execute(deleteEvent, titleTuple) #Execute the query with value
    cursor.close()
    discordBotDB.commit()

'''
Create a task class and add it to eventDictionary as value for the key '{title}task'
It also start the task class and loop the timer function every 60 seconds
eventMessage: the main message that display the event title, date, and time
countdownMessage: the message that display the time remaining till event start
title: the name of event
'''
def createTask(ctx, countdownMessage, eventTime, title):
    global eventDictionary
    task = tasks.loop(seconds = 60)(timer) #Create the task
    eventDictionary[f"{title}task"] = task #Insert task into dictionary
    task.start(ctx, countdownMessage, eventTime, title) #Start the task

'''
Calculate the time remaining and edit the countdownMessage accordingly
It will also ping one hour ahead of event time and delete the event from database once it start
eventMessage: the main message that display the event title, date, and time
countdownMessage: the message that display the time remaining till event start
eventTime: the date and time of event
title: the name of event
'''
async def timer(ctx, countdownMessage, eventTime, title):
    difference = eventTime - datetime.now() #Calculate the time remaining
    days = difference.days #Getting the days left
    hours = difference.seconds // 3600 #Getting the hours left
    minutes = (difference.seconds // 60) % 60 #Getting the minutes left
    if days == 0 and hours == 1 and minutes == 0: #Check if it is one hour before event start
        roleName = get(ctx.guild.roles, name = title) #Get the event role
        await ctx.channel.send(f"Friendly reminder that event {roleName.mention} will start in 1 hour") #Ping the event role in discord
    if days == -1: #Check a day has pass since event started
        await deleteEvent(ctx, title) #Delete the event from database and the task from eventDictionary
    else: #Else edit the countdownMessage
        print(f"Edit {title} successful")
        await countdownMessage.edit(content = f"Days: {days}, Hours: {hours}, Minutes: {minutes}") #Edit the countdownMessage with the correct time

'''
Delete event with command using newTitle
newTitle: the name of event
'''
@client.command()
@commands.has_role("Officer")
async def deleteEvent(ctx, newTitle):
    global eventDictionary
    global discordBotDB
    title = newTitle.strip().capitalize() #Capitalize the name and exclude any spaces
    if len(title) > 20: #Check if title is greater than 20 characters long
        await ctx.channel.send(f"Title {title} is greater than 20 characters long")
    else: #Else check if title is in database
        if checkDBForTitle(title) == False: #Check if title does not exist in database
            await ctx.channel.send(f"Event {title} does not exist")
        else: #Else check if {title}task exist in eventDictionary
            task = eventDictionary.get(f"{title}task")
            try: #Try to pop the task from dictionary and cancel the task
                eventDictionary.pop(f"{title}task") #Remove task from dictionary
                task.cancel() #Cancel task
            except:
                print(f"{title}task does not exist")
            finally: #Finally delete the event and role
                deleteEventFromTable(title) #Delete event from database
                await deleteRole(ctx, title) #Delete role from discord
                await ctx.channel.send(f"Event {title} has ended")

'''
Create role in discord using roleName
roleName = the name of the role
'''
@client.command()
@commands.has_role("Officer")
async def createRole(ctx, roleName):
    roleName = roleName.strip().capitalize() #Capitalize the name and exclude any spaces
    if len(roleName) > 20: #Check if roleName is greater than 20 characters long
        await ctx.channel.send(f"{roleName} is greater than 20 characters long")
    else:
        guildRoleList = ctx.guild.roles #Get a list of roles in guild
        roleExist = get(guildRoleList, name = roleName) #Find if the role already exist
        if roleExist == None: #If it does not exist
            await ctx.guild.create_role(name = roleName, mentionable = True) #Create the role using the roleName

'''
Delete role in discord using roleName
roleName: the name of the role
'''
@client.command()
@commands.has_role("Officer")
async def deleteRole(ctx, roleName):
    roleName = roleName.strip().capitalize() #Capitalize the name and exclude any spaces
    if len(roleName) > 20: #Check if roleName is greater than 20 characters long
        await ctx.channel.send("Role name is greater than 20 characters long")
    else: #Else get the role
        guildRoleList = ctx.guild.roles #Get a list of roles in guild
        deleteRoleName = get(guildRoleList, name = roleName) #Get the role to be deleted
        if deleteRoleName != None: #If the role exist
            await deleteRoleName.delete() #Delete the role

'''
Add role to user using roleName and user
roleName: the name of the role
user: the user getting the role
'''
@client.command()
@commands.has_role("Officer")
async def addRole(ctx, roleName, user):
    roleName = roleName.strip().capitalize() #Capitalize the name and exclude any spaces
    if len(roleName) > 20: #Check if roleName is greater than 20 characters long
            await ctx.channel.send(f"Role {roleName} exceed 20 characters long")
    else: #Else check if user is in integet or string form
        guildUserList = ctx.guild.members #List of users from guild
        if user.isdigit(): #Check if input user is in integer form
            guildUserName = get(guildUserList, id = int(user)) #Get the user from id
        else: #Else if input user is in string form
            guildUserName = get(guildUserList, name = user) #Get the user from name
        if guildUserName != None: #Check if user is in the guild
            guildRoleList = ctx.guild.roles #List of roles in the guild
            userRoleList = guildUserName.roles #List of roles from user
            guildRolename = get(guildRoleList, name = roleName) #Get the role from guild role list
            userRoleName = get(userRoleList, name = roleName) #Get the role from user role list
            if guildRolename == None: #Check if guild has role
                await ctx.channel.send(f"Role {roleName} does not exist in guild")
            elif userRoleName == None: #Check if user has role
                await guildUserName.add_roles(guildRolename) #Add the role to user
                await ctx.channel.send(f"Role {guildRolename} has been added to user {guildUserName}")

'''
Remove role from user using roleName and user
roleName: the name of the role
user: the user to have their role remove
'''
@client.command()
@commands.has_role("Officer")
async def removeRole(ctx, roleName, user):
    roleName = roleName.strip().capitalize() #Capitalize the name and exclude any spaces
    if len(roleName) > 20: #Check if roleName is greater than 20 characters long
            await ctx.channel.send(f"Role {roleName} exceed 20 characters long")
    else: #Else check if user is in integet or string form
        guildUserList = ctx.guild.members #List of users in guild
        if user.isdigit(): #Check if input user is in integer form
            guildUserName = get(guildUserList, id = int(user)) #Get the user from id
        else: #Else if input user is in string form
            guildUserName = get(guildUserList, name = user) #Get the user from name
        if guildUserName != None: #Check if user is in the guild
            guildRoleList = ctx.guild.roles #List of roles in guild
            guildRolename = get(guildRoleList, name = roleName) #Get the role from guild role list
            if guildRolename == None: #Check if guild has role
                await ctx.channel.send(f"Role {roleName} does not exist in guild")
            else: #Else remove the role from user
                await guildUserName.remove_roles(guildRolename)
                await ctx.channel.send(f"Role {guildRolename} has been removed from user {guildUserName}")

'''
Get the value of ReactionRemove from database using SELECT
userID: the ID of the user
'''
def selectReactionRemove(userID):
    cursor = discordBotDB.cursor()
    selectRR = ("SELECT ReactionRemove FROM PLAYERS WHERE UserID = %s") #mySQL Query
    userIDTuple = (userID,) #Values to be put in query
    cursor.execute(selectRR, userIDTuple) #Execute the query with its value
    selectRRResult = cursor.fetchone() #Retrieve the first row of SELECT result
    cursor.close()
    try: #Try to return the value from index 0 of selectRRResult
        return selectRRResult[0]
    except: #If it fail then return 1
        return 1

'''
Get the number of players in a particular event using SELECT
event: the name of event
'''
def numberOfPlayers(event):
    cursor = discordBotDB.cursor()
    playersInEvent = ("SELECT COUNT(Event) FROM PLAYERS WHERE Event = %s") #mySQL Query
    eventTuple = (event,) #Values to be put in query
    cursor.execute(playersInEvent, eventTuple) #Execute the query with its value
    numberOfPlayers = cursor.fetchone() #Retrieve the first row of SELECT result
    cursor.close()
    return numberOfPlayers[0]

'''
Put the UPDATE query and its value into queue
number: the update value
userID: the id of user
'''
async def updateReactionRemove(number, userID):
    updateRR = ("UPDATE PLAYERS SET ReactionRemove = ReactionRemove + %s WHERE UserID = %s") #mySQL Query
    updateRRValues = (number, userID) #Values to be put in query
    queryQueue.put((updateRR, updateRRValues)) #Put query and its value into queue


'''
Put the INSERT Query and its value into queue
event: the name of event
userName: the name of user
userID: the id of user
userRole: the role of user
RemoveReaction: the reaction flag to remove the user. 0 will remove the user else nothing
'''
def insertUserINFO(event, userName, userID, userRole, RemoveReaction):
    insertUser = ("INSERT INTO PLAYERS (Event, UserName, UserID, UserRole, ReactionRemove) VALUES (%s, %s, %s, %s, %s)") #mySQL Query
    userINFO = (event, userName, userID, userRole, RemoveReaction) #Values to be put in query
    queryQueue.put((insertUser, userINFO)) #Put query and its value into queue

'''
Put the Delete Query and its value into queue
userID: the id of user
'''
def deleteUserRow(userID):
    deleteUser = ("DELETE FROM PLAYERS WHERE UserID = %s") #mySQL Query
    userIDTuple = (userID,) #Values to be put in query
    queryQueue.put((deleteUser, userIDTuple)) #Put query and its value into queue

'''
Will trigger when a reaction is added in a certain channel
reaction: the reaction that was trigger
user: the user that that use the reaction
'''
@client.event
async def on_reaction_add(reaction, user):
    global discordBotDB
    channel = reaction.message.channel #The channel that the reaction was in
    if user.bot != True and channel.id == 989632089328603156: #Check if user is not a bot and is in the right channel
        reactionRoleList = reaction.message.role_mentions #Get the list of roles that was mentioned in the message that was reacted to
        roleName = reactionRoleList[0] #The role that was mentioned
        userRoleName = get(user.roles, name = roleName.name) #Get the list of roles in user
        if userRoleName != None: #Check if user already has role
            await updateReactionRemove(1, user.id) #Update ReactionRemove by increment by 1
            discordBotDB.commit()
            await reaction.remove(user) #Remove the reaction
        else: #Else check if numberOfPlayers is under 8
            playerLength = numberOfPlayers(roleName.name)
            if playerLength > 8: #If numberOfPlayers is greater than 8
                await reaction.remove(user) #Remove the reaction
                channel.send(f"Number of participants is full for {roleName}")
            else: #Else add user to PLAYERS table
                print(f"{roleName} has been added to {user}")
                insertUserINFO(roleName.name, user.name, user.id, reaction.emoji.name, 1) #Insert user info into database
                discordBotDB.commit()
                await user.add_roles(roleName) #Add role to user

'''
Will trigger when a reaction is removed in a certain channel
reaction: the reaction that was trigger
user: the user that that use the reaction
'''
@client.event
async def on_reaction_remove(reaction, user):
    global discordBotDB
    channel = reaction.message.channel #The channel that the reaction was in
    if user.bot != True and channel.id == 989632089328603156: #Check if user is not a bot and is in the right channel
        reactionRoleList = reaction.message.role_mentions #Get the list of roles that was mentioned in the message that was reacted to
        roleName = reactionRoleList[0] #The role that was mentioned
        userRoleName = get(user.roles, name = roleName.name) #Get the list of roles in user
        if userRoleName != None: #Check if user already has role
            await updateReactionRemove(-1, user.id) #Update ReactionRemove by decrement by 1
            reactionRemove = selectReactionRemove(user.id) #Get the value of ReactionRemove
            if reactionRemove == 0: #Check if ReactionRemove is flag 0
                print(f"{roleName} has been removed from {user}")
                deleteUserRow(user.id) #Delete user from PLAYERS table
                await user.remove_roles(roleName) #Remove role from user
            discordBotDB.commit()

client.run("OTg3NDUyNDgwMzEwOTAyOTA0.G-mDol.er4xY5ILPX7b6llKKZzDbE-ALRgpF5fDbY9VyA")