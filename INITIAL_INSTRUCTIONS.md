GOAL
----

This tool is aimed to be assisting journalists and story writers.
Given a possibly very short sketch of a story, it will be able to automatically
utilize LLMs such as OpenAI's or Anthropic's or Google's in order to provide
answers to a set of generic pre-configured questions on the input story sketch.

Those LLMs will absolutely need to be the ones that will have internal
web search tooling enabled.

So, the user inputs a story sketch and gets a lot of new information in different
sections related to the story.

TECH
----

The tool necessarily needs a back-end to be able to call the LLMs APIs,
and for security as well. It will be in python. No need for persistency yet.
Also think a way where the keys for the LLMs access have to be stored (maybe
a file or some other way that you might find suitable).

For the front-end, you choose the most suitable tech, because I'm not a
front-end developer.

To make the website, follow instructions in /frontend-design/SKILL.md

Make a python environment .venv with uv.

Before starting working, tell the user what he needs to install, possibly
via scoop.

FEATURES
--------

The interface will have a text box where the user is going to write the 
story sketch.

Then there will be other textboxes that will be populated by the responses
that the LLMs are outputting on each previously configured question.

The user also need to be able to edit, add, remove such configurable questions.

