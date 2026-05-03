XHS_SEARCH_URL = "https://www.xiaohongshu.com/search_result"

SEARCH_INPUT_SELECTORS = [
    "input[type='search']",
    "input[placeholder*='\u641c\u7d22']",
    "input.search-input",
    "input",
]

LOGIN_OR_VERIFY_SELECTORS = [
    "[class*='login']",
    "[class*='verify']",
    "[class*='captcha']",
    "[class*='risk']",
    "text=\u767b\u5f55",
    "text=\u9a8c\u8bc1\u7801",
    "text=\u98ce\u63a7",
]

RESULT_ITEM_SELECTORS = [
    "[class*='note-item']",
    "[class*='search-result']",
    "[class*='feeds-page'] section",
    "section",
]
