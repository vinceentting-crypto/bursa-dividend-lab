"""Refresh the factual Bursa symbol directory and ingest owner-supplied history.

This does NOT scrape Yahoo, KLSE Screener, or Bursa prices/dividends. The
repository may be publicly readable; only upload historical data you have
permission to publish. For full market price/DPS coverage, provide an approved
provider whose license permits caching/public redistribution.
"""
import csv
import json
import re
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
SOURCE='https://raw.githubusercontent.com/amaro98/Bursa_Screener/main/bursa_tickers.py'
PRIORITY={'1155':'MAYBANK','1066':'RHBBANK','5199':'HIBISCS','1295':'PUBLIC BANK','5347':'TENAGA',
'7210':'FM GLOBAL LOGISTICS','5012':'TAANN','3301':'HLIND','6491':'KFIMA','9296':'RCECAP',
'5288':'SIMEPROP','5148':'UEMS','5151':'HAIO','7113':'TOPGLOV','1023':'CIMB'}


def read_json(path, default):
    try:
        v=json.loads(path.read_text(encoding='utf-8'))
        return v if isinstance(v,dict) else default
    except (OSError,ValueError):return default


def parse_directory(text):
    return dict(re.findall(r'\(\s*[\'\"](\d{4,5})[\'\"]\s*,\s*[\'\"]([^\'\"\n]{2,160})[\'\"]\s*\)',text))


def update_directory(fetch=True,now=None):
    now=now or datetime.now(timezone.utc).isoformat(timespec='seconds')
    previous=read_json(DATA/'catalog.json',{'stocks':{}})
    codes=dict(previous.get('stocks') or {})
    source_succeeded=False
    if fetch:
        try:
            req=urllib.request.Request(SOURCE,headers={'User-Agent':'BursaDividendLab/2.4 (public ticker reference)'})
            with urllib.request.urlopen(req,timeout=25) as conn:txt=conn.read(230000).decode('utf-8','replace')
            remote=parse_directory(txt)
            if len(remote)<600:raise ValueError('Upstream directory incomplete')
            codes.update(remote)
            source_succeeded=True
        except Exception as exc:
            print('WARN public directory unavailable; retaining local entries:',str(exc)[:160])
    for k,v in PRIORITY.items():codes.setdefault(k,v)
    result={'kind':'bursa-equity-directory','stocks':dict(sorted(codes.items())),'count':len(codes),
            'updatedAt':now if source_succeeded else previous.get('updatedAt'),
            'sourceUrl':SOURCE,'note':'Community-maintained symbol reference; verify listed status. Directory entries do not guarantee historical dividend/price availability.'}
    DATA.mkdir(exist_ok=True,parents=True)
    (DATA/'catalog.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return result


def parse_num(value,allow_zero=False):
    v=str(value or '').strip()
    if not v:return None
    x=float(v)
    if (x>=0 if allow_zero else x>0) and x<100000:return round(x,6)
    raise ValueError('Out-of-range numeric input')


def ingest_csv(path,history_path,now=None):
    """Import annual CALENDAR ex-date DPS + last trading close, never reclassify as FY."""
    if not path.exists():return 0
    existing=read_json(history_path,{'stocks':{}})
    stocks=existing.setdefault('stocks',{})
    grouped=defaultdict(list)
    with path.open('r',encoding='utf-8-sig',newline='') as stream:
        for i,row in enumerate(csv.DictReader(stream),2):
            if not any(str(v or '').strip() for v in row.values()):continue
            code=str(row.get('code','')).strip()
            year=int(row.get('year',''))
            if not re.fullmatch(r'\d{4,5}',code):raise ValueError(f'line {i}: bad code')
            if not 1990<=year<=datetime.now().year+1:raise ValueError(f'line {i}: bad year')
            price=parse_num(row.get('reference_price'))
            dps=parse_num(row.get('annual_dps'),allow_zero=True)
            if price is None and dps is None:continue
            source=str(row.get('source_url','')).strip()
            if not source.startswith(('https://','http://')):raise ValueError(f'line {i}: a source_url is required')
            grouped[code].append({'year':year,'price':price,'dps':dps,'partial':str(row.get('partial','')).lower() in ('yes','true','1'), 'source':source,'name':str(row.get('name',code)).strip()[:110]})
    stamp=now or datetime.now(timezone.utc).isoformat(timespec='seconds')
    for code,rows in grouped.items():
        seen={}
        for r in rows:seen[r['year']]=r
        rows=sorted(seen.values(),key=lambda x:x['year'])
        stocks[code]={
           'ticker':code,'name':rows[-1]['name']+' · '+code,'basisType':'calendar',
           'basis':'用户提供且注明来源的日历年资料。全年每股股息应按除息日所属年份整理；价格是同年度的有日期参考价格，未经实时核价。使用前请复核。',
           'source':'user-authorized-csv','sourceUrls':list(dict.fromkeys(r['source'] for r in rows))[:4],
           'updatedAt':stamp,
           'rows':[{k:r[k] for k in ('year','price','dps','partial')} for r in rows]
        }
    history_path.write_text(json.dumps(existing,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return len(grouped)


def main():
    stamp=datetime.now(timezone.utc).isoformat(timespec='seconds')
    directory=update_directory(now=stamp)
    histories=ingest_csv(DATA/'imported_history.csv',DATA/'history.json',now=stamp)
    actual=read_json(DATA/'history.json',{'stocks':{}})
    status={'lastRun':stamp,'catalogCount':directory['count'],'cacheCount':len(actual.get('stocks',{})),
            'importedCount':histories,'provider':'manual/authorized data',
            'coverageNote':'Automatic stock directory only. No licensed all-stock historical provider is configured; absence of data is NOT 0% yield.'}
    (DATA/'sync_status.json').write_text(json.dumps(status,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('Directory:',status['catalogCount'],'symbols; imported:',histories,'tickers; actual history records:',status['cacheCount'])

if __name__=='__main__':main()
