import aiohttp
import asyncio

from alpaca_trade_api.entity_v2 import BarsV2, QuotesV2, TradesV2, \
    EntityList, TradeV2, QuoteV2
import pandas as pd
from alpaca_trade_api.common import URL, get_credentials, get_data_url


class AsyncRest:
    def __init__(self,
                 key_id: str = None,
                 secret_key: str = None,
                 data_url: URL = None,
                 api_version: str = None,
                 raw_data: bool = False
                 ):
        """
        :param raw_data: should we return api response raw or wrap it with
                         Entity objects.
        """
        self._key_id, self._secret_key, _ = get_credentials(key_id, secret_key)
        self._data_url: URL = URL(data_url or get_data_url())

    def _get_historic_url(self, _type, symbol):
        return f"{self._data_url}/v2/stocks/{symbol}/{_type}"

    def _get_latest_url(self, _type, symbol):
        return f"{self._data_url}/v2/stocks/{symbol}/{_type}/latest"

    async def _iterate_requests(self,
                                symbol,
                                payload,
                                limit,
                                entity_type: str,
                                entity_list_type: EntityList) -> pd.DataFrame:
        """
        iterates the api asynchronously until we get all requested data
        :param symbol:
        :param payload:
        :param entity_type: bars/trades/quotes
        :param entity_list_type:
        :return:
        """
        df = pd.DataFrame({})
        url = self._get_historic_url(entity_type, symbol)
        async for packet in self._request(url, payload):
            if packet.get(entity_type):
                response = entity_list_type(packet[entity_type]).df
                df = pd.concat([df, response], axis=0)
                if len(df) >= limit:
                    break

        return df

    async def get_bars_async(self,
                             symbol,
                             start,
                             end,
                             timeframe,
                             limit=1000,
                             adjustment='raw'):
        _type = "bars"

        payload = {
            "adjustment": adjustment,
            "start":      start,
            "end":        end,
            "timeframe":  timeframe,
            "limit":      limit,
        }
        df = await self._iterate_requests(symbol, payload, limit, _type,
                                          BarsV2)

        return symbol, df

    async def get_trades_async(self, symbol, start, end, limit=1000):
        _type = "trades"

        payload = {
            "start": start,
            "end":   end,
            "limit": limit,
        }
        df = await self._iterate_requests(symbol, payload, limit, _type,
                                          TradesV2)

        return symbol, df

    async def get_quotes_async(self, symbol, start, end, limit=1000):
        _type = "quotes"

        payload = {
            "start": start,
            "end":   end,
            "limit": limit,
        }
        df = await self._iterate_requests(symbol, payload, limit, _type,
                                          QuotesV2)

        return symbol, df

    async def get_latest_trade_async(self, symbol: str) -> TradeV2:
        """
        Get the latest trade for the given symbol
        """
        _type = "trades"
        url = self._get_latest_url(_type, symbol)
        opts = self._get_opts()

        async with aiohttp.ClientSession() as session:
            async with session.get(url, **opts) as response:
                response = await response.json()
                if response.get("quote"):
                    result = TradeV2(response["trade"])
                    return symbol, result

    async def get_latest_quote_async(self, symbol: str) -> QuoteV2:
        """
        Get the latest trade for the given symbol
        """
        _type = "quotes"
        url = self._get_latest_url(_type, symbol)
        opts = self._get_opts()

        async with aiohttp.ClientSession() as session:
            async with session.get(url, **opts) as response:
                response = await response.json()
                if response.get("quote"):
                    result = QuoteV2(response["quote"])
                    return symbol, result

    def _get_opts(self, payload=None):
        headers = {}
        headers['APCA-API-KEY-ID'] = self._key_id
        headers['APCA-API-SECRET-KEY'] = self._secret_key
        opts = {
            'headers':         headers,
            # Since we allow users to set endpoint URL via env var,
            # human error to put non-SSL endpoint could exploit
            # uncanny issues in non-GET request redirecting http->https.
            # It's better to fail early if the URL isn't right.
            'allow_redirects': False,
        }
        opts['params'] = payload

        return opts

    async def _request(self, url, payload):
        opts = self._get_opts(payload)
        async with aiohttp.ClientSession() as session:
            while 1:
                async with session.get(url, **opts) as response:

                    response = await response.json()
                    page_token = response.get('next_page_token')
                    payload["page_token"] = page_token
                    yield response

                    if not page_token:
                        break


async def gather_with_concurrency(n, *tasks):
    """
    when working with python function has limitations on the amount of tasks
    it could handle. for that purpose we use this method that splits the tasks.
    it's a bit slower, but gets the job done.
    Follow the example code to learn how to use that
    """
    semaphore = asyncio.Semaphore(n)

    async def sem_task(task):
        async with semaphore:
            return await task

    return await asyncio.gather(*(sem_task(task) for task in tasks),
                                return_exceptions=True)
