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
* As you know, it is impossible to fill the token window infinitely when working with OpenAI and Anthropic - sooner or later, as the history of dialogues grows, we will hit the token limit. In addition, the cost of each request and the load on the neural network's thought process grow linearly.
* For the bot to work normally, the API used must be able to correctly return the number of tokens used in the request. Working with a maximum token window of less than 8000 has practically not been tested and is not recommended.
* After the first launch, we wait until the cost of a single request exceeds the token threshold specified in the summarizer-limit parameter in config.ini.
* Then we separate 70% of the dialogue volume and retell it using the neural network. The resulting text is called a "memory dump", and we transfer it to the data for the memory neural network. The remaining 30% of the dialogue remains in the main context. This algorithm is called a "lazy summarizer" because it does not lose the dialogue tail, which is necessary for normal communication with the bot.
* Now, with each request to the main neural network, we first make a request to the memory neural network, and if some useful information is found in the "memory dump", it adds it to the text of the request to the main neural network.
* This continues until we again reach the token threshold we specified. After that, we run the "lazy summarizer" algorithm again, and we ask the neural network to combine the resulting "memory dump" with the old "dump" while preserving the important information.
* In theory, this algorithm can allow you to communicate with the bot indefinitely. A faster and cheaper memory network allows you to store large amounts of text information about the character and his communication. In theory, the algorithm can be improved, for example, by switching to RAG with the preservation of several "memory dumps". As neural networks improve, they will increasingly carefully select information to store truly important and relevant data in the character's memory, discarding insignificant details.
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
9. random-response-probability - probability in float with which the bot will respond to a message in public chat that was not addressed to it (where 1 => 100%, 0 => never, 0.01 => 1%, etc.)
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
15. summarizer-engine - determines whether the summarizing mechanism uses the main neural network with its settings or the memory neural network. The value can be changed if the main neural network is not suitable for summarizing due to technical limitations.
## Section [Memory]
The items in the memory level neural network settings correspond to the items in the personality neural network settings, but there you can use another, faster and cheaper neural network, another API, etc.
# Descriptions of prompts in the prompts.py file
1. names - a Python list of nicknames that the bot responds to. The public @-name does not need to be specified in the list. Does not take into account the word cases.
2. start - a basic description of your character that you can freely edit.
3. hard - additional service information that is not recommended to be edited unless you know what you are doing. The system prompt for the bot is sent as "start + hard".
4. prefill - prefills the response that will be sent by the bot. Officially supported by Anthropic (see https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/prefill-claudes-response), and actually works with OpenAI as well. It is recommended to use it to, for example, control the language of the message sent by the bot or its length (the system prompt may not always be effective in the case of an ever-growing context).
5. summarizer - an instruction for compressing the context using a "lazy summarizer". It is recommended to leave it "as is".
6. memory_read - an instruction for getting data from memory using a memory-level neural network. It is recommended to leave it "as is".
7. memory_write - instruction for merging the new "memory dump" obtained during the "lazy summerizer" operation with the old one. It is recommended to leave "as is".
8. memory_prefill - prefills the response for the memory-level neural network. It is recommended to leave "as is".
9. errors - a Python list of aphorisms that are sent to the user in response in case of errors in the bot's operation.
