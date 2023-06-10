import atexit
import datetime
import json
import pyttsx3
import requests
import time
from playsound import playsound
from twitchio.ext import commands


def log(msg):
    print(f"{datetime.datetime.now()} | {msg}")


def convert_seconds_to_hms(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60

    time_string = ""

    if hours > 0:
        time_string += "{}h".format(hours)

    if minutes > 0:
        time_string += "{}m".format(minutes)

    if seconds > 0:
        time_string += "{}s".format(seconds)

    return time_string.strip()


def read_json(file_path):
    try:
        with open(file_path, "r") as json_file:
            json_data = json.load(json_file)
        return json_data
    except Exception as e:
        log(str(e))


def list_cmd(bot_class):
    cmd_list = []
    for member_name in dir(bot_class):
        member_type = f"{type(getattr(bot_class, member_name))}"
        if member_type == "<class 'twitchio.ext.commands.core.Command'>":
            cmd_list.append(member_name)
    return cmd_list


def gen_audio_cmd():
    audio_path = read_json("settings.json")["audios"]["path"]
    audio_data = read_json(audio_path + "/manifest.json")
    code = ""

    if bool(audio_data) and isinstance(audio_data["audios"], list):
        for audio in audio_data["audios"]:
            if audio["enabled"]:
                code += f"""
@commands.command()
async def {audio["cmd"]}(self, ctx: commands.Context):
    msg = ctx.author.name + " played audio " + "{audio["cmd"]}"
    log(msg)
    playsound("{audio_path}/{audio["file"]}")

Bot.{audio["cmd"]} = {audio["cmd"]}
"""

    return code


def get_twitch_access_token():
    url = "https://id.twitch.tv/oauth2/token"
    secret = read_json("secret.json")
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": secret["twitch-refresh-token"],
        "client_id": secret["twitch-client-id"],
        "client_secret": secret["twitch-client-secret"]
    }

    while True:
        log("Attempting to refresh Twitch access token...")
        response = requests.post(url, headers=headers, data=data)

        if response.status_code == 200:
            response_data = response.json()
            access_token = response_data["access_token"]
            expiration = response_data["expires_in"]
            token_type = response_data["token_type"]
            scope = response_data["scope"]

            log("Successfully acquired access token")
            log(f"Token type: {token_type}")
            log(f"Token scope: {scope}")
            log(f"Token expires in: {convert_seconds_to_hms(expiration)}")
            return access_token

        else:
            response_data = response.json()
            log(json.dumps(response_data))
            delay = 10
            log(f"Waiting for {delay} seconds...")
            time.sleep(delay)


def revoke_twitch_access_token(token):
    url = "https://id.twitch.tv/oauth2/revoke"
    secret = read_json("secret.json")
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "client_id": secret["twitch-client-id"],
        "token": token
    }

    log("Attempting to revoke Twitch access token...")
    response = requests.post(url, headers=headers, data=data)

    if response.status_code == 200:
        log("Successfully revoked token")
    else:
        response_data = response.json()
        log(json.dumps(response_data))


class Bot(commands.Bot):

    def __init__(self):
        settings = read_json("settings.json")

        self.voice_engine = pyttsx3.init()
        voices = self.voice_engine.getProperty("voices")
        self.voice_engine.setProperty("voice", voices[settings["voice"]["id"]].id)
        self.voice_engine.setProperty("rate", settings["voice"]["rate"])
        self.voice_engine.setProperty("volume", settings["voice"]["volume"])

        self.access_token = get_twitch_access_token()
        atexit.register(revoke_twitch_access_token, self.access_token)
        super().__init__(self.access_token,
                         prefix=settings["bot"]["prefix"],
                         initial_channels=[settings["bot"]["channel"]])

    async def event_ready(self):
        log(f"Logged in as {self.nick}")

    async def event_token_expired(self):
        log("Access token has expired")
        return get_twitch_access_token()

    @commands.command()
    async def comandos(self, ctx: commands.Context):
        twitch_line_width = 51  # actually 52 (51 + space)
        pad_char = "_"
        header = " ".rjust(38, pad_char)
        line_sep = " ".rjust(twitch_line_width, pad_char)

        msg = header
        msg += "Comandos Disponíveis".ljust(47, pad_char) + " "

        for cmd in list_cmd(Bot):
            msg += f"!{cmd} "

        msg += line_sep

        await ctx.send(msg)

    @commands.command()
    async def falar(self, ctx: commands.Context):
        msg = ctx.author.name + " disse: " + ctx.message.content.removeprefix("!falar ")
        log(msg)
        self.voice_engine.say(msg)
        self.voice_engine.runAndWait()
        self.voice_engine.stop()


# Generate audio commands from JSON
exec(gen_audio_cmd())

# Run bot
bot = Bot()
bot.run()

