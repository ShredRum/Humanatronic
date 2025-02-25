# Humanotronic
ChatGPT-based bot code that imitates a personality, knows the current date and time and the names of those who write to it, remembers events in permanent memory.
# How to launch a bot?
1. Download the attached files to a separate folder
2. (Recommended) Create a separate Python virtual environment and activate it
3. Run the main.py file
4. You can run main.py with the "folder name" argument. The bot will automatically create a folder with this name and a config.ini file in it. You can copy the prompts.py file there and edit it as you like. This feature can be used to run multiple characters independent of each other.
# Description of items in config.ini
## Section [Telegram]
1. token - Telegram API token for the bot.
2. whitelist-chats - comma separated list of chat IDs where the bot can be used, leave empty to allow everyone to use it.
3. unified-context - if True, the conversation history is shared across all chats with the bot, if False, each chat has its own conversation history
4. service-messages - whether the bot responds to the /start command or not (yes, if True).
5. markdown-enable - if True, the bot tries to send a message using Markdown as formatting (if it fails, it will send as is). If False, it will always send the message without formatting.
6. split-paragraphs - if True, the bot will send text separated by "\n\n" as separate messages.
7. reply-to-quotes - if True, you can quote text from messages (including bot messages) as a replay, and the bot will respond to them, taking into account the quoted text and the text of the main message. If False, the bot will completely ignore the message with the quote.
8. max-answer-len - the maximum length of a message sent in Telegram. If the message is longer, it is automatically divided into parts using a smart parser (at each stage, it tries to divide the message by line breaks, then by sentences, then by words, then by symbols, moving on to a rougher version if the previous one fails). Setting a value greater than 4096 may cause the bot to malfunction when sending messages that are too long.
## Section [Personality]
1. api-key - key for accessing OpenAI/Anthropic API
2. base-url - URL where OpenAI/Anthropic API requests are sent (empty by default)
3. model - name of the model of the neural network used
4. model-vendor - currently supported values ​​are "openai" or "anthropic". Specify which type of API is used for work.
5. temperature - "temperature" value for the neural network in float
6. timezone - specifies in which time zone the time information for the bot will be shown, takes values ​​(-12..+12)
7. stream-mode - boolean value, specifies whether streaming will be used to access the API (may be unstable, currently not implemented for OpenAI). The bot continues to send messages in full when using this setting.
8. gen-attempts - how many times the bot tries to get a response from the API before sending an error to the user
9. queue-size - how many simultaneous requests the bot processes
10. summarizer-limit - the size of the dialog in tokens, upon reaching which the "lazy summarizing" process is launched
11. tokens-per-answer - the value of the maximum number of tokens in the API response
12. memory-dump-size - the number of characters limiting the size of the memory dump, use in the "summarizer" prompt parameter using quotation marks {}. Deprecated parameter.
13. vision - if True, the bot will be able to recognize images and stickers (requires support for the used API, must be disabled for the first launch after switching the "model-vendor" parameter)
14. full-debug - the bot saves ALL service information to the logs (request data, API responses, full text of errors that occur), used to debug its operation. It is not recommended to enable it on a permanent basis.
