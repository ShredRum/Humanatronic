# Humanotronic
ChatGPT-based bot code that imitates a personality, knows the current date and time and the names of those who write to it, remembers events in permanent memory.
# Main features of the bot
* OpenAI and Anthropic API support out of the box (Gemini is planned, if necessary, we can provide an HTML wrapper that converts OpenAI requests to Gemini)
* Transferring the current date and time to the bot at a certain frequency
* Transferring the chat name and speaker's nickname to the bot
* Vision support for all API types
* Convenient work with several characters
* The bot uses a two-layer structure "character neural network" - "memory neural network", which allows it to store information from the dialogue longer
* A ready-made example of a prompt for the convenience of the first launch
# How the "second layer of memory" mechanism works
>Version 2.10 and later (Memory Reboot update) uses a significantly improved "Lazy Summarizer+" memory engine, but the number of tokens it consumes may be unacceptable for you. In this case, you can use version 2.9, but its support has been discontinued (I can fix critical bugs in it upon request). A version with a simplified algorithm that consumes fewer tokens may be released in the future.
* As you know, it is impossible to fill the token window infinitely when working with OpenAI and Anthropic - sooner or later, as the history of dialogues grows, we will hit the token limit. In addition, the cost of each request and the load on the neural network's thought process grow linearly.
* For the bot to work normally, the API used must be able to correctly return the number of tokens used in the request. Working with a maximum token window of less than 8000 has practically not been tested and is not recommended.
* After the first launch, we wait until the cost of a single request exceeds the token threshold specified in the summarizer-limit parameter in config.ini.
* We then extract 70% of the dialogue and retell it using a neural network in a strictly formalized format similar to JSON. We make several requests to the neural network until it sends a confirmation code to ensure it has fully completed the retell and hasn't cut it short. The resulting text is called a "memory dump" and is stored in a database for the memory neural network . The remaining 30% of the dialogue remains in the main context. This algorithm is called a "lazy summarizer" because it doesn't lose the "tail" of the dialogue, which is necessary for normal communication with the bot. A memory dump is not written if its length is less than 400 characters or if it consists only of spaces.
* Now, with each request to the main neural network, we first make a request to the memory neural network, and if some useful information is found in the "memory dump", it adds it to the text of the request to the main neural network.
* This continues until we again reach the token threshold we specified. After that, we run the "lazy summarizer" algorithm again, and we ask the neural network to combine the resulting "memory dump" with the old "dump" while preserving the important information. The process of merging the old and new dumps also uses a mechanism with a completion confirmation code and multiple retries. Furthermore, if the ratio of the lengths of the new and old dumps is less than the value defined in the "summarizer-minimal-ratio" parameter, or if its overall length is less than 400 characters or it consists only of spaces, overwriting the old memory dump is rejected.
* In theory, this algorithm can allow you to communicate with the bot indefinitely. A faster and cheaper memory network allows you to store large amounts of text information about the character and his communication. Maybe the algorithm can be improved, for example, by switching to RAG with the preservation of several "memory dumps". As neural networks improve, they will increasingly carefully select information to store truly important and relevant data in the character's memory, discarding insignificant details.
# How to launch a bot?
1. Download all files from this repository to any folder
2. Edit the prompts.py file as needed (the meaning of each variable is indicated in the corresponding section of this README)
3. (Recommended) Create a separate Python virtual environment and activate it (you will have to activate venv every time you launch the bot)
4. Install all requirements (pip install -r requirements.txt)
5. Run the main.py file (python main.py)
6. You can run main.py with the "folder name" argument (for example, "python main.py my_dear_girl"). The bot will automatically create a folder with this name and a config.ini file in it. You can copy the prompts.py file there and edit it as you like. This feature can be used to run multiple characters independent of each other.
# Description of items in config.ini
## Section [Telegram]
1. token - Telegram API token for the bot.
2. whitelist-chats - comma separated list of chat IDs where the bot can be used, leave empty to allow everyone to use it.
3. unified-context - if True, the conversation history is shared across all chats with the bot, if False, each chat has its own conversation history
4. service-messages - whether the bot responds to the /start command or not (yes, if True).
5. markdown-enable - if True, the bot tries to send a message using Markdown as formatting (if it fails, it will send as is). If False, it will always send the message without formatting.
6. markdown-filter - If True, this parameter removes unnecessary Markdown formatting characters from the text that interfere with reading. Only works if Markdown formatting is disabled or sending a message with Markdown formatting failed.
7. unicode-filter - if True, service characters except tabs and carriage returns are removed from the LLM request. Protects against invisible character attacks, so disabling is strongly discouraged.
8. split-paragraphs - if True, the bot will send text separated by "\n\n" as separate messages.
9. reply-to-quotes - if True, you can quote text from messages (including bot messages) as a replay, and the bot will respond to them, taking into account the quoted text and the text of the main message. If False, the bot will completely ignore the message with the quote.
10. max-answer-len - the maximum length of a message sent in Telegram. If the message is longer, it is automatically divided into parts using a smart parser (at each stage, it tries to divide the message by line breaks, then by sentences, then by words, then by symbols, moving on to a rougher version if the previous one fails). Setting a value greater than 4096 may cause the bot to malfunction when sending messages that are too long.
11. random-response-probability - probability in float with which the bot will respond to a message in public chat that was not addressed to it (where 1 => 100%, 0 => never, 0.01 => 1%, etc.)
## Section [Personality]
1. api-key - key for accessing OpenAI/Anthropic API
2. base-url - URL where OpenAI/Anthropic API requests are sent (empty by default)
3. model - name of the model of the neural network used
4. model-vendor - currently supported values are "openai" or "anthropic". Specify which type of API is used for work.
5. temperature - "temperature" value for the neural network in float
6. timezone - specifies in which time zone the time information for the bot will be shown, takes values (-12..+12)
7. stream-mode - boolean value, specifies whether streaming will be used to access the API (maybe unstable, currently not implemented for OpenAI). The bot continues to send messages in full when using this setting.
8. gen-attempts - how many times the bot tries to get a response from the API before sending an error to the user
9. queue-size - how many simultaneous requests the bot processes
10. summarizer-limit - the size of the dialog in tokens, upon reaching which the "lazy summarizing" process is launched
11. tokens-per-answer - the value of the maximum number of tokens in the API response
12. memory-dump-size - The token limit that is spent on EVERY iteration of the summator (applies to both chat summaries and merging with the old memory dump).
13. vision - This setting has three possible values:
    - enabled - The bot can recognize images and stickers directly. This requires support from both the LLM and the API endpoint.
    - memory-mode - The bot recognizes images and stickers using a dedicated memory neural network. This network generates a text description of the image, which is then sent to the character's primary LLM. This mode allows for image processing if the memory network can recognize them, but the character's LLM cannot.
    - disabled - The bot does not recognize images and stickers.
    > Warning! If you change the "model-vendor" parameter while "vision" is set to "enabled", you must first disable "vision" for the initial run to prevent bot failures. It can be re-enabled afterward.
14. full-debug - the bot saves ALL service information to the logs (request data, API responses, full text of errors that occur), used to debug its operation. It is not recommended to enable it on a permanent basis.
15. summarizer-engine - determines whether the summarizing mechanism uses the main neural network with its settings or the memory neural network. The value can be changed if the main neural network is not suitable for summarizing due to technical limitations.
16. summarizer-iterations - Summarizer-iterations is a number that determines the limit of attempts for summarizing a conversation and merging with an old memory dump. The attempt counter for these two operations is not shared (for example, there are three summarizing attempts and three merging attempts by default, for a total of six requests to LLM).
17. summarizer-minimal-ratio - A safety mechanism to prevent an existing memory dump from being overwritten by a new, significantly shorter one. If the length ratio (new dump / old dump) is less than a specified threshold, the overwrite operation will be rejected.
18. prefill-mode - describes how the prefill will work in a dialogue with the bot
    - assistant - prefill will be added to the assistant role after the message that the user sends to the bot. The standard scheme for Anthropic, see https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/prefill-claudes-response. When used with the OpenAI API, it may give an unpredictable result.
    - pre-user - prefill is added to the very beginning of the text that is sent to the neural network from the user (in addition to the request text from the user, there is a lot of service information)
    - post-user - prefill is added to the end of the text that is sent to the neural network from the user
    - disabled - prefill is completely disabled
You can use full-debug to better understand how service information and prefills work in Humanotronic.
## Section [Memory]
The items in the memory level neural network settings correspond to the items in the personality neural network settings, but there you can use another, faster and cheaper neural network, another API, etc.
# Descriptions of prompts in the prompts.py file
1. names - a Python list of nicknames that the bot responds to. The public @-name does not need to be specified in the list. Does not take into account the word cases.
2. start - a basic description of your character that you can freely edit.
3. hard - additional service information that is not recommended to be edited unless you know what you are doing. The system prompt for the bot is sent as "start + hard".
4. prefill - prefills the response that will be sent by the bot. Officially supported by Anthropic (see https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/prefill-claudes-response), and actually works with OpenAI as well. It is recommended to use it to, for example, control the language of the message sent by the bot or its length (the system prompt may not always be effective in the case of an ever-growing context).
5. summarizer - an instruction for compressing the context using a "lazy summarizer". It is recommended to leave it "as is".
6. memory_read - an instruction for getting data from memory using a memory-level neural network. It is recommended to leave it "as is".
7. memory_write - instruction for merging the new "memory dump" obtained during the "lazy summarizer" operation with the old one. It is recommended to leave "as is".
8. memory_prefill - prefills the response for the memory-level neural network. It is recommended to leave "as is".
9. errors - a Python list of aphorisms that are sent to the user in response in case of errors in the bot's operation.
