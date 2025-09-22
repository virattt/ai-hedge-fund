import logging
import os
from typing import Iterator, List, Optional, Union
import requests
from requests.exceptions import HTTPError
import time
from enum import Enum
from alpaca_trade_api import __version__
from .common import (
    get_base_url,
    get_data_url,
    get_credentials,
    get_api_version, URL, FLOAT,
)
from .entity import (
    Bar, Entity, Account, AccountConfigurations, AccountActivity,
    Asset, Order, Position, Clock, Calendar,
    Trade, Quote, Watchlist, PortfolioHistory
)
from .entity_v2 import (
    BarV2, BarsV2, LatestBarsV2, LatestQuotesV2, LatestTradesV2,
    SnapshotV2, SnapshotsV2, TradesV2, TradeV2, QuotesV2, QuoteV2,
    NewsV2, NewsListV2, OrderbookV2, OrderbooksV2
)

logger = logging.getLogger(__name__)
Positions = List[Position]
Orders = List[Order]
Assets = List[Asset]
AccountActivities = List[AccountActivity]
Calendars = List[Calendar]
Watchlists = List[Watchlist]
TradeIterator = Iterator[Union[Trade, dict]]
QuoteIterator = Iterator[Union[Quote, dict]]
BarIterator = Iterator[Union[Bar, dict]]
NewsIterator = Iterator[Union[NewsV2, dict]]

DATA_V2_MAX_LIMIT = 10000  # max items per api call
NEWS_MAX_LIMIT = 50  # max items per api call


class RetryException(Exception):
    pass


class APIError(Exception):
    """
    Represent API related error.
    error.status_code will have http status code.
    """

    def __init__(self, error, http_error=None):
        super().__init__(error['message'])
        self._error = error
        self._http_error = http_error

    @property
    def code(self):
        return self._error.get('code', self.status_code)

    @property
    def status_code(self):
        http_error = self._http_error
        if http_error is not None and hasattr(http_error, 'response'):
            return http_error.response.status_code

    @property
    def request(self):
        if self._http_error is not None:
            return self._http_error.request

    @property
    def response(self):
        if self._http_error is not None:
            return self._http_error.response

def raise_api_error(resp: requests.Response, http_error: requests.HTTPError):
    try:
        error = resp.json()
    except:
        raise http_error from None
    if 'message' in error:
        raise APIError(error, http_error) from None
    raise http_error from None


class TimeFrameUnit(Enum):
    Minute = "Min"
    Hour = "Hour"
    Day = "Day"
    Week = "Week"
    Month = "Month"


class TimeFrame:
    def __init__(self, amount: int, unit: TimeFrameUnit):
        self.validate(amount, unit)
        self.__amount = amount
        self.__unit = unit

    @property
    def amount(self):
        return self.__amount

    @amount.setter
    def amount(self, value: int):
        self.validate(value, self.__unit)
        self.__amount = value

    @property
    def unit(self) -> TimeFrameUnit:
        return self.__unit

    @unit.setter
    def unit(self, value: TimeFrameUnit):
        self.validate(self.__amount, value)
        self.__unit = value

    # using "value" field for backwards compatibility
    @property
    def value(self):
        return f"{self.__amount}{self.__unit.value}"

    def __str__(self):
        return self.value

    @staticmethod
    def validate(amount: int, unit: TimeFrameUnit):
        if amount <= 0:
            raise ValueError("Amount must be a positive integer value.")

        if unit == TimeFrameUnit.Minute and amount > 59:
            raise ValueError("Second or Minute units can only be " +
                             "used with amounts between 1-59.")

        if unit == TimeFrameUnit.Hour and amount > 23:
            raise ValueError("Hour units can only be used with amounts 1-23")

        if unit in (TimeFrameUnit.Day, TimeFrameUnit.Week) and amount != 1:
            raise ValueError(
                "Day and Week units can only be used with amount 1")

        if unit == TimeFrameUnit.Month and amount not in (1, 2, 3, 6, 12):
            raise ValueError(
                "Month units can only be used with amount 1, 2, 3, 6 and 12")


# These are kept for backwards compatibility
TimeFrame.Minute = TimeFrame(1, TimeFrameUnit.Minute)
TimeFrame.Hour = TimeFrame(1, TimeFrameUnit.Hour)
TimeFrame.Day = TimeFrame(1, TimeFrameUnit.Day)
TimeFrame.Week = TimeFrame(1, TimeFrameUnit.Week)
TimeFrame.Month = TimeFrame(1, TimeFrameUnit.Month)


class Sort(Enum):
    Asc = "asc"
    Desc = "desc"

    def __str__(self):
        return self.value


class REST(object):
    def __init__(self,
                 key_id: str = None,
                 secret_key: str = None,
                 base_url: URL = None,
                 api_version: str = None,
                 oauth=None,
                 raw_data: bool = False
                 ):
        """
        :param raw_data: should we return api response raw or wrap it with
                         Entity objects.
        """
        self._key_id, self._secret_key, self._oauth = get_credentials(
            key_id, secret_key, oauth)
        self._base_url: URL = URL(base_url or get_base_url())
        self._api_version = get_api_version(api_version)
        self._session = requests.Session()
        self._use_raw_data = raw_data
        self._retry = int(os.environ.get('APCA_RETRY_MAX', 3))
        self._retry_wait = int(os.environ.get('APCA_RETRY_WAIT', 3))
        self._retry_codes = [int(o) for o in os.environ.get(
            'APCA_RETRY_CODES', '429,504').split(',')]

    def _request(self,
                 method,
                 path,
                 data=None,
                 base_url: URL = None,
                 api_version: str = None):
        base_url = base_url or self._base_url
        version = api_version if api_version else self._api_version
        url: URL = URL(base_url + '/' + version + path)
        headers = {}
        if self._oauth:
            headers['Authorization'] = 'Bearer ' + self._oauth
        else:
            headers['APCA-API-KEY-ID'] = self._key_id
            headers['APCA-API-SECRET-KEY'] = self._secret_key
        headers['User-Agent'] = 'APCA-TRADE-SDK-PY/' + __version__
        opts = {
            'headers':         headers,
            # Since we allow users to set endpoint URL via env var,
            # human error to put non-SSL endpoint could exploit
            # uncanny issues in non-GET request redirecting http->https.
            # It's better to fail early if the URL isn't right.
            'allow_redirects': False,
        }
        if method.upper() in ['GET', 'DELETE']:
            opts['params'] = data
        else:
            opts['json'] = data

        retry = self._retry
        if retry < 0:
            retry = 0
        while retry >= 0:
            try:
                return self._one_request(method, url, opts, retry)
            except RetryException:
                retry_wait = self._retry_wait
                logger.warning(
                    'sleep {} seconds and retrying {} '
                    '{} more time(s)...'.format(
                        retry_wait, url, retry))
                time.sleep(retry_wait)
                retry -= 1
                continue

    def _one_request(self, method: str, url: URL, opts: dict, retry: int):
        """
        Perform one request, possibly raising RetryException in the case
        the response is 429. Otherwise, if error text contain "code" string,
        then it decodes to json object and returns APIError.
        Returns the body json in the 200 status.
        """
        retry_codes = self._retry_codes
        resp = self._session.request(method, url, **opts)
        try:
            resp.raise_for_status()
        except HTTPError as http_error:
            # retry if we hit Rate Limit
            if resp.status_code in retry_codes and retry > 0:
                raise RetryException()
            raise_api_error(resp, http_error)
        if resp.text != '':
            return resp.json()
        return None

    def get(self, path, data=None):
        return self._request('GET', path, data)

    def post(self, path, data=None):
        return self._request('POST', path, data)

    def put(self, path, data=None):
        return self._request('PUT', path, data)

    def patch(self, path, data=None):
        return self._request('PATCH', path, data)

    def delete(self, path, data=None):
        return self._request('DELETE', path, data)

    def data_get(self, path, data=None,
                 feed: Optional[str] = None, api_version='v1'):
        base_url: URL = get_data_url()
        if feed:
            data = data or {}
            data['feed'] = feed
        return self._request(
            'GET', path, data, base_url=base_url, api_version=api_version,
        )

    def get_account(self) -> Account:
        """Get the account"""
        resp = self.get('/account')
        return self.response_wrapper(resp, Account)

    def get_account_configurations(self) -> AccountConfigurations:
        """Get account configs"""
        resp = self.get('/account/configurations')
        return self.response_wrapper(resp, AccountConfigurations)

    def update_account_configurations(
            self,
            no_shorting: bool = None,
            dtbp_check: str = None,
            trade_confirm_email: str = None,
            suspend_trade: bool = None) -> AccountConfigurations:
        """
        alpaca.markets/docs/api-documentation/api-v2/account-configuration/
        Update account configs
        :param dtbp_check: both, entry, or exit
        :param trade_confirm_email: all or none
        """
        params = {}
        if no_shorting is not None:
            params['no_shorting'] = no_shorting
        if dtbp_check is not None:
            params['dtbp_check'] = dtbp_check
        if trade_confirm_email is not None:
            params['trade_confirm_email'] = trade_confirm_email
        if suspend_trade is not None:
            params['suspend_trade'] = suspend_trade
        resp = self.patch('/account/configurations', params)
        return self.response_wrapper(resp, AccountConfigurations)

    def list_orders(self,
                    status: str = None,
                    limit: int = None,
                    after: str = None,
                    until: str = None,
                    direction: str = None,
                    params=None,
                    nested: bool = None,
                    symbols: List[str] = None,
                    side: str = None
                    ) -> Orders:
        """
        Get a list of orders
        https://docs.alpaca.markets/web-api/orders/#get-a-list-of-orders

        :param status: open, closed or all. Defaults to open.
        :param limit: Defaults to 50 and max is 500
        :param after: timestamp
        :param until: timestamp
        :param direction: asc or desc.
        :param params: refer to documentation
        :param nested: should the data be nested like json
        :param symbols: list of str (symbols)
        :param side: Lets you filter to only 'buy' or 'sell' orders
        """
        if params is None:
            params = dict()
        if limit is not None:
            params['limit'] = limit
        if after is not None:
            params['after'] = after
        if until is not None:
            params['until'] = until
        if direction is not None:
            params['direction'] = direction
        if status is not None:
            params['status'] = status
        if nested is not None:
            params['nested'] = nested
        if side is not None:
            params['side'] = side
        if symbols is not None:
            params['symbols'] = ",".join(symbols)
        url = '/orders'
        resp = self.get(url, params)
        if self._use_raw_data:
            return resp
        else:
            return [self.response_wrapper(o, Order) for o in resp]

    def submit_order(self,
                     symbol: str,
                     qty: float = None,
                     side: str = "buy",
                     type: str = "market",
                     time_in_force: str = "day",
                     limit_price: str = None,
                     stop_price: str = None,
                     client_order_id: str = None,
                     extended_hours: bool = None,
                     order_class: str = None,
                     take_profit: dict = None,
                     stop_loss: dict = None,
                     trail_price: str = None,
                     trail_percent: str = None,
                     notional: float = None):
        """
        :param symbol: symbol or asset ID
        :param qty: float. Mutually exclusive with "notional".
        :param side: buy or sell
        :param type: market, limit, stop, stop_limit or trailing_stop
        :param time_in_force: day, gtc, opg, cls, ioc, fok
        :param limit_price: str of float
        :param stop_price: str of float
        :param client_order_id:
        :param extended_hours: bool. If true, order will be eligible to execute
               in premarket/afterhours.
        :param order_class: simple, bracket, oco or oto
        :param take_profit: dict with field "limit_price" e.g
               {"limit_price": "298.95"}
        :param stop_loss: dict with fields "stop_price" and "limit_price" e.g
               {"stop_price": "297.95", "limit_price": "298.95"}
        :param trail_price: str of float
        :param trail_percent: str of float
        :param notional: float. Mutually exclusive with "qty".
        """
        """Request a new order"""
        params = {
            'symbol':        symbol,
            'side':          side,
            'type':          type,
            'time_in_force': time_in_force
        }
        if qty is not None:
            params['qty'] = qty
        if notional is not None:
            params['notional'] = notional
        if limit_price is not None:
            params['limit_price'] = FLOAT(limit_price)
        if stop_price is not None:
            params['stop_price'] = FLOAT(stop_price)
        if client_order_id is not None:
            params['client_order_id'] = client_order_id
        if extended_hours is not None:
            params['extended_hours'] = extended_hours
        if order_class is not None:
            params['order_class'] = order_class
        if take_profit is not None:
            if 'limit_price' in take_profit:
                take_profit['limit_price'] = FLOAT(take_profit['limit_price'])
            params['take_profit'] = take_profit
        if stop_loss is not None:
            if 'limit_price' in stop_loss:
                stop_loss['limit_price'] = FLOAT(stop_loss['limit_price'])
            if 'stop_price' in stop_loss:
                stop_loss['stop_price'] = FLOAT(stop_loss['stop_price'])
            params['stop_loss'] = stop_loss
        if trail_price is not None:
            params['trail_price'] = trail_price
        if trail_percent is not None:
            params['trail_percent'] = trail_percent
        resp = self.post('/orders', params)
        return self.response_wrapper(resp, Order)

    def get_order_by_client_order_id(self, client_order_id: str) -> Order:
        """Get an order by client order id"""
        params = {
            'client_order_id': client_order_id,
        }
        resp = self.get('/orders:by_client_order_id', params)
        return self.response_wrapper(resp, Order)

    def get_order(self, order_id: str, nested: bool = None) -> Order:
        """Get an order"""
        params = {}
        if nested is not None:
            params['nested'] = nested
        resp = self.get('/orders/{}'.format(order_id), params)
        return self.response_wrapper(resp, Order)

    def replace_order(
            self,
            order_id: str,
            qty: str = None,
            limit_price: str = None,
            stop_price: str = None,
            trail: str = None,
            time_in_force: str = None,
            client_order_id: str = None,
    ) -> Order:
        """
        :param order_id:
        :param qty: str of int
        :param limit_price: str of float
        :param stop_price: str of float
        :param trail: str of float, represents trailing_price or
               trailing_percent. determined by the original order.
        :param time_in_force: day, gtc, opg, cls, ioc, fok

        note: you cannot replace type of order. so, it was trailing_stop(e.g)
              it will remain trailing_stop.
        """
        params = {}
        if qty is not None:
            params['qty'] = qty
        if limit_price is not None:
            params['limit_price'] = FLOAT(limit_price)
        if stop_price is not None:
            params['stop_price'] = FLOAT(stop_price)
        if trail is not None:
            params['trail'] = FLOAT(trail)
        if time_in_force is not None:
            params['time_in_force'] = time_in_force
        if client_order_id is not None:
            params['client_order_id'] = client_order_id
        resp = self.patch('/orders/{}'.format(order_id), params)
        return self.response_wrapper(resp, Order)

    def cancel_order(self, order_id: str) -> None:
        """Cancel an order"""
        self.delete('/orders/{}'.format(order_id))

    def cancel_all_orders(self) -> None:
        """Cancel all open orders"""
        self.delete('/orders')

    def list_positions(self) -> Positions:
        """Get a list of open positions"""
        resp = self.get('/positions')
        if self._use_raw_data:
            return resp
        else:
            return [self.response_wrapper(p, Position) for p in resp]

    def get_position(self, symbol: str) -> Position:
        """Get an open position"""
        resp = self.get('/positions/{}'.format(symbol))
        return self.response_wrapper(resp, Position)

    def close_position(self, symbol: str, *,
                       qty: float = None,
                       # percentage: float = None  # currently unsupported api
                       ) -> Position:
        """Liquidates the position for the given symbol at market price"""
        # if qty and percentage:
        #     raise Exception("Can't close position with qty and pecentage")
        # elif qty:
        #     data = {'qty': qty}
        # elif percentage:
        #     data = {'percentage': percentage}
        # else:
        #     data = {}
        if qty:
            data = {'qty': qty}
        else:
            data = {}
        resp = self.delete('/positions/{}'.format(symbol), data=data)
        return self.response_wrapper(resp, Position)

    def close_all_positions(self) -> Positions:
        """Liquidates all open positions at market price"""
        resp = self.delete('/positions')
        if self._use_raw_data:
            return resp
        else:
            return [self.response_wrapper(o, Position) for o in resp]

    def list_assets(self, status=None, asset_class=None) -> Assets:
        """Get a list of assets"""
        params = {
            'status':      status,
            'asset_class': asset_class,
        }
        resp = self.get('/assets', params)
        if self._use_raw_data:
            return resp
        else:
            return [self.response_wrapper(o, Asset) for o in resp]

    def get_asset(self, symbol: str) -> Asset:
        """Get an asset"""
        resp = self.get('/assets/{}'.format(symbol))
        return self.response_wrapper(resp, Asset)

    def _data_get(self,
                  endpoint: str,
                  symbol_or_symbols: Union[str, List[str]],
                  api_version: str = 'v2',
                  endpoint_base: str = 'stocks',
                  resp_grouped_by_symbol: Optional[bool] = None,
                  page_limit: int = DATA_V2_MAX_LIMIT,
                  feed: Optional[str] = None,
                  asof: Optional[str] = None,
                  loc: Optional[str] = None,
                  **kwargs):
        page_token = None
        total_items = 0
        limit = kwargs.get('limit')
        is_multi_symbol = api_version == 'v1beta3' or \
            not isinstance(symbol_or_symbols, str)
        if resp_grouped_by_symbol is None:
            resp_grouped_by_symbol = is_multi_symbol
        while True:
            actual_limit = None
            if limit:
                actual_limit = min(int(limit) - total_items, page_limit)
                if actual_limit < 1:
                    break
            data = kwargs
            data['limit'] = actual_limit
            data['page_token'] = page_token
            path = f'/{endpoint_base}'
            if loc:
                path += f'/{loc}'
            if is_multi_symbol:
                data['symbols'] = _join_with_commas(symbol_or_symbols)
            elif symbol_or_symbols:
                path += f'/{symbol_or_symbols}'
            if asof:
                data['asof'] = asof
            if endpoint:
                path += f'/{endpoint}'
            resp = self.data_get(path, data=data, feed=feed,
                                 api_version=api_version)
            if not resp_grouped_by_symbol:
                k = endpoint or endpoint_base
                for item in resp.get(k, []) or []:
                    yield item
                    total_items += 1
            else:
                by_symbol = resp.get(endpoint, {}) or {}
                for sym, items in sorted(by_symbol.items()):
                    for item in items or []:
                        item['S'] = sym
                        yield item
                        total_items += 1
            page_token = resp.get('next_page_token')
            if not page_token:
                break

    def get_trades_iter(self,
                        symbol: Union[str, List[str]],
                        start: Optional[str] = None,
                        end: Optional[str] = None,
                        limit: int = None,
                        feed: Optional[str] = None,
                        asof: Optional[str] = None,
                        sort: Optional[Sort] = None,
                        raw=False) -> TradeIterator:
        trades = self._data_get('trades', symbol,
                                start=start,
                                end=end,
                                limit=limit,
                                feed=feed,
                                asof=asof,
                                sort=sort,
                                )
        for trade in trades:
            if raw:
                yield trade
            else:
                yield self.response_wrapper(trade, Trade)

    def get_trades(self,
                   symbol: Union[str, List[str]],
                   start: Optional[str] = None,
                   end: Optional[str] = None,
                   limit: int = None,
                   feed: Optional[str] = None,
                   asof: Optional[str] = None,
                   sort: Optional[Sort] = None,
                   ) -> TradesV2:
        trades = list(self.get_trades_iter(symbol,
                                           start=start,
                                           end=end,
                                           limit=limit,
                                           feed=feed,
                                           asof=asof,
                                           sort=sort,
                                           raw=True))
        return TradesV2(trades)

    def get_quotes_iter(self,
                        symbol: Union[str, List[str]],
                        start: Optional[str] = None,
                        end: Optional[str] = None,
                        limit: int = None,
                        feed: Optional[str] = None,
                        asof: Optional[str] = None,
                        sort: Optional[Sort] = None,
                        raw=False) -> QuoteIterator:
        quotes = self._data_get('quotes', symbol,
                                start=start,
                                end=end,
                                limit=limit,
                                feed=feed,
                                asof=asof,
                                sort=sort,
                                )
        for quote in quotes:
            if raw:
                yield quote
            else:
                yield self.response_wrapper(quote, Quote)

    def get_quotes(self,
                   symbol: Union[str, List[str]],
                   start: Optional[str] = None,
                   end: Optional[str] = None,
                   limit: int = None,
                   feed: Optional[str] = None,
                   asof: Optional[str] = None,
                   sort: Optional[Sort] = None,
                   ) -> QuotesV2:
        quotes = list(self.get_quotes_iter(symbol=symbol,
                                           start=start,
                                           end=end,
                                           limit=limit,
                                           feed=feed,
                                           raw=True,
                                           asof=asof,
                                           sort=sort,
                                           ))
        return QuotesV2(quotes)

    def get_bars_iter(self,
                      symbol: Union[str, List[str]],
                      timeframe: TimeFrame,
                      start: Optional[str] = None,
                      end: Optional[str] = None,
                      adjustment: str = 'raw',
                      limit: int = None,
                      feed: Optional[str] = None,
                      asof: Optional[str] = None,
                      sort: Optional[Sort] = None,
                      raw=False) -> BarIterator:
        bars = self._data_get('bars', symbol,
                              timeframe=timeframe,
                              adjustment=adjustment,
                              start=start,
                              end=end,
                              limit=limit,
                              feed=feed,
                              asof=asof,
                              sort=sort,
                              )
        for bar in bars:
            if raw:
                yield bar
            else:
                yield self.response_wrapper(bar, Bar)

    def get_bars(self,
                 symbol: Union[str, List[str]],
                 timeframe: TimeFrame,
                 start: Optional[str] = None,
                 end: Optional[str] = None,
                 adjustment: str = 'raw',
                 limit: int = None,
                 feed: Optional[str] = None,
                 asof: Optional[str] = None,
                 sort: Optional[Sort] = None,
                 ) -> BarsV2:
        bars = list(self.get_bars_iter(symbol,
                                       timeframe,
                                       start,
                                       end,
                                       adjustment,
                                       limit,
                                       feed=feed,
                                       asof=asof,
                                       sort=sort,
                                       raw=True))
        return BarsV2(bars)

    def get_latest_bar(self, symbol: str, feed: Optional[str] = None) -> BarV2:
        resp = self.data_get(
            '/stocks/{}/bars/latest'.format(symbol),
            feed=feed,
            api_version='v2')
        return self.response_wrapper(resp['bar'], BarV2)

    def get_latest_bars(self, symbols: List[str],
                        feed: Optional[str] = None) -> LatestBarsV2:
        resp = self.data_get(
            f'/stocks/bars/latest?symbols={_join_with_commas(symbols)}',
            feed=feed,
            api_version='v2')
        return self.response_wrapper(resp['bars'], LatestBarsV2)

    def get_latest_trade(self, symbol: str,
                         feed: Optional[str] = None) -> TradeV2:
        resp = self.data_get(
            '/stocks/{}/trades/latest'.format(symbol),
            feed=feed,
            api_version='v2')
        return self.response_wrapper(resp['trade'], TradeV2)

    def get_latest_trades(self, symbols: List[str],
                          feed: Optional[str] = None) -> LatestTradesV2:
        resp = self.data_get(
            f'/stocks/trades/latest?symbols={_join_with_commas(symbols)}',
            feed=feed,
            api_version='v2')
        return self.response_wrapper(resp['trades'], LatestTradesV2)

    def get_latest_quote(self, symbol: str,
                         feed: Optional[str] = None) -> QuoteV2:
        resp = self.data_get(
            '/stocks/{}/quotes/latest'.format(symbol),
            feed=feed,
            api_version='v2')
        return self.response_wrapper(resp['quote'], QuoteV2)

    def get_latest_quotes(self, symbols: List[str],
                          feed: Optional[str] = None) -> LatestQuotesV2:
        resp = self.data_get(
            f'/stocks/quotes/latest?symbols={_join_with_commas(symbols)}',
            feed=feed,
            api_version='v2')
        return self.response_wrapper(resp['quotes'], LatestQuotesV2)

    def get_snapshot(self, symbol: str,
                     feed: Optional[str] = None) -> SnapshotV2:
        resp = self.data_get('/stocks/{}/snapshot'.format(symbol),
                             feed=feed,
                             api_version='v2')
        return self.response_wrapper(resp, SnapshotV2)

    def get_snapshots(self, symbols: List[str],
                      feed: Optional[str] = None) -> SnapshotsV2:
        resp = self.data_get(
            '/stocks/snapshots?symbols={}'.format(_join_with_commas(symbols)),
            feed=feed,
            api_version='v2')
        return self.response_wrapper(resp, SnapshotsV2)

    def get_crypto_trades_iter(self,
                               symbol: Union[str, List[str]],
                               start: Optional[str] = None,
                               end: Optional[str] = None,
                               limit: int = None,
                               sort: Optional[Sort] = None,
                               loc: str = "us",
                               raw=False) -> TradeIterator:
        trades = self._data_get('trades', symbol,
                                api_version='v1beta3', endpoint_base='crypto',
                                start=start, end=end, limit=limit, sort=sort,
                                loc=loc)
        for trade in trades:
            if raw:
                yield trade
            else:
                yield self.response_wrapper(trade, Trade)

    def get_crypto_trades(self,
                          symbol: Union[str, List[str]],
                          start: Optional[str] = None,
                          end: Optional[str] = None,
                          limit: int = None,
                          sort: Optional[Sort] = None,
                          loc: str = "us") -> TradesV2:
        return TradesV2(list(self.get_crypto_trades_iter(
            symbol, start, end, limit, sort, loc, raw=True)))

    def get_crypto_quotes_iter(self,
                               symbol: Union[str, List[str]],
                               start: Optional[str] = None,
                               end: Optional[str] = None,
                               limit: int = None,
                               sort: Optional[Sort] = None,
                               loc: str = "us",
                               raw=False) -> QuoteIterator:
        quotes = self._data_get('quotes', symbol,
                                api_version='v1beta3', endpoint_base='crypto',
                                start=start, end=end, limit=limit, sort=sort,
                                loc=loc)
        for quote in quotes:
            if raw:
                yield quote
            else:
                yield self.response_wrapper(quote, Quote)

    def get_crypto_quotes(self,
                          symbol: Union[str, List[str]],
                          start: Optional[str] = None,
                          end: Optional[str] = None,
                          limit: int = None,
                          sort: Optional[Sort] = None,
                          loc: str = "us") -> QuotesV2:
        return QuotesV2(list(self.get_crypto_quotes_iter(
            symbol, start, end, limit, sort, loc, raw=True)))

    def get_crypto_bars_iter(self,
                             symbol: Union[str, List[str]],
                             timeframe: TimeFrame,
                             start: Optional[str] = None,
                             end: Optional[str] = None,
                             limit: int = None,
                             sort: Optional[Sort] = None,
                             loc: str = "us",
                             raw=False) -> BarIterator:
        bars = self._data_get('bars', symbol,
                              api_version='v1beta3', endpoint_base='crypto',
                              timeframe=timeframe,
                              start=start, end=end, limit=limit, sort=sort,
                              loc=loc)
        for bar in bars:
            if raw:
                yield bar
            else:
                yield self.response_wrapper(bar, Bar)

    def get_crypto_bars(self,
                        symbol: Union[str, List[str]],
                        timeframe: TimeFrame,
                        start: Optional[str] = None,
                        end: Optional[str] = None,
                        limit: int = None,
                        sort: Optional[Sort] = None,
                        loc: str = "us") -> BarsV2:
        return BarsV2(list(self.get_crypto_bars_iter(
            symbol, timeframe, start, end, limit, sort, loc, raw=True)))

    def get_latest_crypto_bars(self, symbols: List[str],
                               loc: str = "us") -> LatestBarsV2:
        resp = self.data_get(
            f'/crypto/{loc}/latest/bars',
            data={'symbols': _join_with_commas(symbols)},
            api_version='v1beta3')
        return self.response_wrapper(resp['bars'], LatestBarsV2)

    def get_latest_crypto_trades(self, symbols: List[str],
                                 loc: str = "us") -> LatestTradesV2:
        resp = self.data_get(
            f'/crypto/{loc}/latest/trades',
            data={'symbols': _join_with_commas(symbols)},
            api_version='v1beta3')
        return self.response_wrapper(resp['trades'], LatestTradesV2)

    def get_latest_crypto_quotes(self, symbols: List[str],
                                 loc: str = "us") -> LatestQuotesV2:
        resp = self.data_get(
            f'/crypto/{loc}/latest/quotes',
            data={'symbols': _join_with_commas(symbols)},
            api_version='v1beta3')
        return self.response_wrapper(resp['quotes'], LatestQuotesV2)

    def get_crypto_snapshot(self, symbols: str,
                            loc: str = "us") -> SnapshotsV2:
        resp = self.data_get(
            f'/crypto/{loc}/snapshots',
            data={'symbols': symbols},
            api_version='v1beta3')
        return self.response_wrapper(resp['snapshots'], SnapshotsV2)

    def get_crypto_snapshots(self, symbols: List[str],
                             loc: str = "us") -> SnapshotsV2:
        resp = self.data_get(
            f'/crypto/{loc}/snapshots',
            data={'symbols': _join_with_commas(symbols)},
            api_version='v1beta3')
        return self.response_wrapper(resp['snapshots'], SnapshotsV2)

    def get_latest_crypto_orderbook(self, symbol: str,
                                    loc: str = "us") -> OrderbookV2:
        resp = self.data_get(
            f'/crypto/{loc}/latest/orderbooks',
            data={'symbols': symbol},
            api_version='v1beta3')
        return self.response_wrapper(resp['orderbooks'], OrderbooksV2)

    def get_latest_crypto_orderbooks(self, symbols: List[str],
                                     loc: str = "us") -> OrderbookV2:
        resp = self.data_get(
            f'/crypto/{loc}/latest/orderbooks',
            data={'symbols': _join_with_commas(symbols)},
            api_version='v1beta3')
        return self.response_wrapper(resp['orderbooks'], OrderbooksV2)

    def get_news_iter(self,
                      symbol: Optional[Union[str, List[str]]] = None,
                      start: Optional[str] = None,
                      end: Optional[str] = None,
                      limit: int = 10,
                      sort: Sort = Sort.Desc,
                      include_content: bool = False,
                      exclude_contentless: bool = False,
                      raw=False) -> NewsIterator:
        symbol = symbol or []
        # Avoid passing symbol as path param
        if isinstance(symbol, str):
            symbol = [symbol]
        news = self._data_get('', symbol,
                              api_version='v1beta1', endpoint_base='news',
                              start=start, end=end, limit=limit, sort=sort,
                              include_content=include_content,
                              exclude_contentless=exclude_contentless,
                              resp_grouped_by_symbol=False,
                              page_limit=NEWS_MAX_LIMIT)
        for n in news:
            if raw:
                yield n
            else:
                yield self.response_wrapper(n, NewsV2)

    def get_news(self,
                 symbol: Optional[Union[str, List[str]]] = None,
                 start: Optional[str] = None,
                 end: Optional[str] = None,
                 limit: int = 10,
                 sort: Sort = Sort.Desc,
                 include_content: bool = False,
                 exclude_contentless: bool = False,

                 ) -> NewsListV2:
        news = list(self.get_news_iter(symbol=symbol,
                                       start=start, end=end,
                                       limit=limit, sort=sort,
                                       include_content=include_content,
                                       exclude_contentless=exclude_contentless,
                                       raw=True))
        return NewsListV2(news)

    def get_clock(self) -> Clock:
        resp = self.get('/clock')
        return self.response_wrapper(resp, Clock)

    def get_activities(
            self,
            activity_types: str = None,
            until: str = None,
            after: str = None,
            direction: str = None,
            date: str = None,
            page_size: int = None,
            page_token: str = None
    ) -> AccountActivities:
        """
        go to alpaca.markets/docs/api-documentation/api-v2/account-activities/
        :param activity_types: go to documnetation to see available types
        :param until: isoformat timestamp
        :param after: isoformat timestamp
        :param direction: asc or sesc. default is desc
        :param date: str. can't be sued with until/after
        :param page_size:
        :param page_token:
        :return:
        """
        url = '/account/activities'
        params = {}
        if isinstance(activity_types, list):
            params['activity_types'] = ','.join(activity_types)
        elif activity_types is not None:
            url += '/{}'.format(activity_types)
        if after is not None:
            params['after'] = after
        if until is not None:
            params['until'] = until
        if direction is not None:
            params['direction'] = direction
        if date is not None:
            params['date'] = date
        if page_size is not None:
            params['page_size'] = page_size
        if page_token is not None:
            params['page_token'] = page_token
        resp = self.get(url, data=params)
        if self._use_raw_data:
            return resp
        else:
            return [self.response_wrapper(o, AccountActivity) for o in resp]

    def get_calendar(self, start: str = None, end: str = None) -> Calendars:
        """
        :param start: isoformat date string eg '2006-01-02T15:04:05Z' or
               '2006-01-02'
        :param end: isoformat date string
        """
        params = {}
        if start is not None:
            params['start'] = start
        if end is not None:
            params['end'] = end
        resp = self.get('/calendar', data=params)
        if self._use_raw_data:
            return resp
        else:
            return [self.response_wrapper(o, Calendar) for o in resp]

    def get_watchlists(self) -> Watchlists:
        """Get the list of watchlists registered under the account"""
        resp = self.get('/watchlists')
        if self._use_raw_data:
            return resp
        else:
            return [self.response_wrapper(o, Watchlist) for o in resp]

    def get_watchlist(self, watchlist_id: str) -> Watchlist:
        """Get a watchlist identified by the ID"""
        resp = self.get('/watchlists/{}'.format((watchlist_id)))
        return self.response_wrapper(resp, Watchlist)

    def get_watchlist_by_name(self, watchlist_name: str) -> Watchlist:
        """Get a watchlist identified by its name"""
        params = {
            'name': watchlist_name,
        }
        resp = self.get('/watchlists:by_name', data=params)
        return self.response_wrapper(resp, Watchlist)

    def create_watchlist(self,
                         watchlist_name: str,
                         symbols=None) -> Watchlist:
        """Create a new watchlist with an optional initial set of assets"""
        params = {
            'name': watchlist_name,
        }
        if symbols is not None:
            params['symbols'] = symbols
        resp = self.post('/watchlists', data=params)
        return self.response_wrapper(resp, Watchlist)

    def add_to_watchlist(self, watchlist_id: str, symbol: str) -> Watchlist:
        """Add an asset to the watchlist"""
        resp = self.post(
            '/watchlists/{}'.format(watchlist_id), data=dict(symbol=symbol)
        )
        return self.response_wrapper(resp, Watchlist)

    def update_watchlist(self,
                         watchlist_id: str,
                         name: str = None,
                         symbols=None) -> Watchlist:
        """Update a watchlist's name and/or asset list"""
        params = {}
        if name is not None:
            params['name'] = name
        if symbols is not None:
            params['symbols'] = symbols
        resp = self.put('/watchlists/{}'.format(watchlist_id), data=params)
        return self.response_wrapper(resp, Watchlist)

    def delete_watchlist(self, watchlist_id: str) -> None:
        """Delete a watchlist identified by the ID permanently"""
        self.delete('/watchlists/{}'.format(watchlist_id))

    def delete_from_watchlist(self, watchlist_id: str, symbol: str) -> None:
        """Remove an asset from the watchlist's asset list"""
        self.delete('/watchlists/{}/{}'.format(watchlist_id, symbol))

    def get_portfolio_history(self,
                              date_start: str = None,
                              date_end: str = None,
                              period: str = None,
                              timeframe=None,
                              extended_hours: bool = None) -> PortfolioHistory:
        """
        alpaca.markets/docs/api-documentation/api-v2/portfolio-history/
        :param date_start: YYYY-MM-DD
        :param date_end: YYYY-MM-DD
        :param period: The duration of the data in <number> + <unit>
               such as 1D, where <unit> can be D for day, W for week,
               M for month and A for year. Defaults to 1M.
        :param timeframe: The resolution of time window. 1Min, 5Min, 15Min,
               1H, or 1D
        :param extended_hours: bool. If true, include extended hours in the
               result.
        """
        params = {}
        if date_start is not None:
            params['date_start'] = date_start
        if date_end is not None:
            params['date_end'] = date_end
        if period is not None:
            params['period'] = period
        if timeframe is not None:
            params['timeframe'] = timeframe
        if extended_hours is not None:
            params['extended_hours'] = extended_hours
        resp = self.get('/account/portfolio/history', data=params)
        return self.response_wrapper(resp, PortfolioHistory)

    def __enter__(self):
        return self

    def close(self):
        self._session.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def response_wrapper(self, obj, entity: Entity):
        """
        To allow the user to get raw response from the api, we wrap all
        functions with this method, checking if the user has set raw_data
        bool. if they didn't, we wrap the response with an Entity object.
        :param obj: response from server
        :param entity: derivative object of Entity
        :return:
        """
        if self._use_raw_data:
            return obj
        else:
            return entity(obj)


def _join_with_commas(x: Union[str, List[str]]) -> str:
    if isinstance(x, str):
        return x
    return ','.join(x)
