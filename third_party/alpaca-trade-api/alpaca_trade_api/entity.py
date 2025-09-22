import pandas as pd
import pprint
import re

ISO8601YMD = re.compile(r'\d{4}-\d{2}-\d{2}T')
NY = 'America/New_York'


class Entity(object):
    '''This helper class provides property access (the "dot notation")
    to the json object, backed by the original object stored in the _raw
    field.
    '''

    def __init__(self, raw):
        self._raw = raw

    def __getattr__(self, key):
        if key in self._raw:
            val = self._raw[key]
            if (isinstance(val, str) and
                    (key.endswith('_at') or
                     key.endswith('_timestamp') or
                     key.endswith('_time')) and
                    ISO8601YMD.match(val)):
                return pd.Timestamp(val)
            else:
                return val
        return super().__getattribute__(key)

    def __repr__(self):
        return '{name}({raw})'.format(
            name=self.__class__.__name__,
            raw=pprint.pformat(self._raw, indent=4),
        )


class Account(Entity):
    """
    Entity properties:
    https://alpaca.markets/docs/api-documentation/api-v2/account/
    """
    pass


class AccountConfigurations(Entity):
    """
    Entity properties:
    https://alpaca.markets/docs/api-documentation/api-v2/account-configuration/
    """
    pass


class Asset(Entity):
    """
    Entity properties:
    https://alpaca.markets/docs/api-documentation/api-v2/assets/#asset-entity
    """
    pass


class Order(Entity):
    """
    Entity properties:
    https://alpaca.markets/docs/api-documentation/api-v2/orders/#order-entity
    """

    def __init__(self, raw):
        super().__init__(raw)
        try:
            self.legs = [Order(o) for o in self.legs]
        except Exception:
            # No order legs existed
            pass


class Position(Entity):
    """
    Entity properties:
https://alpaca.markets/docs/api-documentation/api-v2/positions/#position-entity
    """
    pass


class AccountActivity(Entity):
    """
    Entity properties:
    https://alpaca.markets/docs/api-documentation/api-v2/account-activities/
    """
    pass


class Bar(Entity):
    """
    Entity properties:
    https://alpaca.markets/docs/api-documentation/api-v2/market-data/bars/
    #bars-entity
    """

    def __getattr__(self, key):
        if key == 't':
            val = self._raw[key[0]]
            return pd.Timestamp(val, unit='s', tz=NY)
        return super().__getattr__(key)


class Bars(list):
    def __init__(self, raw):
        super().__init__([Bar(o) for o in raw])
        self._raw = raw

    @property
    def df(self):
        if not hasattr(self, '_df'):
            df = pd.DataFrame(
                self._raw, columns=('t', 'o', 'h', 'l', 'c', 'v'),
            )
            alias = {
                't': 'time',
                'o': 'open',
                'h': 'high',
                'l': 'low',
                'c': 'close',
                'v': 'volume',
            }
            df.columns = [alias[c] for c in df.columns]
            df.set_index('time', inplace=True)
            if not df.empty:
                df.index = pd.to_datetime(
                    (df.index * 1e9).astype('int64'), utc=True,
                ).tz_convert(NY)
            else:
                df.index = pd.to_datetime(
                    df.index, utc=True
                )
            self._df = df
        return self._df


class _Timestamped(object):
    _tskeys = ('timestamp',)

    def __getattr__(self, key):
        if key in self._raw:
            val = self._raw[key]
            if key in self._tskeys:
                return pd.Timestamp(val, tz=NY, unit=self._unit)
            return val
        return getattr(super(), key)


class _NanoTimestamped(_Timestamped):
    _unit = 'ns'


class Trade(_NanoTimestamped, Entity):
    pass


class Quote(_NanoTimestamped, Entity):
    """
    Entity properties:
    https://alpaca.markets/docs/api-documentation/api-v2/market-data/last-quote
    /#last-quote-entity
    """
    pass


class Clock(Entity):
    """
    Entity properties:
    https://alpaca.markets/docs/api-documentation/api-v2/clock/#clock-entity
    """

    def __getattr__(self, key):
        if key in self._raw:
            val = self._raw[key]
            if key in ('timestamp', 'next_open', 'next_close'):
                return pd.Timestamp(val)
            else:
                return val
        return super().__getattr__(key)


class Calendar(Entity):
    """
    Entity properties:
    https://alpaca.markets/docs/api-documentation/api-v2/calendar/
    #calendar-entity
    """

    def __getattr__(self, key):
        if key in self._raw:
            val = self._raw[key]
            if key in ('date',):
                return pd.Timestamp(val)
            elif key in ('open', 'close'):
                return pd.Timestamp(val).time()
            elif key in ('session_open', 'session_close'):
                return pd.Timestamp(val[:2] + ':' + val[-2:]).time()
            else:
                return val
        return super().__getattr__(key)


class Watchlist(Entity):
    """
    Entity properties:
    https://alpaca.markets/docs/api-documentation/api-v2/watchlist/
    #watchlist-entity
    """
    pass


class PortfolioHistory(Entity):
    """
    Entity properties:
    https://alpaca.markets/docs/api-documentation/api-v2/portfolio-history/
    #portfoliohistory-entity
    """

    def __init__(self, raw):
        self._raw = raw

    @property
    def df(self):
        if not hasattr(self, '_df'):
            df = pd.DataFrame(
                self._raw, columns=(
                    'timestamp', 'profit_loss', 'profit_loss_pct', 'equity'
                ),
            )
            df.set_index('timestamp', inplace=True)
            if not df.empty:
                df.index = pd.to_datetime(
                    (df.index * 1e9).astype('int64'), utc=True,
                ).tz_convert(NY)
            else:
                df.index = pd.to_datetime(
                    df.index, utc=True
                )
            self._df = df
        return self._df


trade_mapping = {
    "T": "symbol",
    "c": "conditions",
    "x": "exchange",
    "p": "price",
    "s": "size",
    "t": "timestamp"
}

quote_mapping = {
    "T": "symbol",
    "X": "askexchange",
    "P": "askprice",
    "S": "asksize",
    "x": "bidexchange",
    "p": "bidprice",
    "s": "bidsize",
    "c": "conditions",
    "t": "timestamp"
}

agg_mapping = {
    "T": "symbol",
    "o": "open",
    "c": "close",
    "h": "high",
    "l": "low",
    "a": "average",
    "x": "exchange",
    "v": "volume",
    "s": "start",
    "e": "end",
    "vw": "vwap",
    "av": "totalvolume",

    # this is extra alias in the client side
    "t": "timestamp",
}
