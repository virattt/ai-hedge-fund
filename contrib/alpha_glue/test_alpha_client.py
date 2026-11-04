"""Offline tests for the pure parts of the keyless client: the as-filed arithmetic and the Form 4 parser."""

import unittest

from alpha_client import instant, parse_form4, series, shares_outstanding, ttm


def fact(start, end, val, filed, form):
    return {"start": start, "end": end, "val": val, "filed": filed, "form": form}


# A fiscal year ending 2025-12-31 and, filed in 2026, the first nine months of 2026 against the same in 2025.
EPS = {"EarningsPerShareDiluted": {"units": {"USD/shares": [
    fact("2025-01-01", "2025-12-31", 8.0, "2026-02-10", "10-K"),
    fact("2026-01-01", "2026-09-30", 7.0, "2026-10-25", "10-Q"),
    fact("2025-01-01", "2025-09-30", 5.5, "2026-10-25", "10-Q"),
]}}}
TAGS = ("EarningsPerShareDiluted",)


class TrailingTwelveMonthsTest(unittest.TestCase):
    def test_adds_the_year_to_date_and_drops_the_same_stretch_a_year_earlier(self):
        self.assertEqual(ttm(EPS, TAGS, "2026-11-01"), (9.5, "2026-09-30", "2026-10-25"))

    def test_before_the_interim_filing_the_last_fiscal_year_stands(self):
        self.assertEqual(ttm(EPS, TAGS, "2026-10-20"), (8.0, "2025-12-31", "2026-02-10"))

    def test_nothing_is_known_before_the_first_filing(self):
        self.assertIsNone(ttm(EPS, TAGS, "2026-01-15"))

    def test_an_amendment_counts_only_from_the_day_it_was_filed(self):
        restated = {"EarningsPerShareDiluted": {"units": {"USD/shares": [
            fact("2025-01-01", "2025-12-31", 8.0, "2026-02-10", "10-K"), fact("2025-01-01", "2025-12-31", 7.5, "2026-06-01", "10-K/A")]}}}
        self.assertEqual(series(restated, TAGS, "2026-05-01", (300, 400), annual_form=True)[("2025-01-01", "2025-12-31")][0], 8.0)
        self.assertEqual(series(restated, TAGS, "2026-07-01", (300, 400), annual_form=True)[("2025-01-01", "2025-12-31")][0], 7.5)


class BalanceAndSharesTest(unittest.TestCase):
    def test_latest_balance_known_by_the_date(self):
        equity = {"StockholdersEquity": {"units": {"USD": [{"end": "2026-06-30", "val": 50.0, "filed": "2026-07-25", "form": "10-Q"},
                                                           {"end": "2026-09-30", "val": 60.0, "filed": "2026-10-25", "form": "10-Q"}]}}}
        self.assertEqual(instant(equity, ("StockholdersEquity",), "2026-10-01"), (50.0, "2026-06-30", "2026-07-25"))
        self.assertEqual(instant(equity, ("StockholdersEquity",), "2026-11-01"), (60.0, "2026-09-30", "2026-10-25"))

    def test_share_classes_filed_together_are_summed(self):
        dei = {"EntityCommonStockSharesOutstanding": {"units": {"shares": [{"end": "2026-10-20", "val": 90.0, "filed": "2026-10-25"},
                                                                          {"end": "2026-10-20", "val": 10.0, "filed": "2026-10-25"}]}}}
        self.assertEqual(shares_outstanding(dei, "2026-11-01"), 100.0)
        self.assertIsNone(shares_outstanding(dei, "2026-10-01"))


FORM4 = """<ownershipDocument><reportingOwner>
<reportingOwnerId><rptOwnerName>DOE JANE</rptOwnerName></reportingOwnerId>
<reportingOwnerRelationship><isDirector>0</isDirector><officerTitle>CFO</officerTitle></reportingOwnerRelationship></reportingOwner>
<nonDerivativeTable>
<nonDerivativeTransaction><transactionDate><value>2026-10-02</value></transactionDate>
<transactionCoding><transactionCode>S</transactionCode></transactionCoding>
<transactionAmounts><transactionShares><value>1000</value></transactionShares>
<transactionPricePerShare><value>200.5</value></transactionPricePerShare></transactionAmounts></nonDerivativeTransaction>
</nonDerivativeTable></ownershipDocument>"""


class Form4Test(unittest.TestCase):
    def test_a_transaction_is_parsed_with_who_made_it(self):
        row = parse_form4(FORM4)[0]
        self.assertEqual((row["owner"], row["title"], row["code"], row["shares"], row["price"]), ("DOE JANE", "CFO", "S", 1000.0, 200.5))


if __name__ == "__main__":
    unittest.main()
