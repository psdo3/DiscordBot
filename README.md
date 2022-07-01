# **Discord Event Bot**

## Description
A bot with various commands that allow users (with administrator privilege) to interact with on discord. It is created using [Discord.py](https://discordpy.readthedocs.io/en/stable/index.html) library. Note it is currently in BETA version and still need more bug fixes. Please do not spam the reaction emote or the bot cannot add and remove user from database properly

## Features
- Create event using title, date, time
    - Allow users to participate via reactions
    - Store event and user info in mysql database
- Delete event
- Create role
- Delete role
- Add role
- Remove role
- More to come later

## Installation
It is highly recommended to follow the discord.py [installation](https://discordpy.readthedocs.io/en/stable/intro.html#installing) instructions. You will also need to download mysql to get access to the database. Follow their [installation](https://dev.mysql.com/doc/mysql-installation-excerpt/5.7/en/) page to download the correct mysql version on your system.

## Support
Please send me an email at phudo15@yahoo.com for any tips and recommendations to improve the bot

## Roadmap
- Incorperate proper queues and mysql into bot.
- Save the timer task in event of bot shutdown or unexpected failure.
- Resume the event and its timer task on reopen if event deadline has not reach.
- Command to end(cancel) the event without deleting it in database.
- Command to display the amount of time a user has talked in server(guild).
- More to come.

## Authors and acknowledgment
Phu Do - main developer and novice practicing with python
