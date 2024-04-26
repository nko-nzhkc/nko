import requests

from dotenv import load_dotenv

load_dotenv()


class Client(object):

    DEFAULT_CONF = {
        "base_url": "https://api.unisender.com",
        "lang": "en",
        'format': 'json',
        "api_key": None,
        'platform': None,
    }

    def _get_default_request_data(self):

        return {
            'api_key': self._config['api_key'],
            'platform': self._config['platform'],
            'format': self._config['format']
        }

    def _build_request_data(self, data, extra_key=None):
        result = self._get_default_request_data()
        for key, val in data.items():
            _key = f'{extra_key}[{key}]' if isinstance(extra_key, str) else key
            if isinstance(val, dict):
                result.update(self._build_request_data(val, _key))
            elif isinstance(val, list):
                result.update(self._build_request_data(dict(enumerate(val)), _key))
            elif val is not None:
                result[_key] = val
        return result

    def _to_camel_case(self, snake_case_str):
        parts = snake_case_str.split('_')
        return parts[0] + ''.join(w.capitalize() or '_' for w in parts[1:])

    def _get_request_url(self, method):

        return '{base_url}/{lang}/api/{method}'.format(
            base_url=self._config['base_url'],
            lang=self._config['lang'],
            method=self._to_camel_case(method),
        )
    
    def __init__(self, api_key, platform, **kwargs):
        self._config = self.DEFAULT_CONF
        self._config['api_key'] = api_key
        self._config['platform'] = platform
        self._config.update(kwargs)

    def _api_request(self, method, data):
        url = self._get_request_url(method)
        data = self._build_request_data(data, extra_key=None)
        response = requests.post(url, data)
        return response
