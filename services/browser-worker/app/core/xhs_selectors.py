XHS_SEARCH_URL = "https://www.xiaohongshu.com/search_result"

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
    "[class*='login']",
    "[class*='verify']",
    "[class*='captcha']",
    "[class*='risk']",
    "[class*='auth']",
    "[class*='modal']",
    "[class*='security']",
    "[class*='restricted']",
    "text=\u767b\u5f55",
    "text=\u8bf7\u5148\u767b\u5f55",
    "text=\u626b\u7801",
    "text=\u5b89\u5168\u9a8c\u8bc1",
    "text=\u5b89\u5168\u786e\u8ba4",
    "text=\u9a8c\u8bc1\u7801",
    "text=\u4eba\u673a\u9a8c\u8bc1",
    "text=\u9a8c\u8bc1",
    "text=\u8bbf\u95ee\u9891\u7e41",
    "text=\u64cd\u4f5c\u9891\u7e41",
    "text=\u8bf7\u7a0d\u540e\u518d\u8bd5",
    "text=\u98ce\u63a7",
    "text=\u8d26\u53f7\u5f02\u5e38",
    "text=\u9875\u9762\u9650\u5236",
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
