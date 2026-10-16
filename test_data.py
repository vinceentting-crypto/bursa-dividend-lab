import importlib.util
import json
from pathlib import Path
import tempfile
spec=importlib.util.spec_from_file_location('sync',Path(__file__).resolve().parents[1]/'scripts'/'update_data.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def test_directory_parser():
    text='BURSA_TICKERS = [("1155","MAYBANK"),("0012","THREE A"),("03051","LEAP COMPANY")]'
    assert m.parse_directory(text)=={'1155':'MAYBANK','0012':'THREE A','03051':'LEAP COMPANY'}

def test_import_with_missing_dividend_keeps_null():
    with tempfile.TemporaryDirectory() as d:
        base=Path(d); csv=base/'history.csv'; out=base/'history.json'
        csv.write_text('code,name,year,reference_price,annual_dps,partial,source_url\n7210,FM,2025,0.83,0.05,false,https://example.org/report\n7210,FM,2026,0.79,,true,https://example.org/report\n0012,THREE A,2024,1.23,,false,https://example.org/closing-price\n')
        out.write_text('{"stocks":{}}')
        assert m.ingest_csv(csv,out)==2
        payload=json.loads(out.read_text())['stocks']
        assert payload['7210']['rows'][0]['dps']==0.05
        assert payload['7210']['rows'][1]['dps'] is None
        assert payload['0012']['rows'][0]['dps'] is None
        assert payload['7210']['basisType']=='calendar'

def test_invalid_code_or_missing_source_rejected():
    with tempfile.TemporaryDirectory() as d:
        p=Path(d); p.joinpath('h.csv').write_text('code,name,year,reference_price,annual_dps,partial,source_url\n1155,MAYBANK,2024,10,0.6,false,\n')
        p.joinpath('h.json').write_text('{"stocks":{}}')
        try:m.ingest_csv(p/'h.csv',p/'h.json')
        except ValueError as e:assert 'source_url' in str(e)
        else:raise AssertionError('Missing data source should fail')
