"""Public ClimateSERV CHIRPS daily means for one 0.1-degree Chipata-area box.

No key, account, market or insurance transaction. Requests are split into at
most 20-year chunks per provider limits. --submit queues missing requests;
--collect checks once and downloads completed jobs. No blocking poll loop.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import requests
import pandas as pd
from agri_hedge.config import RAW,PROCESSED

BASE='https://climateserv.servirglobal.net/api/'
AREA={'type':'Polygon','coordinates':[[[32.6,-13.7],[32.7,-13.7],[32.7,-13.6],[32.6,-13.6],[32.6,-13.7]]]}
CHUNKS=((1981,2000),(2001,2020),(2021,2025))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--submit',action='store_true');ap.add_argument('--collect',action='store_true')
    args=ap.parse_args();cache=RAW/'africa';cache.mkdir(parents=True,exist_ok=True)
    manifest_path=cache/'chipata_chirps_jobs.json'
    manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    # Reuse the successful five-year pilot rather than submitting it again.
    probe=cache/'chirps_probe.json'
    if probe.exists() and '2021_2025' not in manifest:
        meta=json.loads(probe.read_text());manifest['2021_2025']=dict(job=json.loads(meta['response'])[0],params=meta['params'])
    if args.submit:
        for start,end in CHUNKS:
            key=f'{start}_{end}'
            if key in manifest:continue
            params=dict(datatype=0,begintime=f'01/01/{start}',endtime=f'12/31/{end}',
                        intervaltype=0,operationtype=5,geometry=json.dumps(AREA))
            r=requests.get(BASE+'submitDataRequest/',params=params,timeout=30);r.raise_for_status()
            job=r.json()[0]
            manifest[key]=dict(job=job,params=params)
            print(key,job)
        manifest_path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    if args.collect:
        for key,meta in manifest.items():
            path=cache/f'chirps_{key}.json'
            if path.exists():continue
            r=requests.get(BASE+'getDataRequestProgress/',params={'id':meta['job']},timeout=30);r.raise_for_status()
            progress=r.json()[0];print(key,progress)
            if progress<100:continue
            r=requests.get(BASE+'getDataFromRequest/',params={'id':meta['job']},timeout=45);r.raise_for_status()
            d=r.json()
            if not d.get('data'):raise ValueError('Completed request returned no data')
            path.write_text(json.dumps(d),encoding='utf-8')
    if all((cache/f'chirps_{a}_{b}.json').exists() for a,b in CHUNKS):
        rows=[]
        for a,b in CHUNKS:
            for r in json.loads((cache/f'chirps_{a}_{b}.json').read_text())['data']:
                v=float(r['value']['avg'])
                if r.get('NaN',0)>0 or not 0<=v<1000:raise ValueError('Missing/invalid daily rain')
                rows.append(dict(date=f"{int(r['year']):04d}-{int(r['month']):02d}-{int(r['day']):02d}",rain_mm=v))
        df=pd.DataFrame(rows).sort_values('date')
        if df.date.duplicated().any():raise ValueError('Duplicate dates')
        expected=pd.date_range('1981-01-01','2025-12-31').strftime('%Y-%m-%d')
        if df.date.tolist()!=expected.tolist():raise ValueError('Incomplete daily history')
        df.to_csv(PROCESSED/'maya_chipata_chirps_daily.csv',index=False,float_format='%.6f')
        meta=dict(provider=BASE,dataset='ClimateSERV Global CHIRPS datatype 0',geometry=AREA,
                  period=['1981-01-01','2025-12-31'],units='mm/day',spatial_operation='area mean',
                  version_caveat='Archive datatype 0; do not label this CHIRPS v3 without provider confirmation',
                  source_docs='https://github.com/SERVIR/ClimateSERV/blob/master/docs/api.rst')
        (PROCESSED/'maya_chipata_source.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
        print('Saved complete daily history:',len(df))


if __name__=='__main__':main()
