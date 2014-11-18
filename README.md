tamabot
=======
[/r/PuzzleAndDragons](http://www.reddit.com/r/PuzzleAndDragons) helper bot

##Features
* Finds posts with [Iconified](http://tamadra.github.io/iconify/) monster icons (even ones not yet supported by subreddit styles), grab relevant monster information from [PADX](http://www.puzzledragonx.com/), and posts a reply with the information in a table
* Automatically breaks up monster table posts into chunks if they become too long
* Monster table is 'hover-to-view' to be less intrusive
* Finds 'ID in flair'-type posts, grabs the ID from user's flair, and replies with ID (for mobile users)
* Bot posts will automatically delete on comment score below 0
* Parent commenter has ability to delete via PM to bot
* Subreddit mods have ability to delete via PM to bot
* Subreddit mods can request bot shutdown via PM to bot
* Keeps track of processed submissions and comments in case bot crashes and reboots to avoid repeat posts

##Dependencies
* Tested on Python 2.7.6
* [PRAW](https://praw.readthedocs.org/)

##Contact
Please PM [/u/mrmin123](http://www.reddit.com/message/compose?to=mrmin123&subject=tamabot) about any inquiries or feedback about tamabot.
