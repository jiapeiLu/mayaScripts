

class LanguageManager:
    def __init__(self, lang='en_us', languages=None):
        self._current_lang = lang
        self._language = languages if languages else {}

    def set_language(self, lang):
        self._current_lang = lang

    def tr(self,key, **kwargs):
        translation = self._language.get(key, {}).get(self._current_lang, key)
        if kwargs:
            return translation.format(**kwargs)
        return translation

if __name__ == "__main__":
    # Example usage
    languages = {
        'greeting': {'en_us': 'Hello, {name}!', 'fr_fr': 'Bonjour, {name}!'},
        'farewell': {'en_us': 'Goodbye!', 'fr_fr': 'Au revoir!'}
    }
    
    manager = LanguageManager(lang='en_us', languages=languages)
    print(manager.tr('greeting', name='Alice'))  # Output: Hello, Alice!
    
    manager.set_language('fr_fr')
    print(manager.tr('greeting', name='Alice'))  # Output: Bonjour, Alice!
    print(manager.tr('farewell'))  # Output: Au revoir!