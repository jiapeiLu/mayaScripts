import languagelib.language as language
import importlib
# 假設這是使用者選擇的語言
class LanguageManager:
    def __init__(self, lang='en_us'):
        self._current_lang = lang

    def set_language(self, lang):
        importlib.reload(language)
        self._current_lang = lang

    def tr(self,key, **kwargs):
        translation = language.LANG.get(key, {}).get(self._current_lang, key)
        if kwargs:
            return translation.format(**kwargs)
        return translation

languageManager = LanguageManager()