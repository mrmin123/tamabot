tamabot
=======
[/r/PuzzleAndDragons](http://www.reddit.com/r/PuzzleAndDragons) helper bot

##Features
* Finds posts with [Iconified](http://tamadra.com/iconify) monster icons (even ones not yet supported by subreddit styles) and/or [PADX Team Simulator](http://www.puzzledragonx.com/en/simulator.asp) links, grab relevant monster information from [PADX](http://www.puzzledragonx.com/), and posts a reply with the information in a table
* Automatically breaks up expanded monster information table posts into chunks if they become too long
* Monster table is 'hover-to-view' to be less intrusive via subreddit CSS
* Finds 'ID in flair'-type posts, grabs IDs from user's flair, and replies with IDs (for mobile users)
* Bot posts will automatically delete on comment score below 0 (functionality disabled on live bot)
* Parent commenter has ability to delete via PM to bot (+delete [ID] in message body in PM to bot)
* Thread OP/original submitter has ability to tell bot to ignore all posts in thread (+ignore [ID] in message body in PM to bot)
* Commenter can tell tamabot to re-visit a post (+visit [ID] in message body in PM to bot)
* Subreddit mods have ability to delete, ignore thread, re-visit, and shutdown the bot via PM
* Keeps track of ignored threads and processed submissions and comments in case bot crashes and reboots to avoid unnecessary posts

##Dependencies
* Tested on Python 2.7.6
* [PRAW](https://praw.readthedocs.org/)

##Contact
Please PM [/u/mrmin123](http://www.reddit.com/message/compose?to=mrmin123&subject=tamabot) regarding any inquiries or feedback on tamabot.
