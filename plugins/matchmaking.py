import discord
from discord.ext import commands, tasks
import configparser
import re

from utils import common

LFG_COMMAND = "match"

CONFIG_GAMES_COMMANDS = "GamesCommands"
CONFIG_GAMES_NAMES = "GamesFullNames"
CONFIG_GAMES_ROLES = "GamesRoles"
CONFIG_GAMES_ICONS = "GamesIcons"
CONFIG_GAMES_COLORS = "GamesColors"
CONFIG_GAMES_FORUMS = "GamesForums"
CONFIG_GAMES_TAGS = "GamesTags"

EMOJI_JOIN = "👍"
EMOJI_NOTIFY = "🔔"
EMOJI_CANCEL = "❌"
EMOJI_START = "✅"
EMOJIS_VALID = [EMOJI_JOIN, EMOJI_NOTIFY, EMOJI_CANCEL, EMOJI_START]
EMOJIS_CLOSE = [EMOJI_CANCEL, EMOJI_START]

DEFAULT_AVATAR_URL = "https://i.imgur.com/xClQZ1Q.png"

THREAD_TYPES = [discord.ChannelType.public_thread,
                discord.ChannelType.private_thread,
                discord.ChannelType.news_thread]

class matchmaking(commands.Cog):

    def __init__(self, bot, config = None):
        print("Match making plugin started.")
        self.bot = bot
        self.config = config

        activity_text = str(self.bot.command_prefix) + LFG_COMMAND
        activity = self.bot.activity
        if (activity is None):
            activity = discord.Game(name=activity_text)
        else:
            activity.name += " | " + activity_text
        self.bot.activity = activity

        self.custom_emoji_re = re.compile(r"<:[\w]+:[\d]+>")

        ## New feature to converge
        # self.threads = []
        # self.refresh_threads.start()

    def cog_unload(self):
        # self.refresh_threads.cancel()
        super().cog_unload()

    def get_configured_games(self, guild_id, *args):
        guild = common.get_guild_from_config(self.config, guild_id)

        result = []
        for arg in args:
            result.append(common.split_config_list(self.config.get(guild, arg, fallback=None)))

        return tuple(result)

    @tasks.loop(hours=23)
    async def refresh_threads(self):
        valid_threads = []
        for thread in self.threads:
            try:
                if (not(thread.archived)):
                    await thread.send(content="Daily refresh! Enjoy!\nIf this game is over, please let me know!")
                    valid_threads.append(thread)
            except Exception as error:
                print(error)
        self.threads = valid_threads
        print("Refreshed threads:\n", self.threads)

    async def lfg_help(self, ctx):
        text = "Pour annoncer une nouvelle partie :\n"
        text += "\n"
        text += "`" + ctx.prefix + LFG_COMMAND
        text += " <mode> <description>`\n"
        text += "ou\n"
        text += "`" + ctx.prefix + LFG_COMMAND
        text += " <description>`  (personnalisé - sans @mention)\n"
        text += "\n"
        text += "remplace  `<mode>`  par l'un des 4 modes de jeu ci-dessous\n"
        text += "et  `<description>`  par tes options de jeu ou toute autre info\n"

        games, gamesNames = self.get_configured_games(ctx.guild.id, CONFIG_GAMES_COMMANDS, CONFIG_GAMES_NAMES)

        commands_list = []
        align = len(max(games, key=len))
        for game in games:
            index = games.index(game)
            command_text = "• `"
            command_text += game
            command_text += " " * (align-len(game)) + "`"
            if (len(gamesNames) == len(games) and len(gamesNames[index])):
                command_text += "  : pour "
                command_text += "**" + gamesNames[index] + "**"
            command_text += "\n"
            commands_list.append(command_text)

        embed = discord.Embed(description="".join(commands_list))

        await ctx.send(text,embed=embed)

    @commands.command(name=LFG_COMMAND)
    async def lfg(self, ctx, *desc):
        if (not(len(desc)) or desc[0] == common.HELP_COMMAND):
            return await self.lfg_help(ctx)
        else:
            return await self.lfg_v2(ctx, *desc)

    @commands.command()
    async def lfg_v2(self, ctx, *desc):
        games, gamesNames, gamesRoles, gamesIcons, gamesColors = \
        self.get_configured_games(ctx.guild.id, CONFIG_GAMES_COMMANDS, \
                                  CONFIG_GAMES_NAMES, CONFIG_GAMES_ROLES, \
                                  CONFIG_GAMES_ICONS, CONFIG_GAMES_COLORS)

        gameWanted = "match"
        gameRole = ""
        gameIcon = ""
        gameColor = ""
        if (len(desc) and desc[0] in games):
            index = games.index(desc[0])
            if (len(gamesNames) == len(games) and len(gamesNames[index])):
                gameWanted = gamesNames[index]
            if (len(gamesRoles) == len(games) and len(gamesRoles[index])):
                gameRole = gamesRoles[index]
            if (len(gamesIcons) == len(games) and len(gamesIcons[index])):
                gameIcon = gamesIcons[index]
            if (len(gamesColors) == len(games) and len(gamesColors[index])):
                gameColor = gamesColors[index]
            desc = desc[1:]

        text = ""
        if (len(desc)):
            text += " ".join(desc)
        embed = discord.Embed(description=text)
        embed.set_footer(text="Un fil de discussion sera créé automatiquement\nquand vous fermerez la partie avec ✅.")

        if (len(gameRole)):
            embed.add_field(name="Joueurs", value=gameRole, inline=True)

        # Member and User return different mentions for server nicknames...
        # So this :
        # field_text = ctx.message.author.mention
        # can give exclamation marks on the IDs
        # and can break comparisons of mentions when reacting
        # We need the User object
        user = self.bot.get_user(int(ctx.message.author.id))
        field_text = user.mention
        embed.add_field(name="Hôte", value=field_text, inline=True)

        author_avatar = common.DEFAULT_AVATAR_URL
        display_avatar = ctx.message.author.display_avatar
        if (display_avatar is not None):
            author_avatar = display_avatar.url
        embed.set_author(name=ctx.message.author.display_name,
                         icon_url=author_avatar)

        embed.title = "Qui pour "
        embed.title += "un " + gameWanted + " ?"

        if (not(len(gameIcon))):
            gameIcon = common.DEFAULT_AVATAR_URL
        embed.set_thumbnail(url=gameIcon)

        if (not(len(gameColor))):
            gameColor = ctx.message.author.colour
        embed.colour = gameColor

        try:
            await ctx.message.delete()
        except Exception as error:
            print(error)

        try:
            # Ghost pings are not reliable anymore...
            # if (len(gameRole)):
            #     bot_message = await ctx.send(content=gameRole)
            #     await bot_message.edit(content="", embed=embed)
            # else:
            #     bot_message = await ctx.send(content="", embed=embed)
            bot_message = await ctx.send(content=gameRole, embed=embed)
            for emoji in EMOJIS_VALID:
                await bot_message.add_reaction(emoji)
        except Exception as error:
            print(error)

    @commands.command()
    async def rename_thread(self, ctx, *desc):
        thread = ctx.channel
        if (not(thread.type in THREAD_TYPES)):
            return False

        if (int(thread.owner_id) != int(self.bot.user.id)):
            return False

        try:
            await thread.edit(name=common.clean_thread_title(" ".join(desc),
                                                        self.custom_emoji_re))
        except Exception as e:
            print(e)

    @commands.Cog.listener(name = "on_raw_reaction_add")
    @commands.Cog.listener(name = "on_raw_reaction_remove")
    async def refresh_message_embed(self, payload):
        if int(payload.user_id) == int(self.bot.user.id):
            return False

        emoji_name = str(payload.emoji.name)
        if emoji_name not in EMOJIS_VALID:
            return False

        user = self.bot.get_user(int(payload.user_id))
        channel = self.bot.get_channel(int(payload.channel_id))
        message = await channel.fetch_message(int(payload.message_id))
        if (message.author.id != self.bot.user.id):
            return False

        title = ""
        if (len(message.embeds)):
            title = str(message.embeds[0].title)
        if (not(title.startswith("Qui pour"))):
            return False

        # Recover target role and host
        embed = message.embeds[0]
        fields = embed.fields
        host = ""
        target = ""
        for field in fields:
            if (field.name == "Hôte"):
                host = field.value
            if (field.name == "Joueurs"):
                target = field.value
        if (not(len(message.reactions)) # Game already closed, reactions cleaned
            or not(len(host))): # Should not happen...
            return False

        # Recover players (and users to notify)
        players = []
        users_to_notify = []
        for reaction in message.reactions:
            reaction_users = await reaction.users().flatten()
            if ((self.bot.user not in reaction_users) \
                and (str(reaction) in EMOJIS_VALID)):
                return False # Game already closed, reactions cleaned
            reaction_users.remove(self.bot.user)
            if str(reaction) == EMOJI_JOIN:
                players = reaction_users
            if str(reaction) == EMOJI_NOTIFY:
                users_to_notify = reaction_users
        guests = ""
        for player in players:
            if (player.mention == host):
                continue
            if (len(guests)):
                guests += ", "
            guests += player.mention

        if (emoji_name == EMOJI_JOIN and user.mention != host):
            embed.clear_fields()
            if (len(target)):
                embed.add_field(name="Joueurs", value=target, inline=True)
            embed.add_field(name="Hôte", value=host, inline=True)
            if (len(guests)):
                embed.add_field(name ="Participants", value=guests, inline=False)
            try:
                await message.edit(embed=embed)
            except Exception as error:
                print(error)

            if (user in players):
                for user_to_notify in users_to_notify:
                    if (user_to_notify == user):
                        continue
                    message_to_send = "Un joueur (" + str(user) + ")"
                    message_to_send += " a rejoint la partie"
                    message_to_send += " dans "
                    message_to_send += channel.mention + ".\n"
                    if (user_to_notify.mention == host):
                        message_to_send += "Quand la table est complète,"
                        message_to_send += " ouvre un fil de discussion avec "
                        message_to_send += EMOJI_START + ", tous les joueurs"
                        message_to_send += " seront @mentionnés. GLHF!"
                    else:
                        message_to_send += "Tu seras @mentionné "
                        message_to_send += " quand la partie pourra démarrer. GLHF!"
                    try:
                        await user_to_notify.send(message_to_send)
                    except Exception as e:
                        print(e)
                        print("MP impossible " + str(user_to_notify))

        if (str(payload.emoji.name) in EMOJIS_CLOSE and user.mention == host):
            emoji_url = payload.emoji.url
            if (not(len(emoji_url))):
                emoji_url = common.get_default_emoji_url(emoji_name)
            embed.set_footer(text="Table complète, désolé !", icon_url=emoji_url)
            try:
                await message.edit(embed=embed)
                await message.clear_reactions()
            except Exception as error:
                print(error)

            # New feature: create thread
            # 3 cases: a) Do nothing if this message already has a thread
            #          b) Create thread in a (forum) channel if available
            #          c) Create thread under this message otherwise
            if (str(payload.emoji.name) == EMOJI_START and message.thread is None):
                gamesRoles, gamesForums, gamesTags = \
                self.get_configured_games(payload.guild_id, \
                                          CONFIG_GAMES_ROLES, \
                                          CONFIG_GAMES_FORUMS, \
                                          CONFIG_GAMES_TAGS)
                nbGames = len(gamesForums)
                index = -1
                if (nbGames and nbGames == len(gamesRoles) and target in gamesRoles):
                    index = gamesRoles.index(target)

                thread_channel = channel
                parent_message = message
                thread_in_forum = False
                thread_pings = host
                if (len(guests)):
                    thread_pings += ", " + guests
                thread_message = thread_pings + ", "
                thread_message += "la partie peut démarrer ! GLHF!"

                # Thread title = embed description without custom emojis
                thread_title = embed.description
                thread_title = common.clean_thread_title(thread_title, self.custom_emoji_re)
                # if (len(thread_title)):
                #     thread_title = "".join(self.custom_emoji_re.split(thread_title))
                # if (len(thread_title) > 100): # discord refuses thread if title too long
                #     thread_title = thread_title[:100]
                # if (not(len(thread_title))):
                #     thread_title = "Game thread"

                keywords = {}
                keywords['name'] = thread_title

                if (index >= 0 and index < nbGames):
                    forum_id = gamesForums[index]
                    forum = None
                    tag_name = ""
                    if (nbGames == len(gamesTags)):
                        tag_name = gamesTags[index]
                    if (len(forum_id)):
                        forum = self.bot.get_channel(int(forum_id))
                    if (forum is not None):
                        thread_in_forum = True
                        thread_channel = forum
                        thread_embed = embed.copy()
                        thread_embed.remove_footer()
                        thread_tag = None
                        if (len(tag_name)):
                            for forum_tag in forum.available_tags:
                                if (forum_tag.name == tag_name):
                                    thread_tag = forum_tag
                        if (thread_tag is not None):
                            keywords['applied_tags'] = [thread_tag]
                        keywords['content'] = thread_message
                        keywords['embed'] = thread_embed

                if (not(thread_in_forum)):
                    keywords['message'] = parent_message
                    keywords['type'] = discord.ChannelType.public_thread

                try:
                    thread = await thread_channel.create_thread(**keywords)
                    if (not(thread_in_forum)):
                        await thread.send(content=thread_message)
                except Exception as e:
                    print(e)

def setup(bot):
    config = configparser.ConfigParser()
    config.read('config/games.ini')
    bot.add_cog(matchmaking(bot, config))
