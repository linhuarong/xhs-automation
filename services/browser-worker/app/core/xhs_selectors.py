XHS_SEARCH_URL = "https://www.xiaohongshu.com/search_result"
BODY_TEXT_SELECTOR = "body"

SEARCH_INPUT_SELECTORS = [
    "input[type='search']",
    "input[placeholder*='\u641c\u7d22']",
    "input[placeholder*='\u641c']",
    "input[aria-label*='\u641c\u7d22']",
    "input[name*='search']",
    "input[id*='search']",
    "[class*='search'] input",
    "[class*='input'] input",
    "[data-testid*='search'] input",
    "#search-input",
    ".search-input input",
    "input.search-input",
    "textarea[placeholder*='\u641c\u7d22']",
    "textarea[placeholder*='\u641c']",
    "textarea",
    "input",
]

HUMAN_REQUIRED_SELECTORS = [
    "[class*='verify']",
    "[class*='captcha']",
    "[class*='risk']",
    "[class*='security']",
    "[class*='restricted']",
    "[class*='verify-code']",
    "[class*='captcha-box']",
]

HUMAN_REQUIRED_TEXTS = [
    "\u8bf7\u5148\u767b\u5f55",
    "\u767b\u5f55\u540e\u7ee7\u7eed",
    "\u626b\u7801\u767b\u5f55",
    "\u8bf7\u626b\u7801",
    "\u5b89\u5168\u9a8c\u8bc1",
    "\u5b89\u5168\u786e\u8ba4",
    "\u8bf7\u8fdb\u884c\u9a8c\u8bc1",
    "\u9a8c\u8bc1\u7801",
    "\u4eba\u673a\u9a8c\u8bc1",
    "\u8bbf\u95ee\u9891\u7e41",
    "\u64cd\u4f5c\u9891\u7e41",
    "\u8bf7\u7a0d\u540e\u518d\u8bd5",
    "\u8d26\u53f7\u5f02\u5e38",
    "\u9875\u9762\u9650\u5236",
]

LOGIN_OR_VERIFY_SELECTORS = HUMAN_REQUIRED_SELECTORS

RESULT_AREA_SELECTORS = [
    "[class*='search-result']",
    "[class*='feeds-page']",
    "[class*='feeds-container']",
    "[class*='note-list']",
    "[class*='note-item']",
    "[class*='waterfall']",
    "[class*='explore']",
    "section",
]

RESULT_CARD_SELECTORS = [
    "[class*='note-item']",
    "[class*='note-card']",
    "[class*='feed-card']",
    "[class*='search-item']",
    "[class*='cover']",
    "[data-testid*='note']",
    "[class*='search-result']",
    "[class*='feeds-container'] section",
    "[class*='feeds-page'] section",
    "[class*='note-list'] section",
    "[class*='waterfall'] section",
    "[class*='explore'] section",
    "a[href*='/explore/']",
    "section",
]

RESULT_TITLE_SELECTORS = [
    "[class*='title']",
    "[class*='name']",
    "[class*='desc']",
    "[class*='content']",
    "a[href*='/explore/']",
    "span",
]

RESULT_AUTHOR_SELECTORS = [
    "[class*='author']",
    "[class*='user']",
    "[class*='nickname']",
    "[class*='name']",
    "a[href*='/user/']",
]

RESULT_LINK_SELECTORS = [
    "a[href*='/explore/']",
    "a[href*='/search_result/']",
    "a[href]",
]

RESULT_METRIC_SELECTORS = [
    "[class*='like']",
    "[class*='count']",
    "[class*='comment']",
    "[class*='collect']",
    "[class*='interaction']",
    "[class*='engage']",
]

RESULT_ITEM_SELECTORS = RESULT_CARD_SELECTORS
