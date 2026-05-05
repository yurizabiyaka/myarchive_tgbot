# myarchive_tgbot
A telegram bot that keeps your notes

# Description
This is a telegram bot which helps organizing various stuff found on the Net: 
links to marketplaces goods you like but not sure,
pages you'd like to read later or never,
interesting news,
funny pictures, family photos, etc.

The bot carefully keeps it and reminds you several times a week of some old days stuff. Just forward to the bot your staff.

Several commands available:
/list displays (paged) cards with your stuff (what you named it, when it was, the content: link, picture, message, etc). You may go back, forth, and delete the card.
/find followed by keywords searches within card descriptions, displays the same paged stuff related to the keywords.
/forgetme removes all the stuff and the user from the DB

# Tech details

## DB
mysql in Docker

## Python version
3.12

## MVP

### Auth
The bot accepts a user on /start, stores the TG account in the DB.
Then, no authentication is required.
/start will have no effect launched 2nd time.

### Help
/help displays commands with descriptions and a banner with Bot's description.

### Stuff accepted

Forward stuff accepted:
- links,
- forwards from groups, tg channels.

Any forwards are stored (with optional description taken from the forward message) in the DB. 
Accept no keywords given in the message. 
Store: message (if any), date/time, its type (a link, a forwarded message), the stuff itself (URL, message id)
