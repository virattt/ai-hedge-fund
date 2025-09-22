from enum import Enum
import pandas as pd
from .entity import Bar, Entity, Trade, Quote, _NanoTimestamped
from typing import Dict

trade_mapping_v2 = {
    "i": "id",
    "S": "symbol",
    "c": "conditions",
    "x": "exchange",
    "p": "price",
    "s": "size",
    "t": "timestamp",
    "z": "tape",  # stocks only
    "tks": "takerside"  # crypto only
}

quote_mapping_v2 = {
    "S":  "symbol",
    "x": "exchange",  # crypto only
    "ax": "ask_exchange",
    "ap": "ask_price",
    "as": "ask_size",
    "bx": "bid_exchange",
    "bp": "bid_price",
    "bs": "bid_size",
    "c":  "conditions",  # stocks only
    "t":  "timestamp",
    "z":  "tape"  # stocks only
}

bar_mapping_v2 = {
    "S":  "symbol",
    "x": "exchange",  # crypto only
    "o":  "open",
    "h":  "high",
    "l":  "low",
    "c":  "close",
    "v":  "volume",
    "t":  "timestamp",
    "n":  "trade_count",
    "vw": "vwap"
}

status_mapping_v2 = {
    "S":  "symbol",
    "sc": "status_code",
    "sm": "status_message",
    "rc": "reason_code",
    "rm": "reason_message",
    "t":  "timestamp",
    "z":  "tape"
}

luld_mapping_v2 = {
    "S": "symbol",
    "u": "limit_up_price",
    "d": "limit_down_price",
    "i": "indicator",
    "t": "timestamp",
    "z": "tape"
}

cancel_error_mapping_v2 = {
    "S": "symbol",
    "i": "id",
    "x": "exchange",
    "p": "price",
    "s": "size",
    "a": "cancel_error_action",
    "z": "tape",
    "t": "timestamp",
}

correction_mapping_v2 = {
    "S": "symbol",
    "x": "exchange",
    "oi": "original_id",
    "op": "original_price",
    "os": "original_size",
    "oc": "original_conditions",
    "ci": "corrected_id",
    "cp": "corrected_price",
    "cs": "corrected_size",
    "cc": "corrected_conditions",
    "z": "tape",
    "t": "timestamp",
}

orderbook_mapping_v2 = {
    "S": "symbol",
    "x": "exchange",
    "t": "timestamp",
    "b": "bids",
    "a": "asks",
}


class EntityListType(Enum):
    Trade = Trade, trade_mapping_v2
    Quote = Quote, quote_mapping_v2
    Bar = Bar, bar_mapping_v2


class EntityList(list):
    def __init__(self, entity_type: EntityListType, raw):
        entity = entity_type.value[0]
        super().__init__([entity(o) for o in raw])
        self._raw = raw
        self.mapping = entity_type.value[1]

    @property
    def df(self):
        if not hasattr(self, '_df'):
            df = pd.DataFrame(
                self._raw,
            )

            df.columns = [self.mapping.get(c, c) for c in df.columns]
            if not df.empty:
                df.set_index('timestamp', inplace=True)
                df.index = pd.DatetimeIndex(df.index)
            self._df = df
        return self._df


class Remapped:
    def __init__(self, mapping: Dict[str, str], *args, **kwargs):
        self._reversed_mapping = {
            value: key for (key, value) in mapping.items()}
        super().__init__(*args, **kwargs)

    def __getattr__(self, key):
        if key in self._reversed_mapping:
            return super().__getattr__(self._reversed_mapping[key])
        return super().__getattr__(key)


class BarsV2(EntityList):
    def __init__(self, raw):
        super().__init__(EntityListType.Bar, raw)


class TradesV2(EntityList):
    def __init__(self, raw):
        super().__init__(EntityListType.Trade, raw)


class QuotesV2(EntityList):
    def __init__(self, raw):
        super().__init__(EntityListType.Quote, raw)


class TradeV2(Remapped, _NanoTimestamped, Entity):
    _tskeys = ('t',)

    def __init__(self, raw):
        super().__init__(trade_mapping_v2, raw)


class QuoteV2(Remapped, _NanoTimestamped, Entity):
    _tskeys = ('t',)

    def __init__(self, raw):
        super().__init__(quote_mapping_v2, raw)


class BarV2(Remapped, _NanoTimestamped, Entity):
    _tskeys = ('t',)

    def __init__(self, raw):
        super().__init__(bar_mapping_v2, raw)


class StatusV2(Remapped, _NanoTimestamped, Entity):
    _tskeys = ('t',)

    def __init__(self, raw):
        super().__init__(status_mapping_v2, raw)


class LULDV2(Remapped, _NanoTimestamped, Entity):
    _tskeys = ('t',)

    def __init__(self, raw):
        super().__init__(luld_mapping_v2, raw)


class CancelErrorV2(Remapped, _NanoTimestamped, Entity):
    _tskeys = ('t',)

    def __init__(self, raw):
        super().__init__(cancel_error_mapping_v2, raw)


class CorrectionV2(Remapped, _NanoTimestamped, Entity):
    _tskeys = ('t',)

    def __init__(self, raw):
        super().__init__(correction_mapping_v2, raw)


class SnapshotV2:
    def __init__(self, raw):
        self.latest_trade = _convert_or_none(TradeV2, raw.get('latestTrade'))
        self.latest_quote = _convert_or_none(QuoteV2, raw.get('latestQuote'))
        self.minute_bar = _convert_or_none(BarV2, raw.get('minuteBar'))
        self.daily_bar = _convert_or_none(BarV2, raw.get('dailyBar'))
        self.prev_daily_bar = _convert_or_none(BarV2, raw.get('prevDailyBar'))


class SnapshotsV2(dict):
    def __init__(self, raw):
        for k, v in raw.items():
            self[k] = _convert_or_none(SnapshotV2, v)


class LatestBarsV2(dict):
    def __init__(self, raw):
        for k, v in raw.items():
            self[k] = _convert_or_none(BarV2, v)


class LatestTradesV2(dict):
    def __init__(self, raw):
        for k, v in raw.items():
            self[k] = _convert_or_none(TradeV2, v)


class LatestQuotesV2(dict):
    def __init__(self, raw):
        for k, v in raw.items():
            self[k] = _convert_or_none(QuoteV2, v)


class BidOrAsk(Entity):
    def __init__(self, raw):
        super().__init__(raw)


class OrderbookV2(Entity):
    def __init__(self, raw):
        super().__init__(raw)
        if self.bids:
            for i in range(len(self.bids)):
                self.bids[i] = BidOrAsk(self.bids[i])
        if self.asks:
            for i in range(len(self.asks)):
                self.asks[i] = BidOrAsk(self.asks[i])


class OrderbooksV2(dict):
    def __init__(self, raw):
        for k, v in raw.items():
            for side in orderbook_mapping_v2.keys():
                if side not in v:
                    continue
                readable_side = orderbook_mapping_v2[side]
                v[readable_side] = v[side]
                v.pop(side)
            self[k] = _convert_or_none(OrderbookV2, v)


class NewsV2(Entity):
    def __init__(self, raw):
        super().__init__(raw)


class NewsListV2(list):
    def __init__(self, raw):
        super().__init__([NewsV2(o) for o in raw])


def _convert_or_none(entityType, value):
    if value:
        return entityType(value)
    return None
