"""Offline request/response boundary regressions for the actual adapter."""
import importlib.util
import io
import json
from pathlib import Path
import sys
import traceback
import unittest
from unittest.mock import patch
from urllib.error import URLError
from urllib.request import HTTPRedirectHandler

path=Path(__file__).resolve().parents[1] / 'hedge_fund/data/fxmacrodata.py'
spec=importlib.util.spec_from_file_location('boundary_adapter', path)
adapter=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=adapter
spec.loader.exec_module(adapter)

class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.payload={'data': []}
        self.pages=None
        self.seen=[]
        self.status=200
        self.fail_transport=False
        self.key='fixture-key'
        env=patch.dict('os.environ',{'FXMD_API_KEY':'','FXMACRODATA_API_KEY':''})
        env.start();self.addCleanup(env.stop)
        if hasattr(adapter,'urlopen'):
            def open_request(request,timeout=None):
                self.seen.append(request)
                if self.fail_transport:raise URLError('fixture-private-value')
                payload=next(self.pages) if self.pages is not None else self.payload
                return io.BytesIO(json.dumps(payload).encode())
            transport=patch.object(adapter,'urlopen',side_effect=open_request)
        else:
            import httpx
            original=httpx.Client
            def handler(request):
                self.seen.append(request)
                if self.fail_transport:raise httpx.ConnectError('fixture-private-value')
                payload=next(self.pages) if self.pages is not None else self.payload
                return httpx.Response(self.status,json=payload,headers={'Location':'https://other.example/data'})
            transport=patch.object(adapter.httpx,'Client',side_effect=lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))
        transport.start();self.addCleanup(transport.stop)
        self.client=adapter.FXMacroDataClient(api_key=self.key)
        if hasattr(self.client,'close'):self.addCleanup(self.client.close)

    def convert(self,payload):
        if hasattr(self.client,'to_dataframe'):
            return self.client.to_dataframe(payload,index=False).to_dict('records')
        return self.client.rows(payload)

    def test_error_responses_are_rejected_without_echo(self):
        for payload in ({'detail':'fixture-private-value'},{'error':'fixture-private-value'}):
            self.payload=payload
            with self.subTest(payload=next(iter(payload))),self.assertRaises(Exception) as raised:
                self.client.fetch_dataset('calendar',currency='usd')
            self.assertNotIn('fixture-private-value',str(raised.exception))

    def test_direct_conversion_rejects_errors_and_scalars(self):
        for payload in ({'detail':'fixture-private-value'},{'error':'fixture-private-value'},None,'text',1,True):
            with self.subTest(kind=type(payload).__name__),self.assertRaises(Exception):
                self.convert(payload)

    def test_scalar_rest_payload_is_not_success(self):
        for payload in (None,'text',1,True):
            self.payload=payload
            with self.subTest(kind=type(payload).__name__),self.assertRaises(Exception):
                self.client.fetch_dataset('calendar',currency='usd')

    def test_valid_rows_and_empty_rows_are_preserved(self):
        rows=[{'date':'2026-01-01','val':None}]
        self.payload={'data':rows}
        self.assertEqual(self.payload,self.client.fetch_dataset('calendar',currency='usd'))
        converted=self.convert(self.payload)
        self.assertEqual(1,len(converted))
        self.assertIsNone(converted[0]['val'])
        self.assertEqual([],self.convert({'data':[]}))

    def test_catalogue_mapping_is_preserved(self):
        rows=self.convert({'data':{'synthetic_rate':{'name':'Rate'}}})
        self.assertEqual('synthetic_rate',rows[0]['indicator'])

    def test_malformed_key_is_rejected_without_echo(self):
        with self.assertRaises(ValueError) as raised:
            adapter.FXMacroDataClient(api_key='fixture-key\r\nX-Other: value')
        self.assertNotIn(self.key,str(raised.exception))

    def test_key_is_header_only(self):
        self.client.fetch_dataset('calendar',currency='usd')
        request=self.seen[0]
        header=request.get_header('X-api-key') if hasattr(request,'get_header') else request.headers.get('X-API-Key')
        url=request.full_url if hasattr(request,'full_url') else str(request.url)
        self.assertEqual(self.key,header)
        self.assertNotIn(self.key,url)

    def test_private_transport_reason_is_not_in_traceback(self):
        self.fail_transport=True
        try:self.client.fetch_dataset('calendar',currency='usd')
        except Exception as exc:
            self.assertNotIn('fixture-private-value',''.join(traceback.format_exception(exc)))
        else:self.fail('transport failure was suppressed')

    def test_redirect_does_not_forward_key(self):
        if hasattr(adapter,'urlopen'):
            self.client.fetch_dataset('calendar',currency='usd')
            redirected=HTTPRedirectHandler().redirect_request(self.seen[0],None,302,'Found',{},'https://other.example/data')
            self.assertIsNone(redirected.get_header('X-api-key'))
        else:
            self.status=302
            with self.assertRaises(Exception):self.client.fetch_dataset('calendar',currency='usd')
            self.assertEqual(1,len(self.seen))

    def test_bad_later_page_does_not_return_partial_history(self):
        for payload in ({'error':'fixture-private-value'},{'detail':'fixture-private-value'},{},{'data':{}}):
            self.pages=iter([{'data':[{'date':'2026-01-01','val':1.0}],
                             'pagination':{'has_more':True,'next_offset':1}},payload])
            with self.subTest(kind=str(list(payload))),self.assertRaises(Exception):
                self.client.fetch_rows('forex',base='eur',quote='usd')


if __name__=='__main__':unittest.main()
