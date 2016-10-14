# Keypirinha: a fast launcher for Windows (keypirinha.com)

import keypirinha as kp
import keypirinha_util as kpu
import keypirinha_wintypes as kpwt
import urllib.parse
import re
import io
import ast
import tokenize
import math
import decimal
import random
import traceback
from .lib import requests
from .lib import simpleeval
from xml import etree

class WA(kp.Plugin):
    """
    WolframAlpha at your fingertips.

    Requests information from WolframAlpha
    """

    DEFAULT_KEYWORD = ":W"
    DEFAULT_API_KEY = ""
    DEFAULT_MANUAL = True

    apiKey = DEFAULT_API_KEY
    api_url = 'http://api.wolframalpha.com/v2/query'
    query_url = 'http://www.wolframalpha.com/input/?i={}'
    manual = DEFAULT_MANUAL

    def __init__(self):
        super().__init__()

    def on_start(self):
        self._read_config()

    def on_catalog(self):
        self.set_catalog([self.create_item(
            category=kp.ItemCategory.KEYWORD,
            label=self.DEFAULT_KEYWORD,
            short_desc="Ask WolframAlpha",
            target=self.DEFAULT_KEYWORD,
            args_hint=kp.ItemArgsHint.REQUIRED,
            hit_hint=kp.ItemHitHint.NOARGS)])

    def on_suggest(self, user_input, items_chain):
        if not len(user_input):
            return
        if items_chain and (
                items_chain[0].category() != kp.ItemCategory.KEYWORD or
                items_chain[0].target() != self.DEFAULT_KEYWORD):
            return

        eval_requested = False
        if user_input.startswith(self.DEFAULT_KEYWORD):
            # always evaluate if expression is prefixed by DEFAULT_KEYWORD
            user_input = user_input[1:].strip()
            if not len(user_input):
                return
            eval_requested = True
        elif items_chain:
            eval_requested = True
        elif not items_chain:
            return

        results = self._thing(user_input)
        if not isinstance(results, (tuple, list)):
            results = (results,)

        self.set_suggestions(results, kp.Match.ANY, kp.Sort.NONE)

    def on_execute(self, item, action):
        if item and item.category() == kp.ItemCategory.EXPRESSION:
            kpu.set_clipboard(item.target())
        elif item.category() == kp.ItemCategory.URL:
            kpu.web_browser_command(
                    private_mode=False, new_window=False,
                    url=item.target(), execute=True)

    def on_events(self, flags):
        if flags & kp.Events.PACKCONFIG:
            self._read_config()

    def _read_config(self):
        settings = self.load_settings()
        self.apiKey = settings.get(
            "apiKey", "main", self.apiKey)

    def _thing(self, user_input):
        if self.apiKey == "":
            return str("You don't have an API key.").translate("")
        else:
            if user_input[-1] == "\\":
                user_input = user_input[:-1]
                return self._askWA(user_input)
            else:
                return self.create_item(
                        category=kp.ItemCategory.EXPRESSION,
                        label="= " + user_input,
                        short_desc="Add a backslash ( \\ ) to send query.",
                        target=user_input,
                        args_hint=kp.ItemArgsHint.FORBIDDEN,
                        hit_hint=kp.ItemHitHint.IGNORE)

    def _askWA(self, text):
        params = {
            'input': text,
            'appid': self.apiKey
        }

        request = requests.get(self.api_url, params=params)

        if request.status_code != requests.codes.ok:
            return "Error getting query: {}".format(request.status_code)

        result = etree.ElementTree.fromstring(request.content)
        _url = self.query_url.format(urllib.parse.quote_plus(text))

        suggestions = []
        pod_texts = []
        for pod in result.findall(".//pod[@primary='true']"):
            title = pod.attrib['title']
            if pod.attrib['id'] == 'Input':
                continue

            results = []
            for subpod in pod.findall('.//subpod/plaintext'):
                subpod = subpod.text.strip().replace('\\n', '; ')
                subpod = re.sub(r'\s+', ' ', subpod)
                if subpod:
                    results.append(subpod)
            if results:
                ret = 1
                pod_texts = title + ': ' + ', '.join(results)
                suggestions.append(self.create_item(
                    category=kp.ItemCategory.EXPRESSION,
                    label="= " + pod_texts,
                    short_desc="Press Enter to copy to clipboard",
                    target=pod_texts,
                    args_hint=kp.ItemArgsHint.FORBIDDEN,
                    hit_hint=kp.ItemHitHint.IGNORE))

        if not pod_texts:
            return self.create_item(
                    category=kp.ItemCategory.EXPRESSION,
                    label="= No results.",
                    short_desc="Press Enter to copy to clipboard",
                    target="No results.",
                    args_hint=kp.ItemArgsHint.FORBIDDEN,
                    hit_hint=kp.ItemHitHint.IGNORE)

        suggestions.append(self.create_item(
            category=kp.ItemCategory.URL,
            label=text,
            short_desc="Press Enter to see your query at WolframAlpha.",
            target=_url,
            args_hint=kp.ItemArgsHint.FORBIDDEN,
            hit_hint=kp.ItemHitHint.IGNORE))

        if not ret:
            return self.create_item(
                    category=kp.ItemCategory.EXPRESSION,
                    label="= No results.",
                    short_desc="Press Enter to copy to clipboard",
                    target="No results.",
                    args_hint=kp.ItemArgsHint.FORBIDDEN,
                    hit_hint=kp.ItemHitHint.IGNORE)

        return suggestions
